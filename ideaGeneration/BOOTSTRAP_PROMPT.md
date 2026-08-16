# Codex CLI Bootstrap Prompt

Work in the existing repository/VPS. The new authoritative specification is in the `ideaGeneration/` folder.

Read these files in order:

1. `ideaGeneration/docs/IDEA_EVOLUTION_SYSTEM_BOOTSTRAP.md`
2. `ideaGeneration/docs/TASK_450M_5Y.md`
3. `ideaGeneration/docs/TELEGRAM_CONTROL.md`
4. `ideaGeneration/docs/CONTEXTS_V1.md`
5. individual `ideaGeneration/docs/contexts/*.md` when implementing/seeding contexts

Then implement the clean rebuild completely.

Important:

- Start with `git status` and `git pull --ff-only`.
- Inspect the current repo, services, Docker/systemd processes, PostgreSQL schema, Telegram poller, env/secrets, and shared VPS services BEFORE deleting anything.
- Preserve the VPS, Git/SSH/deploy access, existing PostgreSQL service, existing Telegram bot/token, authorized owner chat IDs, and healthy shared infrastructure.
- Make a one-time backup of the old application DB/schema outside Git.
- Stop old app/workers/schedulers and the old Telegram poller.
- Remove the old experimental idea-system implementation and old app-owned DB objects.
- Do not delete unrelated/shared infrastructure.
- Apply the new schema and seed mission + exactly 10 contexts.
- Start exactly one Telegram poller using the existing bot.
- Implement the core exactly as `GENERATE → EVALUATE → EVOLVE`.
- Keep every idea/evaluation historically.
- Implement Hall of Fame, failures, exploit/explore, owner idea injection, direct versioned context editing, reports, `/run`, `/run N`, `/stop`, `/continue`, and all Telegram commands in `TELEGRAM_CONTROL.md`.
- Implement bounded self-healing recovery: maximum 2 automatic recovery attempts for the same failing step. Notify Telegram about diagnosis/action/result. If fixed, continue automatically. If both fail, stop safely, preserve completed data and remaining run-series count.
- The production runtime must NOT autonomously rewrite its own source code.
- Do not add embeddings, vector DB, knowledge graph, autonomous context evolution, mutation-operator database, Redis, Celery, Kafka, Kubernetes, or extra long-lived agent services.
- Use mocked LLM calls for deployment/tests; do not spend live model tokens during bootstrap tests.
- Keep autopilot OFF.
- Do NOT run Generation 1 automatically.
- Never print or commit secrets.

Run all acceptance tests/checks in the bootstrap document.

When finished:
1. send the readiness report through the existing Telegram bot;
2. print a concise terminal report with DB backup path, cleanup status, migration status, Postgres health, Telegram health, context count, mission status, test result, autopilot state, and generation count;
3. tell me the exact start commands: `/status`, `/run`, `/run N`.

If an existing-infrastructure detail forces a deviation, choose the smallest safe equivalent, document it, and continue rather than redesigning the architecture.
