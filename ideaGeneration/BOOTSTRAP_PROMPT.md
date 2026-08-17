# Idea Evolution bootstrap route

Read in order:

1. `docs/TASK_20M_3Y.md` — active mission and rubric.
2. `docs/IDEA_EVOLUTION_SYSTEM_BOOTSTRAP.md` — current runtime contract.
3. `docs/CONTEXTS_V1.md` and only the relevant C01–C10 files.

The Owner Gateway and Commander Web are the sole normal control surface.
Generation 1 is manual after reset. PostgreSQL is authoritative, context edits
are versioned, and user-facing generated fields are bilingual `{en, uk}`.
Telegram is not an idea controller; it provides notifications and the global
owner-only `/help`, `/status`, and `/stop` emergency path.
