BEGIN;
ALTER TABLE landing_workspaces ADD COLUMN template_reference jsonb;
ALTER TABLE landing_workspaces ADD CONSTRAINT landing_template_reference_shape CHECK (
    template_reference IS NULL OR (jsonb_typeof(template_reference) = 'object'
      AND template_reference ?& ARRAY['template_id','template_version','template_sha256'])
);
ALTER TABLE landing_assets DROP CONSTRAINT landing_assets_slot_check;
ALTER TABLE landing_assets ADD CONSTRAINT landing_assets_slot_check CHECK (slot IN (
  'hero_visual','visual_break_visual','app_screen_1','app_screen_2','app_screen_3'
));
ALTER TABLE landing_generation_runs DROP CONSTRAINT landing_generation_runs_stage_check;
ALTER TABLE landing_generation_runs ADD CONSTRAINT landing_generation_runs_stage_check CHECK (stage IN (
  'composition','hero_visual','visual_break_visual','app_screen_1','app_screen_2','app_screen_3'
));
ALTER TABLE landing_assets DROP CONSTRAINT landing_assets_landing_id_content_sha256_key;
ALTER TABLE landing_assets ADD CONSTRAINT landing_assets_landing_slot_digest_key UNIQUE(landing_id,slot,content_sha256);
COMMIT;
