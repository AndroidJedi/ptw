# Telegram runtime boundary

The existing `@ptw_commander_bot`, root-owned token, established allowlisted
owner chat, and established long poller are the only Telegram integration.
Inbound commands are `/help`, `/status`, and `/stop`; every other command
returns the web-console link and cannot mutate state.

Published Landing leads use one direct `sendMessage` from Owner Gateway.
Marketing Positioning uses one direct `sendMessage` after each generation
attempt is durably completed or failed. No new bot, token, webhook, poller,
queue worker, or background notification service is allowed. The lead/graph or
Positioning terminal transaction commits first. Owner and visitor text is
HTML-escaped.

Attempts are append-only `sent`, `failed`, `ambiguous`, or `suppressed`. Store
the Telegram message ID only for confirmed success. A timeout is ambiguous and
is never auto-retried. Emergency stop records suppression. The deployment
canary is clearly marked NOT A LEAD and must not create a lead or Positioning
notification row or polling process.
