# Security notes

- PostgreSQL is reachable only on the internal Compose network.
- Caddy is the only host-published container port and binds to loopback by default.
- Commander and worker have outbound access for Telegram; neither publishes a port.
- The API and worker run unprivileged with read-only roots and `no-new-privileges`.
- Telegram commands require an exact numeric ID match against
  `TELEGRAM_ALLOWED_USER_IDS`; unsupported and unauthorized attempts are logged
  without retaining message text.
- `.env` is ignored by Git and excluded from Docker build contexts. Code retrieves
  secrets through `SecretStore`; the bootstrap backend uses process environment.
- Event metadata is recursively redacted for keys containing `secret`, `token`,
  `password`, `credential`, or `api_key`. Callers should still submit only curated,
  non-secret metadata. Raw message bodies and Telegram tokens are never event data.
- Error rows contain a bounded generic diagnostic rather than exception text that
  might include a credential-bearing URL.
- A production secret manager can replace `EnvironmentSecretStore` by implementing
  `get`, `exists`, and `put`; no command/job code needs to depend on `.env`.
- Container images and Python dependencies are pinned to stable major/exact versions.
