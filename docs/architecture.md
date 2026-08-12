# Phase A architecture

## Components and responsibilities

- **Caddy** is the only public application edge. It obtains certificates for
  `commander.proove-them-wrong.com` and publishes only `GET /health`.
- **Commander API** owns Telegram long polling, deterministic authorization and
  routing, migrations, and internal health endpoints.
- **Commander worker** atomically claims PostgreSQL jobs, runs the four bounded
  command types, and sends Telegram replies.
- **PostgreSQL 16** stores users, sessions, jobs, heartbeats, and append-oriented
  events. It has no host-published port.
- **Git watcher** separates deterministic remote-SHA detection, change
  processing, and Telegram outbox delivery. A future webhook can replace only
  the polling detector.
- **Git credential agent** alone mounts the read-only deploy-key file. Watcher
  and runner containers receive only its Unix socket and GitHub-only SSH config.
- **Host execution layer** detects the installed Codex CLI and publishes only
  version metadata read-only to the worker. Phase A cannot invoke Codex remotely.

## Data flow and trust boundaries

```text
Telegram API -> Commander API -> PostgreSQL <- Commander worker -> Telegram API
Internet -> Caddy /health -> Commander API
Host Codex check -> read-only metadata -> Commander worker /status
Future job -> per-job /opt/ptw/workspaces/jobs/<job-id> -> tests/commit/PR -> cleanup
GitHub main -> ls-remote -> PostgreSQL state/outbox -> authorized Telegram users
```

The Internet-to-Caddy boundary exposes no administration. Telegram identity is
trusted only after exact numeric allowlist matching. The backend Compose network
is internal; API and worker additionally use an outbound edge network. Host state
is not mounted broadly into containers.

Future engineering jobs must receive a unique workspace, cloned repository or
Git worktree, bounded credentials, and explicit cleanup. They must not modify the
Commander source checkout as a shared working tree.

## Engineering pipeline

`/engineer repo=ptw <task>` creates a PostgreSQL job. The Brain classifies risk,
retrieves only relevant accepted memory, and writes bounded `spec.md`. Runner v2
uses an isolated `agent/job-*` checkout, invokes Codex non-interactively with
linked images, performs staged Flutter validation, writes `result.md`, pushes
only its task branch, and creates or reuses a deterministic PR. Stage events and
durations support recovery; unavailable token counts remain unset.

Stable rules live in `docs/project-memory`; lifecycle records and source
references live in PostgreSQL. Category filtering, full-text rank, item limits,
and a character budget prevent sending the full memory base.

## Firebase boundary

This VPS is a control and future agent-execution environment, not the PTW product
web host. Flutter Web remains on Firebase Hosting through branch, pull request,
CI, Firebase preview, approval, merge, and Firebase production deployment. Caddy
must never serve the Flutter build or `prove-them-wrong.com` product traffic.
