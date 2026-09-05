# PTW documentation map

Markdown is canonical; generated exports are derivatives. Read only the route
needed for the task.

| Task | Canonical route |
| --- | --- |
| Current checkpoint | [`architecture/commander-current-state.md`](architecture/commander-current-state.md) |
| Product Brief | [`architecture/simplified-validation-pipeline.md`](architecture/simplified-validation-pipeline.md) and `skills/product-brief-generator/SKILL.md` |
| Project Post and Landing Studio | [`architecture/universal-ad-studio.md`](architecture/universal-ad-studio.md) and [`architecture/landing-studio.md`](architecture/landing-studio.md), plus their composer/learner, phone-hero, Tune, and visual-audit skills |
| Owner UI and authentication | [`operations/owner-gateway.md`](operations/owner-gateway.md) and [`../DESIGN_RULES.md`](../DESIGN_RULES.md) |
| Deployment and reset | [`operations/commander.md`](operations/commander.md) and [`operations/disaster-recovery.md`](operations/disaster-recovery.md) |
| Telegram emergency boundary | [`operations/telegram-runtime.md`](operations/telegram-runtime.md) |

## Authority

- `ptw_commander.public` owns Product Brief validation and project-scoped
  Studio creatives, files/PNG bytes, runs, checkpoints, proposals, decisions,
  skill snapshots, immutable versions, and graph lineage.
- `.local/owner-briefs` is the loopback append-only metadata authority;
  `.local/studio-workspace/creatives` holds per-creative renderer files.
- `/opt/ptw/platform` has unrelated Git and PostgreSQL histories. Its
  authenticated structured/media bridge is the only generation integration.
- Firebase owns identity and static releases, never PTW domain data.
- The repository has one clean baseline. Removed systems are not compatibility
  targets and receive no migration path.
