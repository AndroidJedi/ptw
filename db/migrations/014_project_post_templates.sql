BEGIN;

-- Preserve historical workspaces while allowing accepted authored Post IDs.
-- Exact surface/version/digest resolution is enforced by the runtime registry.
ALTER TABLE universal_studio_workspaces
    DROP CONSTRAINT post_studio_workspaces_template_id_check;
ALTER TABLE universal_studio_workspaces
    ADD CONSTRAINT post_studio_workspaces_template_id_check
    CHECK (template_id = 'phone_metrics' OR template_id ~ '^design_[a-f0-9]{20}$') NOT VALID;

COMMIT;
