BEGIN;

ALTER TABLE commander_creative_reviews
  ALTER COLUMN rating DROP NOT NULL;

COMMIT;
