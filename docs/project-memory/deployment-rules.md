# PTW deployment rules

- Firebase Hosting serves the Flutter product; Commander Caddy never serves it.
- Pull requests may deploy isolated preview channels automatically.
- Merge to `main` and production deployment require explicit user approval.
- Credentials belong in scoped runtime mounts or CI secrets, never Git.
