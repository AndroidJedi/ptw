BEGIN;

ALTER TABLE commander_entities
    DROP CONSTRAINT commander_entities_kind_check,
    ADD CONSTRAINT commander_entities_kind_check CHECK (kind IN (
        'source','validation_project','product_brief','creative_batch','ad_creative','artifact',
        'studio_source_asset','studio_brand_kit','studio_template','studio_recipe','studio_render',
        'studio_sample_set','studio_wizard_proposal','studio_creative_validation',
        'human_feedback','weight_update','task','audit_event','policy_evaluation'
    ));

CREATE TABLE ad_studio_creative_validations (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    recipe_id uuid NOT NULL REFERENCES ad_studio_recipes(entity_id) ON DELETE RESTRICT,
    wizard_proposal_id uuid UNIQUE REFERENCES ad_studio_wizard_proposals(entity_id) ON DELETE RESTRICT,
    render_id uuid UNIQUE REFERENCES ad_studio_renders(entity_id) ON DELETE RESTRICT,
    status text NOT NULL CHECK (status IN ('approved','failed')),
    attempt_count integer NOT NULL CHECK (attempt_count BETWEEN 1 AND 4),
    recreation_count integer NOT NULL CHECK (recreation_count BETWEEN 0 AND 3),
    skill_sha256 char(64) NOT NULL,
    attempts jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK (recreation_count = attempt_count - 1),
    CHECK (
        (status='approved' AND num_nonnulls(wizard_proposal_id,render_id)=1)
        OR (status='failed' AND num_nonnulls(wizard_proposal_id,render_id)=0)
    )
);
CREATE INDEX ad_studio_creative_validations_recipe_created_idx
    ON ad_studio_creative_validations(recipe_id,created_at DESC);

CREATE TRIGGER ad_studio_creative_validations_immutable
BEFORE UPDATE OR DELETE ON ad_studio_creative_validations
FOR EACH ROW EXECUTE FUNCTION ptw_reject_immutable_mutation();

COMMIT;
