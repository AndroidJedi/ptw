# Phase A security notes

- PostgreSQL is reachable only on the internal Compose network.
- The API and worker run unprivileged, with read-only roots and
  `no-new-privileges`.
- Caddy binds to host loopback by default; the Phase A API has no authentication.
- `.env` is ignored by Git. Code retrieves secrets through `SecretStore`; the
  bootstrap implementation uses process environment variables.
- Secret values must never be logged or written to `platform_events.payload`.
- Container images and Python dependencies are pinned to stable major/exact
  versions. Routine updates remain an operator responsibility.

