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
        self._require_active()
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
        additional_sources: Iterable[Entity] = (),
        actor: str = "commander",
        attributes: Mapping[str, Any] | None = None,
    ) -> Entity:
        sources = (source, *tuple(additional_sources))
        for item in sources:
            self._require_kind(item, EntityKind.SOURCE)
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
                **dict(attributes or {}),
            },
            actor=actor,
            reasoning_summary="Converted source evidence into a falsifiable claim.",
            evidence_ids=tuple(item.id for item in sources),
        )
        for item in sources:
            self.relate(hypothesis, RelationType.DERIVED_FROM, item)
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
        self._require_active()
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

    def request_experiment_approval(
        self,
        *,
        hypothesis: Entity,
        creative: Entity,
        audience: Entity,
        budget_minor: int,
        requested_by: str,
    ) -> Entity:
        self._require_active()
        request = self.create_entity(
            EntityKind.APPROVAL_REQUEST,
            {
                "command": "start_experiment",
                "hypothesis_id": hypothesis.id,
                "creative_id": creative.id,
                "audience_id": audience.id,
                "budget_minor": budget_minor,
                "requested_by": requested_by,
            },
            actor=requested_by,
            reasoning_summary="Queued an experiment command for explicit owner approval.",
            evidence_ids=(hypothesis.id, creative.id, audience.id),
        )
        self._append_approval_state(request, "pending", requested_by)
        return request

    def approve_experiment(self, request: Entity, *, approved_by: str) -> Entity:
        self._require_kind(request, EntityKind.APPROVAL_REQUEST)
        if self._approval_status(request) != "pending":
            raise ValueError("approval request is not pending")
        attributes = request.attributes
        with self.store.transaction():
            experiment = self.create_experiment(
                hypothesis=self.store.get_entity(str(attributes["hypothesis_id"])),
                creative=self.store.get_entity(str(attributes["creative_id"])),
                audience=self.store.get_entity(str(attributes["audience_id"])),
                budget_minor=int(attributes["budget_minor"]),
                approved_by=approved_by,
            )
            self._append_approval_state(request, "approved", approved_by)
            self.relate(experiment, RelationType.DERIVED_FROM, request)
        return experiment

    def reject_approval(self, request: Entity, *, rejected_by: str) -> Entity:
        self._require_kind(request, EntityKind.APPROVAL_REQUEST)
        if self._approval_status(request) != "pending":
            raise ValueError("approval request is not pending")
        return self._append_approval_state(request, "rejected", rejected_by)

    def set_emergency_stop(self, active: bool, *, actor: str) -> Entity:
        state = Entity(
            kind=EntityKind.CONTROL_STATE,
            attributes={"emergency_stop": active, "actor": actor},
        )
        self.store.add_entity(state)
        self._audit(
            action="set_emergency_stop",
            actor=actor,
            reasoning_summary=f"Runtime emergency stop set to {active}.",
            evidence_ids=(),
            result_ids=(state.id,),
        )
        return state

    def status(self) -> Mapping[str, Any]:
        return {
            "emergency_stop": self._emergency_stop_active(),
            "running_experiments": sum(
                self._experiment_status(entity) == "running"
                for entity in self.store.entities(EntityKind.EXPERIMENT)
            ),
            "pending_approvals": sum(
                self._approval_status(entity) == "pending"
                for entity in self.store.entities(EntityKind.APPROVAL_REQUEST)
            ),
            "queued_tasks": sum(
                entity.attributes.get("status") == "queued"
                for entity in self.store.entities(EntityKind.TASK)
            ),
            "policy_version": self.policy.version,
            "policy_digest": self.policy.digest,
        }

    def pending_approval_requests(self) -> tuple[Entity, ...]:
        return tuple(
            entity
            for entity in self.store.entities(EntityKind.APPROVAL_REQUEST)
            if self._approval_status(entity) == "pending"
        )

    def record_creative_feedback(
        self,
        *,
        creative: Entity,
        rating: int,
        comment: str,
        actor: str,
    ) -> tuple[Entity, tuple[Entity, ...]]:
        self._require_kind(creative, EntityKind.CREATIVE)
        if rating not in range(1, 6):
            raise ValueError("feedback rating must be an integer from 1 to 5")
        duplicate = any(
            item.attributes.get("creative_id") == creative.id
            and item.attributes.get("actor") == actor
            for item in self.store.entities(EntityKind.HUMAN_FEEDBACK)
        )
        if duplicate:
            raise ValueError("feedback from this actor already exists for the creative")
        with self.store.transaction():
            feedback = self.create_entity(
                EntityKind.HUMAN_FEEDBACK,
                {
                    "creative_id": creative.id,
                    "rating": rating,
                    "comment": comment.strip()[:1000],
                    "actor": actor,
                    "feedback_type": "owner_review",
                },
                actor=actor,
                reasoning_summary="Recorded explicit owner feedback without treating it as an observation.",
                evidence_ids=(creative.id,),
            )
            self.relate(feedback, RelationType.EVALUATES, creative)
            components = tuple(
                self.store.get_entity(edge.target_id)
                for edge in self.store.relationships()
                if edge.source_id == creative.id and edge.relation == RelationType.CONTAINS
            )
            updates: list[Entity] = []
            delta = (rating - 3) * 0.05
            for component in components:
                previous = self.component_weight(component)
                current = max(0.0, min(1.0, previous + delta))
                update = self.create_entity(
                    EntityKind.WEIGHT_UPDATE,
                    {
                        "component_id": component.id,
                        "previous_weight": previous,
                        "delta": delta,
                        "new_weight": current,
                        "algorithm": "owner_rating_linear_v1",
                        "rating": rating,
                    },
                    actor=actor,
                    reasoning_summary="Applied the versioned owner-feedback weighting policy.",
                    evidence_ids=(feedback.id, component.id),
                )
                self.relate(update, RelationType.DERIVED_FROM, feedback)
                self.relate(update, RelationType.ADJUSTS, component)
                updates.append(update)
        return feedback, tuple(updates)

    def component_weight(self, component: Entity) -> float:
        self._require_kind(component, EntityKind.CREATIVE_COMPONENT)
        updates = [
            self.store.get_entity(edge.source_id)
            for edge in self.store.relationships()
            if edge.target_id == component.id and edge.relation == RelationType.ADJUSTS
        ]
        if not updates:
            return 0.5
        latest = max(updates, key=lambda item: item.created_at)
        return float(latest.attributes["new_weight"])

    def rank_creative_components(self, components: Iterable[Entity]) -> tuple[Entity, ...]:
        values = tuple(components)
        return tuple(sorted(values, key=lambda item: (-self.component_weight(item), item.id)))

    def graph_snapshot(self, view: str = "summary", entity_id: str | None = None) -> Mapping[str, Any]:
        if view == "summary":
            counts = {
                kind.value: len(self.store.entities(kind))
                for kind in EntityKind
                if self.store.entities(kind)
            }
            recent = sorted(self.store.entities(), key=lambda item: item.created_at, reverse=True)[:10]
            return {
                "view": view,
                "entity_counts": counts,
                "relationship_count": len(self.store.relationships()),
                "recent": tuple((item.id, item.kind.value) for item in recent),
            }
        if view == "hypotheses":
            values = []
            for hypothesis in sorted(
                self.store.entities(EntityKind.HYPOTHESIS),
                key=lambda item: item.created_at,
                reverse=True,
            )[:10]:
                source_ids = tuple(
                    edge.target_id
                    for edge in self.store.relationships()
                    if edge.source_id == hypothesis.id
                    and edge.relation == RelationType.DERIVED_FROM
                    and self.store.get_entity(edge.target_id).kind == EntityKind.SOURCE
                )
                values.append(
                    {
                        "id": hypothesis.id,
                        "claim": str(hypothesis.attributes.get("claim", "")),
                        "status": str(hypothesis.attributes.get("status", "unknown")),
                        "owner_agent": str(hypothesis.attributes.get("owner_agent", "unassigned")),
                        "source_ids": source_ids,
                    }
                )
            return {"view": view, "hypotheses": tuple(values)}
        if view == "weights":
            components = self.rank_creative_components(
                self.store.entities(EntityKind.CREATIVE_COMPONENT)
            )[:10]
            return {
                "view": view,
                "components": tuple(
                    {
                        "id": item.id,
                        "kind": item.attributes.get("component_kind"),
                        "value": str(item.attributes.get("value", ""))[:60],
                        "weight": self.component_weight(item),
                    }
                    for item in components
                ),
            }
        if view == "creative":
            if not entity_id:
                raise ValueError("usage: /graph creative <creative-uuid>")
            creative = self.store.get_entity(entity_id)
            self._require_kind(creative, EntityKind.CREATIVE)
            edges = self.store.relationships()
            component_ids = tuple(
                edge.target_id
                for edge in edges
                if edge.source_id == creative.id and edge.relation == RelationType.CONTAINS
            )
            feedback_ids = tuple(
                edge.source_id
                for edge in edges
                if edge.target_id == creative.id and edge.relation == RelationType.EVALUATES
            )
            weight_update_ids = tuple(
                update.id
                for update in self.store.entities(EntityKind.WEIGHT_UPDATE)
                if any(
                    edge.source_id == update.id
                    and edge.relation == RelationType.ADJUSTS
                    and edge.target_id in component_ids
                    for edge in edges
                )
            )
            return {
                "view": view,
                "creative_id": creative.id,
                "component_ids": component_ids,
                "feedback_ids": feedback_ids,
                "weight_update_ids": weight_update_ids,
            }
        raise ValueError("graph view must be summary, hypotheses, weights, or creative")

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

    def _append_approval_state(
        self, request: Entity, status: str, actor: str
    ) -> Entity:
        state = self.create_entity(
            EntityKind.APPROVAL_STATE,
            {"status": status, "actor": actor},
            actor=actor,
            reasoning_summary=f"Recorded append-only approval state: {status}.",
            evidence_ids=(request.id,),
        )
        self.relate(state, RelationType.STATE_OF, request)
        return state

    def _approval_status(self, request: Entity) -> str | None:
        states = [
            self.store.get_entity(edge.source_id)
            for edge in self.store.relationships()
            if edge.relation == RelationType.STATE_OF and edge.target_id == request.id
        ]
        states = [state for state in states if state.kind == EntityKind.APPROVAL_STATE]
        return max(states, key=lambda item: item.created_at).attributes["status"] if states else None

    def _emergency_stop_active(self) -> bool:
        states = self.store.entities(EntityKind.CONTROL_STATE)
        if states:
            return bool(max(states, key=lambda item: item.created_at).attributes["emergency_stop"])
        return self.policy.emergency_stop

    def _require_active(self) -> None:
        if self._emergency_stop_active():
            raise PolicyDenied("Commander emergency stop is active")
