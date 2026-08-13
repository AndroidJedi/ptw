"""Run one complete, deterministic PTW learning loop."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from .instagram import InstagramCreativeAdapter, InstagramCreativeSpec
from .model import EntityKind, RelationType
from .policy import CommanderPolicy
from .service import Commander
from .store import JsonlKnowledgeStore


def run_demo(output_dir: Path, *, reset: bool = True) -> dict[str, object]:
    if reset and output_dir.exists():
        shutil.rmtree(output_dir)
    policy = CommanderPolicy.load(Path("config/commander/policies.json"))
    store = JsonlKnowledgeStore(output_dir)
    commander = Commander(store, policy)

    source = commander.create_entity(
        EntityKind.SOURCE,
        {"source_type": "product_assumption", "title": "Direct challenge hook"},
        reasoning_summary="Registered the provenance of the initial product assumption.",
    )
    hypothesis = commander.create_hypothesis(
        claim="A direct challenge hook can reach at least 2% link click-through for this audience.",
        success_metric="link_ctr",
        threshold=0.02,
        scope="Instagram Story; PTW warm audience; demonstration window",
        source=source,
    )
    creative = InstagramCreativeAdapter(commander).generate(
        hypothesis=hypothesis,
        spec=InstagramCreativeSpec(
            hook="They said you would quit. Prove them wrong.",
            hero_image_uri="asset://demo/runner-at-dawn.jpg",
            supporting_visual_uri="asset://demo/progress-streak.png",
            caption="Make the goal public. Show the work.",
            cta="Start your challenge",
        ),
    )
    audience = commander.create_entity(
        EntityKind.AUDIENCE,
        {"name": "PTW warm audience", "definition": "Prior engaged visitors"},
        reasoning_summary="Bound the experiment to an explicit audience scope.",
    )
    experiment = commander.create_experiment(
        hypothesis=hypothesis,
        creative=creative,
        audience=audience,
        budget_minor=500,
        approved_by="owner:demo",
    )
    metrics_source = commander.create_entity(
        EntityKind.SOURCE,
        {"source_type": "manual_metric_import", "platform": "instagram", "simulated": True},
        reasoning_summary="Declared the demonstration metric source and simulation status.",
    )
    metrics = commander.ingest_metrics(
        experiment=experiment,
        source=metrics_source,
        values={"impressions": 1000, "link_clicks": 27, "link_ctr": 0.027},
        attribution_window="24h",
    )
    observation, insight = commander.evaluate(
        experiment=experiment,
        hypothesis=hypothesis,
        metric_set=metrics,
    )
    decision = commander.decide(
        insight=insight,
        hypothesis=hypothesis,
        decision_key="instagram.direct_challenge_hook",
        action="Retain the direct-challenge hook as a candidate for the next scoped experiment.",
        confidence=0.65,
        approved_by="owner:demo",
    )
    knowledge = commander.create_entity(
        EntityKind.KNOWLEDGE_ASSERTION,
        {
            "statement": "Direct-challenge hooks are a candidate pattern for the scoped warm audience.",
            "confidence": 0.65,
            "scope": hypothesis.attributes["scope"],
            "status": "active",
        },
        reasoning_summary="Promoted the approved scoped decision into usable, versioned knowledge.",
        evidence_ids=(decision.id,),
    )
    commander.relate(decision, RelationType.ADOPTED_AS, knowledge)
    next_task = commander.create_entity(
        EntityKind.TASK,
        {
            "title": "Test direct challenge against a progress-led hook",
            "status": "queued",
            "task_class": "experiment_design",
            "context_topics": ["commander", "instagram", "experiments"],
        },
        reasoning_summary="Scheduled a comparison experiment rather than generalizing one sample.",
        evidence_ids=(knowledge.id,),
    )
    commander.relate(next_task, RelationType.SCHEDULED_BY, decision)

    result = {
        "loop": [
            hypothesis.id,
            creative.id,
            experiment.id,
            metrics.id,
            observation.id,
            insight.id,
            decision.id,
            knowledge.id,
            next_task.id,
        ],
        "entity_counts": {
            kind.value: len(store.entities(kind))
            for kind in EntityKind
            if store.entities(kind)
        },
        "relationship_count": len(store.relationships()),
        "projection": str(store.projection_path),
        "event_log": str(store.event_path),
    }
    (output_dir / "demo-result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True), encoding="utf-8"
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
