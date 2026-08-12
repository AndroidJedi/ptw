# PTW engineering rules

- Resolve repositories only through `RepositoryRegistry`; Telegram uses `repo=ptw`.
- Use a fresh `/opt/ptw/workspaces/jobs/<job-id>` checkout and unique `agent/job-*` branch.
- Codex executes `spec.md`; it does not receive unbounded Telegram history.
- Validation must pass before commit, push, and PR creation.
- Never push directly to `main`, merge automatically, or modify production.
