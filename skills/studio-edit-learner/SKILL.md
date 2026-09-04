---
name: studio-edit-learner
description: Convert a PTW Studio Save or Approve checkpoint into a Project lesson and a privacy-safe global proposal. Use only at explicit creative checkpoints, never on live edits or an agent-generated baseline.
---

# Studio Edit Learner

Compare the previous accepted checkpoint with the complete creative state saved
by the owner.

- Run only for an explicit **Save creative** or **Approve creative** checkpoint
  whose state changed. Live keystrokes, previews, image generations, asset
  selection, template changes, imports, and other intermediate mutations only
  accumulate for the next checkpoint.
- Summarize observable owner choices across content, configuration, template,
  and asset provenance. Do not infer preferences from unchanged defaults or the
  initial AI-generated baseline.
- Produce one Project lesson that may retain project-specific context and one
  generalized global proposal.
- The global proposal must omit Project and Brief IDs, Project names, exact
  campaign copy, asset digests, provider identifiers, personal data, and
  unsupported claims. Phrase it as a reusable Studio decision rule.
- Project learning is applied automatically at the checkpoint. Global learning
  remains pending until the owner chooses **Apply globally**; **Keep
  project-only** records the rejection without changing the global skill.
- Never mutate repository skill files. Learned skills are immutable,
  digest-verified runtime snapshots owned by PTW persistence.

