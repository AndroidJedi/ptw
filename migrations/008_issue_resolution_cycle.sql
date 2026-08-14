CREATE TABLE IF NOT EXISTS engineering_issues (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    job_id BIGINT NOT NULL REFERENCES jobs(id),
    stage TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open','resolving','resolved','unresolved','cancelled')),
    error_type TEXT NOT NULL,
    summary TEXT NOT NULL,
    resolution_summary TEXT,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS engineering_issues_job_idx
ON engineering_issues(job_id, created_at, id);

CREATE INDEX IF NOT EXISTS engineering_issues_open_idx
ON engineering_issues(status, created_at) WHERE status IN ('open','resolving');

CREATE TABLE IF NOT EXISTS engineering_issue_logs (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    issue_id BIGINT NOT NULL REFERENCES engineering_issues(id),
    level TEXT NOT NULL CHECK (level IN ('info','warning','error')),
    message TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS engineering_issue_logs_issue_idx
ON engineering_issue_logs(issue_id, created_at, id);

COMMENT ON COLUMN engineering_issue_logs.message IS
    'Sanitized diagnostic text only. Secrets and credentials are forbidden.';

