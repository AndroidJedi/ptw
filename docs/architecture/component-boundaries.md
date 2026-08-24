# PTW Validation component boundaries

- `validation-pipeline`: isolated Product Brief and five-Ad service, strict
  bridge contracts, Pexels selection, deterministic image rendering, immutable
  persistence, approval, feedback, and skill proposals.
- `natal`: dormant fixed brand/templates and source assets for Stage 3; no
  active runtime registration.
- `commander`: minimal health/readiness and established Telegram emergency
  command adapter plus shared UUID/graph vocabulary.
- `owner-control-plane`: Firebase-authenticated Validation proxy, Jobs,
  Docs/System, emergency controls, and root-broker channel.
- `commander-web`: four-workspace PWA; no domain authority.
- `platform-bridge`: independent repository/database, authenticated structured
  execution only. It never owns PTW domain rows.

PostgreSQL relationships and immutable entities cross the active boundaries.
Stage 1 may not call an external research provider. Stage 2 may receive only
the approved Product Brief as business input. No feature may bypass Brief
approval, authenticated image delivery, or Owner Gateway for normal
instructions.
