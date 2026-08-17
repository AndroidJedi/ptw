# PTW documentation map

Markdown in this repository is canonical. Generated exports are derivatives
and must identify their source revision.

## Context routes

| Task | Read first | Read when needed |
| --- | --- | --- |
| Current implementation checkpoint | [`architecture/commander-current-state.md`](architecture/commander-current-state.md) | The relevant route below |
| Owner control plane and learning architecture | [`architecture/commander-architecture-review.md`](architecture/commander-architecture-review.md) | [`architecture/component-boundaries.md`](architecture/component-boundaries.md) |
| React operator UI | [`../DESIGN_RULES.md`](../DESIGN_RULES.md) | `apps/commander-web/README.md` |
| Autonomous jobs, issues, and execution | [`architecture/task-issue-cycle.md`](architecture/task-issue-cycle.md) | [`architecture/session-checkpoints.md`](architecture/session-checkpoints.md) |
| Idea evolution | [`../ideaGeneration/docs/IDEA_EVOLUTION_SYSTEM_BOOTSTRAP.md`](../ideaGeneration/docs/IDEA_EVOLUTION_SYSTEM_BOOTSTRAP.md) | [`../ideaGeneration/docs/TASK_20M_3Y.md`](../ideaGeneration/docs/TASK_20M_3Y.md), then `ideaGeneration/docs/contexts/` |
| Creative feedback and weights | [`architecture/creative-feedback-learning.md`](architecture/creative-feedback-learning.md) | [`architecture/ad-image-estimation-loop.md`](architecture/ad-image-estimation-loop.md) |
| Instagram adapter | [`verticals/instagram/README.md`](verticals/instagram/README.md) | Creative feedback route |
| Firebase authentication and deployment | [`operations/owner-control-plane.md`](operations/owner-control-plane.md) | [`operations/commander.md`](operations/commander.md) |
| Irreversible reset boundary | [`operations/disaster-recovery.md`](operations/disaster-recovery.md) | [`operations/incident-log.md`](operations/incident-log.md) |
| Telegram notifications/emergency controls | [`operations/telegram-runtime.md`](operations/telegram-runtime.md) | Incident log |

## Authority

- PostgreSQL is the complete runtime authority for domain entities and edges.
- Git is authoritative for code, migrations, policy, prompts, and these docs.
- Large artifacts are immutable files identified by SHA-256 digest.
- Firebase stores identity configuration and static Hosting content only, never
  PTW domain data.

Superseded client documents are intentionally absent from the current tree. Git
history is the only archive for removed subsystems.
