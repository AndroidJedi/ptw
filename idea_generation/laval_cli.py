"""The ``lav`` CLI: a second client of the same PostgreSQL Laval services."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
from typing import Any

from .config import Settings
from .laval_pipeline import LavalPipeline
from .laval_providers import providers_from_settings
from .laval_repository import LavalRepository
from .laval_service import LavalRunner, LavalService
from .manage import ROOT
from .provider import BridgeProvider, MockLLMProvider, OpenAIProvider
from .store import PostgresStore


def _llm(settings: Settings):
    if settings.llm_provider == "mock":
        return MockLLMProvider()
    if settings.llm_provider == "openai":
        return OpenAIProvider(settings.openai_api_key, settings.llm_model)
    if settings.llm_provider == "bridge":
        return BridgeProvider(settings.llm_bridge_url, settings.telegram_token, settings.llm_model)
    raise RuntimeError("LLM_PROVIDER must be mock, openai, or bridge")


def _runtime() -> tuple[LavalRepository, LavalPipeline, LavalService]:
    settings = Settings.from_environment()
    store = PostgresStore(settings.database_url)
    store.migrate(ROOT / "db/idea_generation")
    store.seed_laval_mission()
    repository = LavalRepository(store)
    pipeline = LavalPipeline(repository, providers_from_settings(settings, _llm(settings)))
    return repository, pipeline, LavalService(repository, LavalRunner(pipeline))


def _print(value: Any, as_json: bool = False) -> None:
    if as_json or isinstance(value, (dict, list)):
        print(json.dumps(value, ensure_ascii=False, indent=2, default=str))
    else:
        print(value)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="lav", description="Inspectable Idea Laval Engine")
    commands = root.add_subparsers(dest="command", required=True)

    idea = commands.add_parser("idea")
    idea_commands = idea.add_subparsers(dest="idea_command", required=True)
    new = idea_commands.add_parser("new")
    source = new.add_mutually_exclusive_group(required=True)
    source.add_argument("--text")
    source.add_argument("--file", type=Path)
    new.add_argument("--config", type=Path)
    new.add_argument("--automatic", action="store_true")
    new.add_argument("--json", action="store_true")

    run = commands.add_parser("run")
    run.add_argument("run_id")
    run.add_argument("--through")
    run.add_argument("--force", action="store_true")
    run.add_argument("--json", action="store_true")

    for name in ("resume", "resume-market-signals", "pause", "status", "stages", "cost"):
        command = commands.add_parser(name)
        command.add_argument("run_id")
        command.add_argument("--json", action="store_true")
        if name == "status":
            command.add_argument("--watch", action="store_true")

    show = commands.add_parser("show")
    show.add_argument("run_id")
    show.add_argument("stage")
    show.add_argument("--view")
    show.add_argument("--country")
    show.add_argument("--json", action="store_true")

    export = commands.add_parser("export")
    export.add_argument("run_id")
    export.add_argument("--stage")
    export.add_argument("--all", action="store_true")
    export.add_argument("--format", choices=("json", "md"), default="json")
    export.add_argument("--output", type=Path)

    rerun = commands.add_parser("rerun")
    rerun.add_argument("run_id")
    rerun.add_argument("stage")
    rerun.add_argument("--country")
    rerun.add_argument("--force", action="store_true")
    rerun.add_argument("--json", action="store_true")

    approve = commands.add_parser("approve")
    approve.add_argument("run_id")
    approve.add_argument("stage")
    approve.add_argument("--json", action="store_true")

    competitor = commands.add_parser("competitor")
    competitor_actions = competitor.add_subparsers(dest="override_action", required=True)
    add = competitor_actions.add_parser("add")
    add.add_argument("run_id"); add.add_argument("--country", required=True); add.add_argument("--url", required=True); add.add_argument("--name"); add.add_argument("--reason", default="owner-added competitor"); add.add_argument("--json", action="store_true")
    reject = competitor_actions.add_parser("reject")
    reject.add_argument("run_id"); reject.add_argument("--competitor", required=True); reject.add_argument("--reason", required=True); reject.add_argument("--json", action="store_true")

    opportunity = commands.add_parser("opportunity")
    opportunity_actions = opportunity.add_subparsers(dest="override_action", required=True)
    disable_opp = opportunity_actions.add_parser("disable")
    disable_opp.add_argument("run_id"); disable_opp.add_argument("opportunity_id"); disable_opp.add_argument("--reason", default="owner disabled opportunity"); disable_opp.add_argument("--json", action="store_true")

    trend = commands.add_parser("trend")
    trend_actions = trend.add_subparsers(dest="override_action", required=True)
    disable_trend = trend_actions.add_parser("disable")
    disable_trend.add_argument("run_id"); disable_trend.add_argument("trend_id"); disable_trend.add_argument("--reason", default="owner disabled trend"); disable_trend.add_argument("--json", action="store_true")
    return root


def main() -> None:
    args = parser().parse_args()
    repository, pipeline, service = _runtime()
    actor = "cli:owner"
    try:
        if args.command == "idea":
            text = args.text if args.text is not None else args.file.read_text(encoding="utf-8")
            config = json.loads(args.config.read_text(encoding="utf-8")) if args.config else {}
            if args.automatic:
                config["approval_mode"] = "automatic"
            _print(service.create(text, config, actor=actor), args.json)
        elif args.command == "run":
            if args.force:
                repository.invalidate_from(args.run_id, "OWNER_DNA")
            repository.ready(args.run_id, through_stage=args.through)
            _print(pipeline.run(args.run_id, through_stage=args.through, force=args.force), args.json)
        elif args.command == "resume":
            repository.ready(args.run_id)
            _print(pipeline.run(args.run_id), args.json)
        elif args.command == "resume-market-signals":
            repository.upgrade_to_market_signals(args.run_id, actor=actor)
            _print(pipeline.run(args.run_id, start_stage="MARKET_SIGNAL_PLAN"), args.json)
        elif args.command == "pause":
            _print(service.pause(args.run_id), args.json)
        elif args.command == "status":
            while True:
                value = repository.status(args.run_id)
                _print(value, args.json)
                if not args.watch or value["run"]["status"] in {"paused", "completed", "failed", "cancelled"}:
                    break
                time.sleep(2)
        elif args.command == "stages":
            _print({"items": repository.stages(args.run_id)}, args.json)
        elif args.command == "show":
            _print(repository.show(args.run_id, args.stage.upper(), view=args.view, country=args.country), args.json)
        elif args.command == "cost":
            _print(repository.cost(args.run_id), args.json)
        elif args.command == "export":
            filename, _media, content = repository.export(args.run_id, stage=None if args.all else args.stage, format=args.format)
            destination = args.output or Path(filename)
            destination.write_text(content, encoding="utf-8")
            print(destination)
        elif args.command == "rerun":
            stage = args.stage.upper()
            repository.override(args.run_id, "stage", stage, "rerun", reason="CLI rerun", actor=actor, payload={"country": args.country, "force": args.force})
            repository.invalidate_from(args.run_id, stage, country=args.country)
            _print(pipeline.run(args.run_id, start_stage=stage, force=args.force, country=args.country), args.json)
        elif args.command == "approve":
            repository.approve(args.run_id, args.stage.upper(), actor=actor)
            _print(pipeline.run(args.run_id), args.json)
        elif args.command == "competitor":
            if args.override_action == "add":
                request = {"type": "competitor", "action": "add", "target_id": args.url, "reason": args.reason, "payload": {"url": args.url, "country": args.country, "name": args.name}}
            else:
                request = {"type": "competitor", "action": "reject", "target_id": args.competitor, "reason": args.reason}
            _print(service.override(args.run_id, request, actor=actor), args.json)
        elif args.command == "opportunity":
            _print(service.override(args.run_id, {"type": "opportunity", "action": "disable", "target_id": args.opportunity_id, "reason": args.reason}, actor=actor), args.json)
        elif args.command == "trend":
            _print(service.override(args.run_id, {"type": "trend", "action": "disable", "target_id": args.trend_id, "reason": args.reason}, actor=actor), args.json)
    except (KeyError, ValueError, RuntimeError) as error:
        print(f"lav: {error}", file=sys.stderr)
        raise SystemExit(2) from error


if __name__ == "__main__":
    main()
