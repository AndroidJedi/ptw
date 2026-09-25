BEGIN;
ALTER TABLE commander_entities DROP CONSTRAINT commander_entities_kind_check;
ALTER TABLE commander_entities ADD CONSTRAINT commander_entities_kind_check CHECK (kind IN (
    'source','validation_project','product_brief','human_feedback','weight_update',
    'studio_workspace','studio_asset','studio_version','studio_generation_run',
    'studio_edit_checkpoint','studio_learning_run','studio_skill_snapshot',
    'studio_learning_proposal','studio_learning_decision','studio_project_logo_default','landing_operation',
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

CREATE TABLE landing_operations (
    operation_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    landing_id uuid NOT NULL REFERENCES landing_workspaces(entity_id) ON DELETE RESTRICT,
    project_id uuid NOT NULL REFERENCES validation_projects(entity_id) ON DELETE RESTRICT,
    request_id uuid NOT NULL,
    status text NOT NULL CHECK(status IN ('queued','running','completed','failed','interrupted')),
    revision integer NOT NULL,
    payload text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(landing_id,request_id)
);
CREATE UNIQUE INDEX landing_one_active_operation ON landing_operations(landing_id) WHERE status IN ('queued','running');
CREATE TABLE landing_operation_events (
    operation_id uuid NOT NULL REFERENCES landing_operations(operation_id) ON DELETE RESTRICT,
    revision integer NOT NULL,
    payload text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY(operation_id,revision)
);
CREATE FUNCTION protect_landing_operation_history() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Landing operation history is append-only'; END; $$;
CREATE TRIGGER landing_operation_events_immutable BEFORE UPDATE OR DELETE ON landing_operation_events
FOR EACH ROW EXECUTE FUNCTION protect_landing_operation_history();
COMMIT;
