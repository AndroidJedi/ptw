# Telegram creative runtime

Status: installed locally; external activation requires owner credentials and
DNS.

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

## Owner activation steps

### 1. Create the bot

In Telegram, open the verified `@BotFather` account:

1. Send `/newbot`.
2. Choose its display name and username.
3. Copy the bot token once. Do not paste it into chat, issues, or Git.
4. Send `/start` to the new bot from the Telegram account that will control PTW.

### 2. Discover your numeric IDs

On the VPS, edit the ignored local file `/root/ptw/.env.commander` and replace
only `TELEGRAM_BOT_TOKEN` with the real token. Then run:

```sh
cd /root/ptw
docker compose --env-file .env.commander -f docker-compose.commander.yml \
  run --rm commander-api python -m commander.telegram_identity
```

Copy the reported `user_id` and `chat_id` into
`TELEGRAM_ALLOWED_USER_IDS` and `TELEGRAM_ALLOWED_CHAT_IDS`. Multiple IDs use
commas. Authorization requires both lists to match.

### 3. Provide public HTTPS

Create a DNS A/AAAA record such as `commander.your-domain.example` pointing to
this VPS. Configure the existing HTTPS reverse proxy to send that hostname to:

```text
http://127.0.0.1:8091
```

Set `COMMANDER_PUBLIC_BASE_URL` to the resulting `https://` URL. Telegram will
not accept a plain HTTP webhook.

### 4. Finish secrets and restart

Set a new database password and webhook secret in `.env.commander`. Generate
safe values locally:

```sh
openssl rand -hex 32
openssl rand -hex 32
chmod 600 /root/ptw/.env.commander
```

Use hexadecimal output for `COMMANDER_DB_PASSWORD` to avoid URL escaping. Then:

```sh
cd /root/ptw
docker compose --env-file .env.commander -f docker-compose.commander.yml \
  up -d --build --force-recreate
curl -fsS http://127.0.0.1:8091/healthz
curl -fsS http://127.0.0.1:8091/readyz
```

### 5. Register the webhook

Only after the public HTTPS route works:

```sh
docker compose --env-file .env.commander -f docker-compose.commander.yml \
  run --rm commander-api python -m commander.register_webhook
```

The service validates Telegram's secret-token header, numeric user ID, and chat
ID. Replayed update IDs are ignored.

## Operations

```sh
docker compose --env-file .env.commander -f docker-compose.commander.yml ps
docker compose --env-file .env.commander -f docker-compose.commander.yml logs -f commander-api commander-worker
docker compose --env-file .env.commander -f docker-compose.commander.yml restart commander-api commander-worker
```

Database and generated assets live in Docker named volumes. Back up both before
upgrading a live installation. Outbox delivery is at-least-once; a process crash
after Telegram accepts a message but before the database commit can duplicate a
reply. Failed deliveries retain a concise error and retry with capped exponential
backoff rather than crashing the worker.
