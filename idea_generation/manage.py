from __future__ import annotations

import argparse
from pathlib import Path

from .config import Settings
from .seeds import load
from .store import PostgresStore

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("migrate", "seed", "reset-runtime", "verify"))
    args = parser.parse_args()
    store = PostgresStore(Settings.from_environment().database_url)
    if args.command == "migrate": store.migrate(ROOT / "db/idea_generation")
    elif args.command == "seed":
        mission, contexts = load(ROOT / "ideaGeneration")
        store.seed(mission, contexts)
    elif args.command == "reset-runtime":
        with store.transaction() as connection:
            connection.execute("TRUNCATE telegram_events,reports,executions,idea_evaluations,ideas,idea_submissions,generations,guidance RESTART IDENTITY CASCADE")
            connection.execute("UPDATE missions SET status='active',auto_enabled=FALSE,run_series_remaining=0,stop_after_current_cycle=FALSE")
    else:
        mission = store.mission(); contexts = store.active_contexts()
        generations = store.fetchone("SELECT COUNT(*) AS count FROM generations WHERE status='completed'")["count"]
        if mission["auto_enabled"] or generations or len(contexts) != 10: raise SystemExit("verification failed")
        print("Postgres: OK; Mission: MISSION_450M_5Y; Contexts: 10/10; Autopilot: OFF; Generations: 0")


if __name__ == "__main__": main()
