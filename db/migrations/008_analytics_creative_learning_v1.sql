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
    'creative_learning_run','creative_learning_decision','creative_skill_snapshot'
));

CREATE TABLE creative_attribution_sources (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    token char(43) NOT NULL UNIQUE CHECK (token ~ '^[A-Za-z0-9_-]{43}$'),
    token_sha256 char(64) NOT NULL UNIQUE,
    project_id uuid NOT NULL REFERENCES validation_projects(entity_id) ON DELETE RESTRICT,
    channel text NOT NULL CHECK (channel IN ('organic','paid')),
    provider text NOT NULL CHECK (provider IN ('instagram','tiktok','meta')),
    source_entity_id uuid NOT NULL REFERENCES commander_entities(id) ON DELETE RESTRICT,
    landing_publication_id uuid NOT NULL REFERENCES landing_publications(entity_id) ON DELETE RESTRICT,
    landing_publication_event_id uuid NOT NULL REFERENCES landing_publication_events(entity_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(source_entity_id)
);
CREATE INDEX creative_attribution_project_created_idx
    ON creative_attribution_sources(project_id,created_at DESC);

CREATE TABLE creative_insight_snapshots (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    project_id uuid NOT NULL REFERENCES validation_projects(entity_id) ON DELETE RESTRICT,
    source_entity_id uuid NOT NULL REFERENCES commander_entities(id) ON DELETE RESTRICT,
    provider text NOT NULL CHECK (provider IN ('instagram','tiktok')),
    capture_kind text NOT NULL CHECK (capture_kind IN ('milestone','manual','backfill')),
    milestone_hours integer CHECK (milestone_hours IN (24,72,168,336,720)),
    capture_key text NOT NULL UNIQUE,
    source_published_at timestamptz NOT NULL,
    metrics jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK ((capture_kind='milestone')=(milestone_hours IS NOT NULL))
);
CREATE INDEX creative_insight_source_created_idx
    ON creative_insight_snapshots(source_entity_id,created_at DESC);
CREATE INDEX creative_insight_project_created_idx
    ON creative_insight_snapshots(project_id,created_at DESC);

-- Raw, cookieless events intentionally are not Commander entities: their
-- bounded 90-day retention allows physical deletion without weakening the
-- indefinite aggregate and learning lineage below.
CREATE TABLE landing_analytics_events (
    event_id uuid PRIMARY KEY,
    visit_id uuid NOT NULL,
    project_id uuid NOT NULL REFERENCES validation_projects(entity_id) ON DELETE RESTRICT,
    landing_publication_id uuid NOT NULL REFERENCES landing_publications(entity_id) ON DELETE RESTRICT,
    landing_publication_event_id uuid NOT NULL REFERENCES landing_publication_events(entity_id) ON DELETE RESTRICT,
    landing_version_id uuid NOT NULL REFERENCES landing_versions(entity_id) ON DELETE RESTRICT,
    landing_version_sha256 char(64) NOT NULL,
    input_sha256 char(64) NOT NULL,
    event_type text NOT NULL CHECK (event_type IN ('landing_view','primary_cta_click','contact_click')),
    surface text NOT NULL CHECK (surface IN ('page','hero','phone','telegram','instagram','email')),
    target text NOT NULL CHECK (target IN ('page','contacts','telegram','instagram','email','phone')),
    attribution_source_id uuid REFERENCES creative_attribution_sources(entity_id) ON DELETE RESTRICT,
    viewport_class text NOT NULL CHECK (viewport_class IN ('mobile','tablet','desktop')),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX landing_analytics_events_project_created_idx
    ON landing_analytics_events(project_id,created_at DESC);
CREATE INDEX landing_analytics_events_version_created_idx
    ON landing_analytics_events(landing_version_id,created_at DESC);

CREATE TABLE landing_analytics_rollup_snapshots (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    project_id uuid NOT NULL REFERENCES validation_projects(entity_id) ON DELETE RESTRICT,
    landing_publication_event_id uuid NOT NULL REFERENCES landing_publication_events(entity_id) ON DELETE RESTRICT,
    landing_version_id uuid NOT NULL REFERENCES landing_versions(entity_id) ON DELETE RESTRICT,
    landing_version_sha256 char(64) NOT NULL,
    day date NOT NULL,
    event_type text NOT NULL CHECK (event_type IN ('landing_view','primary_cta_click','contact_click')),
    surface text NOT NULL CHECK (surface IN ('page','hero','phone','telegram','instagram','email')),
    target text NOT NULL CHECK (target IN ('page','contacts','telegram','instagram','email','phone')),
    attribution_source_id uuid REFERENCES creative_attribution_sources(entity_id) ON DELETE RESTRICT,
    cumulative_count integer NOT NULL CHECK (cumulative_count > 0),
    source_event_id uuid NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX landing_analytics_rollup_dimension_idx
    ON landing_analytics_rollup_snapshots(
        project_id,day,landing_version_id,event_type,surface,target,
        attribution_source_id,created_at DESC
    );

CREATE TABLE creative_visual_descriptors (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    artifact_sha256 char(64) NOT NULL UNIQUE,
    source_version_id uuid NOT NULL REFERENCES universal_studio_versions(entity_id) ON DELETE RESTRICT,
    project_id uuid NOT NULL REFERENCES validation_projects(entity_id) ON DELETE RESTRICT,
    descriptor jsonb NOT NULL,
    descriptor_sha256 char(64) NOT NULL,
    provider jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE creative_visual_descriptor_sources (
    descriptor_id uuid NOT NULL REFERENCES creative_visual_descriptors(entity_id) ON DELETE RESTRICT,
    source_version_id uuid NOT NULL REFERENCES universal_studio_versions(entity_id) ON DELETE RESTRICT,
    project_id uuid NOT NULL REFERENCES validation_projects(entity_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (descriptor_id,source_version_id)
);

CREATE TABLE creative_learning_runs (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    request_id uuid NOT NULL UNIQUE,
    request_sha256 char(64) NOT NULL,
    scope text NOT NULL CHECK (scope IN ('project','global')),
    project_id uuid REFERENCES validation_projects(entity_id) ON DELETE RESTRICT,
    surface text NOT NULL CHECK (surface IN ('post','landing')),
    status text NOT NULL CHECK (status IN ('running','completed','insufficient_data','failed')),
    dataset jsonb NOT NULL,
    dataset_sha256 char(64) NOT NULL,
    candidates jsonb NOT NULL DEFAULT '[]'::jsonb,
    provider jsonb NOT NULL DEFAULT '{}'::jsonb,
    error_type text,
    error_message text,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    completed_at timestamptz,
    CHECK ((scope='global' AND project_id IS NULL) OR (scope='project' AND project_id IS NOT NULL))
);
CREATE INDEX creative_learning_runs_scope_created_idx
    ON creative_learning_runs(scope,project_id,created_at DESC);

CREATE TABLE creative_skill_snapshots (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    request_id uuid NOT NULL UNIQUE,
    scope text NOT NULL CHECK (scope IN ('project','global')),
    project_id uuid REFERENCES validation_projects(entity_id) ON DELETE RESTRICT,
    version integer NOT NULL CHECK (version > 0),
    rules jsonb NOT NULL,
    rules_sha256 char(64) NOT NULL,
    source_learning_run_id uuid REFERENCES creative_learning_runs(entity_id) ON DELETE RESTRICT,
    requested_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK ((scope='global' AND project_id IS NULL) OR (scope='project' AND project_id IS NOT NULL))
);
CREATE UNIQUE INDEX creative_skill_global_version_idx
    ON creative_skill_snapshots(version) WHERE scope='global';
CREATE UNIQUE INDEX creative_skill_project_version_idx
    ON creative_skill_snapshots(project_id,version) WHERE scope='project';

CREATE TABLE creative_learning_decisions (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    request_id uuid NOT NULL UNIQUE,
    request_sha256 char(64) NOT NULL,
    learning_run_id uuid NOT NULL UNIQUE REFERENCES creative_learning_runs(entity_id) ON DELETE RESTRICT,
    decision text NOT NULL CHECK (decision IN ('activate','reject')),
    selected_rules jsonb NOT NULL,
    skill_snapshot_id uuid REFERENCES creative_skill_snapshots(entity_id) ON DELETE RESTRICT,
    requested_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK ((decision='activate')=(skill_snapshot_id IS NOT NULL))
);

-- A learning run may advance from running to a terminal status, but the
-- frozen request and dataset that produced its candidates are immutable.
CREATE FUNCTION ptw_guard_creative_learning_run_update() RETURNS trigger AS $$
BEGIN
    IF NEW.request_id IS DISTINCT FROM OLD.request_id
       OR NEW.request_sha256 IS DISTINCT FROM OLD.request_sha256
       OR NEW.scope IS DISTINCT FROM OLD.scope
       OR NEW.project_id IS DISTINCT FROM OLD.project_id
       OR NEW.surface IS DISTINCT FROM OLD.surface
       OR NEW.dataset IS DISTINCT FROM OLD.dataset
       OR NEW.dataset_sha256 IS DISTINCT FROM OLD.dataset_sha256
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'creative learning run request and dataset are immutable';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER creative_learning_runs_frozen
    BEFORE UPDATE ON creative_learning_runs
    FOR EACH ROW EXECUTE FUNCTION ptw_guard_creative_learning_run_update();
CREATE TRIGGER creative_learning_runs_no_delete
    BEFORE DELETE ON creative_learning_runs
    FOR EACH ROW EXECUTE FUNCTION ptw_reject_immutable_mutation();

-- Raw events are immutable during their 90-day retention period. The only
-- permitted row mutation is expiry deletion after that boundary.
CREATE FUNCTION ptw_guard_landing_analytics_event_mutation() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'UPDATE' OR OLD.created_at >= clock_timestamp() - interval '90 days' THEN
        RAISE EXCEPTION 'landing analytics events are immutable until retention expiry';
    END IF;
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER landing_analytics_events_retention_guard
    BEFORE UPDATE OR DELETE ON landing_analytics_events
    FOR EACH ROW EXECUTE FUNCTION ptw_guard_landing_analytics_event_mutation();

DO $$
DECLARE table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'creative_attribution_sources','creative_insight_snapshots',
        'landing_analytics_rollup_snapshots','creative_visual_descriptors',
        'creative_visual_descriptor_sources','creative_skill_snapshots',
        'creative_learning_decisions'
    ] LOOP
        EXECUTE format(
            'CREATE TRIGGER %I_immutable BEFORE UPDATE OR DELETE ON %I FOR EACH ROW EXECUTE FUNCTION ptw_reject_immutable_mutation()',
            table_name, table_name
        );
    END LOOP;
END $$;

COMMIT;
