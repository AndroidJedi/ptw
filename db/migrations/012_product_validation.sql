BEGIN;

ALTER TYPE commander_entity_kind ADD VALUE IF NOT EXISTS 'product_mechanism';
ALTER TYPE commander_entity_kind ADD VALUE IF NOT EXISTS 'validation_workspace';

COMMIT;

BEGIN;

CREATE UNIQUE INDEX commander_validation_workspace_hypothesis_idx
  ON commander_entities ((attributes->>'hypothesis_id'))
  WHERE kind = 'validation_workspace' AND attributes ? 'hypothesis_id';

COMMIT;
