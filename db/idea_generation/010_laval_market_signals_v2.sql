ALTER TABLE laval_runs
    ADD COLUMN IF NOT EXISTS pipeline_version TEXT NOT NULL DEFAULT 'legacy-trends-v2';

ALTER TABLE laval_runs ALTER COLUMN pipeline_version SET DEFAULT 'market_signals_v2';

ALTER TABLE laval_runs DROP CONSTRAINT IF EXISTS laval_runs_evidence_mode_check;
ALTER TABLE laval_runs ADD CONSTRAINT laval_runs_evidence_mode_check
    CHECK (evidence_mode IN (
        'demo_fixture', 'live_search_pending_trends', 'live_complete', 'live_market_signals'
    ));

ALTER TABLE laval_transformation_operators
    DROP CONSTRAINT IF EXISTS laval_transformation_operators_name_check;
ALTER TABLE laval_transformation_operators
    ADD CONSTRAINT laval_transformation_operators_name_check
    CHECK (name IN (
        'invert','remove','extreme','transfer','resegment','recombine',
        'distribution_first','behavior_first'
    ));

ALTER TABLE laval_idea_variants
    DROP CONSTRAINT IF EXISTS laval_idea_variants_operator_check;
ALTER TABLE laval_idea_variants
    ADD CONSTRAINT laval_idea_variants_operator_check
    CHECK (operator IN (
        'invert','remove','extreme','transfer','resegment','recombine',
        'distribution_first','behavior_first'
    ));
ALTER TABLE laval_idea_variants
    ADD COLUMN IF NOT EXISTS market_signal_ids UUID[] NOT NULL DEFAULT '{}';

CREATE TABLE IF NOT EXISTS laval_llm_invocations (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES laval_runs(id) ON DELETE CASCADE,
    stage TEXT NOT NULL,
    mode TEXT NOT NULL,
    prompt_template_version TEXT NOT NULL,
    context_hash TEXT NOT NULL CHECK (context_hash ~ '^[0-9a-f]{64}$'),
    output_schema_hash TEXT NOT NULL CHECK (output_schema_hash ~ '^[0-9a-f]{64}$'),
    model TEXT NOT NULL,
    session_id UUID NOT NULL,
    provider_session_id TEXT,
    result_status TEXT NOT NULL CHECK (result_status IN ('success','fallback','failed')),
    error_type TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS laval_llm_invocations_run_stage_idx
    ON laval_llm_invocations(run_id, stage, created_at);

CREATE OR REPLACE FUNCTION laval_reject_llm_invocation_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Laval LLM invocation audit is append-only';
END;
$$;

DROP TRIGGER IF EXISTS laval_llm_invocations_append_only ON laval_llm_invocations;
CREATE TRIGGER laval_llm_invocations_append_only
BEFORE UPDATE OR DELETE ON laval_llm_invocations
FOR EACH ROW EXECUTE FUNCTION laval_reject_llm_invocation_mutation();

CREATE TABLE IF NOT EXISTS laval_market_signal_scores (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES laval_runs(id) ON DELETE CASCADE,
    opportunity_id UUID NOT NULL REFERENCES laval_opportunities(id) ON DELETE CASCADE,
    normalization_version TEXT NOT NULL,
    formula TEXT NOT NULL,
    weights JSONB NOT NULL,
    components JSONB NOT NULL,
    raw_counts JSONB NOT NULL,
    data_status JSONB NOT NULL,
    evidence_ids UUID[] NOT NULL DEFAULT '{}',
    aggregate_score NUMERIC(8,6) NOT NULL CHECK (aggregate_score BETWEEN 0 AND 1),
    as_of TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS laval_market_signal_scores_run_score_idx
    ON laval_market_signal_scores(run_id, aggregate_score DESC, created_at DESC);
