# PTW documentation map

Markdown in this repository is canonical. Generated PDF, DOCX, slide, or other
exports are derivatives and must link back to their source Markdown revision.
Do not use an export as a second source of truth.

## Context routes

Load the smallest route that covers the task. Start here; do not recursively
read `docs/`.

| Task | Read first | Read when needed |
| --- | --- | --- |
| Commander or learning-loop architecture | [`architecture/commander-architecture-review.md`](architecture/commander-architecture-review.md) | [`PTW_Commander_Bootstrap_Addendum.md`](PTW_Commander_Bootstrap_Addendum.md) for original constraints |
| Autonomous tasks, issues, logs, and state export | [`architecture/task-issue-cycle.md`](architecture/task-issue-cycle.md) | [`operations/telegram-runtime.md`](operations/telegram-runtime.md) for owner controls |
| Commander/Codex session checkpoint and restore | [`architecture/session-checkpoints.md`](architecture/session-checkpoints.md) | [`operations/commander.md`](operations/commander.md) for startup verification |
| Component ownership and validation | [`architecture/component-boundaries.md`](architecture/component-boundaries.md) | [`../project.components.json`](../project.components.json) for the executable contract |
| Research and initial hypotheses | [`architecture/research-to-hypothesis.md`](architecture/research-to-hypothesis.md) | Commander architecture review and source-specific research material |
| Product direction | [`../Proof_Them_Wrong_Idea_and_Strengths.md`](../Proof_Them_Wrong_Idea_and_Strengths.md) | [`../DESIGN_RULES.md`](../DESIGN_RULES.md) for UI work |
| Instagram creative adapter | [`verticals/instagram/README.md`](verticals/instagram/README.md) | [`PTW_TEMPLATE_MCP.md`](PTW_TEMPLATE_MCP.md), then the implementation handoff |
| Creative feedback and weights | [`architecture/creative-feedback-learning.md`](architecture/creative-feedback-learning.md) | Instagram vertical and Commander architecture review |
| Template MCP | [`PTW_TEMPLATE_MCP.md`](PTW_TEMPLATE_MCP.md) | `tool/ptw_template_mcp/` and `lib/template_generator/` |
| Flutter application | [`../README.md`](../README.md) | [`../DESIGN_RULES.md`](../DESIGN_RULES.md) and feature-specific source |
| Operations/deployment/recovery | [`operations/commander.md`](operations/commander.md) | [`operations/telegram-runtime.md`](operations/telegram-runtime.md), [`operations/disaster-recovery.md`](operations/disaster-recovery.md), [`operations/incident-log.md`](operations/incident-log.md), and deployment files |

The concise cross-session resume point is
[`architecture/commander-current-state.md`](architecture/commander-current-state.md).

## Document status

### Canonical

- This index and the Commander architecture review.
- `PTW_Commander_Bootstrap_Addendum.md`: original Commander requirements. The
  review refines it where necessary and records deviations.
- `PTW_TEMPLATE_MCP.md`: current template-authoring contract.
- Root `README.md`, `DESIGN_RULES.md`, and
  `Proof_Them_Wrong_Idea_and_Strengths.md`: application, design, and product
  sources respectively. They remain at the root to avoid breaking established
  links.

### Point-in-time handoff

- `PTW_Post_Generator_Current_State_Handoff.md` describes an implementation
  snapshot. It is useful evidence, not the forward architecture authority.

### Generated exports

No generated documentation exports are currently tracked. Put future exports
under `docs/generated/`, include the source path and Git commit in each export,
and regenerate rather than editing them.

### Archived or deprecated

No documents are currently archived. Move superseded Markdown to
`docs/archive/` with a status banner, replacement link, and date. Never leave
two apparently-current documents covering the same decision.

## Context-broker contract

Commander retrieves bootstrap bundles from the machine-readable
`config/commander/context_routes.json` registry by task classification. This
manually curated map explains that registry to humans. Both are intentionally
small and reviewable; a vector index is not required until lexical and metadata
routing are demonstrably insufficient.
