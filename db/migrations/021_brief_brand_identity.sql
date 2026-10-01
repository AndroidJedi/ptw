-- Accept new V3 reservations without changing any stored document or snapshot.
ALTER TABLE product_briefs DROP CONSTRAINT product_briefs_generation_settings_shape;
ALTER TABLE product_briefs ADD CONSTRAINT product_briefs_generation_settings_shape
    CHECK (generation_settings IS NULL OR (
        jsonb_typeof(generation_settings) = 'object'
        AND generation_settings->>'marketing_approach' IN ('benefit_led','identity_led')
        AND generation_settings->>'output_schema_version' IN ('2','3')
        AND generation_settings->>'policy_version' = '1'
        AND jsonb_typeof(generation_settings->'policy_text') = 'string'
        AND octet_length(generation_settings->>'policy_text') BETWEEN 1 AND 12000
        AND generation_settings->>'policy_sha256' ~ '^[0-9a-f]{64}$'
        AND generation_settings ?& ARRAY['marketing_approach','policy_version','policy_sha256','policy_text','output_schema_version']
    ) IS TRUE);
-- The existing immutability trigger remains in force, including historical NULLs.
