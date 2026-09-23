BEGIN;

ALTER TABLE validation_projects
    ADD COLUMN deleted_at timestamptz,
    ADD COLUMN deleted_by text,
    ADD COLUMN delete_request_id uuid;

ALTER TABLE validation_projects
    ADD CONSTRAINT validation_projects_delete_state_check CHECK (
        (deleted_at IS NULL AND deleted_by IS NULL AND delete_request_id IS NULL)
        OR
        (deleted_at IS NOT NULL AND deleted_by IS NOT NULL AND delete_request_id IS NOT NULL)
    ),
    ADD CONSTRAINT validation_projects_delete_request_unique UNIQUE(delete_request_id);

CREATE INDEX validation_projects_active_updated_idx
    ON validation_projects(updated_at DESC)
    WHERE deleted_at IS NULL;

CREATE OR REPLACE FUNCTION ptw_protect_validation_project() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.request_id IS DISTINCT FROM OLD.request_id
       OR NEW.requested_by IS DISTINCT FROM OLD.requested_by
       OR NEW.created_at IS DISTINCT FROM OLD.created_at
       OR (
           NEW.owner_idea_source_id IS DISTINCT FROM OLD.owner_idea_source_id
           AND NOT (OLD.owner_idea_source_id IS NULL AND NEW.owner_idea_source_id IS NOT NULL)
       ) THEN
        RAISE EXCEPTION 'immutable Validation Project fields cannot change';
    END IF;
    IF OLD.deleted_at IS NOT NULL AND (
        NEW.deleted_at IS DISTINCT FROM OLD.deleted_at
        OR NEW.deleted_by IS DISTINCT FROM OLD.deleted_by
        OR NEW.delete_request_id IS DISTINCT FROM OLD.delete_request_id
        OR NEW.name IS DISTINCT FROM OLD.name
        OR NEW.name_source IS DISTINCT FROM OLD.name_source
        OR NEW.updated_at IS DISTINCT FROM OLD.updated_at
        OR NEW.owner_idea_source_id IS DISTINCT FROM OLD.owner_idea_source_id
    ) THEN
        RAISE EXCEPTION 'deleted Validation Project cannot change';
    END IF;
    IF OLD.deleted_at IS NULL AND NEW.deleted_at IS NOT NULL AND (
        NEW.deleted_by IS NULL OR NEW.delete_request_id IS NULL
    ) THEN
        RAISE EXCEPTION 'Validation Project deletion requires actor and request';
    END IF;
    RETURN NEW;
END $$;

COMMIT;
