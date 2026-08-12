CREATE TABLE IF NOT EXISTS repositories (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    clone_url TEXT NOT NULL UNIQUE,
    default_branch TEXT NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT true,
    project_type TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO repositories (id, name, clone_url, default_branch, enabled, project_type, metadata)
VALUES ('ptw', 'Proof Them Wrong', 'git@github.com:AndroidJedi/ptw.git', 'main', true, 'flutter',
        '{"dart_sdk":"^3.7.0","fvm":false}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    name = excluded.name, clone_url = excluded.clone_url,
    default_branch = excluded.default_branch, enabled = excluded.enabled,
    project_type = excluded.project_type, metadata = excluded.metadata, updated_at = now();

CREATE TABLE IF NOT EXISTS watched_branches (
    repository_id TEXT NOT NULL REFERENCES repositories(id),
    branch TEXT NOT NULL,
    last_sha TEXT,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (repository_id, branch),
    CHECK (last_sha IS NULL OR last_sha ~ '^[0-9a-f]{40}$')
);

CREATE TABLE IF NOT EXISTS git_notifications (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repository_id TEXT NOT NULL REFERENCES repositories(id),
    branch TEXT NOT NULL,
    previous_sha TEXT NOT NULL,
    current_sha TEXT NOT NULL,
    recipient_id BIGINT NOT NULL,
    message TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'sent', 'failed')),
    attempts INTEGER NOT NULL DEFAULT 0,
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    sent_at TIMESTAMPTZ,
    last_error_type TEXT,
    UNIQUE (repository_id, branch, current_sha, recipient_id)
);

CREATE INDEX IF NOT EXISTS git_notifications_delivery_idx
    ON git_notifications (next_attempt_at, id) WHERE status = 'pending';
