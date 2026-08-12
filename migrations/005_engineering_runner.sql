CREATE TABLE IF NOT EXISTS telegram_attachments (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    telegram_user_id BIGINT NOT NULL,
    chat_id BIGINT NOT NULL,
    telegram_file_id TEXT NOT NULL,
    file_type TEXT NOT NULL,
    caption TEXT,
    local_path TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','linked','expired')),
    job_id BIGINT REFERENCES jobs(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL DEFAULT now() + interval '30 minutes'
);
CREATE INDEX IF NOT EXISTS telegram_attachments_pending_idx
ON telegram_attachments(telegram_user_id, created_at DESC) WHERE status='pending';

