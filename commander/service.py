"""Commander application service with generic lifecycle invariants."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from .model import Entity, EntityKind, RelationType, Relationship
from .policy import CommanderPolicy, PolicyDenied
from .store import KnowledgeStore


class Commander:
    def __init__(self, store: KnowledgeStore, policy: CommanderPolicy) -> None:
        self.store = store
        self.policy = policy

    def create_entity(
        self,
        kind: EntityKind,
        attributes: Mapping[str, Any],
        *,
        actor: str = "commander",
        reasoning_summary: str,
        evidence_ids: Iterable[str] = (),
    ) -> Entity:
        self.policy.require_active()
        entity = Entity(kind=kind, attributes=dict(attributes))
        self.store.add_entity(entity)
        self._audit(
            action=f"create_{kind.value}",
            actor=actor,
            reasoning_summary=reasoning_summary,
            evidence_ids=tuple(evidence_ids),
            result_ids=(entity.id,),
        )
        return entity

    def relate(
        self,
        source: Entity,
        relation: RelationType,
        target: Entity,
        attributes: Mapping[str, Any] | None = None,
    ) -> Relationship:
        edge = Relationship(
            source_id=source.id,
            relation=relation,
            target_id=target.id,
            attributes=dict(attributes or {}),
        )
        self.store.add_relationship(edge)
        return edge

    def create_hypothesis(
        self,
        *,
        claim: str,
        success_metric: str,
        threshold: float,
        scope: str,
        source: Entity,
    ) -> Entity:
        hypothesis = self.create_entity(
            EntityKind.HYPOTHESIS,
            {
                "claim": claim,
                "success_criterion": {
                    "metric": success_metric,
                    "operator": ">=",
                    "threshold": threshold,
                },
                "scope": scope,
                "status": "proposed",
            },
            reasoning_summary="Converted source evidence into a falsifiable claim.",
            evidence_ids=(source.id,),
        )
        self.relate(hypothesis, RelationType.DERIVED_FROM, source)
        return hypothesis

    def create_experiment(
        self,
        *,
        hypothesis: Entity,
        creative: Entity,
        audience: Entity,
        budget_minor: int,
        approved_by: str | None,
    ) -> Entity:
        self._require_kind(hypothesis, EntityKind.HYPOTHESIS)
        self._require_kind(creative, EntityKind.CREATIVE)
        self._require_kind(audience, EntityKind.AUDIENCE)
        running = sum(
            self._experiment_status(entity) == "running"
            for entity in self.store.entities(EntityKind.EXPERIMENT)
        )
        try:
            self.policy.check_experiment(
                approved=approved_by is not None,
                budget_minor=budget_minor,
                running=running,
            )
        except PolicyDenied as error:
            self._record_policy_evaluation("start_experiment", "deny", str(error))
            raise
        self._record_policy_evaluation(
            "start_experiment", "allow", "Approval, budget, and concurrency gates passed."
        )
        experiment = self.create_entity(
            EntityKind.EXPERIMENT,
            {
                "budget_minor": budget_minor,
                "approved_by": approved_by,
                "policy_version": self.policy.version,
                "policy_digest": self.policy.digest,
            },
            actor=approved_by or "commander",
            reasoning_summary="Experiment passed approval, budget, and concurrency policy gates.",
            evidence_ids=(hypothesis.id, creative.id, audience.id),
        )
        self.relate(experiment, RelationType.TESTS, hypothesis)
        self.relate(creative, RelationType.TESTED_IN, experiment)
        self.relate(experiment, RelationType.TESTED_IN, audience)
        self.transition_experiment(experiment, "running", actor=approved_by or "commander")
        return experiment

    def transition_experiment(
        self, experiment: Entity, status: str, *, actor: str = "commander"
    ) -> Entity:
        self._require_kind(experiment, EntityKind.EXPERIMENT)
        current = self._experiment_status(experiment)
        allowed = {
            None: {"running"},
            "running": {"completed", "cancelled"},
            "completed": {"evaluated"},
            "evaluated": set(),
            "cancelled": set(),
        }
        if status not in allowed[current]:
            raise ValueError(f"invalid experiment transition: {current} -> {status}")
        state = self.create_entity(
            EntityKind.EXPERIMENT_STATE,
            {"status": status, "previous_status": current},
            actor=actor,
            reasoning_summary=f"Recorded append-only experiment transition to {status}.",
            evidence_ids=(experiment.id,),
        )
        self.relate(state, RelationType.STATE_OF, experiment)
        return state

    def ingest_metrics(
        self,
        *,
        experiment: Entity,
        source: Entity,
        values: Mapping[str, float],
        attribution_window: str,
    ) -> Entity:
        self._require_kind(experiment, EntityKind.EXPERIMENT)
        if self._experiment_status(experiment) != "running":
            raise ValueError("metrics can only be ingested for a running experiment")
        metric_set = self.create_entity(
            EntityKind.METRIC_SET,
            {
                "values": dict(values),
                "attribution_window": attribution_window,
                "factual": True,
            },
            reasoning_summary="Recorded adapter-supplied metrics without interpretation.",
            evidence_ids=(source.id, experiment.id),
        )
        self.relate(experiment, RelationType.MEASURED_BY, metric_set)
        self.relate(metric_set, RelationType.DERIVED_FROM, source)
        return metric_set

    def evaluate(
        self,
        *,
        experiment: Entity,
        hypothesis: Entity,
        metric_set: Entity,
    ) -> tuple[Entity, Entity]:
        self._require_kind(metric_set, EntityKind.METRIC_SET)
        if self._experiment_status(experiment) != "running":
            raise ValueError("only a running experiment can be evaluated")
        self.transition_experiment(experiment, "completed")
        criterion = hypothesis.attributes["success_criterion"]
        metric = str(criterion["metric"])
        threshold = float(criterion["threshold"])
        values = metric_set.attributes["values"]
        if metric not in values:
            raise ValueError(f"metric set is missing success metric: {metric}")
        actual = float(values[metric])
        passed = actual >= threshold
        observation = self.create_entity(
            EntityKind.OBSERVATION,
            {
                "statement": f"{metric} was {actual:g} against threshold {threshold:g}.",
                "metric": metric,
                "actual": actual,
                "threshold": threshold,
                "criterion_met": passed,
                "factual": True,
            },
            reasoning_summary="Applied the hypothesis's predeclared threshold to recorded metrics.",
            evidence_ids=(metric_set.id,),
        )
        self.relate(observation, RelationType.DERIVED_FROM, metric_set)
        insight = self.create_entity(
            EntityKind.INSIGHT,
            {
                "interpretation": (
                    "The tested creative is consistent with the hypothesis in this scope."
                    if passed
                    else "The tested creative is not consistent with the hypothesis in this scope."
                ),
                "scope": hypothesis.attributes["scope"],
                "sample_limited": True,
            },
            reasoning_summary="Interpreted the factual observation while retaining scope limitations.",
            evidence_ids=(observation.id,),
        )
        self.relate(insight, RelationType.SUPPORTS if passed else RelationType.CONTRADICTS, hypothesis)
        self.relate(insight, RelationType.DERIVED_FROM, observation)
        self.transition_experiment(experiment, "evaluated")
        return observation, insight

    def decide(
        self,
        *,
        insight: Entity,
        hypothesis: Entity,
        decision_key: str,
        action: str,
        confidence: float,
        previous_decision: Entity | None = None,
        approved_by: str | None = None,
    ) -> Entity:
        if not 0 <= confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        if confidence < self.policy.decision_confidence_threshold and approved_by is None:
            raise PolicyDenied("decision below automatic confidence threshold requires approval")
        version = 1
        if previous_decision is not None:
            self._require_kind(previous_decision, EntityKind.DECISION)
            if previous_decision.attributes["decision_key"] != decision_key:
                raise ValueError("a decision can only replace the same decision key")
            version = int(previous_decision.attributes["version"]) + 1
        decision = self.create_entity(
            EntityKind.DECISION,
            {
                "action": action,
                "decision_key": decision_key,
                "confidence": confidence,
                "version": version,
                "approved_by": approved_by,
                "reasoning_summary": "Decision follows the scoped insight and recorded evidence.",
            },
            actor=approved_by or "commander",
            reasoning_summary="Created an append-only decision version.",
            evidence_ids=(insight.id, hypothesis.id),
        )
        self.relate(decision, RelationType.DERIVED_FROM, insight)
        if previous_decision is not None:
            self.relate(decision, RelationType.SUPERSEDES, previous_decision)
        return decision

    def _audit(
        self,
        *,
        action: str,
        actor: str,
        reasoning_summary: str,
        evidence_ids: tuple[str, ...],
        result_ids: tuple[str, ...],
    ) -> None:
        audit = Entity(
            kind=EntityKind.AUDIT_EVENT,
            attributes={
                "action": action,
                "actor": actor,
                "reasoning_summary": reasoning_summary,
                "evidence_ids": list(evidence_ids),
                "result_ids": list(result_ids),
                "policy_version": self.policy.version,
                "policy_digest": self.policy.digest,
            },
        )
        self.store.add_entity(audit)

    def _record_policy_evaluation(self, command: str, outcome: str, summary: str) -> None:
        self.store.add_entity(
            Entity(
                kind=EntityKind.POLICY_EVALUATION,
                attributes={
                    "command": command,
                    "outcome": outcome,
                    "summary": summary,
                    "policy_version": self.policy.version,
                    "policy_digest": self.policy.digest,
                },
            )
        )

    @staticmethod
    def _require_kind(entity: Entity, expected: EntityKind) -> None:
        if entity.kind != expected:
            raise TypeError(f"expected {expected.value}, got {entity.kind.value}")

    def _experiment_status(self, experiment: Entity) -> str | None:
        states = [
            self.store.get_entity(edge.source_id)
            for edge in self.store.relationships()
            if edge.relation == RelationType.STATE_OF and edge.target_id == experiment.id
        ]
        if not states:
            return None
        return max(states, key=lambda item: item.created_at).attributes["status"]
