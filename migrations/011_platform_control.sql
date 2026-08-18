CREATE TABLE IF NOT EXISTS platform_control (
    singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton),
    emergency_stop BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by TEXT NOT NULL DEFAULT 'migration'
);

INSERT INTO platform_control(singleton, emergency_stop, updated_by)
VALUES(TRUE, FALSE, 'migration:011_platform_control')
ON CONFLICT(singleton) DO NOTHING;
