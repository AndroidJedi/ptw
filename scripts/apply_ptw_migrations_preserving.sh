#!/bin/bash
set -Eeuo pipefail
repository=${1:?repository required}
[[ $repository == /root/ptw && $(id -u) == 0 && ${PTW_MIGRATIONS_AUTHORIZED:-0} == 1 && ${PTW_MAINTENANCE_LOCK_HELD:-0} == 1 ]] || exit 2
platform=/opt/ptw/platform
commander=(docker compose --env-file "$platform/.env" --env-file "$repository/.env.commander" --env-file "$repository/.env.owner-gateway" --project-directory "$repository" -f "$repository/docker-compose.commander.yml")
validation=(docker compose --env-file "$platform/.env" --env-file "$repository/.env.commander" --env-file "$repository/.env.owner-gateway" --project-name ptw-validation --project-directory "$repository" -f "$repository/docker-compose.validation.yml")
install -d -m 0700 /opt/ptw/backups/commander
backup_directory=$(mktemp -d /opt/ptw/backups/commander/migration.XXXXXX)
chmod 0700 "$backup_directory"
"${commander[@]}" stop owner-gateway commander-api >/dev/null
"${validation[@]}" stop validation-api >/dev/null
docker exec ptw-commander-db-1 pg_dump -Fc -U ptw_commander -d ptw_commander > "$backup_directory/before.dump"
[[ -s "$backup_directory/before.dump" ]]
chmod 0600 "$backup_directory/before.dump"
sha256sum "$backup_directory/before.dump" > "$backup_directory/before.dump.sha256"
# Capture projections so adding columns/defaults does not resemble data loss.
docker exec ptw-commander-db-1 psql -X -qAt -U ptw_commander -d ptw_commander -c "SELECT jsonb_object_agg(table_name,columns) FROM (SELECT table_name,jsonb_agg(column_name ORDER BY ordinal_position) columns FROM information_schema.columns WHERE table_schema='public' AND table_name<>'commander_schema_migrations' GROUP BY table_name) s" > "$backup_directory/schema.json"
fingerprint() {
    local database=${1:-ptw_commander}
    docker exec -i ptw-commander-db-1 psql -X -qAt -v ON_ERROR_STOP=1 -v baseline="$(<"$backup_directory/schema.json")" -U ptw_commander -d "$database" <<'SQL'
CREATE TEMP TABLE baseline AS SELECT :'baseline'::jsonb document;
CREATE FUNCTION pg_temp.fingerprints() RETURNS TABLE(line text) LANGUAGE plpgsql AS $$
DECLARE item record; projection text; result text;
BEGIN
 FOR item IN SELECT key,value FROM baseline,jsonb_each(document) ORDER BY key LOOP
  SELECT string_agg(quote_ident(c),',') INTO projection FROM jsonb_array_elements_text(item.value) c;
  EXECUTE format('SELECT count(*)::text || '':'' || coalesce(sum(hashtextextended(to_jsonb(t)::text,0)::numeric),0)::text FROM (SELECT %s FROM public.%I) t',projection,item.key) INTO result;
  line := item.key || ':' || result; RETURN NEXT;
 END LOOP;
END $$;
SELECT line FROM pg_temp.fingerprints();
SQL
}
contract_helper="${PTW_TRUSTED_RELEASE_ROOT:-$repository}/scripts/ptw_migration_contracts.py"
python3 "$contract_helper" prepare "$repository" "$backup_directory"
fingerprint > "$backup_directory/before.rows"
rehearsal="ptw_rehearsal_$(date +%s)_$$"
[[ $rehearsal =~ ^ptw_rehearsal_[0-9]+_[0-9]+$ ]]
docker exec ptw-commander-db-1 createdb -U ptw_commander -T template0 "$rehearsal"
live_started=0
live_verified=0
cleanup_rehearsal() {
    local status=$?
    trap - EXIT
    if [[ $live_started == 1 && $live_verified == 0 ]]; then
        # Writers remain stopped. Restore the exact pre-migration database in
        # one transaction; no newly accepted owner work can be discarded.
        docker exec -i ptw-commander-db-1 pg_restore -U ptw_commander -d ptw_commander \
            --clean --if-exists --single-transaction --exit-on-error < "$backup_directory/before.dump" || {
            echo "Database recovery requires operator attention; retained backup: $backup_directory" >&2; exit 1;
        }
    fi
    docker exec ptw-commander-db-1 dropdb -U ptw_commander --if-exists "$rehearsal" >/dev/null
    exit "$status"
}
trap cleanup_rehearsal EXIT
docker exec -i ptw-commander-db-1 pg_restore -U ptw_commander -d "$rehearsal" --exit-on-error < "$backup_directory/before.dump"
"${commander[@]}" run -T --rm --no-deps -e "PTW_MIGRATION_DATABASE=$rehearsal" commander-migrate
python3 "$contract_helper" verify "$repository" "$backup_directory" "$rehearsal"
fingerprint "$rehearsal" > "$backup_directory/rehearsal.rows"
cmp -s "$backup_directory/before.rows" "$backup_directory/rehearsal.rows" || {
    echo "Migration rehearsal changed existing business data; production migration was not started" >&2; exit 1;
}
live_started=1
"${commander[@]}" run -T --rm --no-deps commander-migrate
python3 "$contract_helper" verify "$repository" "$backup_directory" ptw_commander
fingerprint > "$backup_directory/after.rows"
cmp -s "$backup_directory/before.rows" "$backup_directory/after.rows" || {
    echo "Migration changed existing data; retaining the backup for recovery" >&2; exit 1;
}
live_verified=1
echo "Migrations applied; previous business rows verified and backup retained"
