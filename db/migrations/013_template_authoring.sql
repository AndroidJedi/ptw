BEGIN;

-- Global owner-only design authority. No Project or historical template rows change.
CREATE TABLE template_authoring_records (
    kind text NOT NULL CHECK (kind IN ('run','version','request','builtin')),
    record_key text NOT NULL CHECK (length(record_key) BETWEEN 1 AND 160),
    revision integer NOT NULL CHECK (revision > 0),
    CHECK (kind = 'run' OR revision = 1),
    state_sha256 text NOT NULL CHECK (state_sha256 ~ '^[0-9a-f]{64}$'),
    payload text NOT NULL CHECK (octet_length(payload) <= 256000 AND jsonb_typeof(payload::jsonb) = 'object'),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (kind,record_key,revision)
);
CREATE TABLE template_authoring_media (
    sha256 text PRIMARY KEY CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    png bytea NOT NULL CHECK (octet_length(png) BETWEEN 1 AND 12582912)
);
CREATE FUNCTION template_authoring_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Template history and previews are immutable'; END $$;
CREATE TRIGGER template_authoring_records_immutable BEFORE UPDATE OR DELETE ON template_authoring_records
    FOR EACH ROW EXECUTE FUNCTION template_authoring_immutable();
CREATE TRIGGER template_authoring_media_immutable BEFORE UPDATE OR DELETE ON template_authoring_media
    FOR EACH ROW EXECUTE FUNCTION template_authoring_immutable();

COMMIT;
