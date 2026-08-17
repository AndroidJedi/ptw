ALTER TABLE missions
    ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS activated_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS deadline_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS name_i18n JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE UNIQUE INDEX IF NOT EXISTS missions_one_active_idx
    ON missions (is_active) WHERE is_active;

ALTER TABLE ideas
    ADD COLUMN IF NOT EXISTS title_i18n JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS one_liner_i18n JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE missions DROP CONSTRAINT IF EXISTS missions_deadline_after_activation;
ALTER TABLE missions ADD CONSTRAINT missions_deadline_after_activation CHECK (
    activated_at IS NULL OR deadline_at IS NULL OR deadline_at > activated_at
);

ALTER TABLE missions DROP CONSTRAINT IF EXISTS missions_name_i18n_shape;
ALTER TABLE missions ADD CONSTRAINT missions_name_i18n_shape CHECK (
    name_i18n = '{}'::jsonb OR
    (name_i18n ? 'en' AND name_i18n ? 'uk')
);

ALTER TABLE ideas DROP CONSTRAINT IF EXISTS ideas_title_i18n_shape;
ALTER TABLE ideas ADD CONSTRAINT ideas_title_i18n_shape CHECK (
    title_i18n = '{}'::jsonb OR
    (title_i18n ? 'en' AND title_i18n ? 'uk')
);

ALTER TABLE ideas DROP CONSTRAINT IF EXISTS ideas_one_liner_i18n_shape;
ALTER TABLE ideas ADD CONSTRAINT ideas_one_liner_i18n_shape CHECK (
    one_liner_i18n = '{}'::jsonb OR
    (one_liner_i18n ? 'en' AND one_liner_i18n ? 'uk')
);
