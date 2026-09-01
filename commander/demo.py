"""Emit deterministic Product Brief → five Creatives → owner approval lineage."""

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
    identifiers = [new_uuid7(timestamp_ms=1_700_000_000_000 + index) for index in range(20)]
    owner_source, project, brief, task_source, brand_kit, run = identifiers[:6]
    creatives = identifiers[6:11]
    (
        review_action, feedback, weight, outcome, render, learning_rule,
        learning_snapshot, approval, receipt,
    ) = identifiers[11:]
    relationships = [
        [project, "derived_from", owner_source], [project, "contains", brief],
        [brief, "derived_from", owner_source], [run, "derived_from", brief],
        [run, "derived_from", task_source], [run, "derived_from", brand_kit],
        [project, "contains", run], [run, "contains", review_action],
        [creatives[0], "contains", render],
        [feedback, "evaluates", creatives[0]], [feedback, "contains", weight],
        [weight, "adjusts", creatives[0]], [run, "contains", outcome],
        [learning_rule, "derived_from", feedback], [run, "derived_from", learning_snapshot],
        [approval, "derived_from", feedback], [run, "contains", receipt],
        *[[run, "contains", creative] for creative in creatives],
    ]
    result_document = {
        "schema": "ptw-result-v1",
        "entities": {
            "owner_idea_source": owner_source, "validation_project": project,
            "product_brief": brief, "owner_task_source": task_source,
            "project_brand_kit": brand_kit, "content_run": run,
            "review_creatives": creatives, "owner_review_action": review_action,
            "approved_creative": creatives[0], "render": render,
            "feedback": feedback, "weight_update": weight, "outcome": outcome,
            "learning_rule": learning_rule, "learning_snapshot": learning_snapshot,
            "creative_approval": approval, "notification_receipt": receipt,
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
