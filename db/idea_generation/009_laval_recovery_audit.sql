CREATE TABLE IF NOT EXISTS laval_run_actions (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES laval_runs(id) ON DELETE CASCADE,
    action TEXT NOT NULL,
    stage TEXT,
    actor TEXT NOT NULL,
    previous_status TEXT,
    outcome TEXT NOT NULL DEFAULT 'recorded',
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    dedupe_key TEXT UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS laval_run_actions_run_created_idx
    ON laval_run_actions(run_id, created_at DESC);
