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
    'meta_ads_preset_version','meta_ads_experiment','meta_ads_audience_version',
    'meta_ads_deployment','meta_ads_stage_run','meta_ads_status_snapshot'
));

CREATE TABLE meta_ads_preset_versions (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    version integer NOT NULL UNIQUE CHECK (version > 0),
    specification jsonb NOT NULL,
    specification_sha256 char(64) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

ALTER TABLE universal_studio_versions ADD CONSTRAINT universal_studio_versions_entity_workspace_key
    UNIQUE(entity_id,workspace_id);

CREATE TABLE meta_ads_workspaces (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    project_id uuid NOT NULL UNIQUE REFERENCES validation_projects(entity_id) ON DELETE RESTRICT,
    campaign_name text NOT NULL CHECK (length(campaign_name) BETWEEN 1 AND 255),
    special_ad_categories jsonb NOT NULL,
    meta_campaign_id text UNIQUE,
    status text NOT NULL CHECK (status IN ('reserved','staged','failed')),
    error jsonb,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(entity_id,project_id),
    CHECK (jsonb_typeof(special_ad_categories)='array')
);

CREATE TABLE meta_ads_audience_versions (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    workspace_id uuid NOT NULL REFERENCES meta_ads_workspaces(entity_id) ON DELETE RESTRICT,
    preset_id uuid NOT NULL REFERENCES meta_ads_preset_versions(entity_id) ON DELETE RESTRICT,
    preset_sha256 char(64) NOT NULL,
    specification jsonb NOT NULL,
    ad_set_name text NOT NULL CHECK (length(ad_set_name) BETWEEN 1 AND 255),
    meta_ad_set_id text UNIQUE,
    status text NOT NULL CHECK (status IN ('reserved','staged','failed')),
    error jsonb,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(workspace_id,preset_sha256),
    UNIQUE(entity_id,workspace_id)
);
CREATE INDEX meta_ads_audience_workspace_created_idx
    ON meta_ads_audience_versions(workspace_id,created_at DESC);

CREATE TABLE meta_ads_deployments (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    request_id uuid NOT NULL UNIQUE,
    request_sha256 char(64) NOT NULL,
    project_id uuid NOT NULL REFERENCES validation_projects(entity_id) ON DELETE RESTRICT,
    workspace_id uuid NOT NULL,
    audience_id uuid NOT NULL,
    source_creative_id uuid NOT NULL,
    source_version_id uuid NOT NULL REFERENCES universal_studio_versions(entity_id) ON DELETE RESTRICT,
    source_version integer NOT NULL CHECK (source_version > 0),
    source_version_sha256 char(64) NOT NULL,
    render_sha256 char(64) NOT NULL,
    specification jsonb NOT NULL,
    specification_sha256 char(64) NOT NULL,
    campaign_name text NOT NULL CHECK (length(campaign_name) BETWEEN 1 AND 255),
    ad_set_name text NOT NULL CHECK (length(ad_set_name) BETWEEN 1 AND 255),
    creative_name text NOT NULL CHECK (length(creative_name) BETWEEN 1 AND 255),
    ad_name text NOT NULL CHECK (length(ad_name) BETWEEN 1 AND 255),
    meta_image_hash text,
    meta_creative_id text UNIQUE,
    meta_ad_id text UNIQUE,
    status text NOT NULL CHECK (status IN (
        'queued','creating_campaign','creating_ad_set','uploading_image',
        'creating_creative','creating_ad','staged','failed'
    )),
    error jsonb,
    status_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY(workspace_id,project_id)
        REFERENCES meta_ads_workspaces(entity_id,project_id) ON DELETE RESTRICT,
    FOREIGN KEY(audience_id,workspace_id)
        REFERENCES meta_ads_audience_versions(entity_id,workspace_id) ON DELETE RESTRICT,
    FOREIGN KEY(source_creative_id,project_id)
        REFERENCES universal_studio_workspaces(entity_id,project_id) ON DELETE RESTRICT,
    FOREIGN KEY(source_version_id,source_creative_id)
        REFERENCES universal_studio_versions(entity_id,workspace_id) ON DELETE RESTRICT
);
CREATE INDEX meta_ads_deployments_project_created_idx
    ON meta_ads_deployments(project_id,created_at DESC);

CREATE TABLE meta_ads_stage_runs (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    deployment_id uuid NOT NULL REFERENCES meta_ads_deployments(entity_id) ON DELETE RESTRICT,
    attempt integer NOT NULL CHECK (attempt > 0),
    stage text NOT NULL CHECK (stage IN (
        'connection','campaign','ad_set','image','creative','ad',
        'creating_campaign','creating_ad_set','uploading_image','creating_creative','creating_ad'
    )),
    status text NOT NULL CHECK (status IN ('completed','failed')),
    error jsonb,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(deployment_id,attempt)
);

CREATE TABLE meta_ads_status_snapshots (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    deployment_id uuid NOT NULL REFERENCES meta_ads_deployments(entity_id) ON DELETE RESTRICT,
    objects jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX meta_ads_status_deployment_created_idx
    ON meta_ads_status_snapshots(deployment_id,created_at DESC);

CREATE TRIGGER meta_ads_preset_versions_immutable BEFORE UPDATE OR DELETE
    ON meta_ads_preset_versions FOR EACH ROW EXECUTE FUNCTION ptw_reject_immutable_mutation();
CREATE TRIGGER meta_ads_stage_runs_immutable BEFORE UPDATE OR DELETE
    ON meta_ads_stage_runs FOR EACH ROW EXECUTE FUNCTION ptw_reject_immutable_mutation();
CREATE TRIGGER meta_ads_status_snapshots_immutable BEFORE UPDATE OR DELETE
    ON meta_ads_status_snapshots FOR EACH ROW EXECUTE FUNCTION ptw_reject_immutable_mutation();

CREATE FUNCTION ptw_protect_meta_ads_workspace() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.entity_id IS DISTINCT FROM OLD.entity_id
       OR NEW.project_id IS DISTINCT FROM OLD.project_id
       OR NEW.campaign_name IS DISTINCT FROM OLD.campaign_name
       OR NEW.special_ad_categories IS DISTINCT FROM OLD.special_ad_categories
       OR NEW.created_at IS DISTINCT FROM OLD.created_at
       OR (OLD.meta_campaign_id IS NOT NULL AND NEW.meta_campaign_id IS DISTINCT FROM OLD.meta_campaign_id) THEN
        RAISE EXCEPTION 'immutable Meta Ads workspace fields cannot change';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER meta_ads_workspaces_protected BEFORE UPDATE ON meta_ads_workspaces
    FOR EACH ROW EXECUTE FUNCTION ptw_protect_meta_ads_workspace();

CREATE FUNCTION ptw_protect_meta_ads_audience() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.entity_id IS DISTINCT FROM OLD.entity_id
       OR NEW.workspace_id IS DISTINCT FROM OLD.workspace_id
       OR NEW.preset_id IS DISTINCT FROM OLD.preset_id
       OR NEW.preset_sha256 IS DISTINCT FROM OLD.preset_sha256
       OR NEW.specification IS DISTINCT FROM OLD.specification
       OR NEW.ad_set_name IS DISTINCT FROM OLD.ad_set_name
       OR NEW.created_at IS DISTINCT FROM OLD.created_at
       OR (OLD.meta_ad_set_id IS NOT NULL AND NEW.meta_ad_set_id IS DISTINCT FROM OLD.meta_ad_set_id) THEN
        RAISE EXCEPTION 'immutable Meta Ads audience fields cannot change';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER meta_ads_audience_versions_protected BEFORE UPDATE ON meta_ads_audience_versions
    FOR EACH ROW EXECUTE FUNCTION ptw_protect_meta_ads_audience();

CREATE FUNCTION ptw_protect_meta_ads_deployment() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF ROW(
        NEW.entity_id,NEW.request_id,NEW.request_sha256,NEW.project_id,NEW.workspace_id,
        NEW.audience_id,NEW.source_creative_id,NEW.source_version_id,NEW.source_version,
        NEW.source_version_sha256,NEW.render_sha256,NEW.specification,NEW.specification_sha256,
        NEW.campaign_name,NEW.ad_set_name,NEW.creative_name,NEW.ad_name,NEW.created_at
    ) IS DISTINCT FROM ROW(
        OLD.entity_id,OLD.request_id,OLD.request_sha256,OLD.project_id,OLD.workspace_id,
        OLD.audience_id,OLD.source_creative_id,OLD.source_version_id,OLD.source_version,
        OLD.source_version_sha256,OLD.render_sha256,OLD.specification,OLD.specification_sha256,
        OLD.campaign_name,OLD.ad_set_name,OLD.creative_name,OLD.ad_name,OLD.created_at
    ) OR (OLD.meta_image_hash IS NOT NULL AND NEW.meta_image_hash IS DISTINCT FROM OLD.meta_image_hash)
      OR (OLD.meta_creative_id IS NOT NULL AND NEW.meta_creative_id IS DISTINCT FROM OLD.meta_creative_id)
      OR (OLD.meta_ad_id IS NOT NULL AND NEW.meta_ad_id IS DISTINCT FROM OLD.meta_ad_id) THEN
        RAISE EXCEPTION 'immutable Meta Ads deployment fields cannot change';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER meta_ads_deployments_protected BEFORE UPDATE ON meta_ads_deployments
    FOR EACH ROW EXECUTE FUNCTION ptw_protect_meta_ads_deployment();

COMMIT;
