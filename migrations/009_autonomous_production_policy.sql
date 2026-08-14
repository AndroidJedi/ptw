UPDATE project_memory
SET status = 'superseded', updated_at = now()
WHERE repository_id = 'ptw'
  AND title IN ('Agent branch policy', 'Production approval boundary')
  AND status = 'accepted';

INSERT INTO project_memory(
    repository_id,category,title,content,tags,source_type,source_reference,status
)
VALUES
('ptw','engineering_rules','Validated main merge policy',
 'Agents must work on agent/job-* branches. After component-driven validation passes, Commander may merge the pull request to main autonomously. Direct main pushes remain forbidden so review and rollback evidence are retained.',
 ARRAY['git','branch','main','autonomy'],'owner_policy','telegram:2026-08-14','accepted'),
('ptw','deployment_rules','Autonomous production authority',
 'Commander is authorized to merge validated PTW pull requests to main and thereby trigger the established production pipeline. It must record the pre-merge main revision as the rollback point and report merge or deployment failures as issues.',
 ARRAY['production','deployment','main','rollback'],'owner_policy','telegram:2026-08-14','accepted')
ON CONFLICT DO NOTHING;

UPDATE repositories
SET metadata = metadata || '{"autonomous_main_merge":true,"production_via_main":true,"rollback_required":true}'::jsonb,
    updated_at = now()
WHERE id = 'ptw';

