from __future__ import annotations

import argparse

from .config import Settings
from .repository import ValidationRepository


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("verify", "recover"))
    args = parser.parse_args()
    repository = ValidationRepository(Settings.from_environment().database_url)
    if args.command == "recover":
        print(repository.recover_interrupted())
        return
    required = {
        "product_briefs", "creative_batches", "ad_creatives", "ad_creative_assets",
        "validation_generation_attempts", "validation_provider_invocations",
    }
    with repository.connection() as connection:
        rows = connection.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
        ).fetchall()
    missing = required - {row[0] for row in rows}
    if missing:
        raise SystemExit(f"Validation schema is incomplete: {sorted(missing)}")
    print("PTW Validation schema: OK")


if __name__ == "__main__":
    main()

