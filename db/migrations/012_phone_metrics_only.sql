BEGIN;

-- Keep historical rows byte-for-byte for PTW's preservation contract while
-- rejecting every new or updated Post workspace outside the active registry.
ALTER TABLE universal_studio_workspaces
    DROP CONSTRAINT universal_studio_workspaces_template_id_check;

ALTER TABLE universal_studio_workspaces
    ADD CONSTRAINT post_studio_workspaces_template_id_check
    CHECK (template_id = 'phone_metrics') NOT VALID;

COMMIT;
