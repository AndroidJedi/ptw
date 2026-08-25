BEGIN;

ALTER TABLE commander_entities
    DROP CONSTRAINT commander_entities_kind_check,
    ADD CONSTRAINT commander_entities_kind_check CHECK (kind IN (
        'source','validation_project','product_brief','creative_batch','ad_creative','artifact',
        'human_feedback','weight_update','task','audit_event','policy_evaluation'
    ));

CREATE TABLE validation_projects (
    entity_id uuid PRIMARY KEY REFERENCES commander_entities(id) ON DELETE RESTRICT,
    request_id uuid NOT NULL UNIQUE,
    owner_idea_source_id uuid NOT NULL UNIQUE REFERENCES commander_sources(entity_id) ON DELETE RESTRICT,
    name text NOT NULL CHECK (length(btrim(name)) BETWEEN 1 AND 120),
    name_source text NOT NULL CHECK (name_source IN ('raw_idea','product_brief','owner')),
    requested_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

ALTER TABLE product_briefs
    ADD COLUMN project_id uuid REFERENCES validation_projects(entity_id) ON DELETE RESTRICT;

CREATE TEMP TABLE validation_project_backfill ON COMMIT DROP AS
SELECT gen_random_uuid() AS project_id,
       root.request_id,
       root.owner_idea_source_id,
       left(
           COALESCE(
               NULLIF(regexp_replace(btrim(latest.product), '\s+', ' ', 'g'), ''),
               regexp_replace(btrim(source.content), '\s+', ' ', 'g')
           ),
           120
       ) AS name,
       CASE
           WHEN NULLIF(regexp_replace(btrim(latest.product), '\s+', ' ', 'g'), '') IS NULL
               THEN 'raw_idea'
           ELSE 'product_brief'
       END AS name_source,
       root.requested_by,
       root.created_at,
       GREATEST(root.updated_at, COALESCE(latest.updated_at, root.updated_at)) AS updated_at
  FROM product_briefs root
  JOIN commander_sources source ON source.entity_id=root.owner_idea_source_id
  LEFT JOIN LATERAL (
      SELECT brief.document->>'product' AS product,brief.updated_at
        FROM product_briefs brief
       WHERE brief.owner_idea_source_id=root.owner_idea_source_id
         AND brief.status='completed'
         AND NULLIF(btrim(brief.document->>'product'), '') IS NOT NULL
       ORDER BY brief.created_at DESC
       LIMIT 1
  ) latest ON true
 WHERE root.base_brief_id IS NULL;

INSERT INTO commander_entities(id,kind,attributes,created_at)
SELECT project_id,'validation_project',jsonb_build_object('schema_version',1,'backfilled',true),created_at
  FROM validation_project_backfill;

INSERT INTO validation_projects(
    entity_id,request_id,owner_idea_source_id,name,name_source,requested_by,created_at,updated_at
)
SELECT project_id,request_id,owner_idea_source_id,name,name_source,requested_by,created_at,updated_at
  FROM validation_project_backfill;

UPDATE product_briefs brief
   SET project_id=project.project_id
  FROM validation_project_backfill project
 WHERE project.owner_idea_source_id=brief.owner_idea_source_id;

ALTER TABLE product_briefs
    ALTER COLUMN project_id SET NOT NULL,
    ADD CONSTRAINT product_briefs_entity_project_key UNIQUE(entity_id,project_id),
    DROP CONSTRAINT product_briefs_base_brief_id_fkey,
    ADD CONSTRAINT product_briefs_base_same_project_fkey
        FOREIGN KEY(base_brief_id,project_id)
        REFERENCES product_briefs(entity_id,project_id) ON DELETE RESTRICT;

CREATE UNIQUE INDEX product_briefs_one_root_per_project_key
    ON product_briefs(project_id)
    WHERE base_brief_id IS NULL;
CREATE INDEX product_briefs_project_created_idx
    ON product_briefs(project_id,created_at DESC);

INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes)
SELECT gen_random_uuid(),project_id,'derived_from',owner_idea_source_id,
       jsonb_build_object('input','owner_idea','backfilled',true)
  FROM validation_project_backfill;

INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes)
SELECT gen_random_uuid(),brief.project_id,'contains',brief.entity_id,
       jsonb_build_object('member','product_brief','backfilled',true)
  FROM product_briefs brief;

CREATE OR REPLACE FUNCTION ptw_protect_product_brief() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.project_id IS DISTINCT FROM OLD.project_id
       OR NEW.request_id IS DISTINCT FROM OLD.request_id
       OR NEW.owner_idea_source_id IS DISTINCT FROM OLD.owner_idea_source_id
       OR NEW.base_brief_id IS DISTINCT FROM OLD.base_brief_id
       OR NEW.feedback_id IS DISTINCT FROM OLD.feedback_id
       OR (NEW.document IS DISTINCT FROM OLD.document AND OLD.document IS NOT NULL)
       OR (NEW.document_sha256 IS DISTINCT FROM OLD.document_sha256 AND OLD.document_sha256 IS NOT NULL)
       OR NEW.requested_by IS DISTINCT FROM OLD.requested_by THEN
        RAISE EXCEPTION 'immutable Product Brief fields cannot change';
    END IF;
    RETURN NEW;
END $$;

CREATE FUNCTION ptw_protect_validation_project() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.request_id IS DISTINCT FROM OLD.request_id
       OR NEW.owner_idea_source_id IS DISTINCT FROM OLD.owner_idea_source_id
       OR NEW.requested_by IS DISTINCT FROM OLD.requested_by
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'immutable Validation Project fields cannot change';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER validation_projects_protected BEFORE UPDATE ON validation_projects
FOR EACH ROW EXECUTE FUNCTION ptw_protect_validation_project();

COMMIT;
