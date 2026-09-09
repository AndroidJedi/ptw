BEGIN;
ALTER TABLE meta_ads_workspaces ADD COLUMN objective text NOT NULL DEFAULT 'OUTCOME_ENGAGEMENT'
    CHECK (objective IN ('OUTCOME_ENGAGEMENT','OUTCOME_TRAFFIC'));
ALTER TABLE meta_ads_workspaces DROP CONSTRAINT meta_ads_workspaces_project_id_key;
ALTER TABLE meta_ads_workspaces ADD CONSTRAINT meta_ads_campaign_identity
    UNIQUE(project_id,objective,special_ad_categories);
CREATE FUNCTION ptw_protect_meta_objective() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.objective IS DISTINCT FROM OLD.objective THEN
        RAISE EXCEPTION 'campaign objective is immutable';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER meta_ads_objective_protected BEFORE UPDATE ON meta_ads_workspaces
    FOR EACH ROW EXECUTE FUNCTION ptw_protect_meta_objective();
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
    'instagram_publication','instagram_publication_attempt'
));


CREATE TABLE instagram_publications (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    project_id uuid NOT NULL REFERENCES validation_projects(entity_id) ON DELETE RESTRICT,
    source_creative_id uuid NOT NULL,
    source_version_id uuid NOT NULL,
    request_id uuid NOT NULL UNIQUE,
    request_sha256 char(64) NOT NULL,
    specification jsonb NOT NULL,
    state jsonb NOT NULL CHECK (state->>'status' IN (
        'queued','creating_container','preparing','publishing','published','published_unresolved','uncertain','failed'
    )),
    delivery_jpeg bytea NOT NULL CHECK (octet_length(delivery_jpeg) BETWEEN 1 AND 8388608),
    media_token_sha256 char(64) NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY(source_creative_id,project_id)
        REFERENCES universal_studio_workspaces(entity_id,project_id) ON DELETE RESTRICT,
    FOREIGN KEY(source_version_id,source_creative_id)
        REFERENCES universal_studio_versions(entity_id,workspace_id) ON DELETE RESTRICT
);
CREATE INDEX instagram_publications_project_idx ON instagram_publications(project_id,created_at DESC);
CREATE TABLE instagram_publication_attempts (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    publication_id uuid NOT NULL REFERENCES instagram_publications(entity_id) ON DELETE RESTRICT,
    record jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TRIGGER instagram_attempts_immutable BEFORE UPDATE OR DELETE ON instagram_publication_attempts
    FOR EACH ROW EXECUTE FUNCTION ptw_reject_immutable_mutation();
CREATE FUNCTION ptw_protect_instagram_publication() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF (to_jsonb(NEW) - 'state') IS DISTINCT FROM (to_jsonb(OLD) - 'state') THEN
        RAISE EXCEPTION 'Instagram publication input is immutable';
    END IF;
    IF OLD.state->>'container_id' IS NOT NULL AND NEW.state->>'container_id' IS DISTINCT FROM OLD.state->>'container_id'
       OR OLD.state->>'media_id' IS NOT NULL AND NEW.state->>'media_id' IS DISTINCT FROM OLD.state->>'media_id'
       OR OLD.state->>'publish_started' = 'true' AND NEW.state->>'publish_started' IS DISTINCT FROM 'true' THEN
        RAISE EXCEPTION 'Instagram publication identity cannot be replaced';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER instagram_publications_protected BEFORE UPDATE ON instagram_publications
    FOR EACH ROW EXECUTE FUNCTION ptw_protect_instagram_publication();
COMMIT;
