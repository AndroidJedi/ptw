BEGIN;

CREATE TABLE IF NOT EXISTS positioning_notification_attempts (
    id uuid PRIMARY KEY,
    revision_id uuid NOT NULL REFERENCES positioning_revisions(entity_id) ON DELETE RESTRICT,
    generation_attempt_id uuid NOT NULL UNIQUE REFERENCES positioning_generation_attempts(id) ON DELETE RESTRICT,
    terminal_status text NOT NULL CHECK (terminal_status IN ('completed','failed')),
    status text NOT NULL CHECK (status IN ('sent','failed','ambiguous','suppressed')),
    telegram_chat_id bigint NOT NULL,
    telegram_message_id bigint,
    error_code text,
    error_message text,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    completed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK (telegram_message_id IS NULL OR status = 'sent')
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'positioning_notification_attempts_immutable'
          AND tgrelid = 'positioning_notification_attempts'::regclass
    ) THEN
        CREATE TRIGGER positioning_notification_attempts_immutable
            BEFORE UPDATE OR DELETE ON positioning_notification_attempts
            FOR EACH ROW EXECUTE FUNCTION ptw_reject_immutable_mutation();
    END IF;
END $$;

COMMIT;
