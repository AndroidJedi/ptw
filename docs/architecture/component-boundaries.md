# PTW v2 component boundaries

- `marketing-positioning`: isolated owner-input-only synthesis service,
  immutable positioning domain, terminal existing-bot notifications, approvals,
  and skill proposals.
- `natal`: dependency-free fixed brand/templates, v2 brief/page/form contracts,
  static renderer, and inert/public modes.
- `commander`: minimal health/readiness and established Telegram emergency
  command adapter plus shared UUID/graph vocabulary.
- `owner-control-plane`: Firebase-authenticated API, Landing orchestration,
  lead persistence/notification, Jobs, Docs/System, and root-broker channel.
- `commander-web`: four-workspace PWA; no domain authority.
- `platform-bridge`: independent repository/database, authenticated structured
  execution only. It never owns PTW domain rows.

PostgreSQL relationships and immutable entities cross the first four boundaries.
Marketing Positioning may not call an external research provider or present
model knowledge as evidence. No feature may bypass approval gating for
Landing/Ads or Owner Gateway for normal instructions.
