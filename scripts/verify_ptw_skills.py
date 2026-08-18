#!/usr/bin/env python3
"""Verify canonical PTW skills and their desktop/CLI wiring."""

from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ("ptw-owner-console-incident", "ptw-vps-operations")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    canonical_root = ROOT / "skills"
    for name in SKILLS:
        skill = canonical_root / name
        require((skill / "SKILL.md").is_file(), f"missing {name}/SKILL.md")
        require((skill / "agents" / "openai.yaml").is_file(), f"missing {name}/agents/openai.yaml")
        frontmatter = (skill / "SKILL.md").read_text().split("---", 2)
        require(len(frontmatter) == 3, f"invalid frontmatter in {name}")
        require(f"name: {name}" in frontmatter[1], f"wrong skill name in {name}")
        require("description:" in frontmatter[1], f"missing description in {name}")

    compose = (ROOT / "docker-compose.commander.yml").read_text()
    require(compose.count("./skills:/run/ptw-auth/skills:ro") == 1, "Commander skill mount is missing")
    require(compose.count("./skills:/run/ptw-auth/skills\n") == 1, "Owner Gateway skill mount is missing")

    desktop_root = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "skills"
    if desktop_root.exists():
        for name in SKILLS:
            desktop = desktop_root / name
            canonical = canonical_root / name
            if desktop.is_symlink():
                require(desktop.resolve() == canonical.resolve(), f"desktop skill {name} is not canonical")
            else:
                require(
                    (desktop / "SKILL.md").read_bytes() == (canonical / "SKILL.md").read_bytes(),
                    f"CLI skill {name} differs from canonical content",
                )

    print("Verified canonical PTW skills and desktop/CLI views.")


if __name__ == "__main__":
    main()
