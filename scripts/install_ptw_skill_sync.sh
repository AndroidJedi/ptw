#!/bin/sh
set -eu

repository_root=$(git rev-parse --show-toplevel)
codex_root=${CODEX_HOME:-$(python3 -c 'from pathlib import Path; print(Path.home() / ".codex")')}
desktop_skills="$codex_root/skills"
mkdir -p "$desktop_skills"

for skill_file in "$repository_root"/skills/*/SKILL.md; do
  skill_dir=$(dirname "$skill_file")
  skill_name=$(basename "$skill_dir")
  desktop_skill="$desktop_skills/$skill_name"
  if [ -L "$desktop_skill" ]; then
    resolved=$(python3 -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).resolve())' "$desktop_skill")
    [ "$resolved" = "$skill_dir" ] || {
      echo "skill symlink points elsewhere: $desktop_skill" >&2
      exit 1
    }
  elif [ -e "$desktop_skill" ]; then
    python3 -c 'import os,sys; raise SystemExit(0 if os.path.samefile(sys.argv[1], sys.argv[2]) else 1)' \
      "$desktop_skill" "$skill_dir" || {
        echo "refusing to replace non-canonical skill: $desktop_skill" >&2
        exit 1
      }
  else
    ln -s "$skill_dir" "$desktop_skill"
  fi
done

hook_source="$repository_root/scripts/git-hooks/post-merge"
hook_target=$(git rev-parse --git-path hooks/post-merge)
if [ -L "$hook_target" ]; then
  resolved_hook=$(python3 -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).resolve())' "$hook_target")
  [ "$resolved_hook" = "$hook_source" ] || {
    echo "post-merge hook points elsewhere: $hook_target" >&2
    exit 1
  }
elif [ -e "$hook_target" ]; then
  echo "refusing to replace existing post-merge hook: $hook_target" >&2
  exit 1
else
  hook_link=$(python3 -c 'import os,sys; print(os.path.relpath(sys.argv[1], os.path.dirname(sys.argv[2])))' "$hook_source" "$hook_target")
  ln -s "$hook_link" "$hook_target"
fi

if [ "$(uname -s)" = Linux ] && [ "$(id -u)" -eq 0 ]; then
  chgrp -R 10001 "$repository_root/skills"
  find "$repository_root/skills" -type d -exec chmod 2775 {} +
  find "$repository_root/skills" -type f -exec chmod g+rw {} +
fi

echo "Installed canonical PTW skill links, hook, and applicable CLI permissions."
