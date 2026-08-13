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

Existing control commands remain available:

```text
/status
/queue
/policy
/approve <approval-uuid>
/reject <approval-uuid>
/reasoning <decision-or-audit-uuid>
/stop
/resume
```

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

Its installed forwarding change is local commit `0db9522`; that deployment
repository has no configured remote. Do not reset it when updating the
independent GitHub repository.

Database and generated assets live in Docker named volumes. Back up both before
upgrading a live installation. Outbox delivery is at-least-once; a process crash
after Telegram accepts a message but before the database commit can duplicate a
reply. Failed deliveries retain a concise error and retry with capped exponential
backoff rather than crashing the worker.
