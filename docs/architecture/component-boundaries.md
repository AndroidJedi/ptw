# PTW component boundaries

- `validation_pipeline`: Product Brief generation/persistence plus the separate
  Universal Studio workspace and renderer.
- `owner_gateway`: Firebase-authenticated Project, Brief, and Studio proxy.
- `commander`: readiness and established Telegram emergency controls.
- `apps/commander-web`: Product Brief and Studio UI; never data authority.
- `/opt/ptw/platform`: unrelated bridge runtime; exactly two Product Brief JSON
  modes and no media mode.

The web Owner Gateway is the only normal instruction channel. PostgreSQL owns
the complete Brief graph; Studio state is independently file-backed. Telegram
remains emergency-only.
