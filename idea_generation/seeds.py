from __future__ import annotations

import re
from pathlib import Path


def load(root: Path) -> tuple[str, list[dict[str, str]]]:
    mission = (root / "docs/TASK_450M_5Y.md").read_text()
    contexts = []
    for path in sorted((root / "docs/contexts").glob("C*.md")):
        prompt = path.read_text()
        code_match = re.search(r"\*\*Code:\*\* `(C\d{2})`", prompt)
        title_match = re.search(r"^# C\d{2} — (.+)$", prompt, re.MULTILINE)
        if not code_match or not title_match: raise ValueError(f"invalid context seed: {path}")
        contexts.append({"code": code_match.group(1), "name": title_match.group(1), "prompt": prompt})
    return mission, contexts
