BEGIN;

CREATE TABLE commander_bot_conversations (
    id uuid PRIMARY KEY,
    title text NOT NULL CHECK (length(btrim(title)) BETWEEN 1 AND 120),
    status text NOT NULL CHECK (status IN ('idle','working','waiting_user','waiting_approval','completed','failed','cancelled')),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE commander_bot_tasks (
    id uuid PRIMARY KEY,
    conversation_id uuid NOT NULL REFERENCES commander_bot_conversations(id) ON DELETE CASCADE,
    task_type text NOT NULL CHECK (task_type IN ('business_research')),
    status text NOT NULL CHECK (status IN ('queued','running','waiting_user','waiting_approval','completed','failed','cancelled')),
    assigned_agent text NOT NULL CHECK (assigned_agent='business_researcher'),
    context jsonb NOT NULL DEFAULT '{}'::jsonb,
    result jsonb NOT NULL DEFAULT '{}'::jsonb,
    error text,
    started_at timestamptz,
    finished_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX commander_bot_tasks_conversation_idx ON commander_bot_tasks(conversation_id, created_at);

CREATE TABLE commander_bot_runs (
    id uuid PRIMARY KEY,
    conversation_id uuid NOT NULL REFERENCES commander_bot_conversations(id) ON DELETE CASCADE,
    task_id uuid NOT NULL REFERENCES commander_bot_tasks(id) ON DELETE CASCADE,
    agent_id text NOT NULL CHECK (agent_id IN ('commander','business_researcher')),
    status text NOT NULL CHECK (status IN ('running','completed','failed','interrupted')),
    input jsonb NOT NULL DEFAULT '{}'::jsonb,
    output jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    finished_at timestamptz
);
CREATE INDEX commander_bot_runs_task_idx ON commander_bot_runs(task_id, created_at);

CREATE TABLE commander_bot_messages (
    id uuid PRIMARY KEY,
    conversation_id uuid NOT NULL REFERENCES commander_bot_conversations(id) ON DELETE CASCADE,
    task_id uuid REFERENCES commander_bot_tasks(id) ON DELETE CASCADE,
    sender text NOT NULL CHECK (sender IN ('user','commander','business_researcher')),
    recipient text NOT NULL CHECK (recipient IN ('user','commander','business_researcher')),
    kind text NOT NULL CHECK (kind IN ('user_input','agent_request','commander_question','action_result','approval_required','action_decision','final_result')),
    body jsonb NOT NULL DEFAULT '{}'::jsonb,
    request_id uuid UNIQUE,
    sequence bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX commander_bot_messages_conversation_idx ON commander_bot_messages(conversation_id, sequence);

CREATE TABLE commander_bot_actions (
    id uuid PRIMARY KEY,
    conversation_id uuid NOT NULL REFERENCES commander_bot_conversations(id) ON DELETE CASCADE,
    task_id uuid NOT NULL REFERENCES commander_bot_tasks(id) ON DELETE CASCADE,
    requested_by text NOT NULL CHECK (requested_by IN ('commander','business_researcher')),
    action_type text NOT NULL,
    mode text NOT NULL CHECK (mode IN ('allowed','approval_required','denied')),
    status text NOT NULL CHECK (status IN ('pending','approved','rejected','executed','denied')),
    reason text NOT NULL,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    decided_at timestamptz
);
CREATE INDEX commander_bot_actions_conversation_idx ON commander_bot_actions(conversation_id, created_at);

COMMIT;
