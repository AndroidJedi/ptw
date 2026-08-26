#!/usr/bin/env python3
"""Validate or deterministically refresh the versioned Result writing corpus."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "skills/content-candidate-generator/references/corpus"
EXAMPLES = CORPUS / "examples.jsonl"
MANIFEST = CORPUS / "manifest.json"
EXPECTED_COUNTS = {
    "natal_landing": 10,
    "natal_online": 5,
    "natal_business": 10,
    "sesh": 10,
    "openforcoffee": 5,
}
REQUIRED_FIELDS = {
    "example_id", "excerpt", "source_project", "source_repository", "source_path",
    "source_commit", "excerpt_sha256", "language", "artifact_type", "output_profiles",
    "audience", "product", "funnel_stage", "techniques", "quality_tier", "restrictions",
}


def canonical_line(value: dict[str, object]) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh-digests", action="store_true")
    args = parser.parse_args()
    items = [json.loads(line) for line in EXAMPLES.read_text().splitlines() if line.strip()]
    errors: list[str] = []
    seen: set[str] = set()
    counts: dict[str, int] = {}
    for item in items:
        if set(item) != REQUIRED_FIELDS:
            errors.append(f"{item.get('example_id')}: fields do not match v1")
            continue
        example_id = str(item["example_id"])
        if example_id in seen:
            errors.append(f"{example_id}: duplicate ID")
        seen.add(example_id)
        digest = hashlib.sha256(str(item["excerpt"]).encode()).hexdigest()
        if args.refresh_digests:
            item["excerpt_sha256"] = digest
        elif item["excerpt_sha256"] != digest:
            errors.append(f"{example_id}: excerpt digest mismatch")
        project = str(item["source_project"])
        counts[project] = counts.get(project, 0) + 1
        if item["quality_tier"] not in {"canonical", "supporting", "negative"}:
            errors.append(f"{example_id}: unknown quality tier")
        if item["quality_tier"] == "negative" and "never_use_as_imitation_target" not in item["restrictions"]:
            errors.append(f"{example_id}: negative example lacks imitation restriction")
        if not item["source_path"] or len(str(item["source_commit"])) != 40:
            errors.append(f"{example_id}: incomplete source provenance")
    if len(items) != 40 or counts != EXPECTED_COUNTS:
        errors.append(f"corpus distribution mismatch: count={len(items)} projects={counts}")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    if args.refresh_digests:
        data = "\n".join(canonical_line(item) for item in items) + "\n"
        EXAMPLES.write_text(data)
        manifest = json.loads(MANIFEST.read_text())
        manifest["examples_sha256"] = hashlib.sha256(data.encode()).hexdigest()
        MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    else:
        manifest = json.loads(MANIFEST.read_text())
        if manifest.get("example_count") != len(items):
            errors.append("manifest example_count mismatch")
        if manifest.get("project_counts") != EXPECTED_COUNTS:
            errors.append("manifest project_counts mismatch")
        if manifest.get("examples_sha256") != hashlib.sha256(EXAMPLES.read_bytes()).hexdigest():
            errors.append("manifest examples_sha256 mismatch")
        if errors:
            print("\n".join(errors), file=sys.stderr)
            return 1
    print(f"Verified {len(items)} Result writing examples across {len(counts)} source projects")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
