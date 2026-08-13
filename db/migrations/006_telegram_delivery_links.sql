BEGIN;

CREATE TABLE commander_telegram_deliveries (
  chat_id bigint NOT NULL,
  message_id bigint NOT NULL,
  entity_id uuid NOT NULL REFERENCES commander_entities(id),
  delivered_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (chat_id, message_id)
);

CREATE INDEX commander_telegram_deliveries_entity_idx
  ON commander_telegram_deliveries (entity_id);

COMMIT;
