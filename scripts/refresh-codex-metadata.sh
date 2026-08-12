#!/usr/bin/env bash
set -euo pipefail

metadata_dir=/opt/ptw/persistent-data/runtime
metadata_file=$metadata_dir/codex-version
install -d -m 0755 "$metadata_dir"

if ! command -v codex >/dev/null 2>&1; then
  echo "Codex CLI is not installed or not in PATH." >&2
  exit 1
fi

codex_version=$(codex --version)
case "$codex_version" in
  codex-cli\ *) ;;
  *) echo "Unexpected Codex version output." >&2; exit 1 ;;
esac
printf '%s\n' "$codex_version" > "$metadata_file"
chmod 0644 "$metadata_file"
printf 'Recorded host Codex availability: %s\n' "$codex_version"
