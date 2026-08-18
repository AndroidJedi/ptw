from __future__ import annotations

import argparse
from pathlib import Path

from .config import Settings
from .store import PostgresStore

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("migrate", "seed", "reset-runtime", "verify"))
    args = parser.parse_args()
    store = PostgresStore(Settings.from_environment().database_url)
    if args.command == "migrate": store.migrate(ROOT / "db/idea_generation")
    elif args.command == "seed":
        store.seed_laval_mission()
    elif args.command == "reset-runtime":
        with store.transaction() as connection:
            connection.execute("TRUNCATE laval_runs,telegram_inbox,telegram_offsets,telegram_events,reports,executions,idea_evaluations,ideas,idea_submission_drafts,idea_submissions,generations,guidance,context_revisions,contexts RESTART IDENTITY CASCADE")
            connection.execute("UPDATE missions SET status='active',auto_enabled=FALSE,run_series_remaining=0,stop_after_current_cycle=FALSE")
    else:
        mission = store.mission()
        legacy = store.fetchone(
            "SELECT (SELECT count(*) FROM generations) + (SELECT count(*) FROM ideas) + "
            "(SELECT count(*) FROM contexts) AS count"
        )["count"]
        runs = store.fetchone("SELECT COUNT(*) AS count FROM laval_runs")["count"]
        if legacy: raise SystemExit("verification failed: legacy Idea Evolution data exists")
        print(f"Postgres: OK; Mission: {mission['code']}; Legacy rows: 0; Laval runs: {runs}")


if __name__ == "__main__": main()
