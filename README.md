# PTW v2 — Marketing Positioning → Landing → Ads

PTW is an owner-operated, web-only marketing workspace. Its normal workflow is
explicit and revision-bound:

```text
raw idea + market
        ↓
Marketing Positioning (research, evidence, correction, owner approval)
        ↓                         ↓
Landing (three Natal drafts)      Ads (read-only concepts stub)
        ↓
exact-snapshot publication → lead form → existing PTW bot notification
```

The React PWA is authenticated by Firebase Auth and App Check. Owner Gateway is
the only normal instruction channel. PostgreSQL is the complete domain and
graph authority; Firebase hosts UI/static Landing files only. Admin contains
Jobs, Docs/System, and the break-glass root terminal.

Marketing Positioning runs as an isolated Compose project and retains port
8093. It requires verified DataForSEO research and the authenticated platform
bridge. Landing accepts only an active approved Positioning revision. Ads has
no mutation: generation and publishing are explicitly unimplemented.

Telegram uses only the existing `@ptw_commander_bot` and allowlisted owner
chat. Leads are committed before one direct `sendMessage`; no new bot, token,
webhook, poller, or notification worker exists.

## Local verification

```sh
python3 -m unittest discover -s tests/commander -v
python3 -m unittest discover -s tests/marketing_positioning -v
python3 -m unittest discover -s tests/owner_gateway -v
python3 -m commander.demo --output-dir .local/commander-demo
npm --prefix apps/commander-web run check
python3 scripts/verify_ptw_skills.py
git diff --check
```

Use [`docs/README.md`](docs/README.md) for selective documentation routes and
[`docs/architecture/commander-current-state.md`](docs/architecture/commander-current-state.md)
for the current verified milestone. Production reset is irreversible,
backup-free, limited to `ptw_commander.public`, and requires the exact phrase
`RESET PTW PRODUCTION`.
