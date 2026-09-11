#!/usr/bin/env python3
"""Validate a release envelope without executing any candidate code."""
import argparse
import json
from pathlib import Path
import re
import subprocess
from uuid import UUID

REQUEST_PATH = ".ptw-release-request.json"


def validate(repository: Path, request_revision: str, *, deployed: str | None = None):
    def git(*args):
        return subprocess.check_output(["git", "-C", str(repository), *args], text=True).strip()
    if not re.fullmatch(r"[0-9a-f]{40}", request_revision):
        raise ValueError("Invalid release request revision")
    parents = git("rev-list", "--parents", "-n", "1", request_revision).split()
    if len(parents) != 2:
        raise ValueError("Release request must have exactly one deployed parent")
    base = parents[1]
    if deployed and base != deployed:
        raise ValueError("Release request base is no longer deployed")
    if git("diff", "--name-only", base, request_revision) != REQUEST_PATH:
        raise ValueError("Release request changed trusted workflow or source")
    raw = git("show", f"{request_revision}:{REQUEST_PATH}")
    if len(raw) > 4096:
        raise ValueError("Release request is too large")
    manifest = json.loads(raw)
    if set(manifest) != {"version", "id", "base_revision", "revision", "candidate_branch"}:
        raise ValueError("Release request fields do not match the contract")
    identifier = str(UUID(manifest["id"]))
    if manifest["version"] != 2 or manifest["base_revision"] != base or manifest["candidate_branch"] != f"god-candidate/{identifier}":
        raise ValueError("Release request identity is invalid")
    if not re.fullmatch(r"[0-9a-f]{40}", manifest["revision"]):
        raise ValueError("Candidate revision is invalid")
    git("merge-base", "--is-ancestor", base, manifest["revision"])
    if not git("diff", "--name-only", base, manifest["revision"]):
        raise ValueError("Release candidate is empty")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--request", required=True)
    parser.add_argument("--deployed")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    value = validate(args.repository, args.request, deployed=args.deployed)
    if args.output:
        with args.output.open("a") as output:
            for key in ("id", "base_revision", "revision", "candidate_branch"):
                output.write(f"{key}={value[key]}\n")
    else:
        print(json.dumps(value, sort_keys=True))
