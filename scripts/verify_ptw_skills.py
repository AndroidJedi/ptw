#!/usr/bin/env python3
"""Verify canonical PTW skills and their desktop/CLI wiring."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
SKILLS = (
    "commander-god-mode",
    "product-brief-generator",
    "studio-creative-composer",
    "creative-performance-learner",
    "creative-visual-analyzer",
    "studio-phone-hero-generator",
    "studio-manual-agent",
    "template-creation-agent",
    "landing-page-composer",
    "studio-tune-local",
    "studio-ui-visual-audit",
    "ptw-owner-console-incident",
    "ptw-vps-operations",
    "legacy-social-automation-recovery",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def is_generated_skill_artifact(path: Path) -> bool:
    return "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}


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
        if name == "template-creation-agent":
            # Runtime caps the complete system prompt at 6 KiB. Keep enough
            # editing headroom that an ordinary skill update cannot break it.
            require(len((skill / "SKILL.md").read_bytes()) <= 5 * 1024,
                    "template-creation-agent skill exceeds its 5 KiB maintenance budget")

    validation_compose = (ROOT / "docker-compose.validation.yml").read_text()
    require(
        validation_compose.count("./skills:/run/ptw-auth/skills:ro") == 1,
        "Validation canonical read-only skill mount is missing",
    )
    hook = Path(
        subprocess.run(
            ["git", "rev-parse", "--git-path", "hooks/post-merge"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    if not hook.is_absolute():
        hook = ROOT / hook
    require(hook.is_symlink(), "post-merge skill-sync hook is missing")
    require(hook.resolve() == (ROOT / "scripts" / "git-hooks" / "post-merge").resolve(), "wrong post-merge hook")

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

    for retired in (
        "marketing-positioning", "ad-creative-generator", "ad-creative-validator", "ad-studio-composer",
        "natal-landing-builder", "content-result-critic",
        "content-candidate-generator",
        "studio-edit-learner", "landing-edit-learner",
    ):
        require(not (canonical_root / retired).exists(), f"retired {retired} skill remains")
        require(not (desktop_root / retired).exists(), f"retired desktop {retired} skill remains")

    if ROOT == Path("/root/ptw"):
        for path in canonical_root.rglob("*"):
            if is_generated_skill_artifact(path):
                continue
            require(path.stat().st_gid == 10001, f"wrong CLI skill group: {path}")
            require(path.stat().st_mode & 0o020 != 0, f"CLI skill is not group-writable: {path}")

    print("Verified canonical PTW skills and desktop/CLI views.")


if __name__ == "__main__":
    main()
