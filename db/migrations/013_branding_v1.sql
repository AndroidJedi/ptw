BEGIN;

ALTER TYPE commander_entity_kind ADD VALUE IF NOT EXISTS 'brand_direction';
ALTER TYPE commander_entity_kind ADD VALUE IF NOT EXISTS 'brand_kit';

ALTER TABLE commander_ad_batches
  ADD COLUMN IF NOT EXISTS brand_kit_id uuid REFERENCES commander_entities(id);

CREATE INDEX IF NOT EXISTS commander_ad_batches_brand_kit_idx
  ON commander_ad_batches (brand_kit_id) WHERE brand_kit_id IS NOT NULL;

COMMIT;
