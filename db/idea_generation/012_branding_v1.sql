CREATE TABLE IF NOT EXISTS brand_runs (
    id uuid PRIMARY KEY,
    source_laval_run_id uuid NOT NULL REFERENCES laval_runs(id) ON DELETE RESTRICT,
    pipeline_version text NOT NULL DEFAULT 'branding_v1' CHECK (pipeline_version='branding_v1'),
    status text NOT NULL CHECK (status IN ('pending','running','paused','awaiting_review','completed','failed','cancelled')),
    current_stage text NOT NULL,
    source_snapshot_hash text NOT NULL CHECK (length(source_snapshot_hash)=64),
    source_snapshot jsonb NOT NULL CHECK (jsonb_typeof(source_snapshot)='object'),
    constraints_text text NOT NULL DEFAULT '',
    reference_urls jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(reference_urls)='array'),
    manual_transcripts jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(manual_transcripts)='array'),
    provider_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(provider_snapshot)='object'),
    selected_direction_id uuid,
    commander_brand_kit_id uuid,
    source_stale boolean NOT NULL DEFAULT false,
    error_text text,
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    completed_at timestamptz
);

CREATE INDEX IF NOT EXISTS brand_runs_status_idx ON brand_runs(status,updated_at DESC);
CREATE INDEX IF NOT EXISTS brand_runs_source_idx ON brand_runs(source_laval_run_id,created_at DESC);

CREATE TABLE IF NOT EXISTS brand_stage_runs (
    run_id uuid NOT NULL REFERENCES brand_runs(id) ON DELETE CASCADE,
    stage text NOT NULL,
    ordinal integer NOT NULL CHECK (ordinal BETWEEN 0 AND 9),
    status text NOT NULL CHECK (status IN ('pending','running','completed','failed','paused','stale')),
    input_hash text,
    attempt integer NOT NULL DEFAULT 0 CHECK (attempt>=0),
    provider text,
    model text,
    artifact jsonb,
    metrics jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(metrics)='object'),
    cost jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(cost)='object'),
    error jsonb,
    started_at timestamptz,
    completed_at timestamptz,
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY(run_id,stage),
    UNIQUE(run_id,ordinal),
    CHECK (status<>'completed' OR artifact IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS brand_sources (
    id uuid PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES brand_runs(id) ON DELETE CASCADE,
    source_type text NOT NULL CHECK (source_type IN ('idea','competitor_page','youtube','youtube_comment','manual_reference','manual_transcript')),
    source_url text NOT NULL,
    title text NOT NULL,
    excerpt text NOT NULL DEFAULT '',
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(metadata)='object'),
    commander_source_id uuid,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(run_id,source_type,source_url)
);

CREATE INDEX IF NOT EXISTS brand_sources_run_idx ON brand_sources(run_id,source_type,created_at);

CREATE TABLE IF NOT EXISTS brand_directions (
    id uuid PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES brand_runs(id) ON DELETE CASCADE,
    ordinal integer NOT NULL CHECK (ordinal BETWEEN 1 AND 3),
    name text NOT NULL,
    manifest jsonb NOT NULL CHECK (jsonb_typeof(manifest)='object'),
    evaluation jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(evaluation)='object'),
    status text NOT NULL CHECK (status IN ('draft','evaluated','awaiting_review','reviewed','approved','superseded')),
    commander_direction_id uuid,
    creative_id uuid,
    artifact_id uuid,
    artifact_digest text CHECK (artifact_digest IS NULL OR length(artifact_digest)=64),
    logo_path text,
    latest_feedback_id uuid,
    reviewed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(run_id,ordinal),
    UNIQUE(run_id,name)
);

ALTER TABLE brand_runs DROP CONSTRAINT IF EXISTS brand_runs_selected_direction_fk;
ALTER TABLE brand_runs ADD CONSTRAINT brand_runs_selected_direction_fk
  FOREIGN KEY(selected_direction_id) REFERENCES brand_directions(id) ON DELETE RESTRICT;

CREATE TABLE IF NOT EXISTS brand_kits (
    id uuid PRIMARY KEY,
    run_id uuid NOT NULL UNIQUE REFERENCES brand_runs(id) ON DELETE RESTRICT,
    direction_id uuid NOT NULL UNIQUE REFERENCES brand_directions(id) ON DELETE RESTRICT,
    commander_brand_kit_id uuid NOT NULL UNIQUE,
    previous_commander_brand_kit_id uuid,
    manifest jsonb NOT NULL CHECK (jsonb_typeof(manifest)='object'),
    zip_digest text NOT NULL CHECK (length(zip_digest)=64),
    zip_path text NOT NULL,
    status text NOT NULL CHECK (status IN ('approved','superseded','stale')),
    approved_by text NOT NULL,
    approved_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE IF NOT EXISTS brand_provider_tasks (
    id uuid PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES brand_runs(id) ON DELETE CASCADE,
    stage text NOT NULL,
    item_key text NOT NULL,
    provider text NOT NULL,
    status text NOT NULL CHECK (status IN ('reserved','running','completed','failed','unknown')),
    request_hash text NOT NULL CHECK (length(request_hash)=64),
    response_digest text CHECK (response_digest IS NULL OR length(response_digest)=64),
    response jsonb,
    remote_request_id text,
    request_count integer NOT NULL DEFAULT 0 CHECK (request_count>=0),
    input_tokens integer NOT NULL DEFAULT 0 CHECK (input_tokens>=0),
    output_tokens integer NOT NULL DEFAULT 0 CHECK (output_tokens>=0),
    amount_usd numeric(12,6) NOT NULL DEFAULT 0 CHECK (amount_usd>=0),
    error_text text,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(run_id,stage,item_key)
);

CREATE TABLE IF NOT EXISTS brand_cost_events (
    id uuid PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES brand_runs(id) ON DELETE CASCADE,
    stage text NOT NULL,
    provider text NOT NULL,
    operation text NOT NULL,
    request_count integer NOT NULL DEFAULT 0 CHECK (request_count>=0),
    input_tokens integer NOT NULL DEFAULT 0 CHECK (input_tokens>=0),
    output_tokens integer NOT NULL DEFAULT 0 CHECK (output_tokens>=0),
    amount_usd numeric(12,6) NOT NULL DEFAULT 0 CHECK (amount_usd>=0),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(metadata)='object'),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE IF NOT EXISTS brand_run_actions (
    id uuid PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES brand_runs(id) ON DELETE CASCADE,
    action text NOT NULL,
    actor text NOT NULL,
    details jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(details)='object'),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX IF NOT EXISTS brand_actions_run_idx ON brand_run_actions(run_id,created_at DESC);

CREATE OR REPLACE FUNCTION brand_reject_append_only_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'branding audit rows are append-only';
END;
$$;

DROP TRIGGER IF EXISTS brand_cost_events_append_only ON brand_cost_events;
CREATE TRIGGER brand_cost_events_append_only BEFORE UPDATE OR DELETE ON brand_cost_events
FOR EACH ROW EXECUTE FUNCTION brand_reject_append_only_mutation();

DROP TRIGGER IF EXISTS brand_run_actions_append_only ON brand_run_actions;
CREATE TRIGGER brand_run_actions_append_only BEFORE UPDATE OR DELETE ON brand_run_actions
FOR EACH ROW EXECUTE FUNCTION brand_reject_append_only_mutation();

CREATE OR REPLACE FUNCTION mark_brand_kits_stale_for_idea()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE changed_run_id uuid;
BEGIN
  IF TG_TABLE_NAME='laval_runs' THEN
    changed_run_id := COALESCE(NEW.id, OLD.id);
  ELSE
    changed_run_id := COALESCE(NEW.run_id, OLD.run_id);
  END IF;
  UPDATE brand_runs
     SET source_stale=TRUE,updated_at=clock_timestamp()
   WHERE source_laval_run_id=changed_run_id;
  UPDATE brand_kits k
     SET status='stale'
    FROM brand_runs b
   WHERE k.run_id=b.id AND b.source_laval_run_id=changed_run_id
     AND k.status='approved';
  IF to_regclass('commander_entities') IS NOT NULL THEN
    EXECUTE $query$
      UPDATE commander_entities e
         SET attributes=jsonb_set(e.attributes,'{status}','"stale"'::jsonb,TRUE)
        FROM brand_kits k JOIN brand_runs b ON b.id=k.run_id
       WHERE e.id=k.commander_brand_kit_id AND b.source_laval_run_id=$1
    $query$ USING changed_run_id;
  END IF;
  RETURN COALESCE(NEW, OLD);
END;
$$;

DROP TRIGGER IF EXISTS laval_runs_stale_brand_kits ON laval_runs;
CREATE TRIGGER laval_runs_stale_brand_kits
AFTER UPDATE OF completed_at,pipeline_version,status ON laval_runs
FOR EACH ROW WHEN (OLD.status='completed') EXECUTE FUNCTION mark_brand_kits_stale_for_idea();

DROP TRIGGER IF EXISTS laval_owner_ideas_stale_brand_kits ON laval_owner_ideas;
CREATE TRIGGER laval_owner_ideas_stale_brand_kits
AFTER INSERT OR UPDATE OR DELETE ON laval_owner_ideas
FOR EACH ROW EXECUTE FUNCTION mark_brand_kits_stale_for_idea();

DROP TRIGGER IF EXISTS laval_theses_stale_brand_kits ON laval_product_theses;
CREATE TRIGGER laval_theses_stale_brand_kits
AFTER INSERT OR UPDATE OR DELETE ON laval_product_theses
FOR EACH ROW EXECUTE FUNCTION mark_brand_kits_stale_for_idea();

DROP TRIGGER IF EXISTS laval_mechanisms_stale_brand_kits ON laval_product_mechanisms;
CREATE TRIGGER laval_mechanisms_stale_brand_kits
AFTER INSERT OR UPDATE OR DELETE ON laval_product_mechanisms
FOR EACH ROW EXECUTE FUNCTION mark_brand_kits_stale_for_idea();

DROP TRIGGER IF EXISTS laval_competitors_stale_brand_kits ON laval_competitors;
CREATE TRIGGER laval_competitors_stale_brand_kits
AFTER INSERT OR UPDATE OR DELETE ON laval_competitors
FOR EACH ROW EXECUTE FUNCTION mark_brand_kits_stale_for_idea();

DROP TRIGGER IF EXISTS laval_evidence_stale_brand_kits ON laval_evidence;
CREATE TRIGGER laval_evidence_stale_brand_kits
AFTER INSERT OR UPDATE OR DELETE ON laval_evidence
FOR EACH ROW EXECUTE FUNCTION mark_brand_kits_stale_for_idea();
