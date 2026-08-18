ALTER TABLE laval_runs
    ADD COLUMN IF NOT EXISTS evidence_mode TEXT NOT NULL DEFAULT 'demo_fixture'
        CHECK (evidence_mode IN ('demo_fixture','live_search_pending_trends','live_complete')),
    ADD COLUMN IF NOT EXISTS provider_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS max_spend_usd NUMERIC(8,6) NOT NULL DEFAULT 0.050000
        CHECK (max_spend_usd >= 0 AND max_spend_usd <= 0.050000),
    ADD COLUMN IF NOT EXISTS reserved_spend_usd NUMERIC(8,6) NOT NULL DEFAULT 0.040000
        CHECK (reserved_spend_usd >= 0 AND reserved_spend_usd <= max_spend_usd),
    ADD COLUMN IF NOT EXISTS awaiting_reason TEXT;

UPDATE laval_runs r
SET evidence_mode='demo_fixture',
    provider_snapshot=jsonb_build_object(
        'search', 'fixture',
        'web', 'fixture',
        'trends', 'fixture',
        'llm', COALESCE((
            SELECT NULLIF(s.model, '')
            FROM laval_stage_runs s
            WHERE s.run_id=r.id AND s.model IS NOT NULL
            ORDER BY s.ordinal
            LIMIT 1
        ), 'unknown')
    )
WHERE EXISTS (
    SELECT 1 FROM laval_stage_runs s
    WHERE s.run_id=r.id AND s.provider='fixture'
);

ALTER TABLE laval_stage_runs
    DROP CONSTRAINT IF EXISTS laval_completed_stage_requires_artifact;
ALTER TABLE laval_stage_runs
    ADD CONSTRAINT laval_completed_stage_requires_artifact
    CHECK (status NOT IN ('completed','partial') OR artifact IS NOT NULL) NOT VALID;
ALTER TABLE laval_stage_runs VALIDATE CONSTRAINT laval_completed_stage_requires_artifact;

CREATE TABLE IF NOT EXISTS laval_provider_tasks (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES laval_runs(id) ON DELETE CASCADE,
    stage TEXT NOT NULL,
    item_key TEXT NOT NULL,
    provider TEXT NOT NULL,
    remote_task_id TEXT,
    status TEXT NOT NULL DEFAULT 'reserved'
        CHECK (status IN ('reserved','submitted','completed','failed')),
    request JSONB NOT NULL DEFAULT '{}'::jsonb,
    response JSONB,
    reserved_cost_usd NUMERIC(8,6) NOT NULL DEFAULT 0,
    actual_cost_usd NUMERIC(8,6) NOT NULL DEFAULT 0,
    cost_recorded BOOLEAN NOT NULL DEFAULT FALSE,
    error JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (run_id, stage, item_key),
    UNIQUE (provider, remote_task_id)
);

CREATE INDEX IF NOT EXISTS laval_provider_tasks_run_status_idx
    ON laval_provider_tasks(run_id, status);
