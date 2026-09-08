#!/bin/bash
set -Eeuo pipefail

if [[ $# -ne 2 || $1 != --confirm || $2 != "DEPLOY OWNER CONSOLE WEB" ]]; then
    echo 'usage: scripts/deploy_owner_console_web.sh --confirm "DEPLOY OWNER CONSOLE WEB"' >&2
    exit 2
fi

repository=$(cd "$(dirname "$0")/.." && pwd)
cd "$repository"

[[ $(git branch --show-current) == main ]] || { echo "Owner Console deployment requires main" >&2; exit 1; }
[[ -z $(git status --porcelain) ]] || { echo "Owner Console deployment requires a clean worktree" >&2; exit 1; }
git fetch origin main
[[ $(git rev-parse HEAD) == $(git rev-parse origin/main) ]] || {
    echo "Owner Console deployment requires HEAD to equal origin/main" >&2
    exit 1
}

npm --prefix apps/commander-web run check
npm --prefix apps/commander-web run test:e2e
python3 scripts/verify_ptw_skills.py
git diff --check
firebase deploy --only hosting:owner-console
PYTHONDONTWRITEBYTECODE=1 python3 skills/ptw-owner-console-incident/scripts/audit_live_owner_console.py
