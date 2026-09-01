# SKYNET experiment

This directory is an isolated autonomous competitor to
`apps/commander-web`. Its process memory, implementation, research, generated
artifacts, and runtime records stay here. The competitor remains read-only.

## Run locally

```sh
./skynet/run.sh
```

The launcher deliberately contains no strategy. It starts one fresh
non-interactive Codex run rooted at `skynet/`; whenever that run exits or
crashes, it starts another. `Ctrl-C` or `SIGTERM` stops the child and the
supervisor. A later invocation reconstructs progress from durable files below
`skynet/`, not from a resumed chat.

Generated runtime state is under `skynet/runtime/` and intentionally ignored by
the parent Git repository. JSONL agent events and lifecycle records are under
`runtime/runner/`.

The default Codex model and any future model/tool routing are intentionally not
specified by the launcher. The supervisor uses a 15-minute restart cooldown so
an evidence-saturated hold does not spend nearly continuous agent runs. For a
harness test only, `SKYNET_CODEX_BIN` can point to a fake executable and
`SKYNET_RESTART_DELAY_SECONDS` can reduce the restart delay.

## Telegram output

The autonomous agent has no bot credential. It creates an idempotent outbound
event instead:

```sh
python3 skynet/tools/telegram_outbox.py \
  --event-id skynet.experiment-id.iteration-1 \
  --text 'SKYNET · experiment-id · iteration 1 · competition candidate' \
  --photo skynet/path/to/candidate.png
```

A separately trusted host process drains the queue with the existing
`TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_CHAT_IDS`, and
`TELEGRAM_OWNER_CHAT_ID` environment. It sends directly with `sendMessage` or
`sendPhoto`; it never polls or installs a webhook:

```sh
python3 skynet/host/telegram_sender.py
```

Each event is reserved before network I/O and attempted at most once. If the
sender dies after reservation, restart records an ambiguous receipt and does
not retry. Receipts remain under `runtime/telegram/receipts/`.

For a VPS run, use a dedicated unprivileged SKYNET checkout/process and a
separate credential-owning sender service. Do not pass the Telegram token into
the Codex process or reuse the independent platform bridge's Codex credentials.

## Cheap external-trigger reconciliation

When the creative portfolio is evidence-saturated, refresh the deterministic
local trigger snapshot before spending another image or research call:

```sh
python3 skynet/tools/reconcile_triggers.py
```

The tool fingerprints queued/reserved/receipted outbound events, the local
owner-experiment store, and explicit local media/provider authority records. It
never polls Telegram or inspects environment credentials. An unchanged
fingerprint means the existing creative decision should be preserved unless
some other durable evidence has appeared.
