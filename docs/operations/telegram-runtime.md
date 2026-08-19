# Telegram emergency runtime

Status: emergency-only target contract
Updated: 2026-08-19

The existing `@ptw_commander_bot` and `/opt/ptw/platform` long poller remain the
single Telegram update consumer. No webhook or second poller is allowed.

Telegram is not the normal control plane. Proactive outbound notifications are
retired on the 1 GB profile. The long poller exists only so the three bounded
emergency commands remain available.

Only three inbound commands are supported:

- `/help` — show this bounded command set and the web link;
- `/status` — report mission, active generation/job, emergency-stop state, and
  major service health;
- `/stop` — enable the existing durable emergency stop and prevent new
  autonomous side effects.

All other commands, callbacks, captions, and free-form text return the web
link. They do not create tasks, ideas, creatives, reviews, approvals, context
changes, or resumptions. The sole poller must not route to retired handlers.

The existing user/chat allowlists remain mandatory. Never print, copy, rotate,
or replace the bot token during this cutover. A production acceptance check
must cover unauthorized access, `/help`, `/status`, `/stop`, unsupported-command
redirection, restart persistence, and the absence of queued outbound delivery.

The platform poller returns the bounded command response from Commander's
internal bridge. Commander does not enqueue that response into its retired
outbox worker. PostgreSQL and the web Owner Gateway remain authoritative.

Historical Idea Laval notification rows remain queryable. Migration 011 marks
unpublished Telegram outbox rows cancelled with a reason and timestamp; claim
queries exclude them. The Laval notifier is not constructed and the web status
button/API return path is retired with HTTP 410.
