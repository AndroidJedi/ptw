BEGIN;

ALTER TABLE commander_entities DROP CONSTRAINT commander_entities_kind_check;
ALTER TABLE commander_entities ADD CONSTRAINT commander_entities_kind_check CHECK (kind IN (
    'source','validation_project','product_brief','human_feedback','weight_update',
    'studio_workspace','studio_asset','studio_version','studio_generation_run',
    'studio_edit_checkpoint','studio_learning_run','studio_skill_snapshot',
    'studio_learning_proposal','studio_learning_decision',
    'landing_workspace','landing_asset','landing_version','landing_generation_run',
    'landing_edit_checkpoint','landing_learning_run','landing_skill_snapshot',
    'landing_learning_proposal','landing_learning_decision'
));

CREATE TABLE landing_workspaces (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    project_id uuid NOT NULL REFERENCES validation_projects(entity_id) ON DELETE RESTRICT,
    source_brief_id uuid NOT NULL REFERENCES product_briefs(entity_id) ON DELETE RESTRICT,
    source_creative_id uuid NOT NULL REFERENCES universal_studio_workspaces(entity_id) ON DELETE RESTRICT,
    source_version integer NOT NULL CHECK (source_version > 0),
    source_version_sha256 char(64) NOT NULL,
    source_post_snapshot jsonb NOT NULL,
    ordinal integer NOT NULL CHECK (ordinal > 0),
    origin text NOT NULL CHECK (origin IN ('post_generation','approved_variant')),
    status text NOT NULL CHECK (status IN ('queued','composing','generating_images','draft','failed')),
    state_sha256 char(64),
    generation jsonb NOT NULL DEFAULT '{}'::jsonb,
    learning_baseline jsonb,
    learning_baseline_sha256 char(64),
    requested_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(source_creative_id,source_version,ordinal),
    UNIQUE(entity_id,project_id),
    CHECK ((learning_baseline IS NULL)=(learning_baseline_sha256 IS NULL))
);
ALTER TABLE landing_workspaces ADD CONSTRAINT landing_workspace_brief_same_project_fkey
    FOREIGN KEY(source_brief_id,project_id) REFERENCES product_briefs(entity_id,project_id) ON DELETE RESTRICT;
ALTER TABLE landing_workspaces ADD CONSTRAINT landing_workspace_creative_same_project_fkey
    FOREIGN KEY(source_creative_id,project_id) REFERENCES universal_studio_workspaces(entity_id,project_id) ON DELETE RESTRICT;
CREATE INDEX landing_workspaces_project_created_idx ON landing_workspaces(project_id,created_at DESC);

CREATE TABLE landing_workspace_files (
    landing_id uuid NOT NULL REFERENCES landing_workspaces(entity_id) ON DELETE RESTRICT,
    relative_path text NOT NULL CHECK (length(relative_path) BETWEEN 1 AND 240 AND relative_path !~ '(^/|(^|/)\.\.(/|$))'),
    content_sha256 char(64) NOT NULL,
    content bytea NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY(landing_id,relative_path)
);

CREATE TABLE landing_assets (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    landing_id uuid NOT NULL REFERENCES landing_workspaces(entity_id) ON DELETE RESTRICT,
    slot text NOT NULL CHECK (slot IN ('hero_visual','visual_break_visual')),
    content_sha256 char(64) NOT NULL,
    mime_type text NOT NULL CHECK (mime_type='image/png'),
    content bytea NOT NULL,
    source jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(landing_id,content_sha256)
);

CREATE TABLE landing_generation_runs (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    landing_id uuid NOT NULL REFERENCES landing_workspaces(entity_id) ON DELETE RESTRICT,
    stage text NOT NULL CHECK (stage IN ('composition','hero_visual','visual_break_visual')),
    status text NOT NULL CHECK (status IN ('completed','failed')),
    input_sha256 char(64) NOT NULL,
    output_sha256 char(64),
    prompt_version text NOT NULL,
    invocation jsonb NOT NULL DEFAULT '{}'::jsonb,
    error_type text,
    error_message text,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK ((status='completed' AND output_sha256 IS NOT NULL AND error_type IS NULL AND error_message IS NULL)
        OR (status='failed' AND output_sha256 IS NULL AND error_type IS NOT NULL))
);
CREATE INDEX landing_generation_runs_landing_created_idx ON landing_generation_runs(landing_id,created_at DESC);

CREATE TABLE landing_versions (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    landing_id uuid NOT NULL REFERENCES landing_workspaces(entity_id) ON DELETE RESTRICT,
    version integer NOT NULL CHECK (version > 0),
    version_sha256 char(64) NOT NULL,
    state_sha256 char(64) NOT NULL,
    record jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(landing_id,version),
    UNIQUE(landing_id,version_sha256)
);

CREATE TABLE landing_checkpoints (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    landing_id uuid NOT NULL,
    project_id uuid NOT NULL REFERENCES validation_projects(entity_id) ON DELETE RESTRICT,
    checkpoint_kind text NOT NULL CHECK (checkpoint_kind IN ('save','approve')),
    before_state_sha256 char(64) NOT NULL,
    after_state_sha256 char(64) NOT NULL,
    changed_paths jsonb NOT NULL,
    before_snapshot jsonb NOT NULL,
    after_snapshot jsonb NOT NULL,
    version integer,
    status text NOT NULL CHECK (status IN ('learning','completed','failed')),
    edit_summary text,
    project_skill_snapshot_id uuid,
    error_type text,
    error_message text,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(entity_id,landing_id),
    UNIQUE(landing_id,before_state_sha256,after_state_sha256,checkpoint_kind),
    FOREIGN KEY(landing_id,project_id) REFERENCES landing_workspaces(entity_id,project_id) ON DELETE RESTRICT
);

CREATE TABLE landing_skill_snapshots (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    scope text NOT NULL CHECK (scope IN ('global','project')),
    project_id uuid REFERENCES validation_projects(entity_id) ON DELETE RESTRICT,
    version integer NOT NULL CHECK (version > 0),
    content text NOT NULL,
    content_sha256 char(64) NOT NULL,
    source_checkpoint_id uuid REFERENCES landing_checkpoints(entity_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK ((scope='global' AND project_id IS NULL) OR (scope='project' AND project_id IS NOT NULL)),
    UNIQUE(scope,project_id,version)
);

CREATE TABLE landing_learning_proposals (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    checkpoint_id uuid NOT NULL REFERENCES landing_checkpoints(entity_id) ON DELETE RESTRICT,
    project_skill_snapshot_id uuid NOT NULL REFERENCES landing_skill_snapshots(entity_id) ON DELETE RESTRICT,
    global_rule text NOT NULL,
    status text NOT NULL CHECK (status IN ('pending','apply_global','keep_project')),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    decided_at timestamptz
);

COMMIT;
