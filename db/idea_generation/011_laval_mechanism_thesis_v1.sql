ALTER TABLE laval_runs ALTER COLUMN pipeline_version SET DEFAULT 'mechanism_thesis_v1';

ALTER TABLE laval_stage_runs DROP CONSTRAINT IF EXISTS laval_stage_runs_ordinal_check;
ALTER TABLE laval_stage_runs ADD CONSTRAINT laval_stage_runs_ordinal_check
    CHECK (ordinal BETWEEN 0 AND 31);

CREATE TABLE IF NOT EXISTS laval_youtube_channels (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES laval_runs(id) ON DELETE CASCADE,
    youtube_channel_id TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (run_id, youtube_channel_id)
);

CREATE TABLE IF NOT EXISTS laval_youtube_videos (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES laval_runs(id) ON DELETE CASCADE,
    channel_id UUID NOT NULL REFERENCES laval_youtube_channels(id) ON DELETE CASCADE,
    youtube_video_id TEXT NOT NULL,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    published_at TIMESTAMPTZ,
    country TEXT,
    language TEXT,
    evidence_id UUID REFERENCES laval_evidence(id) ON DELETE SET NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (run_id, youtube_video_id)
);

CREATE TABLE IF NOT EXISTS laval_youtube_snapshots (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES laval_runs(id) ON DELETE CASCADE,
    video_id UUID NOT NULL REFERENCES laval_youtube_videos(id) ON DELETE CASCADE,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    view_count BIGINT NOT NULL DEFAULT 0 CHECK (view_count >= 0),
    like_count BIGINT NOT NULL DEFAULT 0 CHECK (like_count >= 0),
    comment_count BIGINT NOT NULL DEFAULT 0 CHECK (comment_count >= 0),
    provider TEXT NOT NULL,
    raw JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (video_id, observed_at)
);

CREATE TABLE IF NOT EXISTS laval_behavior_observations (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES laval_runs(id) ON DELETE CASCADE,
    observation_type TEXT NOT NULL CHECK (observation_type IN (
        'workaround','challenge_format','motivation','repeated_question','complaint',
        'transformation_narrative','audience_vocabulary','creator_distribution','substitute'
    )),
    statement TEXT NOT NULL,
    video_ids UUID[] NOT NULL DEFAULT '{}',
    channel_ids UUID[] NOT NULL DEFAULT '{}',
    evidence_ids UUID[] NOT NULL DEFAULT '{}',
    independent_creator_count INTEGER NOT NULL DEFAULT 0 CHECK (independent_creator_count >= 0),
    confidence NUMERIC(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS laval_product_mechanisms (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES laval_runs(id) ON DELETE CASCADE,
    name JSONB NOT NULL,
    description JSONB NOT NULL,
    mechanism_type TEXT NOT NULL CHECK (mechanism_type IN (
        'value','behavior','trust','retention','distribution','proof'
    )),
    source_variant_ids UUID[] NOT NULL DEFAULT '{}',
    opportunity_ids UUID[] NOT NULL DEFAULT '{}',
    market_signal_ids UUID[] NOT NULL DEFAULT '{}',
    behavior_observation_ids UUID[] NOT NULL DEFAULT '{}',
    evidence_ids UUID[] NOT NULL DEFAULT '{}',
    support_dimensions JSONB NOT NULL DEFAULT '{}'::jsonb,
    commander_entity_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS laval_product_theses (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES laval_runs(id) ON DELETE CASCADE,
    title JSONB NOT NULL,
    target_user JSONB NOT NULL,
    problem JSONB NOT NULL,
    loop_steps JSONB NOT NULL,
    value_moment JSONB NOT NULL,
    zero_audience_behavior JSONB NOT NULL,
    substitutes JSONB NOT NULL,
    dangerous_assumptions JSONB NOT NULL,
    success_criterion JSONB NOT NULL,
    mechanism_ids UUID[] NOT NULL DEFAULT '{}',
    evidence_ids UUID[] NOT NULL DEFAULT '{}',
    verdict TEXT CHECK (verdict IN ('survives','weak','rejected')),
    recommended BOOLEAN NOT NULL DEFAULT FALSE,
    recommendation_reason TEXT,
    commander_hypothesis_id UUID,
    validation_workspace_id UUID,
    validation_stale BOOLEAN NOT NULL DEFAULT FALSE,
    selected_at TIMESTAMPTZ,
    selected_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS laval_thesis_falsifications (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES laval_runs(id) ON DELETE CASCADE,
    thesis_id UUID NOT NULL UNIQUE REFERENCES laval_product_theses(id) ON DELETE CASCADE,
    risks JSONB NOT NULL,
    fatal_objection TEXT,
    unsupported_high_severity_count INTEGER NOT NULL DEFAULT 0 CHECK (unsupported_high_severity_count >= 0),
    weakest_mechanism_coverage NUMERIC(5,4) NOT NULL DEFAULT 0 CHECK (weakest_mechanism_coverage BETWEEN 0 AND 1),
    verdict TEXT NOT NULL CHECK (verdict IN ('survives','weak','rejected')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS laval_youtube_video_run_idx
    ON laval_youtube_videos(run_id, youtube_video_id);
CREATE INDEX IF NOT EXISTS laval_youtube_snapshot_video_idx
    ON laval_youtube_snapshots(video_id, observed_at);
CREATE INDEX IF NOT EXISTS laval_behavior_run_idx
    ON laval_behavior_observations(run_id, observation_type);
CREATE INDEX IF NOT EXISTS laval_mechanism_run_idx
    ON laval_product_mechanisms(run_id, mechanism_type);
CREATE INDEX IF NOT EXISTS laval_thesis_run_idx
    ON laval_product_theses(run_id, verdict, recommended);
