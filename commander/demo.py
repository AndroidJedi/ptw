"""Emit deterministic Product Brief → five candidates → one Result lineage."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .ids import new_uuid7


def run_demo(output_dir: Path, *, reset: bool = True) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    if reset:
        for name in ("projection.json", "events.jsonl", "demo-result.json"):
            target = output_dir / name
            if target.is_file() or target.is_symlink():
                target.unlink()
    identifiers = [new_uuid7(timestamp_ms=1_700_000_000_000 + index) for index in range(19)]
    owner_source, project, brief, task_source, brand_kit, run = identifiers[:6]
    candidates = identifiers[6:11]
    passes = identifiers[11:14]
    result, feedback, weight, outcome, render = identifiers[14:]
    relationships = [
        [project, "derived_from", owner_source], [project, "contains", brief],
        [brief, "derived_from", owner_source], [run, "derived_from", brief],
        [run, "derived_from", task_source], [run, "derived_from", brand_kit],
        [project, "contains", run], [run, "contains", result],
        [result, "derived_from", candidates[0]], [candidates[0], "contains", render],
        [feedback, "evaluates", result], [feedback, "contains", weight],
        [weight, "adjusts", feedback], [run, "contains", outcome],
        *[[run, "contains", candidate] for candidate in candidates],
        *[[run, "contains", critic_pass] for critic_pass in passes],
        *[[critic_pass, "evaluates", candidate] for critic_pass in passes for candidate in candidates[:2]],
    ]
    result_document = {
        "schema": "ptw-result-v1",
        "entities": {
            "owner_idea_source": owner_source, "validation_project": project,
            "product_brief": brief, "owner_task_source": task_source,
            "project_brand_kit": brand_kit, "content_run": run,
            "content_candidates": candidates, "critic_passes": passes,
            "result_creative": result, "render": render,
            "feedback": feedback, "weight_update": weight, "outcome": outcome,
        },
        "relationships": relationships,
    }
    (output_dir / "demo-result.json").write_text(
        json.dumps(result_document, indent=2) + "\n", encoding="utf-8"
    )
    return result_document


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path(".local/commander-demo"))
    parser.add_argument("--no-reset", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run_demo(args.output_dir, reset=not args.no_reset), indent=2))


if __name__ == "__main__":
    main()
