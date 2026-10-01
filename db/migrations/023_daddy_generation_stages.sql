BEGIN;

-- Daddy records each completed provider phase and the phase of a failed run.
-- Migration 022 added its template identity but left the original stage guard.
ALTER TABLE studio_generation_runs
    DROP CONSTRAINT studio_generation_runs_stage_check;
ALTER TABLE studio_generation_runs
    ADD CONSTRAINT studio_generation_runs_stage_check CHECK (stage IN (
        'composition', 'phone_image',
        'daddy_strategy', 'daddy_composition', 'daddy_assets',
        'daddy_asset:scene', 'daddy_asset:screen', 'daddy_asset:subject',
        'daddy_asset:feature', 'daddy_asset:prop_one', 'daddy_asset:prop_two',
        'daddy_review', 'daddy_polish', 'daddy_ready', 'daddy_needs_review'
    ));

COMMIT;
