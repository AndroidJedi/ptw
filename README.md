# PTW Result bridge

This independent platform is the bounded provider bridge for PTW.
It exposes exactly four authenticated JSON modes and one reviewed non-human
graphic mode. PostgreSQL `jobs` are the durable provider queue; they are not an
owner task system.

Services:

- `commander-api`: authenticated enqueue/result/asset endpoints, capabilities,
  health, and the one established Telegram poller;
- `commander-worker`: fresh schema-bound Codex execution with private mapped
  enhancement references and one-call graphic handling;
- `postgres`: preserved queue, invocation, event, and emergency-stop authority;
- `caddy`: health edge only.

Telegram is emergency-only. Every authorized message is forwarded to the PTW
application boundary, which accepts `/help`, `/status`, and `/stop`; every
other message receives the Owner Console link and cannot create a job.

The API applies numbered additive migrations under an advisory lock. Existing
platform database history is preserved during application resets. Per-attempt
idempotency keys are unique for structured provider jobs.

```bash
cp .env.example .env
# Set POSTGRES_PASSWORD, TELEGRAM_BOT_TOKEN, and TELEGRAM_ALLOWED_USER_IDS.
./scripts/bootstrap.sh
./scripts/smoke-test.sh
```

Never commit `.env`, print the Telegram token, expose generated-asset paths, or
put rendered image base64 into logs.
