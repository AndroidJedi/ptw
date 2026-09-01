# Telegram emergency boundary

The existing `@ptw_commander_bot`, root-owned token, allowlisted owner chat,
and established platform poller are the only Telegram integration. Inbound
commands are `/help`, `/status`, and `/stop`; every other input returns the
Owner Console link and cannot create a task or mutate domain state.

Production Product Brief generation sends no Telegram completion or failure
message. After a Result has persisted exactly five reviewable Creatives and its
delivery receipt, Validation may send one typed review-ready event through
Commander. Commander resolves the owner chat server-side and sends the web
review deep link; it exposes no Telegram review action.

The loopback local app neither reads production Telegram credentials nor
requires the Commander relay. Without an explicitly supplied endpoint and
bridge token it records `not_configured`, creates no delivery receipt, and keeps
the authenticated five-card web review available. It must never report a fake
delivery or start another poller/webhook.

A deployment canary is explicitly labelled and must not create a Brief, Result,
feedback row, or second poller. Never print, copy, rotate, or replace the
existing token without separate owner authorization.
