BEGIN;
ALTER TABLE landing_assets DROP CONSTRAINT landing_assets_slot_check;
ALTER TABLE landing_assets ADD CONSTRAINT landing_assets_slot_check CHECK (slot IN (
  'hero_visual','visual_break_visual','app_screen_1','app_screen_2','app_screen_3','walkthrough_visual'
));
ALTER TABLE landing_generation_runs DROP CONSTRAINT landing_generation_runs_stage_check;
ALTER TABLE landing_generation_runs ADD CONSTRAINT landing_generation_runs_stage_check CHECK (stage IN (
  'composition','hero_visual','visual_break_visual','app_screen_1','app_screen_2','app_screen_3','walkthrough_visual'
));
COMMIT;
