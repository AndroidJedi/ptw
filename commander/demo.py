"""Emit a deterministic Product Brief → five Ad Creatives lineage demo."""

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
    identifiers = [new_uuid7(timestamp_ms=1_700_000_000_000 + index) for index in range(15)]
    owner_source, brief, batch = identifiers[:3]
    creatives = identifiers[3:8]
    assets = identifiers[8:13]
    feedback, weight = identifiers[13:]
    result = {
        "schema": "ptw-validation-v1",
        "entities": {
            "owner_idea_source": owner_source,
            "product_brief": brief,
            "creative_batch": batch,
            "ad_creatives": creatives,
            "assets": assets,
            "feedback": feedback,
            "weight_update": weight,
        },
        "relationships": (
            [[brief, "derived_from", owner_source], [batch, "derived_from", brief]]
            + [[batch, "contains", creative] for creative in creatives]
            + [[creative, "derived_from", brief] for creative in creatives]
            + [[creative, "contains", asset] for creative, asset in zip(creatives, assets)]
            + [[feedback, "evaluates", creatives[0]], [weight, "adjusts", feedback]]
        ),
    }
    (output_dir / "demo-result.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path(".local/commander-demo"))
    parser.add_argument("--no-reset", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run_demo(args.output_dir, reset=not args.no_reset), indent=2))


if __name__ == "__main__":
    main()
