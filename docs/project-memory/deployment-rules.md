# PTW deployment rules

- Firebase Hosting serves the Flutter product; Commander Caddy never serves it.
- Pull requests may deploy isolated preview channels automatically.
- Commander has standing owner authorization to merge validated pull requests
  to `main` and trigger the established production pipeline. Record the
  pre-merge SHA for rollback and report failures as durable issues.
- Credentials belong in scoped runtime mounts or CI secrets, never Git.
