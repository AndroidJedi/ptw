INSERT INTO project_memory(repository_id,category,title,content,tags,source_type,source_reference,status)
VALUES
('ptw','engineering_rules','Agent branch policy','Engineering changes use unique agent/job-* branches. Direct pushes to main and automatic merges are forbidden.',ARRAY['git','branch','main'],'git_markdown','docs/project-memory/engineering-rules.md','accepted'),
('ptw','deployment_rules','Production approval boundary','Firebase previews may be automatic. Production deployment and merge to main require user approval.',ARRAY['firebase','preview','production'],'git_markdown','docs/project-memory/deployment-rules.md','accepted'),
('ptw','known_pitfalls','Credential isolation','Never copy SSH, GitHub, Firebase, Telegram, or Codex credentials into prompts, artifacts, repositories, or event payloads.',ARRAY['security','credentials'],'git_markdown','docs/project-memory/known-pitfalls.md','accepted')
ON CONFLICT DO NOTHING;
