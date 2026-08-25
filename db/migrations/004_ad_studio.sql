BEGIN;

ALTER TABLE commander_entities
    DROP CONSTRAINT commander_entities_kind_check,
    ADD CONSTRAINT commander_entities_kind_check CHECK (kind IN (
        'source','validation_project','product_brief','creative_batch','ad_creative','artifact',
        'studio_source_asset','studio_brand_kit','studio_template','studio_recipe','studio_render',
        'studio_sample_set','studio_wizard_proposal',
        'human_feedback','weight_update','task','audit_event','policy_evaluation'
    ));

ALTER TABLE commander_human_feedback
    DROP CONSTRAINT commander_human_feedback_domain_check,
    ADD CONSTRAINT commander_human_feedback_domain_check
        CHECK (domain IN ('product_brief','ad_creative','ad_studio'));

CREATE TABLE ad_studio_source_assets (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    project_id uuid NOT NULL REFERENCES validation_projects(entity_id) ON DELETE RESTRICT,
    origin text NOT NULL CHECK (origin IN ('owner_upload','pexels','canonical_brand','ai_generated')),
    title text NOT NULL CHECK (length(btrim(title)) BETWEEN 1 AND 200),
    mime_type text NOT NULL CHECK (mime_type IN (
        'image/jpeg','image/png','image/webp','video/mp4','video/quicktime'
    )),
    width integer NOT NULL CHECK (width BETWEEN 64 AND 12000),
    height integer NOT NULL CHECK (height BETWEEN 64 AND 12000),
    duration_seconds numeric,
    bytes bytea NOT NULL,
    bytes_sha256 char(64) NOT NULL,
    source_uri text,
    provider text NOT NULL,
    external_id text,
    license text,
    attribution text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK ((mime_type LIKE 'video/%') = (duration_seconds IS NOT NULL)),
    UNIQUE NULLS NOT DISTINCT (project_id,provider,external_id)
);

CREATE TABLE ad_studio_brand_kits (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    project_id uuid NOT NULL REFERENCES validation_projects(entity_id) ON DELETE RESTRICT,
    parent_brand_kit_id uuid REFERENCES ad_studio_brand_kits(entity_id) ON DELETE RESTRICT,
    logo_source_asset_id uuid REFERENCES ad_studio_source_assets(entity_id) ON DELETE RESTRICT,
    document jsonb NOT NULL,
    document_sha256 char(64) NOT NULL,
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(entity_id,project_id)
);
CREATE INDEX ad_studio_brand_kits_project_created_idx
    ON ad_studio_brand_kits(project_id,created_at DESC);

CREATE TABLE ad_studio_templates (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    project_id uuid NOT NULL REFERENCES validation_projects(entity_id) ON DELETE RESTRICT,
    name text NOT NULL CHECK (length(btrim(name)) BETWEEN 1 AND 120),
    placement_tool_id text NOT NULL,
    document jsonb NOT NULL,
    document_sha256 char(64) NOT NULL,
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX ad_studio_templates_project_created_idx
    ON ad_studio_templates(project_id,created_at DESC);

CREATE TABLE ad_studio_recipes (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    project_id uuid NOT NULL REFERENCES validation_projects(entity_id) ON DELETE RESTRICT,
    brief_id uuid NOT NULL REFERENCES product_briefs(entity_id) ON DELETE RESTRICT,
    brand_kit_id uuid NOT NULL REFERENCES ad_studio_brand_kits(entity_id) ON DELETE RESTRICT,
    template_id uuid REFERENCES ad_studio_templates(entity_id) ON DELETE RESTRICT,
    application_request_id uuid UNIQUE,
    application_creative_id uuid REFERENCES ad_creatives(entity_id) ON DELETE RESTRICT,
    parent_recipe_id uuid REFERENCES ad_studio_recipes(entity_id) ON DELETE RESTRICT,
    placement_tool_id text NOT NULL,
    document jsonb NOT NULL,
    document_sha256 char(64) NOT NULL,
    renderer_version text NOT NULL,
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK ((template_id IS NULL) = (application_request_id IS NULL)),
    UNIQUE(entity_id,project_id)
);
CREATE INDEX ad_studio_recipes_project_created_idx
    ON ad_studio_recipes(project_id,created_at DESC);

CREATE TABLE ad_studio_render_attempts (
    id uuid PRIMARY KEY,
    recipe_id uuid NOT NULL REFERENCES ad_studio_recipes(entity_id) ON DELETE RESTRICT,
    attempt_number integer NOT NULL CHECK (attempt_number > 0),
    status text NOT NULL CHECK (status IN ('started','completed','failed')),
    error_code text,
    error_message text,
    started_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    completed_at timestamptz,
    UNIQUE(recipe_id,attempt_number)
);

CREATE TABLE ad_studio_renders (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    recipe_id uuid NOT NULL REFERENCES ad_studio_recipes(entity_id) ON DELETE RESTRICT,
    attempt_id uuid NOT NULL UNIQUE REFERENCES ad_studio_render_attempts(id) ON DELETE RESTRICT,
    mime_type text NOT NULL CHECK (mime_type IN ('image/jpeg','video/mp4')),
    width integer NOT NULL,
    height integer NOT NULL,
    duration_seconds numeric,
    bytes bytea NOT NULL,
    bytes_sha256 char(64) NOT NULL,
    manifest jsonb NOT NULL,
    manifest_sha256 char(64) NOT NULL,
    embedded_manifest text NOT NULL,
    renderer_version text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK ((mime_type='video/mp4') = (duration_seconds IS NOT NULL))
);
CREATE INDEX ad_studio_renders_recipe_created_idx
    ON ad_studio_renders(recipe_id,created_at DESC);

CREATE TABLE ad_studio_sample_sets (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    project_id uuid NOT NULL REFERENCES validation_projects(entity_id) ON DELETE RESTRICT,
    brief_id uuid NOT NULL REFERENCES product_briefs(entity_id) ON DELETE RESTRICT,
    batch_id uuid NOT NULL UNIQUE REFERENCES creative_batches(entity_id) ON DELETE RESTRICT,
    brand_kit_id uuid NOT NULL REFERENCES ad_studio_brand_kits(entity_id) ON DELETE RESTRICT,
    status text NOT NULL CHECK (status='completed'),
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX ad_studio_sample_sets_project_created_idx
    ON ad_studio_sample_sets(project_id,created_at DESC);

CREATE TABLE ad_studio_sample_set_items (
    id uuid PRIMARY KEY,
    sample_set_id uuid NOT NULL REFERENCES ad_studio_sample_sets(entity_id) ON DELETE RESTRICT,
    ordinal integer NOT NULL CHECK (ordinal BETWEEN 0 AND 4),
    angle text NOT NULL CHECK (angle IN ('emotional','practical','curiosity','authority','problem_first')),
    name text NOT NULL CHECK (length(btrim(name)) BETWEEN 1 AND 120),
    source_creative_id uuid NOT NULL REFERENCES ad_creatives(entity_id) ON DELETE RESTRICT,
    template_id uuid NOT NULL REFERENCES ad_studio_templates(entity_id) ON DELETE RESTRICT,
    recipe_id uuid NOT NULL REFERENCES ad_studio_recipes(entity_id) ON DELETE RESTRICT,
    render_id uuid NOT NULL REFERENCES ad_studio_renders(entity_id) ON DELETE RESTRICT,
    caption text NOT NULL CHECK (length(btrim(caption)) BETWEEN 1 AND 2200),
    alt_text text NOT NULL CHECK (length(btrim(alt_text)) BETWEEN 1 AND 1000),
    UNIQUE(sample_set_id,ordinal),
    UNIQUE(sample_set_id,angle),
    UNIQUE(template_id),
    UNIQUE(recipe_id),
    UNIQUE(render_id)
);

CREATE TABLE ad_studio_wizard_proposals (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    recipe_id uuid NOT NULL REFERENCES ad_studio_recipes(entity_id) ON DELETE RESTRICT,
    instruction text NOT NULL CHECK (length(btrim(instruction)) BETWEEN 1 AND 2000),
    target_instance_id uuid,
    patch jsonb NOT NULL,
    before_sha256 char(64) NOT NULL,
    after_document jsonb NOT NULL,
    after_sha256 char(64) NOT NULL,
    preview_bytes bytea NOT NULL,
    preview_sha256 char(64) NOT NULL,
    preview_mime_type text NOT NULL CHECK (preview_mime_type='image/jpeg'),
    generated_source_asset_id uuid REFERENCES ad_studio_source_assets(entity_id) ON DELETE RESTRICT,
    provider_provenance jsonb NOT NULL,
    status text NOT NULL CHECK (status IN ('previewed','applied')),
    applied_recipe_id uuid UNIQUE REFERENCES ad_studio_recipes(entity_id) ON DELETE RESTRICT,
    applied_render_id uuid UNIQUE REFERENCES ad_studio_renders(entity_id) ON DELETE RESTRICT,
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    applied_at timestamptz,
    CHECK ((status='previewed') = (applied_recipe_id IS NULL AND applied_render_id IS NULL AND applied_at IS NULL)),
    CHECK ((status='applied') = (applied_recipe_id IS NOT NULL AND applied_render_id IS NOT NULL AND applied_at IS NOT NULL))
);
CREATE INDEX ad_studio_wizard_proposals_recipe_created_idx
    ON ad_studio_wizard_proposals(recipe_id,created_at DESC);

CREATE TABLE ad_studio_publications (
    id uuid PRIMARY KEY,
    render_id uuid NOT NULL UNIQUE REFERENCES ad_studio_renders(entity_id) ON DELETE RESTRICT,
    published_by text NOT NULL,
    published_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE ad_studio_skill_proposals (
    id uuid PRIMARY KEY,
    feedback_id uuid NOT NULL UNIQUE REFERENCES commander_human_feedback(entity_id) ON DELETE RESTRICT,
    render_id uuid NOT NULL REFERENCES ad_studio_renders(entity_id) ON DELETE RESTRICT,
    lesson text NOT NULL CHECK (length(lesson) BETWEEN 1 AND 500),
    status text NOT NULL CHECK (status IN ('pending','planning','promoted','rejected','failed')),
    command_session_id uuid,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

DO $$
DECLARE table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'ad_studio_source_assets','ad_studio_brand_kits','ad_studio_templates','ad_studio_recipes',
        'ad_studio_renders','ad_studio_sample_sets','ad_studio_sample_set_items',
        'ad_studio_publications'
    ]
    LOOP
        EXECUTE format(
            'CREATE TRIGGER %I_immutable BEFORE UPDATE OR DELETE ON %I '
            'FOR EACH ROW EXECUTE FUNCTION ptw_reject_immutable_mutation()',
            table_name, table_name
        );
    END LOOP;
END $$;

CREATE FUNCTION ptw_protect_ad_studio_wizard_proposal() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.recipe_id IS DISTINCT FROM OLD.recipe_id
       OR NEW.instruction IS DISTINCT FROM OLD.instruction
       OR NEW.target_instance_id IS DISTINCT FROM OLD.target_instance_id
       OR NEW.patch IS DISTINCT FROM OLD.patch
       OR NEW.before_sha256 IS DISTINCT FROM OLD.before_sha256
       OR NEW.after_document IS DISTINCT FROM OLD.after_document
       OR NEW.after_sha256 IS DISTINCT FROM OLD.after_sha256
       OR NEW.preview_bytes IS DISTINCT FROM OLD.preview_bytes
       OR NEW.preview_sha256 IS DISTINCT FROM OLD.preview_sha256
       OR NEW.preview_mime_type IS DISTINCT FROM OLD.preview_mime_type
       OR NEW.generated_source_asset_id IS DISTINCT FROM OLD.generated_source_asset_id
       OR NEW.provider_provenance IS DISTINCT FROM OLD.provider_provenance
       OR NEW.created_by IS DISTINCT FROM OLD.created_by
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'immutable Ad Studio wizard proposal fields cannot change';
    END IF;
    IF OLD.status='applied' AND NEW IS DISTINCT FROM OLD THEN
        RAISE EXCEPTION 'applied Ad Studio wizard proposal is immutable';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER ad_studio_wizard_proposals_protected
BEFORE UPDATE ON ad_studio_wizard_proposals
FOR EACH ROW EXECUTE FUNCTION ptw_protect_ad_studio_wizard_proposal();

CREATE FUNCTION ptw_protect_ad_studio_proposal() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.feedback_id IS DISTINCT FROM OLD.feedback_id
       OR NEW.render_id IS DISTINCT FROM OLD.render_id
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'immutable Ad Studio proposal fields cannot change';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER ad_studio_skill_proposals_protected
BEFORE UPDATE ON ad_studio_skill_proposals
FOR EACH ROW EXECUTE FUNCTION ptw_protect_ad_studio_proposal();

COMMIT;
