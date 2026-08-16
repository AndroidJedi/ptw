BEGIN;

CREATE TABLE commander_ad_contexts (
  id bigserial PRIMARY KEY,
  code text NOT NULL UNIQUE CHECK (code ~ '^A(0[1-9]|10)$'),
  name text NOT NULL,
  prompt_text text NOT NULL,
  active boolean NOT NULL DEFAULT true,
  sort_order integer NOT NULL UNIQUE CHECK (sort_order BETWEEN 1 AND 10),
  version integer NOT NULL DEFAULT 1 CHECK (version > 0),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE commander_ad_context_revisions (
  id bigserial PRIMARY KEY,
  context_id bigint NOT NULL REFERENCES commander_ad_contexts(id) ON DELETE CASCADE,
  version integer NOT NULL CHECK (version > 0),
  name text NOT NULL,
  prompt_text text NOT NULL,
  changed_by text NOT NULL,
  change_note text,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  UNIQUE (context_id, version)
);

INSERT INTO commander_ad_contexts (code, name, prompt_text, sort_order)
VALUES
  ('A01', 'Pain and urgency',
   'Create an honest ad angle centered on the target customer''s most costly or urgent pain. Make the problem immediately recognizable without exaggerating it.', 1),
  ('A02', 'Desired outcome',
   'Create an ad angle centered on the concrete transformation the target customer wants. Keep the outcome credible for a pre-build concept.', 2),
  ('A03', 'Contrarian reframe',
   'Create a pattern-breaking ad angle that challenges a common assumption about the problem. The claim must remain supportable by the supplied idea.', 3),
  ('A04', 'Mechanism',
   'Create an ad angle that makes the proposed product mechanism easy to understand at a glance. Show how it works without implying unavailable features.', 4),
  ('A05', 'Concrete use case',
   'Create an ad angle around one specific customer situation and moment of use. Prefer concrete behavior over abstract promises.', 5),
  ('A06', 'Status quo comparison',
   'Create an ad angle comparing the concept with the customer''s current workaround. Do not invent competitor claims or unsupported statistics.', 6),
  ('A07', 'Identity and emotion',
   'Create an ad angle that connects the idea to the target customer''s identity, aspiration, or emotional tension while staying respectful and truthful.', 7),
  ('A08', 'Credibility and proof',
   'Create an ad angle that communicates credibility through specificity, process, or visible mechanism. Never fabricate testimonials, adoption, or measured results.', 8),
  ('A09', 'Pattern interrupt',
   'Create a visually distinctive curiosity angle that stops scrolling while still making the product category and value understandable.', 9),
  ('A10', 'Direct-response CTA',
   'Create a direct-response angle with a clear value proposition and an honest learn-more or waitlist call to action.', 10)
ON CONFLICT (code) DO NOTHING;

INSERT INTO commander_ad_context_revisions
  (context_id, version, name, prompt_text, changed_by, change_note)
SELECT id, version, name, prompt_text, 'seed', 'authoritative ad context v1'
FROM commander_ad_contexts
ON CONFLICT (context_id, version) DO NOTHING;

CREATE TABLE commander_ad_batches (
  campaign_id uuid PRIMARY KEY REFERENCES commander_entities(id),
  source_id uuid NOT NULL REFERENCES commander_entities(id),
  chat_id bigint NOT NULL,
  requested_by text NOT NULL,
  external_idea_id bigint NOT NULL,
  idempotency_key text NOT NULL UNIQUE,
  status text NOT NULL CHECK (
    status IN ('queued', 'generating', 'review_ready', 'awaiting_owner',
               'concluding', 'completed', 'failed')
  ),
  current_position integer CHECK (current_position BETWEEN 1 AND 10),
  attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
  last_error text,
  locked_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX commander_ad_batches_work_idx
  ON commander_ad_batches (status, updated_at);
CREATE INDEX commander_ad_batches_chat_idx
  ON commander_ad_batches (chat_id, created_at);
CREATE UNIQUE INDEX commander_ad_batches_one_review_idx
  ON commander_ad_batches (chat_id)
  WHERE status IN ('awaiting_owner', 'concluding');

CREATE TABLE commander_ad_slots (
  batch_id uuid NOT NULL REFERENCES commander_ad_batches(campaign_id) ON DELETE CASCADE,
  position integer NOT NULL CHECK (position BETWEEN 1 AND 10),
  context_code text NOT NULL CHECK (context_code ~ '^A(0[1-9]|10)$'),
  context_version integer NOT NULL CHECK (context_version > 0),
  context_name text NOT NULL,
  context_prompt text NOT NULL,
  status text NOT NULL DEFAULT 'pending' CHECK (
    status IN ('pending', 'spec_ready', 'generated', 'delivered',
               'conclusion_pending', 'concluding', 'completed', 'failed')
  ),
  spec jsonb,
  hypothesis_id uuid REFERENCES commander_entities(id),
  creative_id uuid UNIQUE REFERENCES commander_entities(id),
  artifact_id uuid UNIQUE REFERENCES commander_entities(id),
  visual_path text,
  final_path text,
  predicted_ctr numeric(8,4) CHECK (predicted_ctr BETWEEN 0 AND 100),
  rating integer CHECK (rating BETWEEN 1 AND 5),
  owner_comment text,
  feedback_id uuid UNIQUE REFERENCES commander_entities(id),
  conclusion_id uuid UNIQUE REFERENCES commander_entities(id),
  attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
  last_error text,
  locked_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (batch_id, position),
  UNIQUE (batch_id, context_code)
);

CREATE INDEX commander_ad_slots_work_idx
  ON commander_ad_slots (status, updated_at);

CREATE TABLE commander_ad_executions (
  id uuid PRIMARY KEY,
  batch_id uuid NOT NULL REFERENCES commander_ad_batches(campaign_id) ON DELETE CASCADE,
  position integer NOT NULL CHECK (position BETWEEN 1 AND 10),
  phase text NOT NULL CHECK (phase IN ('spec', 'image', 'conclusion')),
  attempt integer NOT NULL CHECK (attempt BETWEEN 1 AND 3),
  status text NOT NULL CHECK (status IN ('running', 'succeeded', 'failed')),
  model_name text,
  request_digest text NOT NULL CHECK (length(request_digest) = 64),
  response jsonb,
  error_text text,
  started_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  completed_at timestamptz
);

CREATE INDEX commander_ad_executions_batch_idx
  ON commander_ad_executions (batch_id, position, phase, started_at);

CREATE TABLE commander_ad_metric_imports (
  source_id uuid PRIMARY KEY REFERENCES commander_entities(id),
  batch_id uuid NOT NULL REFERENCES commander_ad_batches(campaign_id),
  source_system text NOT NULL,
  import_id text NOT NULL,
  captured_at timestamptz NOT NULL,
  attribution_window text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  UNIQUE (source_system, import_id)
);

COMMIT;
