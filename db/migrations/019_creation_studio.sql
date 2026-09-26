BEGIN;

-- Natal Studio draft sessions; canonical Briefs retain their existing graph authority.
CREATE TABLE creation_studio_records (
    kind text NOT NULL CHECK (kind IN ('run','version','request','builtin')),
    record_key text NOT NULL CHECK (length(record_key) BETWEEN 1 AND 160),
    revision integer NOT NULL CHECK (revision > 0),
    CHECK (kind = 'run' OR revision = 1),
    state_sha256 text NOT NULL CHECK (state_sha256 ~ '^[0-9a-f]{64}$'),
    payload text NOT NULL CHECK (octet_length(payload) <= 256000 AND jsonb_typeof(payload::jsonb) = 'object'),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (kind,record_key,revision)
);
CREATE TABLE creation_studio_media (
    sha256 text PRIMARY KEY CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    png bytea NOT NULL CHECK (octet_length(png) BETWEEN 1 AND 12582912)
);
CREATE FUNCTION creation_studio_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Creation Studio history and previews are immutable'; END $$;
CREATE TRIGGER creation_studio_records_immutable BEFORE UPDATE OR DELETE ON creation_studio_records
    FOR EACH ROW EXECUTE FUNCTION creation_studio_immutable();
CREATE TRIGGER creation_studio_media_immutable BEFORE UPDATE OR DELETE ON creation_studio_media
    FOR EACH ROW EXECUTE FUNCTION creation_studio_immutable();

COMMIT;
