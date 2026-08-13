BEGIN;

CREATE TYPE commander_entity_kind AS ENUM (
  'source', 'hypothesis', 'creative_component', 'creative', 'campaign',
  'audience', 'experiment', 'experiment_state', 'metric_set', 'observation',
  'insight', 'decision', 'knowledge_assertion', 'task', 'artifact', 'audit_event',
  'policy_evaluation'
);

CREATE TYPE commander_relation_type AS ENUM (
  'contains', 'derived_from', 'tests', 'tested_in', 'measured_by', 'supports',
  'contradicts', 'supersedes', 'adopted_as', 'generated', 'scheduled_by', 'state_of'
);

CREATE TABLE commander_entities (
  id uuid PRIMARY KEY,
  kind commander_entity_kind NOT NULL,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  attributes jsonb NOT NULL DEFAULT '{}'::jsonb,
  CHECK (jsonb_typeof(attributes) = 'object')
);

CREATE INDEX commander_entities_kind_created_idx
  ON commander_entities (kind, created_at DESC);
CREATE INDEX commander_entities_attributes_idx
  ON commander_entities USING gin (attributes jsonb_path_ops);

CREATE TABLE commander_relationships (
  id uuid PRIMARY KEY,
  source_id uuid NOT NULL REFERENCES commander_entities(id),
  relation commander_relation_type NOT NULL,
  target_id uuid NOT NULL REFERENCES commander_entities(id),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  attributes jsonb NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE (source_id, relation, target_id),
  CHECK (source_id <> target_id),
  CHECK (jsonb_typeof(attributes) = 'object')
);

CREATE INDEX commander_relationships_target_idx
  ON commander_relationships (target_id, relation);

CREATE TABLE commander_experiments (
  entity_id uuid PRIMARY KEY REFERENCES commander_entities(id),
  budget_minor bigint NOT NULL CHECK (budget_minor >= 0),
  approved_by text,
  policy_version integer NOT NULL,
  policy_digest text NOT NULL CHECK (length(policy_digest) = 64)
);

CREATE TABLE commander_experiment_states (
  entity_id uuid PRIMARY KEY REFERENCES commander_entities(id),
  experiment_id uuid NOT NULL REFERENCES commander_experiments(entity_id),
  state text NOT NULL CHECK (state IN ('draft', 'approved', 'running', 'completed', 'evaluated', 'cancelled')),
  previous_state text,
  occurred_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX commander_experiment_states_history_idx
  ON commander_experiment_states (experiment_id, occurred_at DESC);

CREATE TABLE commander_metric_values (
  metric_set_id uuid NOT NULL REFERENCES commander_entities(id),
  name text NOT NULL,
  value numeric NOT NULL,
  unit text NOT NULL DEFAULT 'ratio',
  PRIMARY KEY (metric_set_id, name)
);

CREATE TABLE commander_decisions (
  entity_id uuid PRIMARY KEY REFERENCES commander_entities(id),
  decision_key text NOT NULL,
  version integer NOT NULL CHECK (version > 0),
  action text NOT NULL,
  reasoning_summary text NOT NULL,
  confidence numeric(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  previous_decision_id uuid REFERENCES commander_decisions(entity_id),
  replacement_decision_id uuid REFERENCES commander_decisions(entity_id),
  UNIQUE (decision_key, version),
  CHECK (previous_decision_id IS NULL OR previous_decision_id <> entity_id),
  CHECK (replacement_decision_id IS NULL OR replacement_decision_id <> entity_id)
);

CREATE TABLE commander_external_aliases (
  system text NOT NULL,
  external_id text NOT NULL,
  entity_id uuid NOT NULL REFERENCES commander_entities(id),
  PRIMARY KEY (system, external_id)
);

CREATE TABLE commander_tasks (
  entity_id uuid PRIMARY KEY REFERENCES commander_entities(id),
  status text NOT NULL CHECK (status IN ('queued', 'running', 'blocked', 'completed', 'cancelled')),
  available_at timestamptz NOT NULL DEFAULT now(),
  attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
  idempotency_key text UNIQUE
);

CREATE TABLE commander_outbox (
  id uuid PRIMARY KEY,
  topic text NOT NULL,
  aggregate_id uuid REFERENCES commander_entities(id),
  payload jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  published_at timestamptz,
  attempts integer NOT NULL DEFAULT 0
);

CREATE INDEX commander_outbox_pending_idx
  ON commander_outbox (created_at) WHERE published_at IS NULL;

CREATE TABLE commander_policy_evaluations (
  id uuid PRIMARY KEY,
  command_id uuid,
  policy_version integer NOT NULL,
  policy_digest text NOT NULL CHECK (length(policy_digest) = 64),
  outcome text NOT NULL CHECK (outcome IN ('allow', 'deny', 'require_approval')),
  summary text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

COMMIT;
