CREATE TABLE IF NOT EXISTS missions (
 id BIGSERIAL PRIMARY KEY, code TEXT NOT NULL UNIQUE, name TEXT NOT NULL, task_text TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','paused','completed')),
 generation_size INTEGER NOT NULL DEFAULT 10 CHECK(generation_size=10), hall_of_fame_size INTEGER NOT NULL DEFAULT 3,
 failure_size INTEGER NOT NULL DEFAULT 2, exploit_count INTEGER NOT NULL DEFAULT 7, explore_count INTEGER NOT NULL DEFAULT 3,
 auto_enabled BOOLEAN NOT NULL DEFAULT FALSE, cadence_hours INTEGER NOT NULL DEFAULT 24,
 max_generations_per_day INTEGER NOT NULL DEFAULT 1, run_series_remaining INTEGER NOT NULL DEFAULT 0,
 stop_after_current_cycle BOOLEAN NOT NULL DEFAULT FALSE, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS contexts (
 id BIGSERIAL PRIMARY KEY, code TEXT NOT NULL UNIQUE CHECK(code ~ '^C(0[1-9]|10)$'), name TEXT NOT NULL,
 prompt_text TEXT NOT NULL, active BOOLEAN NOT NULL DEFAULT TRUE, sort_order INTEGER NOT NULL UNIQUE,
 version INTEGER NOT NULL DEFAULT 1, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS context_revisions (
 id BIGSERIAL PRIMARY KEY, context_id BIGINT NOT NULL REFERENCES contexts(id) ON DELETE CASCADE, version INTEGER NOT NULL,
 name TEXT NOT NULL, prompt_text TEXT NOT NULL, changed_by TEXT NOT NULL DEFAULT 'owner', change_note TEXT,
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), UNIQUE(context_id,version)
);
CREATE TABLE IF NOT EXISTS generations (
 id BIGSERIAL PRIMARY KEY, mission_id BIGINT NOT NULL REFERENCES missions(id) ON DELETE CASCADE, number INTEGER NOT NULL CHECK(number>0),
 status TEXT NOT NULL CHECK(status IN ('creating','created','evaluating','completed','failed')), started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 completed_at TIMESTAMPTZ, error_text TEXT, UNIQUE(mission_id,number)
);
CREATE TABLE IF NOT EXISTS idea_submissions (
 id BIGSERIAL PRIMARY KEY, mission_id BIGINT NOT NULL REFERENCES missions(id) ON DELETE CASCADE, title TEXT, raw_text TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','scheduled','inserted','cancelled')),
 target_generation_number INTEGER, inserted_idea_id BIGINT, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS ideas (
 id BIGSERIAL PRIMARY KEY, mission_id BIGINT NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
 generation_id BIGINT NOT NULL REFERENCES generations(id) ON DELETE CASCADE, creator_context_id BIGINT REFERENCES contexts(id),
 mode TEXT NOT NULL CHECK(mode IN ('initial','exploit','explore','human')), title TEXT NOT NULL, one_liner TEXT NOT NULL, details JSONB NOT NULL,
 parent_ids BIGINT[] NOT NULL DEFAULT '{}', lineage_note TEXT, owner_submission_id BIGINT UNIQUE REFERENCES idea_submissions(id), created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
DO $$ BEGIN ALTER TABLE idea_submissions ADD CONSTRAINT idea_submissions_inserted_idea_fk FOREIGN KEY(inserted_idea_id) REFERENCES ideas(id) ON DELETE SET NULL;
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
CREATE INDEX IF NOT EXISTS idx_ideas_generation ON ideas(mission_id,generation_id);
CREATE INDEX IF NOT EXISTS idx_ideas_parent_ids ON ideas USING GIN(parent_ids);
CREATE TABLE IF NOT EXISTS idea_evaluations (
 id BIGSERIAL PRIMARY KEY, idea_id BIGINT NOT NULL REFERENCES ideas(id) ON DELETE CASCADE,
 evaluator_context_id BIGINT NOT NULL REFERENCES contexts(id), score NUMERIC(5,2) NOT NULL CHECK(score BETWEEN 0 AND 100), criteria JSONB NOT NULL,
 strengths TEXT NOT NULL, critique TEXT NOT NULL, fatal_flaw TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), UNIQUE(idea_id,evaluator_context_id)
);
CREATE OR REPLACE VIEW idea_scores AS SELECT i.id idea_id,i.mission_id,i.generation_id,AVG(e.score)::NUMERIC(5,2) aggregate_score,COUNT(e.id) evaluation_count
 FROM ideas i JOIN idea_evaluations e ON e.idea_id=i.id GROUP BY i.id,i.mission_id,i.generation_id;
CREATE TABLE IF NOT EXISTS guidance (
 id BIGSERIAL PRIMARY KEY, mission_id BIGINT NOT NULL REFERENCES missions(id) ON DELETE CASCADE, idea_id BIGINT REFERENCES ideas(id) ON DELETE CASCADE,
 text TEXT NOT NULL, active BOOLEAN NOT NULL DEFAULT TRUE, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS executions (
 id BIGSERIAL PRIMARY KEY, mission_id BIGINT NOT NULL REFERENCES missions(id) ON DELETE CASCADE, generation_id BIGINT REFERENCES generations(id) ON DELETE SET NULL,
 phase TEXT NOT NULL CHECK(phase IN ('generate','evaluate','evolve','normalize_human','telegram_chat')),
 status TEXT NOT NULL CHECK(status IN ('running','succeeded','failed')), context_id BIGINT REFERENCES contexts(id), attempt INTEGER NOT NULL DEFAULT 1,
 model_name TEXT,prompt_hash TEXT,input_tokens BIGINT,output_tokens BIGINT,request_json JSONB,response_json JSONB,error_text TEXT,
 started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),completed_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS reports (
 id BIGSERIAL PRIMARY KEY,mission_id BIGINT NOT NULL REFERENCES missions(id) ON DELETE CASCADE,generation_id BIGINT REFERENCES generations(id) ON DELETE SET NULL,
 report_type TEXT NOT NULL CHECK(report_type IN ('generation','run_series','recovery')),title TEXT NOT NULL,body_text TEXT NOT NULL,payload JSONB,created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS telegram_events (
 id BIGSERIAL PRIMARY KEY,chat_id BIGINT NOT NULL,direction TEXT NOT NULL CHECK(direction IN ('in','out')),event_type TEXT NOT NULL,text TEXT,payload JSONB,
 execution_id BIGINT REFERENCES executions(id) ON DELETE SET NULL,created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS telegram_offsets (
 bot_key TEXT PRIMARY KEY,update_id BIGINT NOT NULL,updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
