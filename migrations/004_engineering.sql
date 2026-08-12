ALTER TABLE jobs ADD COLUMN IF NOT EXISTS parent_job_id BIGINT REFERENCES jobs(id);
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS stage TEXT;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS retry_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS metrics JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE TABLE IF NOT EXISTS project_memory (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repository_id TEXT NOT NULL REFERENCES repositories(id),
    category TEXT NOT NULL CHECK (category IN ('architecture','product_rules','engineering_rules','design_rules','business_rules','research_findings','decisions','known_pitfalls','deployment_rules')),
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    tags TEXT[] NOT NULL DEFAULT '{}',
    source_type TEXT NOT NULL,
    source_reference TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'candidate' CHECK (status IN ('candidate','accepted','superseded','rejected')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS project_memory_search_idx ON project_memory
USING GIN (to_tsvector('english', title || ' ' || content || ' ' || array_to_string(tags, ' ')));

CREATE TABLE IF NOT EXISTS engineering_artifacts (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    job_id BIGINT NOT NULL REFERENCES jobs(id),
    kind TEXT NOT NULL,
    path TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(job_id, kind, path)
);

CREATE TABLE IF NOT EXISTS engineering_runs (
    job_id BIGINT PRIMARY KEY REFERENCES jobs(id),
    repository_id TEXT NOT NULL REFERENCES repositories(id),
    task_class TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    branch TEXT,
    commit_sha TEXT,
    pull_request_number INTEGER,
    pull_request_url TEXT,
    preview_url TEXT,
    status TEXT NOT NULL DEFAULT 'specified',
    failure_stage TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

