#!/usr/bin/env python3
"""Create a conservative component plan from two committed PTW revisions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = ("commander", "validation", "owner-gateway", "commander-god")
GOD_ONLY_FILES = {
    "validation_pipeline/commander_chat.py",
    "validation_pipeline/commander_chat_worker.py",
    "validation_pipeline/commander_host_api.py",
    "validation_pipeline/commander_release.py",
}


def _matches(path: str, prefixes: Iterable[str], exact: Iterable[str] = ()) -> bool:
    return path in exact or any(path.startswith(prefix) for prefix in prefixes)


def classify(paths: Iterable[str]) -> dict[str, object]:
    changed = sorted(set(paths))
    build = {name: False for name in COMPONENTS}
    restart = {name: False for name in COMPONENTS}
    hosting = {"owner-console": False, "public-landings": False}
    migrations = False
    known = set()

    for path in changed:
        matched = False
        if _matches(path, ("commander/",), ("requirements-commander.txt",)):
            build["commander"] = restart["commander"] = True
            matched = True
        if (
            path not in GOD_ONLY_FILES
            and _matches(
                path,
                ("validation_pipeline/", "natal/assets/"),
                ("requirements-validation.txt", "commander/ids.py", "commander/__init__.py"),
            )
        ):
            build["validation"] = restart["validation"] = True
            matched = True
        if _matches(path, ("owner_gateway/",), ("requirements-owner-gateway.txt",)):
            build["owner-gateway"] = restart["owner-gateway"] = True
            matched = True
        if _matches(
            path,
            ("commander_god/",),
            (
                "requirements-commander-god.txt",
                "validation_pipeline/__init__.py",
                "validation_pipeline/commander_chat.py",
                "validation_pipeline/commander_chat_worker.py",
                "validation_pipeline/commander_host_api.py",
                "validation_pipeline/commander_release.py",
            ),
        ):
            build["commander-god"] = restart["commander-god"] = True
            matched = True
        if path == "docker-compose.commander.yml":
            for name in ("commander", "owner-gateway", "commander-god"):
                restart[name] = True
            matched = True
        if path == "docker-compose.validation.yml":
            restart["validation"] = True
            matched = True
        if path.startswith("db/migrations/"):
            migrations = True
            matched = True
        if path.startswith("apps/commander-web/"):
            hosting["owner-console"] = True
            matched = True
        if path.startswith("apps/landing-web/"):
            hosting["public-landings"] = True
            matched = True
        if path in {"firebase.json", ".firebaserc"}:
            hosting = {name: True for name in hosting}
            matched = True
        if path == ".dockerignore":
            build = {name: True for name in build}
            restart = {name: True for name in restart}
            matched = True
        if _matches(
            path,
            ("docs/", "tests/", "scripts/", "skills/", "config/", ".github/", ".vscode/", "deploy/"),
            (
                "AGENTS.md", "README.md", "DESIGN_RULES.md", "project.components.json",
                ".gitignore", ".env.commander.example",
            ),
        ):
            matched = True
        if matched:
            known.add(path)

    unmapped = sorted(set(changed) - known)
    if unmapped:
        # Unknown production files fail toward a complete application rebuild.
        build = {name: True for name in build}
        restart = {name: True for name in restart}
        hosting = {name: True for name in hosting}

    return {
        "version": 1,
        "changed_paths": changed,
        "unmapped_paths": unmapped,
        "build": build,
        "restart": restart,
        "hosting": hosting,
        "migrations": migrations,
    }


def git(*arguments: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(ROOT), *arguments], text=True,
    ).strip()


def create_plan(base: str, target: str, release_tag: str) -> dict[str, object]:
    base_revision = git("rev-parse", f"{base}^{{commit}}")
    target_revision = git("rev-parse", f"{target}^{{commit}}")
    subprocess.run(
        ["git", "-C", str(ROOT), "merge-base", "--is-ancestor", base_revision, target_revision],
        check=True,
    )
    paths = git("diff", "--name-only", f"{base_revision}..{target_revision}").splitlines()
    plan = classify(paths)
    plan.update({
        "mode": "selective",
        "release_tag": release_tag,
        "base_revision": base_revision,
        "target_revision": target_revision,
    })
    return plan


def validate_plan(path: Path, release_tag: str, target: str) -> dict[str, object]:
    plan = json.loads(path.read_text(encoding="utf-8"))
    if plan.get("version") != 1 or plan.get("release_tag") != release_tag:
        raise ValueError("release plan identity is invalid")
    if plan.get("target_revision") != target:
        raise ValueError("release plan revision is invalid")
    for field in ("build", "restart"):
        values = plan.get(field)
        if not isinstance(values, dict) or set(values) != set(COMPONENTS):
            raise ValueError(f"release plan {field} set is invalid")
        if any(type(value) is not bool for value in values.values()):
            raise ValueError(f"release plan {field} values are invalid")
    hosting = plan.get("hosting")
    if not isinstance(hosting, dict) or set(hosting) != {"owner-console", "public-landings"}:
        raise ValueError("release plan hosting set is invalid")
    if any(type(value) is not bool for value in hosting.values()):
        raise ValueError("release plan hosting values are invalid")
    if type(plan.get("migrations")) is not bool:
        raise ValueError("release plan migration value is invalid")
    mode = plan.get("mode")
    if mode == "selective":
        base = plan.get("base_revision")
        if not isinstance(base, str):
            raise ValueError("release plan base revision is invalid")
        expected = create_plan(base, target, release_tag)
        if plan != expected:
            raise ValueError("release plan does not match the committed changes")
    elif mode == "full":
        if not all(plan["build"].values()) or not all(plan["restart"].values()):
            raise ValueError("full release plan must build and restart every component")
        if not all(plan["hosting"].values()):
            raise ValueError("full release plan must publish both web targets")
    else:
        raise ValueError("release plan mode is invalid")
    return plan


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base")
    parser.add_argument("--target", default="HEAD")
    parser.add_argument("--release-tag", required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--validate", type=Path)
    args = parser.parse_args()
    if args.validate:
        target = git("rev-parse", f"{args.target}^{{commit}}")
        plan = validate_plan(args.validate, args.release_tag, target)
    else:
        if not args.base:
            parser.error("--base is required when creating a plan")
        plan = create_plan(args.base, args.target, args.release_tag)
    payload = json.dumps(plan, sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")


if __name__ == "__main__":
    main()
