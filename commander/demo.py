"""Emit deterministic Product Brief correction and owner-learning lineage."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .ids import new_uuid7


def run_demo(output_dir: Path, *, reset: bool = True) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    if reset:
        for name in ("projection.json", "events.jsonl", "demo-result.json", "demo-brief.json"):
            target = output_dir / name
            if target.is_file() or target.is_symlink():
                target.unlink()
    identifiers = [
        new_uuid7(timestamp_ms=1_700_000_000_000 + index)
        for index in range(6)
    ]
    owner_source, project, base_brief, feedback, weight, replacement_brief = identifiers
    relationships = [
        [project, "derived_from", owner_source],
        [project, "contains", base_brief],
        [base_brief, "derived_from", owner_source],
        [feedback, "evaluates", base_brief],
        [feedback, "contains", weight],
        [weight, "adjusts", feedback],
        [replacement_brief, "supersedes", base_brief],
        [replacement_brief, "derived_from", feedback],
        [project, "contains", replacement_brief],
    ]
    document = {
        "schema": "ptw-brief-v1",
        "entities": {
            "owner_idea_source": owner_source,
            "validation_project": project,
            "base_product_brief": base_brief,
            "owner_feedback": feedback,
            "weight_update": weight,
            "replacement_product_brief": replacement_brief,
        },
        "relationships": relationships,
    }
    (output_dir / "demo-brief.json").write_text(
        json.dumps(document, indent=2) + "\n", encoding="utf-8",
    )
    return document


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path(".local/commander-demo"))
    parser.add_argument("--no-reset", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run_demo(args.output_dir, reset=not args.no_reset), indent=2))


if __name__ == "__main__":
    main()
