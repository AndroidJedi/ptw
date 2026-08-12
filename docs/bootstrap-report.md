# Bootstrap report

## Existing state discovered

The Docker-based Phase A skeleton and points 7–12 were already committed. Docker,
Compose, PostgreSQL 16, Caddy 2.10, Python containers, Git, and host Codex CLI
`0.147.0` were present. At bootstrap, no DNS answer existed for the Commander
hostname. `commander.proove-them-wrong.com` now resolves to the VPS.

## Changes made for points 13–24

- Added the Caddy HTTPS virtual host and public 80/TCP, 443/TCP, and 443/UDP
  bindings; retained operator diagnostics on `127.0.0.1:8080`.
- Restricted the public virtual host to `GET /health` (other paths return 404).
- Added host Codex version detection without an execution endpoint.
- Prepared `/opt/ptw/workspaces/jobs` and `/opt/ptw/workspaces/archive`.
- Added unit, integration, lifecycle, authorization, and smoke tests.
- Added architecture, operations, bootstrap, and security-model documentation.

No new host package was installed. No firewall, SSH, DNS, Firebase, GitHub,
Flutter, user-account, or disk-layout configuration was changed.

## Runtime inventory

- Services: `postgres`, `commander-api`, `commander-worker`, `caddy`
- Persistent data: `/opt/ptw/persistent-data/postgres`, `caddy/data`,
  `caddy/config`, and `runtime`
- Workspaces: `/opt/ptw/workspaces/jobs` and `archive`
- Required secrets: `POSTGRES_PASSWORD`, `TELEGRAM_BOT_TOKEN`
- Required identity: `TELEGRAM_ALLOWED_USER_IDS`
- Public hostname: `COMMANDER_PUBLIC_HOST` (defaults to the Commander hostname)

## Assumptions and unresolved items

DNS points the Commander hostname to this VPS, and Caddy has obtained a public
certificate. Ports 80 and 443 must remain permitted by the provider firewall, if
one exists. Telegram end-to-end completion requires the allowed user to press
Start in the bot chat. The previously shared bot token must be rotated.
