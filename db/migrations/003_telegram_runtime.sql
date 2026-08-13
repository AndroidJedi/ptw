BEGIN;

CREATE TABLE commander_telegram_inbox (
  update_id bigint PRIMARY KEY,
  received_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

COMMIT;
