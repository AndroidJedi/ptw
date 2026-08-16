"""Dedicated durable worker for ad generation and owner-context conclusions."""

from __future__ import annotations

import argparse
import time

from .ad_runtime import create_ad_engine
from .postgres_store import connect_postgres
from .settings import Settings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    args = parser.parse_args()
    settings = Settings.from_environment()
    store = connect_postgres(settings.database_url)
    engine = create_ad_engine(settings, store)
    while True:
        worked = engine.process_once()
        if args.once:
            return
        if worked == 0:
            time.sleep(args.poll_seconds)


if __name__ == "__main__":
    main()
