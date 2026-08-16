ALTER TABLE idea_submissions
    ADD COLUMN IF NOT EXISTS replaces_idea_id BIGINT REFERENCES ideas(id) ON DELETE SET NULL;

ALTER TABLE ideas DROP CONSTRAINT IF EXISTS ideas_mode_check;
ALTER TABLE ideas
    ADD CONSTRAINT ideas_mode_check
    CHECK (mode IN ('initial','exploit','explore','human','retained'));

CREATE TABLE IF NOT EXISTS idea_submission_drafts (
    chat_id BIGINT PRIMARY KEY,
    mission_id BIGINT NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
    raw_text TEXT NOT NULL DEFAULT '',
    part_count INTEGER NOT NULL DEFAULT 0 CHECK (part_count >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS telegram_inbox (
    update_id BIGINT PRIMARY KEY,
    response_text TEXT,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);
