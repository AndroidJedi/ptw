# PTW documentation map

Markdown is canonical; generated exports are derivatives. Read only the route
needed for the task.

| Task | Canonical route |
| --- | --- |
| Current checkpoint | [`architecture/commander-current-state.md`](architecture/commander-current-state.md) |
| Product Brief | [`architecture/simplified-validation-pipeline.md`](architecture/simplified-validation-pipeline.md) and `skills/product-brief-generator/SKILL.md` |
| Result generation | [`architecture/content-result-agent.md`](architecture/content-result-agent.md), `skills/content-candidate-generator/SKILL.md`, and `skills/content-result-critic/SKILL.md` |
| Instagram recipe/render adapter | [`architecture/ad-studio.md`](architecture/ad-studio.md) |
| Universal Ad Studio | [`architecture/universal-ad-studio.md`](architecture/universal-ad-studio.md), [`architecture/ad-studio.md`](architecture/ad-studio.md), [`../skills/studio-tune-local/SKILL.md`](../skills/studio-tune-local/SKILL.md) for Tune changes, and [`../skills/studio-ui-visual-audit/SKILL.md`](../skills/studio-ui-visual-audit/SKILL.md) for visual QA |
| Owner UI and authentication | [`operations/owner-gateway.md`](operations/owner-gateway.md) and [`../DESIGN_RULES.md`](../DESIGN_RULES.md) |
| Deployment and reset | [`operations/commander.md`](operations/commander.md) and [`operations/disaster-recovery.md`](operations/disaster-recovery.md) |
| Telegram emergency boundary | [`operations/telegram-runtime.md`](operations/telegram-runtime.md) |

## Authority

- `ptw_commander.public` owns Product Brief and Result entities, edges, source
  snapshots, recipes, renders, feedback, and provider provenance.
- `/opt/ptw/platform` has unrelated Git and PostgreSQL histories. Its
  authenticated structured bridge is the only integration; its database is
  never reset by the application deployment.
- Git owns the one clean migration baseline, schema contracts, templates,
  skills, prompts, corpus, and documentation.
- Firebase owns identity and static releases, never PTW domain data.
- Removed systems exist only in Git history and are not compatibility targets.
