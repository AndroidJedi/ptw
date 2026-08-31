#!/usr/bin/env bash
set -euo pipefail

repository="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
confirmation="${1:-}"
expected="RESET PTW LOCAL OWNER DATA"

if [[ "$confirmation" != "--confirm=$expected" ]]; then
  echo "Refusing irreversible local reset. Use: scripts/reset_ptw_local.sh --confirm='$expected'" >&2
  exit 2
fi

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

python_binary="${repository}/.venv/bin/python"
if [[ ! -x "$python_binary" ]]; then
  python_binary="$(command -v python3)"
fi

"$python_binary" - "$repository" <<'PY'
from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys

repository = Path(sys.argv[1]).resolve()
local_root = (repository / ".local").resolve()
allowed_names = {"studio-workspace", "studio-tune", "owner-experiments"}
targets = [local_root / name for name in sorted(allowed_names)]

run_root = local_root / "owner-experiments" / "records" / "runs"
if run_root.is_dir():
    for entity in run_root.iterdir():
        revisions = sorted(entity.glob("*.json")) if entity.is_dir() else []
        if not revisions:
            continue
        value = json.loads(revisions[-1].read_text(encoding="utf-8"))
        if (value.get("payload") or {}).get("status") in {"queued", "generating"}:
            raise SystemExit(f"refusing reset while local Result run {entity.name} is active")

tune_root = local_root / "studio-tune" / "runs"
if tune_root.is_dir():
    for path in tune_root.glob("*/run.json"):
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("status") in {"queued", "running"}:
            raise SystemExit(f"refusing reset while Studio Tune run {path.parent.name} is active")

local_root.mkdir(parents=True, exist_ok=True)
for target in targets:
    if target.parent.resolve() != local_root or target.name not in allowed_names:
        raise SystemExit(f"refusing non-allowlisted reset target: {target}")
    if target.is_symlink():
        raise SystemExit(f"refusing symlink reset target: {target}")
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(mode=0o700)

for target in targets:
    if any(target.iterdir()):
        raise SystemExit(f"local reset verification failed; store is not empty: {target}")
    print(f"cleared and verified empty: {target.relative_to(repository)}")
PY
