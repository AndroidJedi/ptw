#!/bin/sh

set -u

skynet_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
codex_bin=${SKYNET_CODEX_BIN:-codex}
restart_delay=${SKYNET_RESTART_DELAY_SECONDS:-5}
runner_root="$skynet_root/runtime/runner"
stop_requested=0
child_pid=

case "$restart_delay" in
    ''|*[!0-9]*) restart_delay=5 ;;
esac

stop_runner() {
    stop_requested=1
    if [ -n "$child_pid" ]; then
        kill -TERM "$child_pid" 2>/dev/null || true
    fi
}

trap stop_runner INT TERM HUP
mkdir -p "$runner_root"

iteration=0
while [ "$stop_requested" -eq 0 ]; do
    iteration=$((iteration + 1))
    run_id="$(date -u '+%Y%m%dT%H%M%SZ')-$$-$iteration"
    event_log="$runner_root/$run_id.jsonl"
    last_message="$runner_root/$run_id-last-message.md"

    printf '%s run=%s event=started\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$run_id" \
        >> "$runner_root/lifecycle.log"

    "$codex_bin" --ask-for-approval never --search exec \
        --ephemeral \
        --sandbox workspace-write \
        --color never \
        --json \
        --output-last-message "$last_message" \
        --cd "$skynet_root" \
        - < "$skynet_root/WAKE.md" > "$event_log" 2>&1 &
    child_pid=$!
    wait "$child_pid"
    exit_code=$?
    child_pid=

    printf '%s run=%s event=exited status=%s\n' \
        "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$run_id" "$exit_code" \
        >> "$runner_root/lifecycle.log"

    if [ "$stop_requested" -ne 0 ]; then
        break
    fi

    sleep "$restart_delay" &
    child_pid=$!
    wait "$child_pid" 2>/dev/null || true
    child_pid=
done

printf '%s event=supervisor-stopped\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" \
    >> "$runner_root/lifecycle.log"

