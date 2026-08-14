UPDATE repositories
SET metadata = metadata || '{"production_via_main":false,"deployment_verification_required":true}'::jsonb,
    updated_at = now()
WHERE id = 'ptw';

INSERT INTO project_memory(
    repository_id,category,title,content,tags,source_type,source_reference,status
)
VALUES(
    'ptw','deployment_rules','Verified production completion',
    'A successful main merge is not proof of production deployment. Commander must report main as merged but deployment unverified until a release executor rebuilds the affected service and verifies its live behavior.',
    ARRAY['production','deployment','verification','main'],
    'incident','TASK-48/ISSUE-4','accepted'
)
ON CONFLICT DO NOTHING;
