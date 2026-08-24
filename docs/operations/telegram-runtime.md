# Telegram runtime boundary

The existing `@ptw_commander_bot`, root-owned token, established allowlisted
owner chat, and established long poller are the only Telegram integration.
Inbound commands are `/help`, `/status`, and `/stop`; every other command
returns the web-console link and cannot mutate state.

Product Brief and Ad generation send no Telegram message. Dormant Landing
accepts no leads and sends no notification. No new bot, token, webhook, poller,
queue worker, or background notification service is allowed.

Any deployment canary is clearly marked and must not create a Brief, creative,
feedback, notification, or polling process. Emergency-stop behavior and the
existing allowlisted inbound boundary remain unchanged.
