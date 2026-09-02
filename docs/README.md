# PTW documentation map

Markdown is canonical; generated exports are derivatives. Read only the route
needed for the task.

| Task | Canonical route |
| --- | --- |
| Current checkpoint | [`architecture/commander-current-state.md`](architecture/commander-current-state.md) |
| Product Brief | [`architecture/simplified-validation-pipeline.md`](architecture/simplified-validation-pipeline.md) and `skills/product-brief-generator/SKILL.md` |
| Universal Studio | [`architecture/universal-ad-studio.md`](architecture/universal-ad-studio.md) and [`../skills/studio-tune-local/SKILL.md`](../skills/studio-tune-local/SKILL.md) |
| Owner UI and authentication | [`operations/owner-gateway.md`](operations/owner-gateway.md) and [`../DESIGN_RULES.md`](../DESIGN_RULES.md) |
| Deployment and reset | [`operations/commander.md`](operations/commander.md) and [`operations/disaster-recovery.md`](operations/disaster-recovery.md) |
| Telegram emergency boundary | [`operations/telegram-runtime.md`](operations/telegram-runtime.md) |

## Authority

- `ptw_commander.public` owns Product Brief validation entities and graph lineage.
- `.local/owner-briefs` is the loopback Brief authority; `.local/studio-workspace`
  is the standalone Studio authority.
- `/opt/ptw/platform` has unrelated Git and PostgreSQL histories. Its
  authenticated structured bridge is the only generation integration.
- Firebase owns identity and static releases, never PTW domain data.
- Removed systems exist only in Git history and are not compatibility targets.
