UPDATE repositories
SET project_type = 'monorepo',
    metadata = metadata || '{"validation_manifest":"project.components.json"}'::jsonb,
    updated_at = now()
WHERE id = 'ptw';
