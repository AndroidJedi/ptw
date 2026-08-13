BEGIN;

ALTER TYPE commander_entity_kind ADD VALUE IF NOT EXISTS 'human_feedback';
ALTER TYPE commander_entity_kind ADD VALUE IF NOT EXISTS 'weight_update';
ALTER TYPE commander_relation_type ADD VALUE IF NOT EXISTS 'evaluates';
ALTER TYPE commander_relation_type ADD VALUE IF NOT EXISTS 'adjusts';

COMMIT;
