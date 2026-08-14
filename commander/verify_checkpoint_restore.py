"""Fresh-process startup canary for durable Commander session checkpoints."""

from __future__ import annotations

import argparse

from .postgres_store import connect_postgres
from .settings import Settings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", default="commander")
    args = parser.parse_args()
    settings = Settings.from_environment()
    checkpoint = connect_postgres(settings.database_url).latest_session_checkpoint(args.scope)
    status = checkpoint.restore_status(settings.checkpoint_max_age_seconds)
    if status != "fresh":
        raise RuntimeError(f"checkpoint restore failed: {status}")
    print(
        f"checkpoint {checkpoint.checkpoint_id} restored in a fresh process; "
        f"next action: {checkpoint.next_action}"
    )


if __name__ == "__main__":
    main()
