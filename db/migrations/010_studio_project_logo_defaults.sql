BEGIN;

ALTER TABLE commander_entities DROP CONSTRAINT commander_entities_kind_check;
ALTER TABLE commander_entities ADD CONSTRAINT commander_entities_kind_check CHECK (kind IN (
    'source','validation_project','product_brief','human_feedback','weight_update',
    'studio_workspace','studio_asset','studio_version','studio_generation_run',
    'studio_edit_checkpoint','studio_learning_run','studio_skill_snapshot',
    'studio_learning_proposal','studio_learning_decision','studio_project_logo_default',
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

ALTER TABLE studio_edit_checkpoints
    ADD CONSTRAINT studio_edit_checkpoints_entity_project_key
    UNIQUE(entity_id,project_id);

CREATE TABLE studio_project_logo_defaults (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    project_id uuid NOT NULL REFERENCES validation_projects(entity_id) ON DELETE RESTRICT,
    source_checkpoint_id uuid NOT NULL UNIQUE,
    symbol_color char(7) NOT NULL CHECK (symbol_color ~ '^#[0-9A-F]{6}$'),
    name_color char(7) NOT NULL CHECK (name_color ~ '^#[0-9A-F]{6}$'),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY(source_checkpoint_id,project_id)
        REFERENCES studio_edit_checkpoints(entity_id,project_id) ON DELETE RESTRICT
);
CREATE INDEX studio_project_logo_defaults_project_created_idx
    ON studio_project_logo_defaults(project_id,created_at DESC,entity_id DESC);

CREATE TRIGGER studio_project_logo_defaults_immutable BEFORE UPDATE OR DELETE
    ON studio_project_logo_defaults FOR EACH ROW EXECUTE FUNCTION ptw_reject_immutable_mutation();

COMMIT;
