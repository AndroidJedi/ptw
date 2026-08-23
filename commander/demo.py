"""Emit a deterministic v2 graph-lineage demonstration."""

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
    owner_source, research_source, positioning, draft, snapshot, landing, lead = (
        new_uuid7(timestamp_ms=1_700_000_000_000 + index) for index in range(7)
    )
    result = {
        "schema": "ptw-marketing-v1",
        "entities": {
            "sources": [owner_source, research_source], "positioning": positioning,
            "landing_draft_set": draft, "landing_snapshot": snapshot,
            "landing": landing, "lead_submission": lead,
        },
        "relationships": [
            [positioning, "derived_from", owner_source], [positioning, "derived_from", research_source],
            [draft, "derived_from", positioning], [draft, "contains", snapshot],
            [landing, "derived_from", snapshot], [landing, "derived_from", positioning],
            [lead, "submitted_to", landing],
        ],
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
