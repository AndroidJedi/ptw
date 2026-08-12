# Security model

## Current controls

- Telegram privileged commands require an exact match in the configured numeric
  user-ID allowlist. Rejections are logged without raw message bodies.
- Bootstrap secrets are accessed through `SecretStore`; `.env` is mode 600,
  ignored by Git, and excluded from Docker builds.
- Event metadata recursively redacts secret-like keys. HTTP client request logs
  are suppressed to prevent token-bearing Telegram URLs from being recorded.
- Caddy exposes only `/health`; there is no dashboard, shell endpoint, Codex
  endpoint, or arbitrary job endpoint.
- PostgreSQL is internal-only. Caddy alone publishes public ports 80/443; its
  diagnostic listener binds host loopback.
- Containers are unprivileged, read-only where practical, memory-limited, and
  configured with `no-new-privileges` and restart policies.

## Trust assumptions

The VPS root operator, Docker daemon, Telegram Bot API, DNS/provider control
plane, and local `.env` are trusted. Telegram ID allowlisting authenticates an
account, not the intent or safety of a future engineering action. Host Codex
metadata proves availability only; Phase A offers no Codex execution.

## Future approval gates

The following should require explicit approval and auditable events: destructive
filesystem/database changes, production deploys, merges, pull requests with broad
impact, secret creation or rotation, privilege changes, external messages,
spending, and any command that escapes a per-job workspace. Future runners should
use disposable workspaces, scoped credentials, network policy, resource limits,
and cleanup with retention rules.
