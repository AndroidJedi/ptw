# PTW agent entrypoint

Start every session by reading, in order:

1. `docs/README.md` for the selective context routes.
2. `docs/architecture/commander-current-state.md` for the last completed
   milestone, verification status, and next work.
3. Only the canonical route relevant to the current task.

Do not load the entire documentation tree. Markdown is canonical; generated
exports are derivatives. Preserve the generic learning architecture and keep
Instagram-specific behavior behind an adapter.

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

The GitHub working tree and `/opt/ptw/platform` have unrelated histories; do not
merge them or reuse unrelated deployment credentials. The one explicit
operational integration is the existing `@ptw_commander_bot`: the creative
stack reads its environment file at runtime and the established long poller
forwards `/creative` over the shared internal network. Never print, copy into
Git, rotate, or replace that token without owner authorization. Use disposable
databases for migration tests unless the user explicitly authorizes a target
database.

The owner's general Telegram instruction channel is `/task <free-form request>`.
It queues the established specification-driven engineering workflow and may
include screenshots/images when `/task ...` is used as the attachment caption.
`/engineer` is a compatibility alias; `/creative` is reserved for Story image
generation.

Commander recovery uses `scripts/backup_commander.sh`,
`verify_commander_backup.sh`, and the confirmation-gated
`restore_commander.sh`. The VPS schedules daily backups in
`/etc/cron.d/ptw-commander-backup`. Before destructive recovery, verify the
archive and recorded Git revision. Research must enter through
`ResearchKnowledgeService` so every initial hypothesis retains `derived_from`
edges to permanent research-source IDs.
