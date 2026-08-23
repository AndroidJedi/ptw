from __future__ import annotations

import argparse

from .config import Settings
from .repository import PositioningRepository


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("verify", "recover"))
    args = parser.parse_args()
    repository = PositioningRepository(Settings.from_environment().database_url)
    if args.command == "recover":
        print(f"recovered={repository.recover_interrupted()}")
        return
    with repository.connection() as connection:
        tables = connection.execute(
            """SELECT count(*) FROM information_schema.tables
               WHERE table_schema='public' AND table_name IN (
                   'positioning_projects','positioning_revisions',
                   'positioning_notification_attempts','landing_draft_sets','landing_leads'
               )"""
        ).fetchone()[0]
    if tables != 5:
        raise SystemExit("Marketing Positioning v1 schema is incomplete")
    print("Marketing Positioning v1 schema: OK")


if __name__ == "__main__":
    main()
