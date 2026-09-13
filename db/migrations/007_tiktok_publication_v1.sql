BEGIN;

ALTER TABLE commander_entities DROP CONSTRAINT commander_entities_kind_check;
ALTER TABLE commander_entities ADD CONSTRAINT commander_entities_kind_check CHECK (kind IN (
    'source','validation_project','product_brief','human_feedback','weight_update',
    'studio_workspace','studio_asset','studio_version','studio_generation_run',
    'studio_edit_checkpoint','studio_learning_run','studio_skill_snapshot',
    'studio_learning_proposal','studio_learning_decision',
    'landing_workspace','landing_asset','landing_version','landing_generation_run',
    'landing_edit_checkpoint','landing_learning_run','landing_skill_snapshot',
    'landing_learning_proposal','landing_learning_decision',
    'landing_publication','landing_publication_event',
    'meta_ads_preset_version','meta_ads_experiment','meta_ads_audience_version',
    'meta_ads_deployment','meta_ads_stage_run','meta_ads_status_snapshot',
    'meta_ads_control_action','meta_ads_insight_snapshot','meta_ads_recommendation',
    'instagram_publication','instagram_publication_attempt',
    'tiktok_publication','tiktok_publication_attempt'
));

CREATE TABLE tiktok_account_connections (
    connection_key text PRIMARY KEY CHECK (connection_key = 'natal_cast'),
    open_id text,
    username text,
    nickname text,
    scopes text[] NOT NULL DEFAULT '{}',
    token_nonce bytea,
    token_ciphertext bytea,
    access_expires_at timestamptz,
    refresh_expires_at timestamptz,
    connected boolean NOT NULL DEFAULT false,
    connected_at timestamptz,
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK (connected = false OR (
        open_id IS NOT NULL AND username IS NOT NULL AND
        token_nonce IS NOT NULL AND token_ciphertext IS NOT NULL AND
        access_expires_at IS NOT NULL AND refresh_expires_at IS NOT NULL
    ))
);

CREATE TABLE tiktok_oauth_states (
    state_sha256 char(64) PRIMARY KEY,
    requested_by text NOT NULL,
    return_to text NOT NULL,
    expires_at timestamptz NOT NULL,
    consumed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE tiktok_publications (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    project_id uuid NOT NULL REFERENCES validation_projects(entity_id) ON DELETE RESTRICT,
    source_creative_id uuid NOT NULL,
    source_version_id uuid NOT NULL,
    request_id uuid NOT NULL UNIQUE,
    request_sha256 char(64) NOT NULL,
    specification jsonb NOT NULL,
    state jsonb NOT NULL CHECK (state->>'phase' IN (
        'queued','preparing','publishing','published','published_unresolved','uncertain','failed'
    )),
    delivery_jpeg bytea NOT NULL CHECK (octet_length(delivery_jpeg) BETWEEN 1 AND 20971520),
    media_token_sha256 char(64) NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY(source_creative_id,project_id)
        REFERENCES universal_studio_workspaces(entity_id,project_id) ON DELETE RESTRICT,
    FOREIGN KEY(source_version_id,source_creative_id)
        REFERENCES universal_studio_versions(entity_id,workspace_id) ON DELETE RESTRICT
);
CREATE INDEX tiktok_publications_project_idx
    ON tiktok_publications(project_id,created_at DESC);

CREATE TABLE tiktok_publication_attempts (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    publication_id uuid NOT NULL REFERENCES tiktok_publications(entity_id) ON DELETE RESTRICT,
    record jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE FUNCTION ptw_protect_tiktok_connection() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.open_id IS NOT NULL AND NEW.open_id IS DISTINCT FROM OLD.open_id THEN
        RAISE EXCEPTION 'TikTok account identity cannot be replaced';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER tiktok_connection_protected BEFORE UPDATE ON tiktok_account_connections
    FOR EACH ROW EXECUTE FUNCTION ptw_protect_tiktok_connection();

CREATE FUNCTION ptw_protect_tiktok_publication() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF (to_jsonb(NEW) - 'state') IS DISTINCT FROM (to_jsonb(OLD) - 'state') THEN
        RAISE EXCEPTION 'TikTok publication input is immutable';
    END IF;
    IF OLD.state->>'transfer_id' IS NOT NULL
       AND NEW.state->>'transfer_id' IS DISTINCT FROM OLD.state->>'transfer_id'
       OR OLD.state->>'transfer_started' = 'true'
       AND NEW.state->>'transfer_started' IS DISTINCT FROM 'true'
       OR OLD.state->>'commit_started' = 'true'
       AND NEW.state->>'commit_started' IS DISTINCT FROM 'true' THEN
        RAISE EXCEPTION 'TikTok publication identity cannot be replaced';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER tiktok_publications_protected BEFORE UPDATE ON tiktok_publications
    FOR EACH ROW EXECUTE FUNCTION ptw_protect_tiktok_publication();
CREATE TRIGGER tiktok_attempts_immutable BEFORE UPDATE OR DELETE ON tiktok_publication_attempts
    FOR EACH ROW EXECUTE FUNCTION ptw_reject_immutable_mutation();

COMMIT;
