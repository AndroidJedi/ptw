# Telegram runtime boundary

The existing `@ptw_commander_bot`, root-owned token, established allowlisted
owner chat, and established long poller are the only Telegram integration.
Inbound commands are `/help`, `/status`, and `/stop`; every other command
returns the web-console link and cannot mutate state.

Published Landing leads use one direct `sendMessage` from Owner Gateway. No new
bot, token, webhook, poller, queue worker, or background notification service is
allowed. The lead/graph transaction commits first. Visitor text is HTML-escaped
and the message includes lead UUID, form, exact Landing and Positioning IDs,
timestamp, and fields.

Attempts are append-only `sent`, `failed`, `ambiguous`, or `suppressed`. Store
the Telegram message ID only for confirmed success. A timeout is ambiguous and
is never auto-retried. Emergency stop records suppression; explicit owner retry
is the only retry path. The deployment canary is clearly marked NOT A LEAD and
must not create a lead row or polling process.
