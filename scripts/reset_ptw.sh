#!/bin/sh
set -eu

confirmation=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --confirm) confirmation=$2; shift 2 ;;
    *) echo "usage: $0 --confirm 'RESET PTW PRODUCTION'" >&2; exit 2 ;;
  esac
done
[ "$(id -u)" -eq 0 ] || { echo "reset must run as root" >&2; exit 1; }
[ "$confirmation" = "RESET PTW PRODUCTION" ] || { echo "exact confirmation is required" >&2; exit 2; }

commander_root=/root/ptw
platform_root=/opt/ptw/platform
commander_compose="docker compose --env-file $commander_root/.env.commander -f $commander_root/docker-compose.commander.yml"
platform_compose="docker compose --env-file $platform_root/.env --env-file $commander_root/.env.owner-gateway -f $platform_root/docker-compose.yml"
idea_compose="docker compose --env-file $platform_root/.env --env-file $commander_root/.env.owner-gateway -f $commander_root/docker-compose.idea-generation.yml"

# Exact app processes only. PostgreSQL, Caddy, owner gateway, root broker, Git,
# SSH, credentials, volumes, and Git stay intact.
$commander_compose stop commander-api commander-worker commander-ad-worker >/dev/null
$idea_compose stop idea-generation-api >/dev/null 2>&1 || true
$platform_compose stop commander-api commander-worker git-watcher >/dev/null 2>&1 || true

$commander_compose exec -T commander-db psql -X -v ON_ERROR_STOP=1 -U ptw_commander -d ptw_commander \
  -c 'DROP SCHEMA public CASCADE; CREATE SCHEMA public AUTHORIZATION ptw_commander;'
$platform_compose exec -T postgres sh -c \
  'psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public AUTHORIZATION \"$POSTGRES_USER\";"'

docker run --rm -v ptw_commander-assets:/data alpine:3.22 sh -c \
  'find /data -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +'
for live_directory in \
  /opt/ptw/workspaces/incoming \
  /opt/ptw/workspaces/jobs \
  /opt/ptw/persistent-data/runtime
do
  case "$live_directory" in
    /opt/ptw/workspaces/incoming|/opt/ptw/workspaces/jobs|/opt/ptw/persistent-data/runtime) ;;
    *) echo "refusing unexpected live directory: $live_directory" >&2; exit 1 ;;
  esac
  [ -d "$live_directory" ] || continue
  find "$live_directory" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
done

$commander_compose run --rm commander-migrate
$idea_compose run --rm --no-deps idea-generation-api python -m idea_generation.manage migrate
$idea_compose run --rm --no-deps idea-generation-api python -m idea_generation.manage seed
$platform_compose run --rm commander-api python -c \
  'from common.database import apply_migrations; apply_migrations()'
$platform_compose run --rm commander-api python -c \
  'import os, psycopg; from common.database import database_url; owner=int(os.environ["PLATFORM_OWNER_TELEGRAM_ID"]); c=psycopg.connect(database_url()); c.execute("INSERT INTO users(telegram_user_id,role) VALUES(%s,%s) ON CONFLICT(telegram_user_id) DO NOTHING",(owner,"operator")); c.commit(); c.close()'

$commander_compose up -d commander-api commander-worker commander-ad-worker >/dev/null
$idea_compose up -d idea-generation-api >/dev/null
$platform_compose up -d commander-api commander-worker git-watcher >/dev/null 2>&1 || true

$commander_compose exec -T commander-db psql -X -v ON_ERROR_STOP=1 -U ptw_commander -d ptw_commander -At <<'SQL'
DO $$
DECLARE failures text;
BEGIN
  SELECT string_agg(label || '=' || value, ', ') INTO failures FROM (
    VALUES
      ('missions', (SELECT count(*) FROM missions)),
      ('active_mission', (SELECT count(*) FROM missions WHERE code='MISSION_20M_3Y' AND is_active)),
      ('contexts', (SELECT count(*) FROM contexts)),
      ('context_revisions', (SELECT count(*) FROM context_revisions)),
      ('ad_contexts', (SELECT count(*) FROM commander_ad_contexts)),
      ('ad_context_revisions', (SELECT count(*) FROM commander_ad_context_revisions)),
      ('generations', (SELECT count(*) FROM generations)),
      ('ideas', (SELECT count(*) FROM ideas)),
      ('evaluations', (SELECT count(*) FROM idea_evaluations)),
      ('idea_submissions', (SELECT count(*) FROM idea_submissions)),
      ('idea_submission_drafts', (SELECT count(*) FROM idea_submission_drafts)),
      ('guidance', (SELECT count(*) FROM guidance)),
      ('idea_executions', (SELECT count(*) FROM executions)),
      ('reports', (SELECT count(*) FROM reports)),
      ('idea_telegram_events', (SELECT count(*) FROM telegram_events)),
      ('idea_telegram_inbox', (SELECT count(*) FROM telegram_inbox)),
      ('idea_telegram_offsets', (SELECT count(*) FROM telegram_offsets)),
      ('laval_runs', (SELECT count(*) FROM laval_runs)),
      ('entities', (SELECT count(*) FROM commander_entities)),
      ('relationships', (SELECT count(*) FROM commander_relationships)),
      ('tasks', (SELECT count(*) FROM commander_tasks)),
      ('outbox', (SELECT count(*) FROM commander_outbox)),
      ('policy_evaluations', (SELECT count(*) FROM commander_policy_evaluations)),
      ('session_checkpoints', (SELECT count(*) FROM commander_session_checkpoints)),
      ('telegram_inbox', (SELECT count(*) FROM commander_telegram_inbox)),
      ('telegram_deliveries', (SELECT count(*) FROM commander_telegram_deliveries)),
      ('ad_batches', (SELECT count(*) FROM commander_ad_batches)),
      ('ad_slots', (SELECT count(*) FROM commander_ad_slots)),
      ('ad_executions', (SELECT count(*) FROM commander_ad_executions)),
      ('ad_metric_imports', (SELECT count(*) FROM commander_ad_metric_imports)),
      ('reviews', (SELECT count(*) FROM commander_creative_reviews))
  ) AS counts(label,value)
  WHERE (label IN ('missions','active_mission') AND value<>1)
     OR (label IN ('ad_contexts','ad_context_revisions') AND value<>10)
     OR (label NOT IN ('missions','active_mission','ad_contexts','ad_context_revisions') AND value<>0);
  IF failures IS NOT NULL THEN RAISE EXCEPTION 'clean checkpoint failed: %', failures; END IF;
END $$;
SQL

$platform_compose exec -T postgres sh -c \
  'psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<'SQL'
DO $$
BEGIN
  IF (SELECT count(*) FROM jobs) <> 0
     OR (SELECT count(*) FROM users) <> 1
     OR (SELECT count(*) FROM platform_control) <> 1
     OR (SELECT count(*) FROM sessions) <> 0
     OR (SELECT count(*) FROM events) <> 0
     OR (SELECT count(*) FROM git_notifications) <> 0
     OR (SELECT count(*) FROM engineering_artifacts) <> 0
     OR (SELECT count(*) FROM engineering_runs) <> 0
     OR (SELECT count(*) FROM telegram_attachments) <> 0
     OR (SELECT count(*) FROM engineering_issues) <> 0
     OR (SELECT count(*) FROM engineering_issue_logs) <> 0 THEN
    RAISE EXCEPTION 'platform clean checkpoint failed';
  END IF;
END $$;
SQL

echo "clean reset complete; Generation 1 remains manual"
