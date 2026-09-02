# PTW agent entrypoint

Start every session by reading, in order:

1. `docs/README.md` for the selective context routes.
2. `docs/architecture/commander-current-state.md` for the last completed
   milestone, verification status, and next work.
3. Only the canonical route relevant to the current task.

Do not load the entire documentation tree. Markdown is canonical; generated
exports are derivatives. Preserve the generic Product Brief learning architecture.

Before changing code, run `git status --short --branch` and synchronize the
tracked branch without overwriting uncommitted work. After Commander changes,
run:

```sh
python3 -m unittest discover -s tests/commander -v
python3 -m commander.demo --output-dir .local/commander-demo
git diff --check
```

Runtime tests requiring FastAPI and Pillow run in the built image:

```sh
docker run --rm -v "$PWD:/workspace:ro" -w /workspace \
  --entrypoint python ptw-commander-api:latest \
  -m unittest discover -s tests/commander -v
```

Update `docs/architecture/commander-current-state.md` whenever a Commander
milestone changes. It is a concise resume point, not a replacement for decision
history or the architecture review.

PTW-specific Codex skills are canonical under `skills/`. Desktop skill paths
must symlink to those folders, and Commander/Owner Gateway containers mount the
same tree at `$CODEX_HOME/skills`. After every production incident, update the
narrowest applicable skill with reusable diagnostics and guardrails in the same
commit, then run `python3 scripts/verify_ptw_skills.py`. Never put secrets or
ephemeral release hashes in skills. Run `scripts/install_ptw_skill_sync.sh`
once per checkout; its post-merge hook adds new skill links and repairs CLI
write permissions after every pull.

The GitHub working tree and `/opt/ptw/platform` have unrelated histories; do not
merge them or reuse unrelated deployment credentials. The one explicit
operational integration is the existing `@ptw_commander_bot`: Commander reads
its root-owned environment at runtime and the established long poller exposes
only emergency controls. Never print, copy into Git, rotate, or replace that
token without owner authorization. Use disposable databases for migration
tests unless the user explicitly authorizes a target database.

The web Owner Gateway is the only normal instruction channel. Telegram is
limited to emergency `/help`, `/status`, and `/stop`; every
other inbound command returns the web-console link and must not mutate state.

Unified production reset uses the confirmation-gated `scripts/reset_ptw.sh`.
It intentionally has no backup prerequisite by owner decision, so every reset
must keep its exact target allowlist and must be treated as irreversible.
Product Brief corrections persist HumanFeedback and WeightUpdate UUID entities
connected through `evaluates`, `contains`, `derived_from`, and `adjusts` edges.
Weight history is append-only; do not silently update a component row.

The owner inspects graph state through bounded web APIs and the Docs/System UI.
Keep output ID-explicit; PostgreSQL entities and relationship edges remain the
complete authority.

Before claiming a Telegram capability is available, verify deployed help,
routing, authorization, provider readiness, real end-to-end execution, graph
persistence, restart behavior, and its user-facing failure path. Read
`docs/operations/incident-log.md` when changing Telegram or providers.
