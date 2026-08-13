# Telegram creative runtime

Status: active through the existing `@ptw_commander_bot` long-polling transport.

PTW already had an operational Telegram bot. Commander reuses bot ID
`7930450559` (`@ptw_commander_bot`); do not create or register another bot. The
existing `/opt/ptw/platform` API remains the sole `getUpdates` consumer and
forwards only `/creative` updates over the internal Docker network. The new
worker uses the same bot identity to return generated images.

## Available command

Send a text message:

```text
/creative They said I would quit | Day one starts now | WATCH ME
```

The three pipe-separated fields are Hook, Caption, and CTA. Caption and CTA are
optional. You may attach a photo and put the same command in its caption; the
photo becomes the full-bleed hero background. Commander returns a 1080x1920 PNG
marked ready for review. It does not publish or spend money.

After receiving the image, reply directly to that image:

```text
/feedback 4 Strong hook, CTA needs work
```

The reply link lets Commander resolve the Creative UUID automatically. You do
not need to copy the ID shown in the caption. Feedback and component-weight
updates are persisted as separate UUID entities with typed graph edges.

Use `/graph` whenever you want to see what Commander currently knows. Views are
bounded for Telegram but show permanent IDs; PostgreSQL retains the full entity
and relationship history.

Existing control commands remain available:

```text
/status
/queue
/graph
/graph hypotheses
/graph weights
/graph creative <creative-uuid>
/policy
/approve <approval-uuid>
/reject <approval-uuid>
/reasoning <decision-or-audit-uuid>
/stop
/resume
```

Creative-ideation research is a separate, explicitly typed workflow:

```text
/research hooks for skeptical founders considering a public challenge
```

Commander persists bounded Source findings with canonical URLs, then creates
only proposed hypotheses derived from those Source UUIDs. Generate from a
returned hypothesis without copying its claim:

```text
/creative from <hypothesis-uuid>
```

This command is deliberately limited to creative ideas. Future market, product,
competitor, or technical research must use distinct research types and policies.
The runtime requires `OPENAI_API_KEY` in `/opt/ptw/platform/.env`; optionally set
`COMMANDER_RESEARCH_MODEL` (default `gpt-5-mini`). Restart both Compose stacks
after adding it. Never send the key through Telegram or commit it to Git.

## Free-form engineering requests

Use `/task` as the default way to tell Commander what to fix, implement, review,
or change:

```text
/task Fix the login error shown in the attached screenshot, add regression tests, and report what changed.
```

The remainder of the message is free-form. Commander queues it through the
existing specification-driven engineering workflow for the PTW repository.
`/engineer repo=ptw <task>` remains a compatibility alias.

To provide visual context, attach a screenshot or image and put `/task ...` in
the attachment caption. The established poller stores the attachment privately
and links it to the queued job. Do not include credentials or tokens in task
text or screenshots.

## Transport ownership

Never call `setWebhook` for this bot while the established platform uses
`getUpdates`; Telegram permits only one update-consumption mode and a webhook
would break the existing `/engineer`, `/status`, and notification workflows.

The creative Compose services read the existing root-owned environment file at
`/opt/ptw/platform/.env` at runtime. The token is not copied into Git or written
to documentation. `TELEGRAM_ALLOWED_CHAT_IDS` may be configured separately;
for private owner chats it defaults to the existing allowed user IDs.

The bridge endpoint is not public. Both stacks share the internal
`ptw-agent-platform_backend` Docker network, and the established poller
authenticates using the already-shared bot credential. The creative service
still rechecks both Telegram user and chat authorization.

## Operations

```sh
docker compose --env-file .env.commander -f docker-compose.commander.yml ps
docker compose --env-file .env.commander -f docker-compose.commander.yml logs -f commander-api commander-worker
docker compose --env-file .env.commander -f docker-compose.commander.yml restart commander-api commander-worker
```

The forwarding poller lives in `/opt/ptw/platform`. After changing its source,
rebuild only its API with:

```sh
cd /opt/ptw/platform
docker compose up -d --build commander-api
```

Its installed forwarding change is local commit `0db9522`, and the free-form
`/task` command is local commit `c21febf`. Feedback forwarding is `78f4dcd` and
graph inspection forwarding is `d28b7d1`. That deployment repository has no
configured upstream for this history. Do not reset it when updating the
independent GitHub repository.

Database and generated assets live in Docker named volumes. Back up both before
upgrading a live installation. Outbox delivery is at-least-once; a process crash
after Telegram accepts a message but before the database commit can duplicate a
reply. Failed deliveries retain a concise error and retry with capped exponential
backoff rather than crashing the worker.
