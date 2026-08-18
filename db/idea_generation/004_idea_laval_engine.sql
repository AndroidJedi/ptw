CREATE TABLE IF NOT EXISTS laval_runs (
    id UUID PRIMARY KEY,
    mission_id BIGINT NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
    owner_idea_id UUID,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','running','paused','completed','failed','cancelled')),
    current_stage TEXT,
    through_stage TEXT,
    config JSONB NOT NULL,
    approval_mode TEXT NOT NULL DEFAULT 'manual'
        CHECK (approval_mode IN ('manual','automatic')),
    approval_gates TEXT[] NOT NULL DEFAULT '{}',
    error_text TEXT,
    created_by TEXT NOT NULL DEFAULT 'owner',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS laval_owner_ideas (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL UNIQUE REFERENCES laval_runs(id) ON DELETE CASCADE,
    raw_text TEXT NOT NULL CHECK (length(btrim(raw_text)) > 0),
    structured_dna JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

DO $$ BEGIN
    ALTER TABLE laval_runs ADD CONSTRAINT laval_runs_owner_idea_fk
        FOREIGN KEY (owner_idea_id) REFERENCES laval_owner_ideas(id) ON DELETE RESTRICT;
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE TABLE IF NOT EXISTS laval_stage_runs (
    run_id UUID NOT NULL REFERENCES laval_runs(id) ON DELETE CASCADE,
    stage TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal BETWEEN 0 AND 15),
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','running','partial','completed','failed','paused','stale')),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    input_hash TEXT,
    attempt INTEGER NOT NULL DEFAULT 0 CHECK (attempt >= 0),
    provider TEXT,
    model TEXT,
    cost JSONB NOT NULL DEFAULT '{}'::jsonb,
    metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    error JSONB,
    artifact JSONB,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (run_id, stage),
    UNIQUE (run_id, ordinal)
);

CREATE TABLE IF NOT EXISTS laval_stage_items (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES laval_runs(id) ON DELETE CASCADE,
    stage TEXT NOT NULL,
    item_key TEXT NOT NULL,
    country TEXT,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','running','partial','completed','failed','stale')),
    input_hash TEXT,
    attempt INTEGER NOT NULL DEFAULT 0,
    provider TEXT,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    error JSONB,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (run_id, stage, item_key)
);

CREATE TABLE IF NOT EXISTS laval_artifacts (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES laval_runs(id) ON DELETE CASCADE,
    stage TEXT NOT NULL,
    name TEXT NOT NULL,
    media_type TEXT NOT NULL CHECK (media_type IN ('application/json','text/markdown')),
    sha256 TEXT NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    content JSONB,
    text_content TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (run_id, stage, name, sha256),
    CHECK ((content IS NULL) <> (text_content IS NULL))
);

CREATE TABLE IF NOT EXISTS laval_evidence (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES laval_runs(id) ON DELETE CASCADE,
    source_type TEXT NOT NULL
        CHECK (source_type IN ('website','youtube','reddit','review','forum','serp','trend','fixture','manual')),
    source_url TEXT NOT NULL,
    source_title TEXT NOT NULL,
    publisher TEXT NOT NULL DEFAULT '',
    retrieved_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    competitor_id UUID,
    country TEXT,
    raw_artifact_id UUID REFERENCES laval_artifacts(id) ON DELETE SET NULL,
    excerpt TEXT NOT NULL DEFAULT '',
    claim TEXT NOT NULL DEFAULT '',
    confidence NUMERIC(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    commander_source_id UUID
);

CREATE TABLE IF NOT EXISTS laval_competitors (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES laval_runs(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    domain TEXT NOT NULL,
    url TEXT NOT NULL,
    result_type TEXT NOT NULL
        CHECK (result_type IN ('direct_product','adjacent_product','substitute','directory','article','review_site','social','irrelevant')),
    score NUMERIC(8,6) NOT NULL DEFAULT 0 CHECK (score BETWEEN 0 AND 1),
    selected BOOLEAN NOT NULL DEFAULT FALSE,
    components JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (run_id, domain)
);

ALTER TABLE laval_evidence DROP CONSTRAINT IF EXISTS laval_evidence_competitor_fk;
ALTER TABLE laval_evidence ADD CONSTRAINT laval_evidence_competitor_fk
    FOREIGN KEY (competitor_id) REFERENCES laval_competitors(id) ON DELETE SET NULL;

CREATE TABLE IF NOT EXISTS laval_competitor_country_rankings (
    run_id UUID NOT NULL REFERENCES laval_runs(id) ON DELETE CASCADE,
    competitor_id UUID NOT NULL REFERENCES laval_competitors(id) ON DELETE CASCADE,
    country TEXT NOT NULL,
    rank INTEGER NOT NULL CHECK (rank > 0),
    score NUMERIC(8,6) NOT NULL CHECK (score BETWEEN 0 AND 1),
    evidence_ids UUID[] NOT NULL DEFAULT '{}',
    PRIMARY KEY (run_id, country, rank),
    UNIQUE (run_id, country, competitor_id)
);

CREATE TABLE IF NOT EXISTS laval_competitor_dossiers (
    competitor_id UUID PRIMARY KEY REFERENCES laval_competitors(id) ON DELETE CASCADE,
    run_id UUID NOT NULL REFERENCES laval_runs(id) ON DELETE CASCADE,
    dossier JSONB NOT NULL,
    confidence NUMERIC(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    evidence_ids UUID[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS laval_opportunities (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES laval_runs(id) ON DELETE CASCADE,
    statement TEXT NOT NULL,
    pain TEXT NOT NULL DEFAULT '',
    affected_segment TEXT NOT NULL DEFAULT '',
    competitor_ids UUID[] NOT NULL DEFAULT '{}',
    countries TEXT[] NOT NULL DEFAULT '{}',
    evidence_ids UUID[] NOT NULL DEFAULT '{}',
    scores JSONB NOT NULL,
    aggregate_score NUMERIC(8,6) NOT NULL CHECK (aggregate_score BETWEEN 0 AND 1),
    selected_for_trends BOOLEAN NOT NULL DEFAULT FALSE,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    evidence_count INTEGER NOT NULL DEFAULT 0,
    source_type_count INTEGER NOT NULL DEFAULT 0,
    country_count INTEGER NOT NULL DEFAULT 0,
    competitor_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS laval_trend_queries (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES laval_runs(id) ON DELETE CASCADE,
    opportunity_id UUID NOT NULL REFERENCES laval_opportunities(id) ON DELETE CASCADE,
    term TEXT NOT NULL,
    country TEXT NOT NULL,
    time_window TEXT NOT NULL CHECK (time_window IN ('90d','12m','5y')),
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (run_id, opportunity_id, term, country, time_window)
);

CREATE TABLE IF NOT EXISTS laval_trend_scores (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES laval_runs(id) ON DELETE CASCADE,
    trend_query_id UUID NOT NULL REFERENCES laval_trend_queries(id) ON DELETE CASCADE,
    opportunity_id UUID NOT NULL REFERENCES laval_opportunities(id) ON DELETE CASCADE,
    term TEXT NOT NULL,
    country TEXT NOT NULL,
    time_window TEXT NOT NULL,
    dimensions JSONB NOT NULL,
    aggregate_score NUMERIC(8,6) NOT NULL CHECK (aggregate_score BETWEEN 0 AND 1),
    evidence_ids UUID[] NOT NULL DEFAULT '{}',
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (run_id, trend_query_id)
);

CREATE TABLE IF NOT EXISTS laval_trend_discoveries (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES laval_runs(id) ON DELETE CASCADE,
    seed_term TEXT NOT NULL,
    discovered_term TEXT NOT NULL,
    discovery_type TEXT NOT NULL
        CHECK (discovery_type IN ('related_query','rising_query','breakout','related_topic')),
    country TEXT NOT NULL,
    time_window TEXT NOT NULL,
    growth_label TEXT NOT NULL DEFAULT '',
    opportunity_ids UUID[] NOT NULL DEFAULT '{}',
    evidence_ids UUID[] NOT NULL DEFAULT '{}',
    confidence NUMERIC(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (run_id, seed_term, discovered_term, discovery_type, country, time_window)
);

CREATE TABLE IF NOT EXISTS laval_transformation_operators (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES laval_runs(id) ON DELETE CASCADE,
    name TEXT NOT NULL
        CHECK (name IN ('invert','remove','extreme','transfer','resegment','recombine','distribution_first')),
    instruction TEXT NOT NULL,
    UNIQUE (run_id, name)
);

CREATE TABLE IF NOT EXISTS laval_idea_variants (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES laval_runs(id) ON DELETE CASCADE,
    owner_idea_id UUID NOT NULL REFERENCES laval_owner_ideas(id) ON DELETE RESTRICT,
    title JSONB NOT NULL,
    one_liner JSONB NOT NULL,
    mechanism JSONB NOT NULL,
    target_user JSONB NOT NULL,
    why_new JSONB NOT NULL,
    operator TEXT NOT NULL
        CHECK (operator IN ('invert','remove','extreme','transfer','resegment','recombine','distribution_first')),
    opportunity_ids UUID[] NOT NULL DEFAULT '{}',
    trend_signal_ids UUID[] NOT NULL DEFAULT '{}',
    trend_discovery_ids UUID[] NOT NULL DEFAULT '{}',
    evidence_ids UUID[] NOT NULL DEFAULT '{}',
    cluster_key TEXT,
    representative BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS laval_idea_scores (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES laval_runs(id) ON DELETE CASCADE,
    idea_id UUID NOT NULL REFERENCES laval_idea_variants(id) ON DELETE CASCADE,
    deterministic JSONB NOT NULL,
    deterministic_score NUMERIC(8,6) NOT NULL CHECK (deterministic_score BETWEEN 0 AND 1),
    evaluator JSONB NOT NULL,
    evaluator_score NUMERIC(8,6) NOT NULL CHECK (evaluator_score BETWEEN 0 AND 1),
    final_score NUMERIC(8,6) NOT NULL CHECK (final_score BETWEEN 0 AND 1),
    rank INTEGER,
    finalist BOOLEAN NOT NULL DEFAULT FALSE,
    commander_hypothesis_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (run_id, idea_id)
);

CREATE TABLE IF NOT EXISTS laval_overrides (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES laval_runs(id) ON DELETE CASCADE,
    override_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    action TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    actor TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS laval_approvals (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES laval_runs(id) ON DELETE CASCADE,
    stage TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    actor TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (run_id, stage, input_hash)
);

CREATE TABLE IF NOT EXISTS laval_cost_events (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES laval_runs(id) ON DELETE CASCADE,
    stage TEXT NOT NULL,
    provider TEXT NOT NULL,
    operation TEXT NOT NULL,
    request_count INTEGER NOT NULL DEFAULT 1 CHECK (request_count >= 0),
    input_tokens BIGINT NOT NULL DEFAULT 0 CHECK (input_tokens >= 0),
    output_tokens BIGINT NOT NULL DEFAULT 0 CHECK (output_tokens >= 0),
    amount_usd NUMERIC(12,6) NOT NULL DEFAULT 0 CHECK (amount_usd >= 0),
    cached BOOLEAN NOT NULL DEFAULT FALSE,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS laval_lineage_edges (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES laval_runs(id) ON DELETE CASCADE,
    source_kind TEXT NOT NULL,
    source_id UUID NOT NULL,
    relation TEXT NOT NULL CHECK (relation IN ('derived_from','contains','selected_from','transformed_by','evaluates','supersedes')),
    target_kind TEXT NOT NULL,
    target_id UUID NOT NULL,
    attributes JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (run_id, source_kind, source_id, relation, target_kind, target_id)
);

CREATE INDEX IF NOT EXISTS laval_runs_status_idx ON laval_runs(status, updated_at DESC);
CREATE INDEX IF NOT EXISTS laval_stage_runs_status_idx ON laval_stage_runs(run_id, ordinal, status);
CREATE INDEX IF NOT EXISTS laval_stage_items_stage_idx ON laval_stage_items(run_id, stage, country, status);
CREATE INDEX IF NOT EXISTS laval_evidence_run_idx ON laval_evidence(run_id, source_type, country);
CREATE INDEX IF NOT EXISTS laval_competitors_run_idx ON laval_competitors(run_id, selected, score DESC);
CREATE INDEX IF NOT EXISTS laval_opportunities_run_idx ON laval_opportunities(run_id, enabled, aggregate_score DESC);
CREATE INDEX IF NOT EXISTS laval_trend_scores_run_idx ON laval_trend_scores(run_id, enabled, aggregate_score DESC);
CREATE INDEX IF NOT EXISTS laval_variants_run_idx ON laval_idea_variants(run_id, representative, created_at);
CREATE INDEX IF NOT EXISTS laval_scores_run_idx ON laval_idea_scores(run_id, rank, final_score DESC);
