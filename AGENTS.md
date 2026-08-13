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

Never inspect or reuse credentials from `/opt/ptw/platform`. The GitHub working
tree and that deployed checkout have unrelated histories. Use disposable
databases for Commander migration tests unless the user explicitly authorizes a
target database.
