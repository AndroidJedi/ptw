# Telegram creative runtime

Status: active through the existing `@ptw_commander_bot` long-polling transport.

PTW already had an operational Telegram bot. Commander reuses bot ID
`7930450559` (`@ptw_commander_bot`); do not create or register another bot. The
existing `/opt/ptw/platform` API remains the sole `getUpdates` consumer and
forwards only `/creative` updates over the internal Docker network. The new
worker uses the same bot identity to return generated images.

## Available command

### Ten-context ad estimation

Inspect an Idea Evolution idea and tap **Generate 10 ads**, or send:

```text
/ads from <idea-id>
```

Idea Evolution validates and snapshots the selected idea. Commander creates ten
high-quality image posts and saves all ten before Telegram sends the first one.
Review remains serialized. Reply to the active image:

```text
/estimate 1.8 4 Strong proof; simplify the lower copy
```

The estimate and feedback are saved first. Then only that image's producing
context examines the final image and records its structured conclusion; the
next image is queued only after that conclusion commits.

```text
/ads status [batch-id]
/ads continue <batch-id>
/ads ranking [batch-id]
/ad_contexts
/ad_context A01
/ad_context_set A01 <prompt>
/ad_context_name A01 <name>
/ad_context_history A01
/ad_context_restore A01 <version>
/ad_context_enable A01
/ad_context_disable A01
```

Only one batch per chat can be in owner review at once. Later batches may finish
generation and wait in `review_ready`. Reply delivery maps resolve Creative
UUIDs automatically; the owner never has to manage them.

The established poller must route `/ads from` and the Idea button callback to
Idea Evolution, and route `/estimate`, `/ads status|continue|ranking`, and
`/ad_context*` to Commander. A capability is not production-ready until these
routes, the three Commander services, provider credentials, delivery mapping,
restart continuation, and a real reply cycle have been verified.

### Existing creative command

Request one hook as a Telegram text message, without generating an image:

```text
/creative hook [optional brief]
```

Commander replies with only hook text. A brief-bearing request remains
text-only and selects the best matching stored creative-research hypothesis;
it never falls through to Story rendering or image feedback.

Each new creative task produces a different delivered variant. Repeating the
same hook brief rotates through matching research hypotheses, then versioned
copy variants; repeating a Story request changes its hook variant. Every
selection is persisted for audit. Telegram retries with the same update ID are
deduplicated and return no second creative.

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
/inspect TASK-<id>
/inspect ISSUE-<id>
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
/research creative hooks for skeptical founders considering a public challenge
/research product retention mechanics for public accountability apps
/research design evidence for progress visualization and social proof
/research engineering primary-source guidance for offline-first sync
```

Research is a tracked long-running task. Telegram first returns `TASK-<id>` and
an `/inspect` instruction; the final source/hypothesis response begins with the
same task ID. The operational ledger stores the bridge result. A bridge failure
creates an inspectable issue and performs one bounded retry before failing.

Consume creative research with `/creative from <hypothesis-id>`. Consume
product, design, or engineering research with
`/task from <hypothesis-id> <request>`; the task specification includes the
sourced claim, direction, owner, and source summaries and logs consumption.

Commander persists bounded Source findings with canonical URLs, then creates
only proposed hypotheses derived from those Source UUIDs. Generate from a
returned hypothesis without copying its claim:

```text
/creative from <hypothesis-uuid>
```

Each command has a distinct owner and research type; findings are not pooled as
unowned generic context.
The deployed runtime uses the VPS's existing authenticated Codex agent for web
research, so it does not require a second API key. `OPENAI_API_KEY` remains an
optional provider override; never send credentials through Telegram or Git.

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

Each task is acknowledged and then reports its start, completion, and result.
If execution is blocked, Commander creates and reports an `ISSUE-<id>`, logs
bounded diagnostic and resolution attempts, resolves it autonomously when
possible, and resumes the original `TASK-<id>`. Inspect either ID at any time
with `/inspect`; `/cancel <numeric-task-id>` also interrupts issue resolution.

A privileged host operator can produce a secret-scrubbed handoff for another
agent with `python -m engineering.state_export`, optionally scoped to a task or
issue ID. The exporter belongs to the established platform checkout and does
not copy its unrelated source history into this repository.

### Codex workspace acceptance gate

A workspace session registers an accepted implementation task at Commander's
authenticated `POST /internal/workspace/tasks` route before changing files.
Commander commits the `TASK-<number>`, interpreted scope, session ID, target
chat, and Telegram outbox message atomically. The workspace then polls the
acknowledgement route and may start only after Telegram has returned a real
message ID. A restart cannot erase pending delivery because both the task and
outbox item are PostgreSQL records.

After a host reboot or Commander restart, perform a real delivery probe before
declaring the bridge operational. Use a fresh task ID reserved for the probe;
the command exits nonzero unless the worker delivers the message and records
Telegram's message ID:

```sh
set -a
. /opt/ptw/platform/.env
set +a
python3 -m commander.verify_workspace_ack \
  --task-id TASK-<fresh-number> \
  --scope "Post-restart acknowledgement bridge verification; no implementation" \
  --session-id "startup-verification-<timestamp>" \
  --chat-id <allowed-owner-chat-id>
```

Do not place the token in the command line or logs. A health check, a pending
outbox row, or a mocked Bot API response is not completion evidence.

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
docker compose --env-file .env.commander -f docker-compose.commander.yml logs -f commander-api commander-worker commander-ad-worker
docker compose --env-file .env.commander -f docker-compose.commander.yml restart commander-api commander-worker commander-ad-worker
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
