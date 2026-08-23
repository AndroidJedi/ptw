BEGIN;

CREATE TABLE commander_entities (
    id uuid PRIMARY KEY,
    kind text NOT NULL CHECK (kind IN (
        'source','positioning_project','marketing_positioning','landing_draft_set',
        'landing_draft','landing','lead_submission','human_feedback','weight_update',
        'task','artifact','audit_event','policy_evaluation'
    )),
    attributes jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE commander_relationships (
    id uuid PRIMARY KEY,
    source_id uuid NOT NULL REFERENCES commander_entities(id) ON DELETE RESTRICT,
    relation text NOT NULL CHECK (relation IN (
        'contains','derived_from','supersedes','evaluates','adjusts','submitted_to'
    )),
    target_id uuid NOT NULL REFERENCES commander_entities(id) ON DELETE RESTRICT,
    attributes jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (source_id, relation, target_id)
);
CREATE INDEX commander_relationships_target_idx ON commander_relationships(target_id, relation);

CREATE TABLE commander_sources (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    source_type text NOT NULL CHECK (source_type IN ('owner_idea','research_finding')),
    title text NOT NULL,
    source_uri text,
    publisher text,
    content text NOT NULL,
    country_code text NOT NULL,
    language_code text NOT NULL,
    provider text NOT NULL,
    external_id text,
    content_sha256 char(64) NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (provider, external_id)
);

CREATE TABLE commander_human_feedback (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    target_id uuid NOT NULL REFERENCES commander_entities(id) ON DELETE RESTRICT,
    domain text NOT NULL CHECK (domain IN ('marketing_positioning','landing')),
    section_id text NOT NULL,
    instruction text NOT NULL CHECK (length(instruction) BETWEEN 1 AND 2000),
    actor text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE commander_weight_updates (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    feedback_id uuid NOT NULL REFERENCES commander_human_feedback(entity_id) ON DELETE RESTRICT,
    component text NOT NULL,
    delta numeric NOT NULL CHECK (delta = 0),
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

CREATE TABLE commander_plan_execute_sessions (
    id uuid PRIMARY KEY,
    mode text NOT NULL CHECK (mode IN ('plan','execute')),
    instruction text NOT NULL,
    plan jsonb,
    plan_digest char(64),
    status text NOT NULL CHECK (status IN ('queued','planning','awaiting_approval','executing','completed','failed','cancelled')),
    approved_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE commander_plan_execute_events (
    id uuid PRIMARY KEY,
    session_id uuid NOT NULL REFERENCES commander_plan_execute_sessions(id) ON DELETE RESTRICT,
    sequence integer NOT NULL,
    event jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (session_id, sequence)
);

CREATE TABLE commander_operation_guard (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    operation_kind text,
    operation_id uuid,
    acquired_at timestamptz,
    CHECK ((operation_kind IS NULL) = (operation_id IS NULL)),
    CHECK ((operation_id IS NULL) = (acquired_at IS NULL))
);
INSERT INTO commander_operation_guard(singleton) VALUES (true);

CREATE TABLE commander_control (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    emergency_stop boolean NOT NULL DEFAULT false,
    updated_by text NOT NULL DEFAULT 'baseline',
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
INSERT INTO commander_control(singleton) VALUES (true);

CREATE TABLE positioning_projects (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    request_id uuid NOT NULL UNIQUE,
    owner_idea_source_id uuid NOT NULL REFERENCES commander_sources(entity_id) ON DELETE RESTRICT,
    idea_sha256 char(64) NOT NULL,
    target_country text NOT NULL CHECK (target_country ~ '^[A-Z]{2}$'),
    research_language text NOT NULL CHECK (research_language ~ '^[a-z]{2}$'),
    output_language text NOT NULL CHECK (output_language IN ('uk','en')),
    requested_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE positioning_revisions (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    project_id uuid NOT NULL REFERENCES positioning_projects(entity_id) ON DELETE RESTRICT,
    request_id uuid NOT NULL UNIQUE,
    revision_number integer NOT NULL CHECK (revision_number > 0),
    base_revision_id uuid REFERENCES positioning_revisions(entity_id) ON DELETE RESTRICT,
    feedback_id uuid REFERENCES commander_human_feedback(entity_id) ON DELETE RESTRICT,
    status text NOT NULL CHECK (status IN ('queued','researching','synthesizing','completed','failed')),
    document jsonb,
    document_sha256 char(64),
    quality_gates jsonb,
    failure_count integer NOT NULL DEFAULT 0 CHECK (failure_count >= 0),
    error_code text,
    error_message text,
    requested_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    completed_at timestamptz,
    UNIQUE(project_id, revision_number),
    CHECK ((document IS NULL) = (document_sha256 IS NULL))
);

CREATE TABLE positioning_generation_attempts (
    id uuid PRIMARY KEY,
    revision_id uuid NOT NULL REFERENCES positioning_revisions(entity_id) ON DELETE RESTRICT,
    attempt_number integer NOT NULL CHECK (attempt_number > 0),
    status text NOT NULL CHECK (status IN ('started','completed','failed')),
    error_code text,
    error_message text,
    started_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    completed_at timestamptz,
    UNIQUE(revision_id, attempt_number)
);

CREATE TABLE positioning_provider_invocations (
    id uuid PRIMARY KEY,
    revision_id uuid NOT NULL REFERENCES positioning_revisions(entity_id) ON DELETE RESTRICT,
    attempt_id uuid NOT NULL REFERENCES positioning_generation_attempts(id) ON DELETE RESTRICT,
    provider text NOT NULL,
    mode text NOT NULL CHECK (mode IN (
        'marketing_positioning_research_plan','marketing_positioning_document','marketing_positioning_revision','dataforseo_serp'
    )),
    idempotency_key text NOT NULL UNIQUE,
    remote_task_id text,
    request_sha256 char(64) NOT NULL,
    response_sha256 char(64),
    status text NOT NULL CHECK (status IN ('submitted','completed','failed')),
    invocation jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    completed_at timestamptz
);

CREATE TABLE positioning_provider_costs (
    id uuid PRIMARY KEY,
    invocation_id uuid NOT NULL UNIQUE REFERENCES positioning_provider_invocations(id) ON DELETE RESTRICT,
    amount_usd numeric(12,6) NOT NULL CHECK (amount_usd >= 0 AND amount_usd <= 0.05),
    provider_record jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE positioning_notification_attempts (
    id uuid PRIMARY KEY,
    revision_id uuid NOT NULL REFERENCES positioning_revisions(entity_id) ON DELETE RESTRICT,
    generation_attempt_id uuid NOT NULL UNIQUE REFERENCES positioning_generation_attempts(id) ON DELETE RESTRICT,
    terminal_status text NOT NULL CHECK (terminal_status IN ('completed','failed')),
    status text NOT NULL CHECK (status IN ('sent','failed','ambiguous','suppressed')),
    telegram_chat_id bigint NOT NULL,
    telegram_message_id bigint,
    error_code text,
    error_message text,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    completed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK (telegram_message_id IS NULL OR status = 'sent')
);

CREATE TABLE positioning_revision_sources (
    revision_id uuid NOT NULL REFERENCES positioning_revisions(entity_id) ON DELETE RESTRICT,
    source_id uuid NOT NULL REFERENCES commander_sources(entity_id) ON DELETE RESTRICT,
    citation_order integer NOT NULL CHECK (citation_order >= 0),
    PRIMARY KEY (revision_id, source_id),
    UNIQUE (revision_id, citation_order)
);

CREATE TABLE positioning_approvals (
    id uuid PRIMARY KEY,
    revision_id uuid NOT NULL REFERENCES positioning_revisions(entity_id) ON DELETE RESTRICT,
    project_id uuid NOT NULL REFERENCES positioning_projects(entity_id) ON DELETE RESTRICT,
    approved_by text NOT NULL,
    approved_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    revoked_at timestamptz
);
CREATE UNIQUE INDEX positioning_one_active_approval_idx ON positioning_approvals(project_id) WHERE revoked_at IS NULL;

CREATE TABLE positioning_skill_proposals (
    id uuid PRIMARY KEY,
    feedback_id uuid NOT NULL UNIQUE REFERENCES commander_human_feedback(entity_id) ON DELETE RESTRICT,
    revision_id uuid NOT NULL REFERENCES positioning_revisions(entity_id) ON DELETE RESTRICT,
    lesson text NOT NULL CHECK (length(lesson) BETWEEN 1 AND 500),
    status text NOT NULL CHECK (status IN ('pending','planning','promoted','rejected','failed')),
    command_session_id uuid,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE landing_draft_sets (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    request_id uuid NOT NULL UNIQUE,
    positioning_project_id uuid NOT NULL REFERENCES positioning_projects(entity_id) ON DELETE RESTRICT,
    positioning_revision_id uuid NOT NULL REFERENCES positioning_revisions(entity_id) ON DELETE RESTRICT,
    privacy_policy_url text NOT NULL CHECK (privacy_policy_url ~ '^https://'),
    source_brief jsonb NOT NULL,
    status text NOT NULL CHECK (status IN ('queued','populating','completed','failed')),
    population_summary text,
    population_invocation jsonb,
    error_code text,
    error_message text,
    requested_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    completed_at timestamptz
);

CREATE TABLE landing_draft_snapshots (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    draft_set_id uuid NOT NULL REFERENCES landing_draft_sets(entity_id) ON DELETE RESTRICT,
    template_id text NOT NULL CHECK (template_id IN ('product','community','waitlist')),
    snapshot_number integer NOT NULL CHECK (snapshot_number > 0),
    parent_snapshot_id uuid REFERENCES landing_draft_snapshots(entity_id) ON DELETE RESTRICT,
    source_feedback_id uuid REFERENCES commander_human_feedback(entity_id) ON DELETE RESTRICT,
    page_content jsonb NOT NULL,
    page_content_sha256 char(64) NOT NULL,
    preview_html text NOT NULL,
    summary text NOT NULL,
    invocation jsonb NOT NULL,
    is_current boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(draft_set_id, template_id, snapshot_number)
);
CREATE UNIQUE INDEX landing_one_current_snapshot_idx ON landing_draft_snapshots(draft_set_id, template_id) WHERE is_current;

CREATE TABLE landing_draft_edits (
    request_id uuid PRIMARY KEY,
    draft_set_id uuid NOT NULL REFERENCES landing_draft_sets(entity_id) ON DELETE RESTRICT,
    template_id text NOT NULL CHECK (template_id IN ('product','community','waitlist')),
    base_snapshot_id uuid NOT NULL REFERENCES landing_draft_snapshots(entity_id) ON DELETE RESTRICT,
    block_id text NOT NULL CHECK (block_id IN ('hero','problem','features','steps','proof','faq','final_cta','lead_form')),
    instruction text NOT NULL CHECK (length(instruction) BETWEEN 1 AND 2000),
    feedback_id uuid NOT NULL REFERENCES commander_human_feedback(entity_id) ON DELETE RESTRICT,
    proposal_id uuid,
    result_snapshot_id uuid REFERENCES landing_draft_snapshots(entity_id) ON DELETE RESTRICT,
    status text NOT NULL CHECK (status IN ('queued','editing','completed','failed')),
    error_code text,
    error_message text,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    completed_at timestamptz
);

CREATE TABLE landing_skill_proposals (
    id uuid PRIMARY KEY,
    feedback_id uuid NOT NULL UNIQUE REFERENCES commander_human_feedback(entity_id) ON DELETE RESTRICT,
    lesson text NOT NULL CHECK (length(lesson) BETWEEN 1 AND 500),
    status text NOT NULL CHECK (status IN ('pending_generation','pending','planning','promoted','rejected','failed')),
    command_session_id uuid,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
ALTER TABLE landing_draft_edits ADD CONSTRAINT landing_draft_edits_proposal_fk
    FOREIGN KEY (proposal_id) REFERENCES landing_skill_proposals(id) ON DELETE RESTRICT;

CREATE TABLE landing_builds (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    request_id uuid NOT NULL UNIQUE,
    positioning_project_id uuid NOT NULL REFERENCES positioning_projects(entity_id) ON DELETE RESTRICT,
    positioning_revision_id uuid NOT NULL REFERENCES positioning_revisions(entity_id) ON DELETE RESTRICT,
    source_snapshot_id uuid NOT NULL REFERENCES landing_draft_snapshots(entity_id) ON DELETE RESTRICT,
    template_id text NOT NULL CHECK (template_id IN ('product','community','waitlist')),
    page_content jsonb NOT NULL,
    page_content_sha256 char(64) NOT NULL,
    output_path text NOT NULL,
    build_manifest jsonb,
    artifact_sha256 char(64),
    firebase_site_id text NOT NULL,
    firebase_version text,
    public_url text,
    status text NOT NULL CHECK (status IN ('queued','building','publishing','published','failed')),
    error_code text,
    error_message text,
    requested_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    completed_at timestamptz
);

CREATE TABLE landing_publications (
    id uuid PRIMARY KEY,
    build_id uuid NOT NULL UNIQUE REFERENCES landing_builds(entity_id) ON DELETE RESTRICT,
    positioning_revision_id uuid NOT NULL REFERENCES positioning_revisions(entity_id) ON DELETE RESTRICT,
    snapshot_id uuid NOT NULL REFERENCES landing_draft_snapshots(entity_id) ON DELETE RESTRICT,
    firebase_version text NOT NULL,
    public_url text NOT NULL,
    published_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE landing_leads (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    build_id uuid NOT NULL REFERENCES landing_builds(entity_id) ON DELETE RESTRICT,
    form_id text NOT NULL CHECK (form_id IN ('waitlist','contact_request','community_interest')),
    fields jsonb NOT NULL,
    dedupe_sha256 char(64) NOT NULL,
    ip_hmac char(64) NOT NULL,
    submitted_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(build_id, dedupe_sha256)
);
CREATE INDEX landing_leads_rate_idx ON landing_leads(ip_hmac, submitted_at);

CREATE TABLE landing_lead_notification_attempts (
    id uuid PRIMARY KEY,
    lead_id uuid NOT NULL REFERENCES landing_leads(entity_id) ON DELETE RESTRICT,
    attempt_number integer NOT NULL CHECK (attempt_number > 0),
    status text NOT NULL CHECK (status IN ('sent','failed','ambiguous','suppressed')),
    telegram_chat_id bigint NOT NULL,
    telegram_message_id bigint,
    error_code text,
    error_message text,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    completed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(lead_id, attempt_number)
);

-- Source, lineage, feedback, costs, publications, leads, and notification
-- attempt rows are append-only. The reset drops the schema; runtime code has no
-- mutation path for these permanent records.
CREATE FUNCTION ptw_reject_immutable_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION '% is append-only', TG_TABLE_NAME;
END $$;

DO $$
DECLARE table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'commander_entities','commander_relationships','commander_sources',
        'commander_human_feedback','commander_weight_updates','commander_audit_events',
        'positioning_provider_costs','positioning_notification_attempts',
        'landing_publications','landing_leads',
        'landing_lead_notification_attempts'
    ]
    LOOP
        EXECUTE format(
            'CREATE TRIGGER %I_immutable BEFORE UPDATE OR DELETE ON %I '
            'FOR EACH ROW EXECUTE FUNCTION ptw_reject_immutable_mutation()',
            table_name, table_name
        );
    END LOOP;
END $$;

CREATE FUNCTION ptw_protect_positioning_document() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.document IS NOT NULL AND (
        NEW.document IS DISTINCT FROM OLD.document
        OR NEW.document_sha256 IS DISTINCT FROM OLD.document_sha256
        OR NEW.quality_gates IS DISTINCT FROM OLD.quality_gates
    ) THEN
        RAISE EXCEPTION 'completed positioning document payload is immutable';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER positioning_document_immutable
    BEFORE UPDATE ON positioning_revisions
    FOR EACH ROW EXECUTE FUNCTION ptw_protect_positioning_document();

CREATE FUNCTION ptw_protect_positioning_project_input() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.request_id IS DISTINCT FROM OLD.request_id
       OR NEW.owner_idea_source_id IS DISTINCT FROM OLD.owner_idea_source_id
       OR NEW.idea_sha256 IS DISTINCT FROM OLD.idea_sha256
       OR NEW.target_country IS DISTINCT FROM OLD.target_country
       OR NEW.research_language IS DISTINCT FROM OLD.research_language
       OR NEW.output_language IS DISTINCT FROM OLD.output_language
       OR NEW.requested_by IS DISTINCT FROM OLD.requested_by THEN
        RAISE EXCEPTION 'Positioning project input is immutable';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER positioning_project_input_immutable
    BEFORE UPDATE ON positioning_projects
    FOR EACH ROW EXECUTE FUNCTION ptw_protect_positioning_project_input();

CREATE FUNCTION ptw_protect_provider_invocation_input() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.revision_id IS DISTINCT FROM OLD.revision_id
       OR NEW.attempt_id IS DISTINCT FROM OLD.attempt_id
       OR NEW.provider IS DISTINCT FROM OLD.provider
       OR NEW.mode IS DISTINCT FROM OLD.mode
       OR NEW.idempotency_key IS DISTINCT FROM OLD.idempotency_key
       OR NEW.request_sha256 IS DISTINCT FROM OLD.request_sha256
       OR (OLD.remote_task_id IS NOT NULL AND NEW.remote_task_id IS DISTINCT FROM OLD.remote_task_id)
       OR (OLD.status = 'completed' AND (
           NEW.response_sha256 IS DISTINCT FROM OLD.response_sha256
           OR NEW.invocation IS DISTINCT FROM OLD.invocation
       )) THEN
        RAISE EXCEPTION 'provider invocation input or completed result is immutable';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER positioning_provider_invocation_input_immutable
    BEFORE UPDATE ON positioning_provider_invocations
    FOR EACH ROW EXECUTE FUNCTION ptw_protect_provider_invocation_input();

CREATE FUNCTION ptw_protect_landing_draft_input() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.request_id IS DISTINCT FROM OLD.request_id
       OR NEW.positioning_project_id IS DISTINCT FROM OLD.positioning_project_id
       OR NEW.positioning_revision_id IS DISTINCT FROM OLD.positioning_revision_id
       OR NEW.privacy_policy_url IS DISTINCT FROM OLD.privacy_policy_url
       OR NEW.source_brief IS DISTINCT FROM OLD.source_brief
       OR NEW.requested_by IS DISTINCT FROM OLD.requested_by
       OR (OLD.population_invocation IS NOT NULL AND (
           NEW.population_invocation IS DISTINCT FROM OLD.population_invocation
           OR NEW.population_summary IS DISTINCT FROM OLD.population_summary
       )) THEN
        RAISE EXCEPTION 'Landing draft input or completed population is immutable';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER landing_draft_input_immutable
    BEFORE UPDATE ON landing_draft_sets
    FOR EACH ROW EXECUTE FUNCTION ptw_protect_landing_draft_input();

CREATE FUNCTION ptw_protect_landing_edit_input() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.draft_set_id IS DISTINCT FROM OLD.draft_set_id
       OR NEW.template_id IS DISTINCT FROM OLD.template_id
       OR NEW.base_snapshot_id IS DISTINCT FROM OLD.base_snapshot_id
       OR NEW.block_id IS DISTINCT FROM OLD.block_id
       OR NEW.instruction IS DISTINCT FROM OLD.instruction
       OR NEW.feedback_id IS DISTINCT FROM OLD.feedback_id
       OR NEW.proposal_id IS DISTINCT FROM OLD.proposal_id
       OR (OLD.result_snapshot_id IS NOT NULL AND NEW.result_snapshot_id IS DISTINCT FROM OLD.result_snapshot_id) THEN
        RAISE EXCEPTION 'Landing edit input or result is immutable';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER landing_edit_input_immutable
    BEFORE UPDATE ON landing_draft_edits
    FOR EACH ROW EXECUTE FUNCTION ptw_protect_landing_edit_input();

CREATE FUNCTION ptw_protect_landing_snapshot() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.draft_set_id IS DISTINCT FROM OLD.draft_set_id
       OR NEW.template_id IS DISTINCT FROM OLD.template_id
       OR NEW.snapshot_number IS DISTINCT FROM OLD.snapshot_number
       OR NEW.parent_snapshot_id IS DISTINCT FROM OLD.parent_snapshot_id
       OR NEW.source_feedback_id IS DISTINCT FROM OLD.source_feedback_id
       OR NEW.page_content IS DISTINCT FROM OLD.page_content
       OR NEW.page_content_sha256 IS DISTINCT FROM OLD.page_content_sha256
       OR NEW.preview_html IS DISTINCT FROM OLD.preview_html
       OR NEW.summary IS DISTINCT FROM OLD.summary
       OR NEW.invocation IS DISTINCT FROM OLD.invocation THEN
        RAISE EXCEPTION 'Landing snapshot payload is immutable';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER landing_snapshot_payload_immutable
    BEFORE UPDATE ON landing_draft_snapshots
    FOR EACH ROW EXECUTE FUNCTION ptw_protect_landing_snapshot();

CREATE FUNCTION ptw_protect_landing_build_input() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.request_id IS DISTINCT FROM OLD.request_id
       OR NEW.positioning_project_id IS DISTINCT FROM OLD.positioning_project_id
       OR NEW.positioning_revision_id IS DISTINCT FROM OLD.positioning_revision_id
       OR NEW.source_snapshot_id IS DISTINCT FROM OLD.source_snapshot_id
       OR NEW.template_id IS DISTINCT FROM OLD.template_id
       OR NEW.page_content IS DISTINCT FROM OLD.page_content
       OR NEW.page_content_sha256 IS DISTINCT FROM OLD.page_content_sha256
       OR NEW.output_path IS DISTINCT FROM OLD.output_path
       OR NEW.firebase_site_id IS DISTINCT FROM OLD.firebase_site_id
       OR (OLD.build_manifest IS NOT NULL AND NEW.build_manifest IS DISTINCT FROM OLD.build_manifest)
       OR (OLD.artifact_sha256 IS NOT NULL AND NEW.artifact_sha256 IS DISTINCT FROM OLD.artifact_sha256) THEN
        RAISE EXCEPTION 'Landing build input or artifact is immutable';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER landing_build_input_immutable
    BEFORE UPDATE ON landing_builds
    FOR EACH ROW EXECUTE FUNCTION ptw_protect_landing_build_input();

COMMIT;
