BEGIN;

CREATE TABLE commander_entities (
    id uuid PRIMARY KEY,
    kind text NOT NULL CHECK (kind IN (
        'source','validation_project','product_brief','project_asset','project_brand_kit',
        'studio_recipe','studio_render','content_run','content_candidate','content_element',
        'content_critic_pass','content_improvement_action','content_result','content_outcome',
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
    domain text NOT NULL CHECK (domain IN ('product_brief','content_result')),
    section_id text NOT NULL,
    instruction text NOT NULL CHECK (length(instruction) BETWEEN 1 AND 2000),
    actor text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE commander_weight_updates (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    feedback_id uuid NOT NULL REFERENCES commander_human_feedback(entity_id) ON DELETE RESTRICT,
    component text NOT NULL,
    delta numeric NOT NULL CHECK (delta=0),
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
        'product_brief','content_candidate_generation','content_result_critic',
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
        'content_result_critic','content_non_human_graphic_generation'
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
CREATE UNIQUE INDEX project_assets_content_candidate_idx
    ON project_assets((metadata->>'content_candidate_id'))
    WHERE metadata ? 'content_candidate_id';

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
    candidate_id uuid NOT NULL UNIQUE REFERENCES commander_entities(id) ON DELETE RESTRICT,
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
    task_source_id uuid NOT NULL UNIQUE REFERENCES commander_sources(entity_id) ON DELETE RESTRICT,
    brand_kit_id uuid NOT NULL REFERENCES project_brand_kits(entity_id) ON DELETE RESTRICT,
    output_profile text NOT NULL CHECK (output_profile IN (
        'marketing_copy_v1','instagram_static_ad_v1','tiktok_photo_post_v1'
    )),
    task text NOT NULL CHECK (length(btrim(task)) BETWEEN 1 AND 4000),
    context_bundle jsonb NOT NULL,
    context_sha256 char(64) NOT NULL,
    initial_candidate_ids uuid[] NOT NULL CHECK (
        cardinality(initial_candidate_ids)=5
        AND initial_candidate_ids[1]<>initial_candidate_ids[2]
        AND initial_candidate_ids[1]<>initial_candidate_ids[3]
        AND initial_candidate_ids[1]<>initial_candidate_ids[4]
        AND initial_candidate_ids[1]<>initial_candidate_ids[5]
        AND initial_candidate_ids[2]<>initial_candidate_ids[3]
        AND initial_candidate_ids[2]<>initial_candidate_ids[4]
        AND initial_candidate_ids[2]<>initial_candidate_ids[5]
        AND initial_candidate_ids[3]<>initial_candidate_ids[4]
        AND initial_candidate_ids[3]<>initial_candidate_ids[5]
        AND initial_candidate_ids[4]<>initial_candidate_ids[5]
    ),
    critic_pass_ids uuid[] NOT NULL CHECK (
        cardinality(critic_pass_ids)=3
        AND critic_pass_ids[1]<>critic_pass_ids[2]
        AND critic_pass_ids[1]<>critic_pass_ids[3]
        AND critic_pass_ids[2]<>critic_pass_ids[3]
    ),
    status text NOT NULL CHECK (status IN ('queued','generating','completed','failed')),
    current_stage text NOT NULL CHECK (current_stage IN (
        'queued','initial_candidates','critic_pass_1','critic_pass_2','critic_pass_3',
        'materializing_result','completed','failed'
    )),
    budget_state jsonb NOT NULL,
    generator_skill_sha256 char(64) NOT NULL,
    critic_skill_sha256 char(64) NOT NULL,
    corpus_sha256 char(64) NOT NULL,
    error_code text,
    error_message text,
    requested_by text NOT NULL,
    deadline_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    completed_at timestamptz,
    UNIQUE(entity_id,project_id),
    CHECK ((status='completed')=(completed_at IS NOT NULL))
);
CREATE INDEX content_generation_runs_project_created_idx ON content_generation_runs(project_id,created_at DESC);
CREATE INDEX content_generation_runs_resume_idx ON content_generation_runs(status,current_stage,created_at)
    WHERE status IN ('queued','generating');

CREATE TABLE content_candidates (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    run_id uuid NOT NULL REFERENCES content_generation_runs(entity_id) ON DELETE RESTRICT,
    alias text NOT NULL CHECK (alias ~ '^[CSR][0-9]+$'),
    round integer NOT NULL CHECK (round BETWEEN 0 AND 2),
    generation_kind text NOT NULL CHECK (generation_kind IN ('initial','recomposition','element_regeneration','template_rerun')),
    parent_candidate_id uuid REFERENCES content_candidates(entity_id) ON DELETE RESTRICT,
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
    response_sha256 char(64) NOT NULL,
    retry_count integer NOT NULL CHECK (retry_count BETWEEN 0 AND 1),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(run_id,alias),
    CHECK ((recipe_id IS NULL)=(render_id IS NULL))
);
CREATE UNIQUE INDEX content_candidates_initial_template_idx ON content_candidates(run_id,template_id)
    WHERE generation_kind='initial';

CREATE TABLE content_candidate_previews (
    candidate_id uuid PRIMARY KEY REFERENCES content_candidates(entity_id) ON DELETE RESTRICT,
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
    born_in_candidate_id uuid NOT NULL REFERENCES content_candidates(entity_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(run_id,display_alias),
    UNIQUE(born_in_candidate_id,slot,ordinal)
);

CREATE TABLE content_candidate_elements (
    id uuid PRIMARY KEY,
    candidate_id uuid NOT NULL REFERENCES content_candidates(entity_id) ON DELETE RESTRICT,
    element_id uuid NOT NULL REFERENCES content_elements(entity_id) ON DELETE RESTRICT,
    slot text NOT NULL,
    ordinal integer NOT NULL CHECK (ordinal>=0),
    reuse_mode text NOT NULL CHECK (reuse_mode IN ('generated','reuse_exact','adapt_concept','replacement')),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(candidate_id,slot,ordinal),
    UNIQUE(candidate_id,element_id)
);

CREATE TABLE content_critic_passes (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    run_id uuid NOT NULL REFERENCES content_generation_runs(entity_id) ON DELETE RESTRICT,
    pass_number smallint NOT NULL CHECK (pass_number BETWEEN 1 AND 3),
    active_candidate_ids uuid[] NOT NULL CHECK (cardinality(active_candidate_ids) BETWEEN 2 AND 5),
    hard_gates jsonb NOT NULL,
    element_scores jsonb NOT NULL,
    candidate_scores jsonb NOT NULL,
    ranking uuid[] NOT NULL,
    pairwise_results jsonb NOT NULL,
    observations jsonb NOT NULL,
    final_selection jsonb,
    provider_provenance jsonb NOT NULL,
    response_sha256 char(64) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(run_id,pass_number),
    CHECK (cardinality(ranking)=cardinality(active_candidate_ids))
);

CREATE TABLE content_improvement_actions (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    run_id uuid NOT NULL REFERENCES content_generation_runs(entity_id) ON DELETE RESTRICT,
    critic_pass_id uuid NOT NULL REFERENCES content_critic_passes(entity_id) ON DELETE RESTRICT,
    ordinal integer NOT NULL CHECK (ordinal BETWEEN 0 AND 3),
    action_type text NOT NULL CHECK (action_type IN ('recompose','regenerate_elements','rerun_template','discard')),
    base_candidate_id uuid REFERENCES content_candidates(entity_id) ON DELETE RESTRICT,
    locked_element_ids uuid[] NOT NULL DEFAULT '{}',
    target_element_ids uuid[] NOT NULL DEFAULT '{}',
    source_element_ids uuid[] NOT NULL DEFAULT '{}',
    parameter_deltas jsonb,
    command jsonb NOT NULL,
    reserved_candidate_id uuid UNIQUE REFERENCES commander_entities(id) ON DELETE RESTRICT,
    status text NOT NULL CHECK (status IN ('queued','executing','completed','failed','discarded')),
    output_candidate_id uuid UNIQUE REFERENCES content_candidates(entity_id) ON DELETE RESTRICT,
    failure jsonb,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    completed_at timestamptz,
    UNIQUE(critic_pass_id,ordinal),
    CHECK ((status='completed')=(output_candidate_id IS NOT NULL)),
    CHECK ((status='failed')=(failure IS NOT NULL))
);

CREATE TABLE content_results (
    creative_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    run_id uuid NOT NULL UNIQUE REFERENCES content_generation_runs(entity_id) ON DELETE RESTRICT,
    selected_candidate_id uuid NOT NULL REFERENCES content_candidates(entity_id) ON DELETE RESTRICT,
    recipe_id uuid REFERENCES studio_recipes(entity_id) ON DELETE RESTRICT,
    render_id uuid REFERENCES studio_renders(entity_id) ON DELETE RESTRICT,
    final_element_map jsonb NOT NULL,
    decision_summary jsonb NOT NULL,
    result_sha256 char(64) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK ((recipe_id IS NULL)=(render_id IS NULL))
);
ALTER TABLE content_generation_runs ADD COLUMN final_result_id uuid UNIQUE
    REFERENCES content_results(creative_id) ON DELETE RESTRICT;

CREATE TABLE content_generation_outcomes (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    run_id uuid NOT NULL REFERENCES content_generation_runs(entity_id) ON DELETE RESTRICT,
    creative_id uuid NOT NULL REFERENCES content_results(creative_id) ON DELETE RESTRICT,
    event_type text NOT NULL CHECK (event_type IN ('accepted','rejected','downloaded','used','metric_observed')),
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    source_type text NOT NULL CHECK (source_type IN ('owner','system','authorized_analytics_adapter')),
    source_id text,
    observed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE content_generation_skill_proposals (
    id uuid PRIMARY KEY,
    feedback_id uuid NOT NULL REFERENCES commander_human_feedback(entity_id) ON DELETE RESTRICT,
    creative_id uuid NOT NULL REFERENCES content_results(creative_id) ON DELETE RESTRICT,
    target_skill text NOT NULL CHECK (target_skill IN ('content-candidate-generator','content-result-critic')),
    lesson text NOT NULL CHECK (length(lesson) BETWEEN 1 AND 500),
    status text NOT NULL CHECK (status IN ('pending','promoted','rejected')),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(feedback_id,target_skill)
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
        'studio_renders','content_candidates','content_candidate_previews','content_elements',
        'content_candidate_elements','content_critic_passes','content_results',
        'content_generation_outcomes','content_generation_checkpoints'
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
    IF NEW.request_id IS DISTINCT FROM OLD.request_id OR NEW.parent_run_id IS DISTINCT FROM OLD.parent_run_id
       OR NEW.project_id IS DISTINCT FROM OLD.project_id OR NEW.brief_id IS DISTINCT FROM OLD.brief_id
       OR NEW.task_source_id IS DISTINCT FROM OLD.task_source_id OR NEW.brand_kit_id IS DISTINCT FROM OLD.brand_kit_id
       OR NEW.output_profile IS DISTINCT FROM OLD.output_profile OR NEW.task IS DISTINCT FROM OLD.task
       OR NEW.context_bundle IS DISTINCT FROM OLD.context_bundle OR NEW.context_sha256 IS DISTINCT FROM OLD.context_sha256
       OR NEW.initial_candidate_ids IS DISTINCT FROM OLD.initial_candidate_ids
       OR NEW.critic_pass_ids IS DISTINCT FROM OLD.critic_pass_ids
       OR NEW.generator_skill_sha256 IS DISTINCT FROM OLD.generator_skill_sha256
       OR NEW.critic_skill_sha256 IS DISTINCT FROM OLD.critic_skill_sha256
       OR NEW.corpus_sha256 IS DISTINCT FROM OLD.corpus_sha256
       OR NEW.requested_by IS DISTINCT FROM OLD.requested_by OR NEW.deadline_at IS DISTINCT FROM OLD.deadline_at
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'immutable content generation run fields cannot change';
    END IF;
    IF OLD.status IN ('completed','failed') AND NEW IS DISTINCT FROM OLD THEN
        RAISE EXCEPTION 'terminal content generation run is immutable';
    END IF;
    IF OLD.final_result_id IS NOT NULL AND NEW.final_result_id IS DISTINCT FROM OLD.final_result_id THEN
        RAISE EXCEPTION 'content generation final result cannot change';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER content_generation_runs_protected BEFORE UPDATE ON content_generation_runs
FOR EACH ROW EXECUTE FUNCTION ptw_protect_content_run();

CREATE FUNCTION ptw_protect_content_action() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.run_id IS DISTINCT FROM OLD.run_id OR NEW.critic_pass_id IS DISTINCT FROM OLD.critic_pass_id
       OR NEW.ordinal IS DISTINCT FROM OLD.ordinal OR NEW.action_type IS DISTINCT FROM OLD.action_type
       OR NEW.base_candidate_id IS DISTINCT FROM OLD.base_candidate_id
       OR NEW.locked_element_ids IS DISTINCT FROM OLD.locked_element_ids
       OR NEW.target_element_ids IS DISTINCT FROM OLD.target_element_ids
       OR NEW.source_element_ids IS DISTINCT FROM OLD.source_element_ids
       OR NEW.parameter_deltas IS DISTINCT FROM OLD.parameter_deltas
       OR NEW.command IS DISTINCT FROM OLD.command
       OR NEW.reserved_candidate_id IS DISTINCT FROM OLD.reserved_candidate_id
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'immutable content improvement action fields cannot change';
    END IF;
    IF OLD.status IN ('completed','failed','discarded') AND NEW IS DISTINCT FROM OLD THEN
        RAISE EXCEPTION 'terminal content improvement action is immutable';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER content_improvement_actions_protected BEFORE UPDATE ON content_improvement_actions
FOR EACH ROW EXECUTE FUNCTION ptw_protect_content_action();

CREATE FUNCTION ptw_protect_skill_proposal() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.feedback_id IS DISTINCT FROM OLD.feedback_id OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'immutable skill proposal fields cannot change';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER content_generation_skill_proposals_protected BEFORE UPDATE ON content_generation_skill_proposals
FOR EACH ROW EXECUTE FUNCTION ptw_protect_skill_proposal();

COMMIT;
