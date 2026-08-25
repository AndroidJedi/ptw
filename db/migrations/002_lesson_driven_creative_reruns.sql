BEGIN;

ALTER TABLE creative_batches
    DROP CONSTRAINT creative_batches_brief_id_key;

ALTER TABLE creative_batches
    ADD COLUMN request_id uuid,
    ADD COLUMN rerun_of_batch_id uuid REFERENCES creative_batches(entity_id) ON DELETE RESTRICT,
    ADD COLUMN requested_by text NOT NULL DEFAULT 'brief-approval',
    ADD COLUMN skill_sha256 char(64),
    ADD CONSTRAINT creative_batches_request_id_key UNIQUE (request_id),
    ADD CONSTRAINT creative_batches_rerun_of_batch_id_key UNIQUE (rerun_of_batch_id),
    ADD CONSTRAINT creative_batches_rerun_request_check CHECK (
        (rerun_of_batch_id IS NULL AND request_id IS NULL)
        OR (rerun_of_batch_id IS NOT NULL AND request_id IS NOT NULL AND skill_sha256 IS NOT NULL)
    );

CREATE UNIQUE INDEX creative_batches_initial_brief_key
    ON creative_batches(brief_id)
    WHERE rerun_of_batch_id IS NULL;

ALTER TABLE commander_relationships
    DROP CONSTRAINT commander_relationships_relation_check,
    ADD CONSTRAINT commander_relationships_relation_check CHECK (relation IN (
        'contains','derived_from','supersedes','rerun_of','evaluates','adjusts'
    ));

COMMIT;
