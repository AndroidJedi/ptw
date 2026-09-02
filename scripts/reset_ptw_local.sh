#!/usr/bin/env bash
set -euo pipefail

repository="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
scope=""
confirmation=""
while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --scope) scope="${2:-}"; shift 2 ;;
    --scope=*) scope="${1#*=}"; shift ;;
    --confirm) confirmation="${2:-}"; shift 2 ;;
    --confirm=*) confirmation="${1#*=}"; shift ;;
    *) echo "usage: scripts/reset_ptw_local.sh --scope owner-briefs --confirm='RESET PTW LOCAL BRIEF DATA'" >&2; exit 2 ;;
  esac
done

[[ "$scope" == "owner-briefs" ]] || {
  echo "only the owner-briefs scope is allowed" >&2
  exit 2
}
[[ "$confirmation" == "RESET PTW LOCAL BRIEF DATA" ]] || {
  echo "exact local Product Brief reset confirmation is required" >&2
  exit 2
}

target="$repository/.local/owner-briefs"
local_root="$repository/.local"
[[ "$target" == "$local_root/owner-briefs" ]] || {
  echo "refusing unexpected reset target: $target" >&2
  exit 1
}
[[ ! -L "$target" ]] || { echo "refusing symlink reset target" >&2; exit 1; }

if command -v lsof >/dev/null 2>&1; then
  for port in 8088 5173; do
    while IFS= read -r pid; do
      [[ -n "$pid" ]] || continue
      process_cwd="$(lsof -a -p "$pid" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p' | head -n 1)"
      if [[ "$process_cwd" == "$repository" || "$process_cwd" == "$repository/"* ]]; then
        echo "refusing reset while local PTW service on port $port is active" >&2
        exit 1
      fi
    done < <(lsof -nP -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
  done
fi

python_binary="$repository/.venv/bin/python"
[[ -x "$python_binary" ]] || python_binary="$(command -v python3)"
"$python_binary" - "$target" "$local_root" <<'PY'
from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys

target = Path(sys.argv[1])
local_root = Path(sys.argv[2]).resolve()
if target.resolve() != local_root / "owner-briefs" or target.parent.resolve() != local_root:
    raise SystemExit(f"refusing non-allowlisted reset target: {target}")
if target.is_symlink():
    raise SystemExit(f"refusing symlink reset target: {target}")

brief_root = target / "records" / "briefs"
if brief_root.is_dir():
    for entity in brief_root.iterdir():
        revisions = sorted(entity.glob("*.json")) if entity.is_dir() else []
        if not revisions:
            continue
        value = json.loads(revisions[-1].read_text(encoding="utf-8"))
        if (value.get("payload") or {}).get("status") == "generating":
            raise SystemExit(f"refusing reset while Product Brief {entity.name} is generating")

local_root.mkdir(parents=True, exist_ok=True)
if target.exists():
    shutil.rmtree(target)
target.mkdir(mode=0o700)
if any(target.iterdir()):
    raise SystemExit("local owner-briefs reset verification failed")
print("cleared and verified only .local/owner-briefs")
PY
