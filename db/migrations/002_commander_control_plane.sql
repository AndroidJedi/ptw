BEGIN;

ALTER TYPE commander_entity_kind ADD VALUE IF NOT EXISTS 'control_state';
ALTER TYPE commander_entity_kind ADD VALUE IF NOT EXISTS 'approval_request';
ALTER TYPE commander_entity_kind ADD VALUE IF NOT EXISTS 'approval_state';

COMMIT;
