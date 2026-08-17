# Telegram notification and emergency runtime

Status: web-first target contract
Updated: 2026-08-17

The existing `@ptw_commander_bot` and `/opt/ptw/platform` long poller remain the
single Telegram update consumer. No webhook or second poller is allowed.

Telegram is not the normal control plane. It sends concise notifications for
ideas, posts, reviews, jobs, issues, deployment, and failures. Every
notification that needs action includes a deep link to
`https://provethemwrong-86123.web.app`.

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
redirection, restart persistence, and a real notification deep link.

Telegram output is a notification projection only. PostgreSQL and the web
Owner Gateway remain authoritative.
