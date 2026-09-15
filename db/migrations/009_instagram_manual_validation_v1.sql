BEGIN;

ALTER TABLE commander_entities DROP CONSTRAINT commander_entities_kind_check;
ALTER TABLE commander_entities ADD CONSTRAINT commander_entities_kind_check CHECK (kind IN (
    'source','validation_project','product_brief','human_feedback','weight_update',
    'studio_workspace','studio_asset','studio_version','studio_generation_run',
    'studio_edit_checkpoint','studio_learning_run','studio_skill_snapshot',
    'studio_learning_proposal','studio_learning_decision',
    'landing_workspace','landing_asset','landing_version','landing_generation_run',
    'landing_edit_checkpoint','landing_learning_run','landing_skill_snapshot',
    'landing_learning_proposal','landing_learning_decision',
    'landing_publication','landing_publication_event',
    'meta_ads_preset_version','meta_ads_experiment','meta_ads_audience_version',
    'meta_ads_deployment','meta_ads_stage_run','meta_ads_status_snapshot',
    'meta_ads_control_action','meta_ads_insight_snapshot','meta_ads_recommendation',
    'instagram_publication','instagram_publication_attempt',
    'tiktok_publication','tiktok_publication_attempt',
    'creative_attribution_source','creative_insight_snapshot',
    'landing_analytics_rollup_snapshot','creative_visual_descriptor',
    'creative_learning_run','creative_learning_decision','creative_skill_snapshot',
    'instagram_manual_post_package','instagram_manual_post_event',
    'instagram_validation_test','instagram_validation_arm',
    'instagram_validation_test_event','instagram_validation_import',
    'instagram_validation_import_row'
));

ALTER TABLE universal_studio_workspaces DROP CONSTRAINT universal_studio_workspaces_origin_check;
ALTER TABLE universal_studio_workspaces ADD CONSTRAINT universal_studio_workspaces_origin_check
    CHECK (origin IN ('brief_generation','approved_variant','approved_clone'));
ALTER TABLE universal_studio_workspaces ADD COLUMN clone_source_version_id uuid
    REFERENCES universal_studio_versions(entity_id) ON DELETE RESTRICT;
ALTER TABLE universal_studio_workspaces ADD COLUMN clone_request_id uuid UNIQUE;
ALTER TABLE universal_studio_workspaces ADD CONSTRAINT universal_studio_clone_lineage_check CHECK (
    (origin='approved_clone')=(clone_source_version_id IS NOT NULL)
    AND (origin='approved_clone')=(clone_request_id IS NOT NULL)
);

CREATE TABLE instagram_manual_post_packages (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    request_id uuid NOT NULL UNIQUE,
    request_sha256 char(64) NOT NULL,
    project_id uuid NOT NULL REFERENCES validation_projects(entity_id) ON DELETE RESTRICT,
    source_creative_id uuid NOT NULL,
    source_version_id uuid NOT NULL,
    source_version integer NOT NULL CHECK (source_version>0),
    source_version_sha256 char(64) NOT NULL,
    render_sha256 char(64) NOT NULL,
    caption text NOT NULL CHECK (length(caption)<=2200),
    caption_sha256 char(64) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY(source_creative_id,project_id)
        REFERENCES universal_studio_workspaces(entity_id,project_id) ON DELETE RESTRICT,
    FOREIGN KEY(source_version_id,source_creative_id)
        REFERENCES universal_studio_versions(entity_id,workspace_id) ON DELETE RESTRICT
);
CREATE INDEX instagram_manual_packages_project_created_idx
    ON instagram_manual_post_packages(project_id,created_at DESC);

CREATE TABLE instagram_manual_post_events (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    package_id uuid NOT NULL REFERENCES instagram_manual_post_packages(entity_id) ON DELETE RESTRICT,
    request_id uuid NOT NULL UNIQUE,
    request_sha256 char(64) NOT NULL,
    action text NOT NULL CHECK (action IN ('prepared','published','abandoned')),
    requested_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(package_id,action)
);
CREATE INDEX instagram_manual_events_package_created_idx
    ON instagram_manual_post_events(package_id,created_at DESC);

CREATE TABLE instagram_validation_tests (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    request_id uuid NOT NULL UNIQUE,
    request_sha256 char(64) NOT NULL,
    project_id uuid NOT NULL REFERENCES validation_projects(entity_id) ON DELETE RESTRICT,
    name text NOT NULL CHECK (length(btrim(name)) BETWEEN 1 AND 80),
    total_budget_minor bigint NOT NULL CHECK (total_budget_minor>0),
    currency char(3) NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
    duration_days integer NOT NULL CHECK (duration_days BETWEEN 1 AND 30),
    daily_budget_minor bigint NOT NULL CHECK (daily_budget_minor>0),
    landing_publication_id uuid NOT NULL REFERENCES landing_publications(entity_id) ON DELETE RESTRICT,
    landing_publication_event_id uuid NOT NULL REFERENCES landing_publication_events(entity_id) ON DELETE RESTRICT,
    landing_version_id uuid NOT NULL REFERENCES landing_versions(entity_id) ON DELETE RESTRICT,
    landing_version_sha256 char(64) NOT NULL,
    canonical_url text NOT NULL CHECK (canonical_url ~ '^https://'),
    campaign_name text NOT NULL UNIQUE CHECK (length(campaign_name) BETWEEN 1 AND 255),
    ad_set_name text NOT NULL UNIQUE CHECK (length(ad_set_name) BETWEEN 1 AND 255),
    requested_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX instagram_validation_tests_project_created_idx
    ON instagram_validation_tests(project_id,created_at DESC);

CREATE TABLE instagram_validation_arms (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    test_id uuid NOT NULL REFERENCES instagram_validation_tests(entity_id) ON DELETE RESTRICT,
    project_id uuid NOT NULL REFERENCES validation_projects(entity_id) ON DELETE RESTRICT,
    ordinal integer NOT NULL CHECK (ordinal BETWEEN 1 AND 6),
    source_creative_id uuid NOT NULL,
    source_version_id uuid NOT NULL,
    source_version integer NOT NULL CHECK (source_version>0),
    source_version_sha256 char(64) NOT NULL,
    render_sha256 char(64) NOT NULL,
    headline text NOT NULL CHECK (length(headline)<=255),
    primary_text text NOT NULL CHECK (length(primary_text)<=2200),
    tracked_url text NOT NULL CHECK (tracked_url ~ '^https://'),
    ad_name text NOT NULL UNIQUE CHECK (length(ad_name) BETWEEN 1 AND 255),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(test_id,ordinal),
    UNIQUE(test_id,source_version_id),
    FOREIGN KEY(source_creative_id,project_id)
        REFERENCES universal_studio_workspaces(entity_id,project_id) ON DELETE RESTRICT,
    FOREIGN KEY(source_version_id,source_creative_id)
        REFERENCES universal_studio_versions(entity_id,workspace_id) ON DELETE RESTRICT
);
CREATE INDEX instagram_validation_arms_test_idx
    ON instagram_validation_arms(test_id,ordinal);

CREATE TABLE instagram_validation_test_events (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    test_id uuid NOT NULL REFERENCES instagram_validation_tests(entity_id) ON DELETE RESTRICT,
    project_id uuid NOT NULL REFERENCES validation_projects(entity_id) ON DELETE RESTRICT,
    request_id uuid NOT NULL UNIQUE,
    request_sha256 char(64) NOT NULL,
    action text NOT NULL CHECK (action IN ('prepared','activated','completed','abandoned')),
    requested_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(test_id,action)
);
CREATE INDEX instagram_validation_test_events_project_idx
    ON instagram_validation_test_events(project_id,created_at);

CREATE TABLE instagram_validation_imports (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    test_id uuid NOT NULL REFERENCES instagram_validation_tests(entity_id) ON DELETE RESTRICT,
    request_id uuid NOT NULL UNIQUE,
    request_sha256 char(64) NOT NULL,
    csv_sha256 char(64) NOT NULL,
    mapping jsonb NOT NULL,
    ignored_rows integer NOT NULL CHECK (ignored_rows>=0),
    requested_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(test_id,csv_sha256)
);
CREATE INDEX instagram_validation_imports_test_created_idx
    ON instagram_validation_imports(test_id,created_at DESC);

CREATE TABLE instagram_validation_import_rows (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    import_id uuid NOT NULL REFERENCES instagram_validation_imports(entity_id) ON DELETE RESTRICT,
    arm_id uuid NOT NULL REFERENCES instagram_validation_arms(entity_id) ON DELETE RESTRICT,
    metrics jsonb NOT NULL,
    reporting_start date,
    reporting_end date,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(import_id,arm_id)
);

CREATE TRIGGER instagram_manual_packages_immutable BEFORE UPDATE OR DELETE
    ON instagram_manual_post_packages FOR EACH ROW EXECUTE FUNCTION ptw_reject_immutable_mutation();
CREATE TRIGGER instagram_manual_events_immutable BEFORE UPDATE OR DELETE
    ON instagram_manual_post_events FOR EACH ROW EXECUTE FUNCTION ptw_reject_immutable_mutation();
CREATE TRIGGER instagram_validation_tests_immutable BEFORE UPDATE OR DELETE
    ON instagram_validation_tests FOR EACH ROW EXECUTE FUNCTION ptw_reject_immutable_mutation();
CREATE TRIGGER instagram_validation_arms_immutable BEFORE UPDATE OR DELETE
    ON instagram_validation_arms FOR EACH ROW EXECUTE FUNCTION ptw_reject_immutable_mutation();
CREATE TRIGGER instagram_validation_events_immutable BEFORE UPDATE OR DELETE
    ON instagram_validation_test_events FOR EACH ROW EXECUTE FUNCTION ptw_reject_immutable_mutation();
CREATE TRIGGER instagram_validation_imports_immutable BEFORE UPDATE OR DELETE
    ON instagram_validation_imports FOR EACH ROW EXECUTE FUNCTION ptw_reject_immutable_mutation();
CREATE TRIGGER instagram_validation_import_rows_immutable BEFORE UPDATE OR DELETE
    ON instagram_validation_import_rows FOR EACH ROW EXECUTE FUNCTION ptw_reject_immutable_mutation();

COMMIT;
