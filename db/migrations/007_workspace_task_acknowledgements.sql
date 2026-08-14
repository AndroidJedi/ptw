BEGIN;

ALTER TABLE commander_tasks
  ADD COLUMN external_task_id text UNIQUE,
  ADD COLUMN interpreted_scope text,
  ADD COLUMN workspace_session_id text,
  ADD COLUMN telegram_chat_id bigint,
  ADD COLUMN acknowledgement_status text NOT NULL DEFAULT 'not_required'
    CHECK (acknowledgement_status IN ('not_required', 'pending', 'acknowledged')),
  ADD COLUMN acknowledgement_outbox_id uuid REFERENCES commander_outbox(id),
  ADD COLUMN acknowledged_at timestamptz,
  ADD COLUMN telegram_message_id bigint,
  ADD CONSTRAINT commander_workspace_task_fields_check CHECK (
    (external_task_id IS NULL AND acknowledgement_status = 'not_required') OR
    (external_task_id ~ '^TASK-[0-9]+$' AND interpreted_scope IS NOT NULL
      AND workspace_session_id IS NOT NULL AND telegram_chat_id IS NOT NULL
      AND acknowledgement_status IN ('pending', 'acknowledged'))
  ),
  ADD CONSTRAINT commander_workspace_task_delivery_check CHECK (
    acknowledgement_status <> 'acknowledged' OR
    (acknowledged_at IS NOT NULL AND telegram_message_id IS NOT NULL)
  );

CREATE INDEX commander_workspace_ack_pending_idx
  ON commander_tasks (external_task_id)
  WHERE acknowledgement_status = 'pending';

COMMIT;
