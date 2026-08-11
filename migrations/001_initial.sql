CREATE TABLE IF NOT EXISTS platform_events (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    event_type TEXT NOT NULL CHECK (length(event_type) BETWEEN 1 AND 100),
    actor_type TEXT NOT NULL CHECK (length(actor_type) BETWEEN 1 AND 100),
    actor_id TEXT,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON COLUMN platform_events.payload IS
    'Non-secret event metadata only. Secrets and credentials are forbidden.';

CREATE INDEX IF NOT EXISTS platform_events_created_at_idx
    ON platform_events (created_at DESC);

