BEGIN;

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
    RETURN NEW;
END $$;

COMMIT;
