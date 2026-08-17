BEGIN;

CREATE TABLE commander_creative_reviews (
  feedback_id uuid PRIMARY KEY REFERENCES commander_entities(id),
  creative_id uuid NOT NULL REFERENCES commander_entities(id),
  artifact_digest text NOT NULL CHECK (length(artifact_digest) = 64),
  rating integer NOT NULL CHECK (rating BETWEEN 1 AND 5),
  overall_comment text NOT NULL DEFAULT '',
  predicted_ctr numeric(8,4) CHECK (predicted_ctr BETWEEN 0 AND 100),
  annotations jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(annotations) = 'array'),
  supersedes_feedback_id uuid REFERENCES commander_creative_reviews(feedback_id),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX commander_creative_reviews_creative_idx
  ON commander_creative_reviews (creative_id, created_at DESC);

CREATE OR REPLACE FUNCTION commander_reject_review_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'commander creative reviews are append-only';
END;
$$;

CREATE TRIGGER commander_creative_reviews_append_only
BEFORE UPDATE OR DELETE ON commander_creative_reviews
FOR EACH ROW EXECUTE FUNCTION commander_reject_review_mutation();

COMMIT;
