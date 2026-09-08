BEGIN;

ALTER TABLE validation_projects ALTER COLUMN owner_idea_source_id DROP NOT NULL;

ALTER TABLE commander_entities DROP CONSTRAINT commander_entities_kind_check;
ALTER TABLE commander_entities ADD CONSTRAINT commander_entities_kind_check CHECK (kind IN (
    'source','validation_project','product_brief','human_feedback','weight_update',
    'studio_workspace','studio_asset','studio_version','studio_generation_run',
    'studio_edit_checkpoint','studio_learning_run','studio_skill_snapshot',
    'studio_learning_proposal','studio_learning_decision',
    'landing_workspace','landing_asset','landing_version','landing_generation_run',
    'landing_edit_checkpoint','landing_learning_run','landing_skill_snapshot',
    'landing_learning_proposal','landing_learning_decision',
    'landing_publication','landing_publication_event',
    'meta_ads_preset_version','meta_ads_experiment','meta_ads_audience_version',
    'meta_ads_deployment','meta_ads_stage_run','meta_ads_status_snapshot'
));

CREATE TABLE landing_publications (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    project_id uuid NOT NULL UNIQUE REFERENCES validation_projects(entity_id) ON DELETE RESTRICT,
    namespace text NOT NULL CHECK (namespace IN ('ai','la','wa')),
    slug text NOT NULL CHECK (
        length(slug) BETWEEN 3 AND 63
        AND slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'
    ),
    status text NOT NULL CHECK (status IN ('published','unpublished')),
    current_event_id uuid,
    requested_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(namespace,slug),
    UNIQUE(entity_id,project_id)
);

CREATE TABLE landing_publication_events (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    publication_id uuid NOT NULL REFERENCES landing_publications(entity_id) ON DELETE RESTRICT,
    request_id uuid NOT NULL UNIQUE,
    request_sha256 char(64) NOT NULL,
    sequence integer NOT NULL CHECK (sequence > 0),
    action text NOT NULL CHECK (action IN ('publish','unpublish')),
    landing_id uuid REFERENCES landing_workspaces(entity_id) ON DELETE RESTRICT,
    landing_version_id uuid REFERENCES landing_versions(entity_id) ON DELETE RESTRICT,
    landing_version integer,
    landing_version_sha256 char(64),
    requested_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(entity_id,publication_id),
    UNIQUE(publication_id,sequence),
    CHECK (
        (action='publish' AND landing_id IS NOT NULL AND landing_version_id IS NOT NULL
          AND landing_version IS NOT NULL AND landing_version > 0
          AND landing_version_sha256 IS NOT NULL)
        OR
        (action='unpublish' AND landing_id IS NULL AND landing_version_id IS NULL
          AND landing_version IS NULL AND landing_version_sha256 IS NULL)
    )
);

ALTER TABLE landing_publications ADD CONSTRAINT landing_publications_current_event_fkey
    FOREIGN KEY(current_event_id,entity_id)
    REFERENCES landing_publication_events(entity_id,publication_id) ON DELETE RESTRICT;
CREATE INDEX landing_publication_events_publication_created_idx
    ON landing_publication_events(publication_id,sequence DESC);

COMMIT;
