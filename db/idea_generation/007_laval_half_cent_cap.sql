UPDATE laval_runs
SET max_spend_usd=LEAST(max_spend_usd, 0.005000),
    reserved_spend_usd=LEAST(reserved_spend_usd, 0.004000, 0.005000);

ALTER TABLE laval_runs
    ALTER COLUMN max_spend_usd SET DEFAULT 0.005000,
    ALTER COLUMN reserved_spend_usd SET DEFAULT 0.004000;

ALTER TABLE laval_runs
    DROP CONSTRAINT IF EXISTS laval_runs_max_spend_usd_check,
    DROP CONSTRAINT IF EXISTS laval_runs_reserved_spend_usd_check;

ALTER TABLE laval_runs
    ADD CONSTRAINT laval_runs_max_spend_usd_check
        CHECK (max_spend_usd >= 0 AND max_spend_usd <= 0.005000),
    ADD CONSTRAINT laval_runs_reserved_spend_usd_check
        CHECK (reserved_spend_usd >= 0 AND reserved_spend_usd <= max_spend_usd AND reserved_spend_usd <= 0.004000);
