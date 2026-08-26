# PTW Validation documentation map

Markdown is canonical; generated exports are derivatives. Read only the route
needed for the task.

| Task | Read first | Then |
| --- | --- | --- |
| Current checkpoint | [`architecture/commander-current-state.md`](architecture/commander-current-state.md) | Relevant route below |
| Product Briefs, Ads, schema, APIs | [`architecture/simplified-validation-pipeline.md`](architecture/simplified-validation-pipeline.md) | Product Brief and Ad Creative skills |
| Ad Studio, templates, recipes, rendering, creative validation | [`architecture/ad-studio.md`](architecture/ad-studio.md) | Ad Studio Composer and Ad Creative Validator skills |
| Dormant Natal Stage 3 source | [`architecture/natal-landing-builder.md`](architecture/natal-landing-builder.md) | [`../natal/README.md`](../natal/README.md) |
| Owner UI/Auth/App Check | [`operations/owner-control-plane.md`](operations/owner-control-plane.md) | [`../DESIGN_RULES.md`](../DESIGN_RULES.md) |
| Services/deployment/1 GB host | [`operations/commander.md`](operations/commander.md) | PTW VPS Operations skill |
| Irreversible reset | [`operations/disaster-recovery.md`](operations/disaster-recovery.md) | Current state |
| Telegram emergency controls | [`operations/telegram-runtime.md`](operations/telegram-runtime.md) | Incident log |
| Jobs and checkpoints | [`architecture/task-issue-cycle.md`](architecture/task-issue-cycle.md) | [`architecture/session-checkpoints.md`](architecture/session-checkpoints.md) |

## Authority

- `ptw_commander` PostgreSQL is the complete PTW Validation runtime/graph and
  reviewed-image authority.
- `/opt/ptw/platform` has an unrelated history and database; the structured
  bridge is the only explicit integration.
- Git owns code, the clean baseline, skills, prompts, and these docs.
- Firebase owns identity configuration and active static releases, not domain
  data.
- Git history is the only archive for removed domains.
