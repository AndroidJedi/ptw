BEGIN;

CREATE TABLE commander_entities (
    id uuid PRIMARY KEY,
    kind text NOT NULL CHECK (kind IN (
        'source','validation_project','product_brief','human_feedback','weight_update',
        'studio_workspace','studio_asset','studio_version','studio_generation_run',
        'studio_edit_checkpoint','studio_learning_run','studio_skill_snapshot',
        'studio_learning_proposal','studio_learning_decision'
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
    UNIQUE(source_id,relation,target_id)
);
CREATE INDEX commander_relationships_target_idx
    ON commander_relationships(target_id,relation);

CREATE TABLE commander_sources (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    source_type text NOT NULL CHECK (source_type='owner_idea'),
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
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE commander_human_feedback (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    target_id uuid NOT NULL REFERENCES commander_entities(id) ON DELETE RESTRICT,
    domain text NOT NULL CHECK (domain='product_brief'),
    section_id text NOT NULL CHECK (section_id='product_brief'),
    instruction text NOT NULL CHECK (length(instruction) BETWEEN 1 AND 2000),
    actor text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE commander_weight_updates (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    feedback_id uuid NOT NULL REFERENCES commander_human_feedback(entity_id) ON DELETE RESTRICT,
    component text NOT NULL CHECK (component='product_brief'),
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
    operation_kind text CHECK (operation_kind IS NULL OR operation_kind='product_brief'),
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
    FOREIGN KEY(base_brief_id,project_id)
    REFERENCES product_briefs(entity_id,project_id) ON DELETE RESTRICT;
CREATE UNIQUE INDEX product_briefs_one_root_per_project_idx
    ON product_briefs(project_id) WHERE base_brief_id IS NULL;
CREATE INDEX product_briefs_project_created_idx
    ON product_briefs(project_id,created_at DESC);

CREATE TABLE product_brief_approvals (
    id uuid PRIMARY KEY,
    brief_id uuid NOT NULL UNIQUE REFERENCES product_briefs(entity_id) ON DELETE RESTRICT,
    approved_by text NOT NULL,
    approved_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE validation_generation_attempts (
    id uuid PRIMARY KEY,
    target_id uuid NOT NULL REFERENCES commander_entities(id) ON DELETE RESTRICT,
    stage text NOT NULL CHECK (stage='product_brief'),
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
        'product_brief','product_brief_revision','studio_creative_generation',
        'studio_edit_learning'
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

CREATE TABLE universal_studio_workspaces (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    project_id uuid NOT NULL REFERENCES validation_projects(entity_id) ON DELETE RESTRICT,
    source_brief_id uuid NOT NULL REFERENCES product_briefs(entity_id) ON DELETE RESTRICT,
    ordinal integer NOT NULL CHECK (ordinal > 0),
    origin text NOT NULL CHECK (origin IN ('brief_generation','approved_variant')),
    template_id text NOT NULL CHECK (template_id IN ('universal_ad','phone_metrics')),
    template_version integer,
    template_sha256 char(64),
    status text NOT NULL CHECK (status IN ('queued','composing','generating_image','draft','failed')),
    state_sha256 char(64),
    generation jsonb NOT NULL DEFAULT '{}'::jsonb,
    learning_baseline jsonb,
    learning_baseline_sha256 char(64),
    latest_checkpoint_id uuid,
    requested_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(source_brief_id,ordinal),
    UNIQUE(entity_id,project_id),
    CHECK ((learning_baseline IS NULL)=(learning_baseline_sha256 IS NULL))
);
ALTER TABLE universal_studio_workspaces ADD CONSTRAINT studio_workspace_brief_same_project_fkey
    FOREIGN KEY(source_brief_id,project_id)
    REFERENCES product_briefs(entity_id,project_id) ON DELETE RESTRICT;
CREATE INDEX universal_studio_workspaces_project_created_idx
    ON universal_studio_workspaces(project_id,created_at DESC);

CREATE TABLE universal_studio_workspace_files (
    workspace_id uuid NOT NULL REFERENCES universal_studio_workspaces(entity_id) ON DELETE RESTRICT,
    relative_path text NOT NULL CHECK (
        length(relative_path) BETWEEN 1 AND 240
        AND relative_path !~ '(^/|(^|/)\.\.(/|$))'
    ),
    content_sha256 char(64) NOT NULL,
    content bytea NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY(workspace_id,relative_path)
);

CREATE TABLE universal_studio_assets (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    workspace_id uuid NOT NULL REFERENCES universal_studio_workspaces(entity_id) ON DELETE RESTRICT,
    slot text NOT NULL,
    content_sha256 char(64) NOT NULL,
    mime_type text NOT NULL CHECK (mime_type IN ('image/png','image/jpeg','image/webp')),
    width integer NOT NULL CHECK (width BETWEEN 1 AND 8192),
    height integer NOT NULL CHECK (height BETWEEN 1 AND 8192),
    content bytea NOT NULL,
    source jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(workspace_id,content_sha256)
);

CREATE TABLE universal_studio_versions (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    workspace_id uuid NOT NULL REFERENCES universal_studio_workspaces(entity_id) ON DELETE RESTRICT,
    version integer NOT NULL CHECK (version > 0),
    version_sha256 char(64) NOT NULL,
    state_sha256 char(64) NOT NULL,
    render_sha256 char(64) NOT NULL,
    record jsonb NOT NULL,
    render_png bytea NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(workspace_id,version),
    UNIQUE(workspace_id,version_sha256)
);

CREATE TABLE studio_generation_runs (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    workspace_id uuid NOT NULL REFERENCES universal_studio_workspaces(entity_id) ON DELETE RESTRICT,
    attempt integer NOT NULL CHECK (attempt > 0),
    stage text NOT NULL CHECK (stage IN ('composition','phone_image')),
    status text NOT NULL CHECK (status IN ('completed','failed')),
    provenance jsonb NOT NULL DEFAULT '{}'::jsonb,
    error_type text,
    error_message text,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(workspace_id,attempt)
);

CREATE TABLE studio_edit_checkpoints (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    workspace_id uuid NOT NULL,
    project_id uuid NOT NULL REFERENCES validation_projects(entity_id) ON DELETE RESTRICT,
    checkpoint_kind text NOT NULL CHECK (checkpoint_kind IN ('save','approve')),
    before_state_sha256 char(64) NOT NULL,
    after_state_sha256 char(64) NOT NULL,
    changed_paths jsonb NOT NULL,
    before_snapshot jsonb NOT NULL,
    after_snapshot jsonb NOT NULL,
    version integer,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(entity_id,workspace_id),
    UNIQUE(workspace_id,before_state_sha256,after_state_sha256,checkpoint_kind),
    FOREIGN KEY(workspace_id,project_id)
        REFERENCES universal_studio_workspaces(entity_id,project_id) ON DELETE RESTRICT
);

ALTER TABLE universal_studio_workspaces ADD CONSTRAINT studio_workspace_latest_checkpoint_fkey
    FOREIGN KEY(latest_checkpoint_id,entity_id)
    REFERENCES studio_edit_checkpoints(entity_id,workspace_id) ON DELETE RESTRICT;

CREATE TABLE studio_skill_snapshots (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    scope text NOT NULL CHECK (scope IN ('global','project')),
    project_id uuid REFERENCES validation_projects(entity_id) ON DELETE RESTRICT,
    version integer NOT NULL CHECK (version > 0),
    content text NOT NULL,
    content_sha256 char(64) NOT NULL,
    source_checkpoint_id uuid REFERENCES studio_edit_checkpoints(entity_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK ((scope='global' AND project_id IS NULL) OR (scope='project' AND project_id IS NOT NULL))
);
CREATE UNIQUE INDEX studio_global_skill_version_idx
    ON studio_skill_snapshots(version) WHERE scope='global';
CREATE UNIQUE INDEX studio_project_skill_version_idx
    ON studio_skill_snapshots(project_id,version) WHERE scope='project';
CREATE UNIQUE INDEX studio_global_skill_checkpoint_idx
    ON studio_skill_snapshots(source_checkpoint_id)
    WHERE scope='global' AND source_checkpoint_id IS NOT NULL;
CREATE UNIQUE INDEX studio_project_skill_checkpoint_idx
    ON studio_skill_snapshots(project_id,source_checkpoint_id)
    WHERE scope='project' AND source_checkpoint_id IS NOT NULL;

CREATE TABLE studio_learning_runs (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    checkpoint_id uuid NOT NULL REFERENCES studio_edit_checkpoints(entity_id) ON DELETE RESTRICT,
    attempt integer NOT NULL CHECK (attempt > 0),
    status text NOT NULL CHECK (status IN ('completed','failed')),
    edit_summary text,
    project_lesson text,
    project_skill_snapshot_id uuid REFERENCES studio_skill_snapshots(entity_id) ON DELETE RESTRICT,
    provider jsonb NOT NULL DEFAULT '{}'::jsonb,
    error_type text,
    error_message text,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(checkpoint_id,attempt)
);
CREATE UNIQUE INDEX studio_learning_runs_completed_idx
    ON studio_learning_runs(checkpoint_id) WHERE status='completed';

CREATE TABLE studio_learning_proposals (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    checkpoint_id uuid NOT NULL UNIQUE REFERENCES studio_edit_checkpoints(entity_id) ON DELETE RESTRICT,
    project_skill_snapshot_id uuid NOT NULL REFERENCES studio_skill_snapshots(entity_id) ON DELETE RESTRICT,
    global_rule text NOT NULL,
    global_rule_sha256 char(64) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE studio_learning_decisions (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    proposal_id uuid NOT NULL UNIQUE REFERENCES studio_learning_proposals(entity_id) ON DELETE RESTRICT,
    decision text NOT NULL CHECK (decision IN ('global','project_only')),
    global_skill_snapshot_id uuid REFERENCES studio_skill_snapshots(entity_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK ((decision='global')=(global_skill_snapshot_id IS NOT NULL))
);

CREATE FUNCTION ptw_reject_immutable_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION '% is append-only',TG_TABLE_NAME; END $$;

DO $$
DECLARE table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'commander_entities','commander_relationships','commander_sources',
        'commander_human_feedback','commander_weight_updates','commander_audit_events',
        'product_brief_approvals','universal_studio_assets','universal_studio_versions',
        'studio_generation_runs','studio_edit_checkpoints','studio_learning_runs',
        'studio_skill_snapshots','studio_learning_proposals','studio_learning_decisions'
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

CREATE FUNCTION ptw_protect_studio_workspace() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.entity_id IS DISTINCT FROM OLD.entity_id
       OR NEW.project_id IS DISTINCT FROM OLD.project_id
       OR NEW.source_brief_id IS DISTINCT FROM OLD.source_brief_id
       OR NEW.ordinal IS DISTINCT FROM OLD.ordinal
       OR NEW.origin IS DISTINCT FROM OLD.origin
       OR NEW.requested_by IS DISTINCT FROM OLD.requested_by
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'immutable Studio creative fields cannot change';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER universal_studio_workspaces_protected BEFORE UPDATE ON universal_studio_workspaces
FOR EACH ROW EXECUTE FUNCTION ptw_protect_studio_workspace();

COMMIT;
