# Telegram runtime boundary

The existing `@ptw_commander_bot`, root-owned token, established allowlisted
owner chat, and established long poller are the only Telegram integration.
Inbound commands are `/help`, `/status`, and `/stop`; every other command
returns the web-console link and cannot mutate state.

A terminal failed Ad creative-batch attempt makes at most one direct
`sendMessage` to the existing allowlisted owner chat after the failure is
durable. Reservation and delivery result are append-only audit events; an
ambiguous timeout is never auto-retried, and emergency stop suppresses the send.
Successful generation and Product Brief generation send no message. Dormant
Landing accepts no leads and sends no notification. No new bot, token, webhook,
poller, queue worker, background notification service, or inbound command is
allowed.

Any deployment canary is clearly marked and must not create a Brief, creative,
feedback, notification, or polling process. Emergency-stop behavior and the
existing allowlisted inbound boundary remain unchanged.
