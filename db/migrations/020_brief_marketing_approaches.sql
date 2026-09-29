-- Null marks an existing V1 reservation; no historical documents are rewritten.
ALTER TABLE product_briefs ADD COLUMN generation_settings jsonb;
ALTER TABLE product_briefs ADD CONSTRAINT product_briefs_generation_settings_shape
    CHECK (generation_settings IS NULL OR (
        jsonb_typeof(generation_settings) = 'object'
        AND generation_settings->>'marketing_approach' IN ('benefit_led','identity_led')
        AND generation_settings->>'output_schema_version' = '2'
        AND generation_settings->>'policy_version' = '1'
        AND jsonb_typeof(generation_settings->'policy_text') = 'string'
        AND octet_length(generation_settings->>'policy_text') BETWEEN 1 AND 12000
        AND generation_settings->>'policy_sha256' ~ '^[0-9a-f]{64}$'
        AND generation_settings ?& ARRAY['marketing_approach','policy_version','policy_sha256','policy_text','output_schema_version']
    ) IS TRUE);

CREATE FUNCTION ptw_protect_brief_generation_settings() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.generation_settings IS DISTINCT FROM OLD.generation_settings THEN
        RAISE EXCEPTION 'immutable Brief generation settings cannot change';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER product_briefs_generation_settings_protected BEFORE UPDATE ON product_briefs
FOR EACH ROW EXECUTE FUNCTION ptw_protect_brief_generation_settings();
