CREATE TABLE IF NOT EXISTS users (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    telegram_user_id BIGINT NOT NULL UNIQUE,
    role TEXT NOT NULL DEFAULT 'operator',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sessions (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id),
    status TEXT NOT NULL,
    summary TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS jobs (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    session_id BIGINT NOT NULL REFERENCES sessions(id),
    type TEXT NOT NULL,
    status TEXT NOT NULL,
    requested_by BIGINT NOT NULL REFERENCES users(id),
    parameters JSONB NOT NULL DEFAULT '{}'::jsonb,
    result JSONB,
    error_code TEXT,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS events (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    session_id BIGINT REFERENCES sessions(id),
    job_id BIGINT REFERENCES jobs(id),
    actor TEXT NOT NULL,
    event_type TEXT NOT NULL,
    status TEXT,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON COLUMN events.payload IS
    'Non-secret event metadata only. Secret values and credentials are forbidden.';

CREATE TABLE IF NOT EXISTS service_heartbeats (
    service TEXT PRIMARY KEY,
    seen_at TIMESTAMPTZ NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS sessions_user_created_idx ON sessions (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS jobs_queue_idx ON jobs (created_at) WHERE status = 'queued';
CREATE INDEX IF NOT EXISTS jobs_session_idx ON jobs (session_id, created_at DESC);
CREATE INDEX IF NOT EXISTS jobs_status_idx ON jobs (status, created_at DESC);
CREATE INDEX IF NOT EXISTS events_session_idx ON events (session_id, created_at, id);
CREATE INDEX IF NOT EXISTS events_job_idx ON events (job_id, created_at, id);
CREATE INDEX IF NOT EXISTS events_type_created_idx ON events (event_type, created_at DESC);
