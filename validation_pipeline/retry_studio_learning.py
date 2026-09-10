"""Retry one existing Studio learning checkpoint through normal domain services."""

from __future__ import annotations

import argparse
import json

from .api import create_studio_creative_service
from .config import Settings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("project_id")
    parser.add_argument("creative_id")
    parser.add_argument("checkpoint_id")
    args = parser.parse_args()
    result = create_studio_creative_service(Settings.from_environment()).retry_learning(
        args.project_id, args.creative_id, args.checkpoint_id,
    )
    checkpoint = result["checkpoint"]
    proposal = result.get("learning_proposal")
    print(json.dumps({
        "checkpoint_id": checkpoint["checkpoint_id"],
        "status": checkpoint["status"],
        "learning_attempt": checkpoint.get("learning_attempt"),
        "proposal_id": None if proposal is None else proposal["proposal_id"],
    }, sort_keys=True))
    if checkpoint["status"] != "completed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
