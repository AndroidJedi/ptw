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
    'instagram_publication','instagram_publication_attempt'
));

CREATE TABLE meta_ads_control_actions (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    project_id uuid NOT NULL REFERENCES validation_projects(entity_id) ON DELETE RESTRICT,
    deployment_id uuid NOT NULL REFERENCES meta_ads_deployments(entity_id) ON DELETE RESTRICT,
    request_id uuid NOT NULL UNIQUE,
    request_sha256 char(64) NOT NULL,
    action jsonb NOT NULL,
    before_snapshot jsonb NOT NULL,
    state jsonb NOT NULL CHECK (state->>'status' IN ('proposed','executing','completed','failed','uncertain')),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK (jsonb_typeof(action) = 'object'),
    CHECK (jsonb_typeof(before_snapshot) = 'object')
);
CREATE INDEX meta_ads_control_actions_project_created_idx
    ON meta_ads_control_actions(project_id,created_at DESC);

CREATE TABLE meta_ads_insight_snapshots (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    deployment_id uuid NOT NULL REFERENCES meta_ads_deployments(entity_id) ON DELETE RESTRICT,
    window_days integer NOT NULL CHECK (window_days IN (7,30)),
    metrics jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX meta_ads_insights_deployment_created_idx
    ON meta_ads_insight_snapshots(deployment_id,created_at DESC);

CREATE TABLE meta_ads_recommendations (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    deployment_id uuid NOT NULL REFERENCES meta_ads_deployments(entity_id) ON DELETE RESTRICT,
    insight_snapshot_id uuid REFERENCES meta_ads_insight_snapshots(entity_id) ON DELETE RESTRICT,
    record jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX meta_ads_recommendations_deployment_created_idx
    ON meta_ads_recommendations(deployment_id,created_at DESC);

CREATE FUNCTION ptw_protect_meta_ads_control_action() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF (to_jsonb(NEW) - 'state' - 'updated_at') IS DISTINCT FROM (to_jsonb(OLD) - 'state' - 'updated_at') THEN
        RAISE EXCEPTION 'Meta Ads control action input is immutable';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER meta_ads_control_action_protected BEFORE UPDATE ON meta_ads_control_actions
    FOR EACH ROW EXECUTE FUNCTION ptw_protect_meta_ads_control_action();
CREATE TRIGGER meta_ads_insight_snapshots_immutable BEFORE UPDATE OR DELETE
    ON meta_ads_insight_snapshots FOR EACH ROW EXECUTE FUNCTION ptw_reject_immutable_mutation();
CREATE TRIGGER meta_ads_recommendations_immutable BEFORE UPDATE OR DELETE
    ON meta_ads_recommendations FOR EACH ROW EXECUTE FUNCTION ptw_reject_immutable_mutation();

COMMIT;
