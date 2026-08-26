# PTW component boundaries

- `validation-pipeline`: Product Brief and channel-neutral Result contracts,
  orchestration, policy, persistence, adapters, rendering, and recovery.
- `commander`: health/readiness, graph vocabulary, demo, and the three-command
  Telegram emergency adapter.
- `owner-gateway`: Firebase-authenticated Project, Product Brief, and Result
  proxy. It owns no domain rows and runs no job system.
- `commander-web`: Product Brief and Result PWA. It is not an authority.
- `platform-bridge`: unrelated repository/database; authenticated ephemeral
  structured execution and reviewed graphic bytes only.

PostgreSQL relationships and immutable entities cross application boundaries.
No component may bypass Brief approval, Project/source ownership, protected
copy, authenticated artifact delivery, or Owner Gateway for normal owner
instructions. Channel behavior belongs in an adapter.
