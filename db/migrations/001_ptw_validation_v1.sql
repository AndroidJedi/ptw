BEGIN;

CREATE TABLE commander_entities (
    id uuid PRIMARY KEY,
    kind text NOT NULL CHECK (kind IN (
        'source','product_brief','creative_batch','ad_creative','artifact',
        'human_feedback','weight_update','task','audit_event','policy_evaluation'
    )),
    attributes jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE commander_relationships (
    id uuid PRIMARY KEY,
    source_id uuid NOT NULL REFERENCES commander_entities(id) ON DELETE RESTRICT,
    relation text NOT NULL CHECK (relation IN (
        'contains','derived_from','supersedes','evaluates','adjusts'
    )),
    target_id uuid NOT NULL REFERENCES commander_entities(id) ON DELETE RESTRICT,
    attributes jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (source_id, relation, target_id)
);
CREATE INDEX commander_relationships_target_idx ON commander_relationships(target_id, relation);

CREATE TABLE commander_sources (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    source_type text NOT NULL CHECK (source_type IN ('owner_idea','stock_photo')),
    title text NOT NULL,
    source_uri text,
    provider text NOT NULL,
    external_id text,
    content text NOT NULL,
    content_sha256 char(64) NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE NULLS NOT DISTINCT (provider, external_id)
);

CREATE TABLE commander_human_feedback (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    target_id uuid NOT NULL REFERENCES commander_entities(id) ON DELETE RESTRICT,
    domain text NOT NULL CHECK (domain IN ('product_brief','ad_creative')),
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
    status text NOT NULL CHECK (status IN (
        'queued','planning','awaiting_approval','executing','completed','failed','cancelled'
    )),
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

CREATE TABLE product_briefs (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    request_id uuid NOT NULL UNIQUE,
    owner_idea_source_id uuid NOT NULL REFERENCES commander_sources(entity_id) ON DELETE RESTRICT,
    base_brief_id uuid REFERENCES product_briefs(entity_id) ON DELETE RESTRICT,
    feedback_id uuid REFERENCES commander_human_feedback(entity_id) ON DELETE RESTRICT,
    status text NOT NULL CHECK (status IN ('queued','generating','completed','failed')),
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
    CHECK ((document IS NULL) = (document_sha256 IS NULL))
);

CREATE TABLE product_brief_approvals (
    id uuid PRIMARY KEY,
    brief_id uuid NOT NULL UNIQUE REFERENCES product_briefs(entity_id) ON DELETE RESTRICT,
    approved_by text NOT NULL,
    approved_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE creative_batches (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    brief_id uuid NOT NULL UNIQUE REFERENCES product_briefs(entity_id) ON DELETE RESTRICT,
    status text NOT NULL CHECK (status IN ('queued','generating','completed','failed')),
    batch_sha256 char(64),
    quality_gates jsonb,
    failure_count integer NOT NULL DEFAULT 0 CHECK (failure_count >= 0),
    error_code text,
    error_message text,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    completed_at timestamptz
);

CREATE TABLE validation_generation_attempts (
    id uuid PRIMARY KEY,
    target_id uuid NOT NULL REFERENCES commander_entities(id) ON DELETE RESTRICT,
    stage text NOT NULL CHECK (stage IN ('product_brief','ad_creative_batch')),
    attempt_number integer NOT NULL CHECK (attempt_number > 0),
    status text NOT NULL CHECK (status IN ('started','completed','failed')),
    error_code text,
    error_message text,
    started_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    completed_at timestamptz,
    UNIQUE(target_id, attempt_number)
);

CREATE TABLE validation_provider_invocations (
    id uuid PRIMARY KEY,
    target_id uuid NOT NULL REFERENCES commander_entities(id) ON DELETE RESTRICT,
    attempt_id uuid NOT NULL REFERENCES validation_generation_attempts(id) ON DELETE RESTRICT,
    provider text NOT NULL,
    mode text NOT NULL CHECK (mode IN ('product_brief','product_brief_revision','ad_creative_batch')),
    idempotency_key text NOT NULL UNIQUE,
    request_sha256 char(64) NOT NULL,
    response_sha256 char(64),
    status text NOT NULL CHECK (status IN ('submitted','completed','failed')),
    invocation jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    completed_at timestamptz
);

CREATE TABLE ad_creatives (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    batch_id uuid NOT NULL REFERENCES creative_batches(entity_id) ON DELETE RESTRICT,
    brief_id uuid NOT NULL REFERENCES product_briefs(entity_id) ON DELETE RESTRICT,
    ordinal integer NOT NULL CHECK (ordinal BETWEEN 0 AND 4),
    angle text NOT NULL CHECK (angle IN ('emotional','practical','curiosity','authority','problem_first')),
    content jsonb NOT NULL,
    content_sha256 char(64) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(batch_id, ordinal),
    UNIQUE(batch_id, angle)
);

CREATE TABLE ad_creative_assets (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    creative_id uuid NOT NULL UNIQUE REFERENCES ad_creatives(entity_id) ON DELETE RESTRICT,
    source_id uuid NOT NULL REFERENCES commander_sources(entity_id) ON DELETE RESTRICT,
    mime_type text NOT NULL CHECK (mime_type = 'image/jpeg'),
    width integer NOT NULL CHECK (width = 1080),
    height integer NOT NULL CHECK (height = 1080),
    bytes bytea NOT NULL,
    bytes_sha256 char(64) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE product_brief_skill_proposals (
    id uuid PRIMARY KEY,
    feedback_id uuid NOT NULL UNIQUE REFERENCES commander_human_feedback(entity_id) ON DELETE RESTRICT,
    brief_id uuid NOT NULL REFERENCES product_briefs(entity_id) ON DELETE RESTRICT,
    lesson text NOT NULL CHECK (length(lesson) BETWEEN 1 AND 500),
    status text NOT NULL CHECK (status IN ('pending','planning','promoted','rejected','failed')),
    command_session_id uuid,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE ad_creative_skill_proposals (
    id uuid PRIMARY KEY,
    feedback_id uuid NOT NULL UNIQUE REFERENCES commander_human_feedback(entity_id) ON DELETE RESTRICT,
    creative_id uuid NOT NULL REFERENCES ad_creatives(entity_id) ON DELETE RESTRICT,
    lesson text NOT NULL CHECK (length(lesson) BETWEEN 1 AND 500),
    status text NOT NULL CHECK (status IN ('pending','planning','promoted','rejected','failed')),
    command_session_id uuid,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

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
        'product_brief_approvals','ad_creatives','ad_creative_assets'
    ]
    LOOP
        EXECUTE format(
            'CREATE TRIGGER %I_immutable BEFORE UPDATE OR DELETE ON %I '
            'FOR EACH ROW EXECUTE FUNCTION ptw_reject_immutable_mutation()',
            table_name, table_name
        );
    END LOOP;
END $$;

CREATE FUNCTION ptw_protect_product_brief() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.request_id IS DISTINCT FROM OLD.request_id
       OR NEW.owner_idea_source_id IS DISTINCT FROM OLD.owner_idea_source_id
       OR NEW.base_brief_id IS DISTINCT FROM OLD.base_brief_id
       OR NEW.feedback_id IS DISTINCT FROM OLD.feedback_id
       OR (NEW.document IS DISTINCT FROM OLD.document AND OLD.document IS NOT NULL)
       OR (NEW.document_sha256 IS DISTINCT FROM OLD.document_sha256 AND OLD.document_sha256 IS NOT NULL)
       OR NEW.requested_by IS DISTINCT FROM OLD.requested_by THEN
        RAISE EXCEPTION 'immutable Product Brief fields cannot change';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER product_briefs_protected BEFORE UPDATE ON product_briefs
FOR EACH ROW EXECUTE FUNCTION ptw_protect_product_brief();

COMMIT;
