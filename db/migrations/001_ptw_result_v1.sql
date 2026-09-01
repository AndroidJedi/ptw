BEGIN;

CREATE TABLE commander_entities (
    id uuid PRIMARY KEY,
    kind text NOT NULL CHECK (kind IN (
        'source','validation_project','product_brief','project_asset','project_brand_kit',
        'studio_recipe','studio_render','content_run','content_creative','content_element',
        'content_review_action','content_learning_rule','content_learning_snapshot',
        'telegram_delivery_receipt','content_outcome','content_creative_approval',
        'human_feedback','weight_update'
    )),
    attributes jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE commander_relationships (
    id uuid PRIMARY KEY,
    source_id uuid NOT NULL REFERENCES commander_entities(id) ON DELETE RESTRICT,
    relation text NOT NULL CHECK (relation IN (
        'contains','derived_from','supersedes','rerun_of','evaluates','adjusts'
    )),
    target_id uuid NOT NULL REFERENCES commander_entities(id) ON DELETE RESTRICT,
    attributes jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(source_id,relation,target_id)
);
CREATE INDEX commander_relationships_target_idx ON commander_relationships(target_id,relation);

CREATE TABLE commander_sources (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    source_type text NOT NULL CHECK (source_type IN ('owner_idea','owner_task')),
    title text NOT NULL,
    provider text NOT NULL CHECK (provider='owner'),
    external_id text NOT NULL,
    content text NOT NULL,
    content_sha256 char(64) NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(provider,external_id)
);

CREATE TABLE validation_projects (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    request_id uuid NOT NULL UNIQUE,
    owner_idea_source_id uuid NOT NULL UNIQUE REFERENCES commander_sources(entity_id) ON DELETE RESTRICT,
    name text NOT NULL CHECK (length(btrim(name)) BETWEEN 1 AND 120),
    name_source text NOT NULL CHECK (name_source IN ('raw_idea','product_brief','owner')),
    requested_by text NOT NULL,
    result_creation_enabled boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE commander_human_feedback (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    target_id uuid NOT NULL REFERENCES commander_entities(id) ON DELETE RESTRICT,
    domain text NOT NULL CHECK (domain IN ('product_brief','content_creative')),
    section_id text NOT NULL,
    instruction text NOT NULL CHECK (length(instruction) BETWEEN 1 AND 2000),
    actor text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE commander_weight_updates (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    feedback_id uuid NOT NULL REFERENCES commander_human_feedback(entity_id) ON DELETE RESTRICT,
    component text NOT NULL,
    delta numeric NOT NULL CHECK (delta BETWEEN -1 AND 1),
    reason text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE commander_audit_events (
    id uuid PRIMARY KEY,
    actor text NOT NULL,
    action text NOT NULL,
    target_id uuid,
    details jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE commander_operation_guard (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    operation_kind text,
    operation_id uuid,
    acquired_at timestamptz,
    CHECK ((operation_kind IS NULL)=(operation_id IS NULL)),
    CHECK ((operation_id IS NULL)=(acquired_at IS NULL))
);
INSERT INTO commander_operation_guard(singleton) VALUES(true);

CREATE TABLE commander_control (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    emergency_stop boolean NOT NULL DEFAULT false,
    updated_by text NOT NULL DEFAULT 'baseline',
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
INSERT INTO commander_control(singleton) VALUES(true);

CREATE TABLE product_briefs (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    project_id uuid NOT NULL REFERENCES validation_projects(entity_id) ON DELETE RESTRICT,
    request_id uuid NOT NULL UNIQUE,
    owner_idea_source_id uuid NOT NULL REFERENCES commander_sources(entity_id) ON DELETE RESTRICT,
    base_brief_id uuid REFERENCES product_briefs(entity_id) ON DELETE RESTRICT,
    feedback_id uuid REFERENCES commander_human_feedback(entity_id) ON DELETE RESTRICT,
    status text NOT NULL CHECK (status IN ('queued','generating','completed','failed')),
    document jsonb,
    document_sha256 char(64),
    quality_gates jsonb,
    failure_count integer NOT NULL DEFAULT 0 CHECK (failure_count>=0),
    error_code text,
    error_message text,
    requested_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    completed_at timestamptz,
    UNIQUE(entity_id,project_id),
    CHECK ((document IS NULL)=(document_sha256 IS NULL))
);
ALTER TABLE product_briefs ADD CONSTRAINT product_briefs_base_same_project_fkey
    FOREIGN KEY(base_brief_id,project_id) REFERENCES product_briefs(entity_id,project_id) ON DELETE RESTRICT;
CREATE UNIQUE INDEX product_briefs_one_root_per_project_idx
    ON product_briefs(project_id) WHERE base_brief_id IS NULL;
CREATE INDEX product_briefs_project_created_idx ON product_briefs(project_id,created_at DESC);

CREATE TABLE product_brief_approvals (
    id uuid PRIMARY KEY,
    brief_id uuid NOT NULL UNIQUE REFERENCES product_briefs(entity_id) ON DELETE RESTRICT,
    approved_by text NOT NULL,
    approved_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE validation_generation_attempts (
    id uuid PRIMARY KEY,
    target_id uuid NOT NULL REFERENCES commander_entities(id) ON DELETE RESTRICT,
    stage text NOT NULL CHECK (stage IN (
        'product_brief','content_candidate_generation',
        'content_non_human_graphic_generation'
    )),
    attempt_number integer NOT NULL CHECK (attempt_number>0),
    status text NOT NULL CHECK (status IN ('started','completed','failed')),
    error_code text,
    error_message text,
    started_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    completed_at timestamptz,
    UNIQUE(target_id,attempt_number)
);

CREATE TABLE validation_provider_invocations (
    id uuid PRIMARY KEY,
    target_id uuid NOT NULL REFERENCES commander_entities(id) ON DELETE RESTRICT,
    attempt_id uuid NOT NULL REFERENCES validation_generation_attempts(id) ON DELETE RESTRICT,
    provider text NOT NULL,
    mode text NOT NULL CHECK (mode IN (
        'product_brief','product_brief_revision','content_candidate_generation',
        'content_non_human_graphic_generation'
    )),
    idempotency_key text NOT NULL,
    request_sha256 char(64) NOT NULL,
    response_sha256 char(64),
    status text NOT NULL CHECK (status IN ('submitted','completed','failed')),
    invocation jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    completed_at timestamptz
);
CREATE INDEX validation_provider_invocations_call_idx
    ON validation_provider_invocations(idempotency_key,created_at);

CREATE TABLE project_assets (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    project_id uuid NOT NULL REFERENCES validation_projects(entity_id) ON DELETE RESTRICT,
    origin text NOT NULL CHECK (origin IN ('owner_upload','pexels','canonical_brand','ai_generated')),
    approval_status text NOT NULL CHECK (approval_status IN ('approved','pending_review','rejected')),
    title text NOT NULL CHECK (length(btrim(title)) BETWEEN 1 AND 200),
    mime_type text NOT NULL CHECK (mime_type IN ('image/jpeg','image/png','image/webp')),
    width integer NOT NULL CHECK (width BETWEEN 64 AND 12000),
    height integer NOT NULL CHECK (height BETWEEN 64 AND 12000),
    bytes bytea NOT NULL,
    bytes_sha256 char(64) NOT NULL,
    source_uri text,
    provider text NOT NULL,
    external_id text NOT NULL,
    license text,
    attribution text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(project_id,provider,external_id)
);
CREATE INDEX project_assets_project_created_idx ON project_assets(project_id,created_at DESC);
CREATE UNIQUE INDEX project_assets_content_creative_idx
    ON project_assets((metadata->>'content_creative_id'))
    WHERE metadata ? 'content_creative_id';

CREATE TABLE project_brand_kits (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    project_id uuid NOT NULL REFERENCES validation_projects(entity_id) ON DELETE RESTRICT,
    parent_brand_kit_id uuid REFERENCES project_brand_kits(entity_id) ON DELETE RESTRICT,
    logo_asset_id uuid REFERENCES project_assets(entity_id) ON DELETE RESTRICT,
    document jsonb NOT NULL,
    document_sha256 char(64) NOT NULL,
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(entity_id,project_id)
);
CREATE INDEX project_brand_kits_project_created_idx ON project_brand_kits(project_id,created_at DESC);

CREATE TABLE studio_recipes (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    creative_id uuid NOT NULL UNIQUE REFERENCES commander_entities(id) ON DELETE RESTRICT,
    project_id uuid NOT NULL REFERENCES validation_projects(entity_id) ON DELETE RESTRICT,
    brief_id uuid NOT NULL REFERENCES product_briefs(entity_id) ON DELETE RESTRICT,
    brand_kit_id uuid NOT NULL REFERENCES project_brand_kits(entity_id) ON DELETE RESTRICT,
    parent_recipe_id uuid REFERENCES studio_recipes(entity_id) ON DELETE RESTRICT,
    placement_tool_id text NOT NULL,
    document jsonb NOT NULL,
    document_sha256 char(64) NOT NULL,
    renderer_version text NOT NULL,
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE studio_render_attempts (
    id uuid PRIMARY KEY,
    recipe_id uuid NOT NULL REFERENCES studio_recipes(entity_id) ON DELETE RESTRICT,
    attempt_number integer NOT NULL CHECK (attempt_number>0),
    status text NOT NULL CHECK (status IN ('started','completed','failed')),
    error_code text,
    error_message text,
    started_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    completed_at timestamptz,
    UNIQUE(recipe_id,attempt_number)
);

CREATE TABLE studio_renders (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    recipe_id uuid NOT NULL UNIQUE REFERENCES studio_recipes(entity_id) ON DELETE RESTRICT,
    attempt_id uuid NOT NULL UNIQUE REFERENCES studio_render_attempts(id) ON DELETE RESTRICT,
    mime_type text NOT NULL CHECK (mime_type='image/jpeg'),
    width integer NOT NULL CHECK (width=1080),
    height integer NOT NULL CHECK (height IN (1080,1920)),
    bytes bytea NOT NULL,
    bytes_sha256 char(64) NOT NULL,
    manifest jsonb NOT NULL,
    manifest_sha256 char(64) NOT NULL,
    embedded_manifest text NOT NULL,
    renderer_version text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE content_generation_runs (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    request_id uuid NOT NULL UNIQUE,
    parent_run_id uuid REFERENCES content_generation_runs(entity_id) ON DELETE RESTRICT,
    project_id uuid NOT NULL REFERENCES validation_projects(entity_id) ON DELETE RESTRICT,
    brief_id uuid NOT NULL REFERENCES product_briefs(entity_id) ON DELETE RESTRICT,
    task_source_id uuid NOT NULL REFERENCES commander_sources(entity_id) ON DELETE RESTRICT,
    brand_kit_id uuid NOT NULL REFERENCES project_brand_kits(entity_id) ON DELETE RESTRICT,
    output_profile text NOT NULL CHECK (output_profile IN (
        'marketing_copy_v1','instagram_static_ad_v1','tiktok_photo_post_v1'
    )),
    task text NOT NULL CHECK (length(btrim(task)) BETWEEN 1 AND 4000),
    context_bundle jsonb NOT NULL,
    context_sha256 char(64) NOT NULL,
    generation_kind text NOT NULL CHECK (generation_kind IN ('initial','regenerate_all','tune')),
    reserved_creative_ids uuid[] NOT NULL CHECK (cardinality(reserved_creative_ids) IN (1,5)),
    generated_creative_ids uuid[] NOT NULL DEFAULT '{}',
    review_creative_ids uuid[] NOT NULL DEFAULT '{}',
    carried_review_creative_ids uuid[] NOT NULL DEFAULT '{}',
    approved_creative_id uuid REFERENCES commander_entities(id) ON DELETE RESTRICT,
    tuned_creative_id uuid REFERENCES commander_entities(id) ON DELETE RESTRICT,
    tuned_strategy_id text,
    status text NOT NULL CHECK (status IN (
        'queued','generating','awaiting_review','approved','superseded','failed'
    )),
    current_stage text NOT NULL CHECK (current_stage IN (
        'queued','generating_creatives','awaiting_review','approved','superseded','failed'
    )),
    budget_state jsonb NOT NULL,
    generator_skill_sha256 char(64) NOT NULL,
    corpus_sha256 char(64) NOT NULL,
    learning_snapshot_id uuid NOT NULL REFERENCES commander_entities(id) ON DELETE RESTRICT,
    notification_state text NOT NULL DEFAULT 'not_scheduled' CHECK (notification_state IN (
        'not_scheduled','pending','delivered','definite_failure','ambiguous'
    )),
    notification_receipt_id uuid REFERENCES commander_entities(id) ON DELETE RESTRICT,
    error_code text,
    error_message text,
    requested_by text NOT NULL,
    deadline_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    completed_at timestamptz,
    CHECK ((status IN ('queued','generating'))=(completed_at IS NULL)),
    CHECK ((generation_kind='tune')=(cardinality(reserved_creative_ids)=1)),
    CHECK ((generation_kind='tune')=(tuned_creative_id IS NOT NULL)),
    CHECK (cardinality(review_creative_ids) IN (0,5)),
    CHECK (cardinality(carried_review_creative_ids) IN (0,5))
);
CREATE INDEX content_generation_runs_project_created_idx
    ON content_generation_runs(project_id,created_at DESC);
CREATE INDEX content_generation_runs_resume_idx
    ON content_generation_runs(status,current_stage,created_at)
    WHERE status IN ('queued','generating');

CREATE TABLE content_creatives (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    run_id uuid NOT NULL REFERENCES content_generation_runs(entity_id) ON DELETE RESTRICT,
    slot text NOT NULL CHECK (slot ~ '^C[1-5]$'),
    round integer NOT NULL CHECK (round BETWEEN 0 AND 100),
    generation_kind text NOT NULL CHECK (generation_kind IN ('initial','regenerate_all','tune')),
    parent_creative_id uuid REFERENCES content_creatives(entity_id) ON DELETE RESTRICT,
    template_id text NOT NULL,
    template_version integer NOT NULL CHECK (template_version>0),
    template_sha256 char(64) NOT NULL,
    hook_pressure smallint NOT NULL CHECK (hook_pressure BETWEEN 0 AND 100),
    emotional_intensity smallint NOT NULL CHECK (emotional_intensity BETWEEN 0 AND 100),
    conceptual_novelty smallint NOT NULL CHECK (conceptual_novelty BETWEEN 0 AND 100),
    information_density smallint NOT NULL CHECK (information_density BETWEEN 0 AND 100),
    visual_complexity smallint NOT NULL CHECK (visual_complexity BETWEEN 0 AND 100),
    parameters jsonb NOT NULL,
    config_sha256 char(64) NOT NULL,
    document jsonb NOT NULL,
    document_sha256 char(64) NOT NULL,
    recipe_id uuid REFERENCES studio_recipes(entity_id) ON DELETE RESTRICT,
    render_id uuid REFERENCES studio_renders(entity_id) ON DELETE RESTRICT,
    provider_provenance jsonb NOT NULL,
    provider_invocation_id uuid NOT NULL REFERENCES validation_provider_invocations(id) ON DELETE RESTRICT,
    media_identity_sha256 char(64),
    response_sha256 char(64) NOT NULL,
    retry_count integer NOT NULL CHECK (retry_count BETWEEN 0 AND 1),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(run_id,slot),
    CHECK ((recipe_id IS NULL)=(render_id IS NULL))
);
CREATE UNIQUE INDEX content_creatives_run_document_idx
    ON content_creatives(run_id,document_sha256);

CREATE TABLE content_creative_previews (
    creative_id uuid PRIMARY KEY REFERENCES content_creatives(entity_id) ON DELETE RESTRICT,
    mime_type text NOT NULL CHECK (mime_type='image/jpeg'),
    width integer NOT NULL CHECK (width=1080),
    height integer NOT NULL CHECK (height IN (1080,1920)),
    bytes bytea NOT NULL,
    bytes_sha256 char(64) NOT NULL,
    renderer_version text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE content_elements (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    run_id uuid NOT NULL REFERENCES content_generation_runs(entity_id) ON DELETE RESTRICT,
    display_alias text NOT NULL,
    slot text NOT NULL,
    element_type text NOT NULL CHECK (element_type IN ('copy','media_request','visual_component')),
    ordinal integer NOT NULL CHECK (ordinal>=0),
    payload jsonb NOT NULL,
    payload_sha256 char(64) NOT NULL,
    born_in_creative_id uuid NOT NULL REFERENCES content_creatives(entity_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(run_id,display_alias),
    UNIQUE(born_in_creative_id,slot,ordinal)
);

CREATE TABLE content_creative_elements (
    id uuid PRIMARY KEY,
    creative_id uuid NOT NULL REFERENCES content_creatives(entity_id) ON DELETE RESTRICT,
    element_id uuid NOT NULL REFERENCES content_elements(entity_id) ON DELETE RESTRICT,
    slot text NOT NULL,
    ordinal integer NOT NULL CHECK (ordinal>=0),
    reuse_mode text NOT NULL CHECK (reuse_mode IN ('generated','reuse_exact')),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(creative_id,slot,ordinal),
    UNIQUE(creative_id,element_id)
);

CREATE TABLE content_review_actions (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    request_id uuid NOT NULL UNIQUE,
    run_id uuid NOT NULL REFERENCES content_generation_runs(entity_id) ON DELETE RESTRICT,
    action_type text NOT NULL CHECK (action_type IN ('approve','regenerate_all','tune')),
    status text NOT NULL CHECK (status IN ('processing','completed','failed')),
    selected_creative_id uuid REFERENCES content_creatives(entity_id) ON DELETE RESTRICT,
    comment text CHECK (comment IS NULL OR length(comment) BETWEEN 3 AND 2000),
    child_run_id uuid REFERENCES content_generation_runs(entity_id) ON DELETE RESTRICT,
    requested_by text NOT NULL,
    failure jsonb,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    completed_at timestamptz
);
CREATE UNIQUE INDEX content_review_actions_active_run_idx
    ON content_review_actions(run_id) WHERE status='processing';

CREATE TABLE content_learning_rules (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    project_id uuid NOT NULL REFERENCES validation_projects(entity_id) ON DELETE RESTRICT,
    feedback_id uuid NOT NULL REFERENCES commander_human_feedback(entity_id) ON DELETE RESTRICT,
    rule_type text NOT NULL CHECK (rule_type IN (
        'preferred_direction','preferred_layout','tune_instruction','exploration_exclusions'
    )),
    strategy_id text,
    output_profile text,
    instruction text,
    slider_values jsonb NOT NULL DEFAULT '{}',
    layout_patch jsonb NOT NULL DEFAULT '[]',
    exclusions jsonb NOT NULL DEFAULT '{}',
    supersedes_rule_id uuid REFERENCES content_learning_rules(entity_id) ON DELETE RESTRICT,
    rule_sha256 char(64) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE content_learning_snapshots (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    project_id uuid NOT NULL REFERENCES validation_projects(entity_id) ON DELETE RESTRICT,
    document jsonb NOT NULL,
    document_sha256 char(64) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE content_creative_approvals (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    creative_id uuid NOT NULL UNIQUE REFERENCES content_creatives(entity_id) ON DELETE RESTRICT,
    feedback_id uuid NOT NULL UNIQUE REFERENCES commander_human_feedback(entity_id) ON DELETE RESTRICT,
    approved_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE telegram_delivery_receipts (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    run_id uuid NOT NULL UNIQUE REFERENCES content_generation_runs(entity_id) ON DELETE RESTRICT,
    status text NOT NULL CHECK (status IN (
        'pending','delivered','definite_failure','ambiguous'
    )),
    attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count BETWEEN 0 AND 100),
    provider_message_id text,
    error_code text,
    error_message text,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE content_generation_outcomes (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    run_id uuid NOT NULL REFERENCES content_generation_runs(entity_id) ON DELETE RESTRICT,
    creative_id uuid NOT NULL REFERENCES content_creatives(entity_id) ON DELETE RESTRICT,
    event_type text NOT NULL CHECK (event_type IN ('accepted','downloaded','used','metric_observed')),
    payload jsonb NOT NULL DEFAULT '{}',
    source_type text NOT NULL CHECK (source_type IN ('owner','system','authorized_analytics_adapter')),
    source_id text,
    observed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE content_generation_checkpoints (
    id uuid PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES content_generation_runs(entity_id) ON DELETE RESTRICT,
    sequence integer NOT NULL CHECK (sequence>0),
    stage text NOT NULL,
    target_id uuid,
    payload jsonb NOT NULL,
    payload_sha256 char(64) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(run_id,sequence),
    UNIQUE(run_id,stage,target_id)
);

CREATE FUNCTION ptw_reject_immutable_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION '% is append-only',TG_TABLE_NAME; END $$;

DO $$
DECLARE table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'commander_entities','commander_relationships','commander_sources',
        'commander_human_feedback','commander_weight_updates','commander_audit_events',
        'product_brief_approvals','project_assets','project_brand_kits','studio_recipes',
        'studio_renders','content_creatives','content_creative_previews','content_elements',
        'content_creative_elements','content_learning_rules','content_learning_snapshots',
        'content_creative_approvals','content_generation_outcomes','content_generation_checkpoints'
    ] LOOP
        EXECUTE format(
            'CREATE TRIGGER %I_immutable BEFORE UPDATE OR DELETE ON %I FOR EACH ROW EXECUTE FUNCTION ptw_reject_immutable_mutation()',
            table_name,table_name
        );
    END LOOP;
END $$;

CREATE FUNCTION ptw_protect_validation_project() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.request_id IS DISTINCT FROM OLD.request_id
       OR NEW.owner_idea_source_id IS DISTINCT FROM OLD.owner_idea_source_id
       OR NEW.requested_by IS DISTINCT FROM OLD.requested_by
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'immutable Validation Project fields cannot change';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER validation_projects_protected BEFORE UPDATE ON validation_projects
FOR EACH ROW EXECUTE FUNCTION ptw_protect_validation_project();

CREATE FUNCTION ptw_protect_product_brief() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.project_id IS DISTINCT FROM OLD.project_id
       OR NEW.request_id IS DISTINCT FROM OLD.request_id
       OR NEW.owner_idea_source_id IS DISTINCT FROM OLD.owner_idea_source_id
       OR NEW.base_brief_id IS DISTINCT FROM OLD.base_brief_id
       OR NEW.feedback_id IS DISTINCT FROM OLD.feedback_id
       OR (NEW.document IS DISTINCT FROM OLD.document AND OLD.document IS NOT NULL)
       OR (NEW.document_sha256 IS DISTINCT FROM OLD.document_sha256 AND OLD.document_sha256 IS NOT NULL)
       OR NEW.requested_by IS DISTINCT FROM OLD.requested_by
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'immutable Product Brief fields cannot change';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER product_briefs_protected BEFORE UPDATE ON product_briefs
FOR EACH ROW EXECUTE FUNCTION ptw_protect_product_brief();

CREATE FUNCTION ptw_protect_content_run() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.request_id IS DISTINCT FROM OLD.request_id
       OR NEW.parent_run_id IS DISTINCT FROM OLD.parent_run_id
       OR NEW.project_id IS DISTINCT FROM OLD.project_id
       OR NEW.brief_id IS DISTINCT FROM OLD.brief_id
       OR NEW.task_source_id IS DISTINCT FROM OLD.task_source_id
       OR NEW.brand_kit_id IS DISTINCT FROM OLD.brand_kit_id
       OR NEW.output_profile IS DISTINCT FROM OLD.output_profile
       OR NEW.task IS DISTINCT FROM OLD.task
       OR NEW.context_bundle IS DISTINCT FROM OLD.context_bundle
       OR NEW.context_sha256 IS DISTINCT FROM OLD.context_sha256
       OR NEW.generation_kind IS DISTINCT FROM OLD.generation_kind
       OR NEW.reserved_creative_ids IS DISTINCT FROM OLD.reserved_creative_ids
       OR NEW.carried_review_creative_ids IS DISTINCT FROM OLD.carried_review_creative_ids
       OR NEW.tuned_creative_id IS DISTINCT FROM OLD.tuned_creative_id
       OR NEW.tuned_strategy_id IS DISTINCT FROM OLD.tuned_strategy_id
       OR NEW.generator_skill_sha256 IS DISTINCT FROM OLD.generator_skill_sha256
       OR NEW.corpus_sha256 IS DISTINCT FROM OLD.corpus_sha256
       OR NEW.learning_snapshot_id IS DISTINCT FROM OLD.learning_snapshot_id
       OR NEW.requested_by IS DISTINCT FROM OLD.requested_by
       OR NEW.deadline_at IS DISTINCT FROM OLD.deadline_at
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'immutable content generation run fields cannot change';
    END IF;
    IF OLD.status IN ('approved','superseded','failed') AND NEW IS DISTINCT FROM OLD THEN
        RAISE EXCEPTION 'terminal content generation run is immutable';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER content_generation_runs_protected BEFORE UPDATE ON content_generation_runs
FOR EACH ROW EXECUTE FUNCTION ptw_protect_content_run();

COMMIT;
