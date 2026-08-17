# Telegram boundary for Idea Evolution

Status: emergency-only
Updated: 2026-08-17

Idea Evolution has no direct Telegram command surface. The single established
platform poller accepts only `/help`, `/status`, and `/stop`; every other input
returns the Commander Web link without forwarding a domain mutation.

`/stop` pauses the active mission, disables autopilot, clears queued generation
count, and requests a stop at the next safe boundary. Resume is available only
from the authenticated web System view after all runtimes acknowledge it.

Normal generation, rankings, reports, owner submissions, context revisions, and
post creation use `https://provethemwrong-86123.web.app`.
