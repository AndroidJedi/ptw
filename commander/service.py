"""Commander application service with generic lifecycle invariants."""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping, Sequence

from .model import Entity, EntityKind, RelationType, Relationship
from .policy import CommanderPolicy, PolicyDenied
from .store import KnowledgeStore


class Commander:
    MARKET_PROBE_TYPES = frozenset({
        "landing_page", "fake_door", "outreach", "mock_flow",
        "creator_feedback", "community_test", "concierge",
    })
    THESIS_DECISIONS = frozenset({"continue", "mutate", "pivot", "reject"})
    SENSITIVE_OBSERVATION = re.compile(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----|\b(?:api[_ -]?key|password|secret|token)\s*[:=]|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}",
        re.IGNORECASE,
    )
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

    def select_product_thesis(
        self,
        *,
        hypothesis: Entity,
        laval_run_id: str,
        thesis_id: str,
        actor: str,
    ) -> Entity:
        """Idempotently open a validation workspace without executing a probe."""

        self._require_kind(hypothesis, EntityKind.HYPOTHESIS)
        if str(hypothesis.attributes.get("idea_laval_thesis_id") or "") != thesis_id:
            raise ValueError("hypothesis does not represent the selected Laval thesis")
        existing = next((
            item for item in self.store.entities(EntityKind.VALIDATION_WORKSPACE)
            if str(item.attributes.get("hypothesis_id")) == hypothesis.id
        ), None)
        if existing is not None:
            return existing
        try:
            workspace = self.create_entity(
                EntityKind.VALIDATION_WORKSPACE,
                {
                    "hypothesis_id": hypothesis.id,
                    "idea_laval_run_id": laval_run_id,
                    "idea_laval_thesis_id": thesis_id,
                    "selected_by": actor,
                    "status": "probe_planning",
                    "external_actions_automatic": False,
                },
                actor=actor,
                reasoning_summary="Owner selected a surviving product thesis for bounded validation.",
                evidence_ids=(hypothesis.id,),
            )
        except Exception:
            # The database uniqueness constraint closes a concurrent double-click
            # race; return the winner as the same idempotent selection.
            existing = next((
                item for item in self.store.entities(EntityKind.VALIDATION_WORKSPACE)
                if str(item.attributes.get("hypothesis_id")) == hypothesis.id
            ), None)
            if existing is not None:
                return existing
            raise
        self.relate(workspace, RelationType.DERIVED_FROM, hypothesis)
        assumptions = list(hypothesis.attributes.get("dangerous_assumptions") or [])
        defaults = ("landing_page", "outreach", "concierge")
        for index, probe_type in enumerate(defaults):
            raw = assumptions[index % len(assumptions)] if assumptions else {}
            statement = raw.get("statement") if isinstance(raw, Mapping) else raw
            if isinstance(statement, Mapping):
                statement = statement.get("en")
            self.create_market_probe(
                workspace=workspace,
                hypothesis=hypothesis,
                probe_type=probe_type,
                assumption_id=str(raw.get("id") or f"assumption-{index + 1}") if isinstance(raw, Mapping) else f"assumption-{index + 1}",
                assumption=str(statement or "Test the thesis's riskiest behavior assumption."),
                procedure=f"Manually run a bounded {probe_type.replace('_', ' ')} probe; PTW records results but performs no external action.",
                target_segment=str(hypothesis.attributes.get("scope") or "target segment"),
                metric=str((hypothesis.attributes.get("success_criterion") or {}).get("metric") or "validated_demand_signal"),
                threshold=float((hypothesis.attributes.get("success_criterion") or {}).get("threshold") or .1),
                sample_target=10,
                duration_days=7,
                budget_minor=0,
                actor=actor,
            )
        return workspace

    def create_market_probe(
        self,
        *,
        workspace: Entity,
        hypothesis: Entity,
        probe_type: str,
        assumption_id: str,
        assumption: str,
        procedure: str,
        target_segment: str,
        metric: str,
        threshold: float,
        sample_target: int,
        duration_days: int,
        budget_minor: int,
        actor: str,
        supersedes_probe: Entity | None = None,
    ) -> Entity:
        self._require_kind(workspace, EntityKind.VALIDATION_WORKSPACE)
        self._require_kind(hypothesis, EntityKind.HYPOTHESIS)
        if probe_type not in self.MARKET_PROBE_TYPES:
            raise ValueError("unsupported market probe type")
        if not assumption.strip() or not procedure.strip() or not metric.strip():
            raise ValueError("probe assumption, procedure, and metric are required")
        if sample_target < 1 or not 1 <= duration_days <= 90 or budget_minor < 0:
            raise ValueError("probe sample, duration, or budget is outside the bounded range")
        if supersedes_probe is not None:
            self._require_kind(supersedes_probe, EntityKind.EXPERIMENT)
            if (
                supersedes_probe.attributes.get("experiment_type") != "market_probe"
                or supersedes_probe.attributes.get("workspace_id") != workspace.id
                or self._experiment_status(supersedes_probe) is not None
            ):
                raise ValueError("only a proposed probe in this workspace can be revised")
        probe = self.create_entity(
            EntityKind.EXPERIMENT,
            {
                "experiment_type": "market_probe",
                "workspace_id": workspace.id,
                "hypothesis_id": hypothesis.id,
                "probe_type": probe_type,
                "assumption_id": assumption_id,
                "assumption": assumption[:4000],
                "procedure": procedure[:10_000],
                "target_segment": target_segment[:4000],
                "success_criterion": {"metric": metric, "operator": ">=", "threshold": float(threshold)},
                "sample_target": sample_target,
                "duration_days": duration_days,
                "budget_minor": budget_minor,
                "approved_by": None,
                "policy_version": self.policy.version,
                "policy_digest": self.policy.digest,
                "external_execution": "manual_owner_only",
                "evidence_capture": "Record aggregate metrics, sample size, timeframe, bounded notes, limitations, and optional source URL.",
            },
            actor=actor,
            reasoning_summary="Prepared a manual market probe; no external action was started.",
            evidence_ids=(workspace.id, hypothesis.id),
        )
        self.relate(workspace, RelationType.CONTAINS, probe)
        self.relate(probe, RelationType.TESTS, hypothesis)
        if supersedes_probe is not None:
            self.relate(probe, RelationType.SUPERSEDES, supersedes_probe)
        return probe

    def start_market_probe(self, probe: Entity, *, actor: str) -> Entity:
        self._require_kind(probe, EntityKind.EXPERIMENT)
        if probe.attributes.get("experiment_type") != "market_probe":
            raise ValueError("experiment is not a manual market probe")
        if self._experiment_status(probe) is not None:
            raise ValueError("market probe has already been started")
        running = sum(
            self._experiment_status(entity) == "running"
            for entity in self.store.entities(EntityKind.EXPERIMENT)
        )
        self.policy.check_experiment(
            approved=True,
            budget_minor=int(probe.attributes.get("budget_minor") or 0),
            running=running,
        )
        return self.transition_experiment(probe, "running", actor=actor)

    def complete_market_probe(
        self,
        *,
        probe: Entity,
        values: Mapping[str, float],
        sample_size: int,
        timeframe: str,
        notes: str,
        limitations: str,
        source_url: str | None,
        actor: str,
    ) -> tuple[Entity, Entity, Entity]:
        self._require_kind(probe, EntityKind.EXPERIMENT)
        if probe.attributes.get("experiment_type") != "market_probe" or self._experiment_status(probe) != "running":
            raise ValueError("only a running market probe can be completed")
        if sample_size < 0 or not values:
            raise ValueError("aggregate probe values are required")
        if self.SENSITIVE_OBSERVATION.search(f"{notes}\n{limitations}"):
            raise ValueError("probe observations must not contain secrets or personal contact data")
        hypothesis = self.store.get_entity(str(probe.attributes["hypothesis_id"]))
        source = self.create_entity(
            EntityKind.SOURCE,
            {
                "title": f"Manual {probe.attributes['probe_type']} probe result",
                "source_uri": (source_url or f"ptw://market-probe/{probe.id}")[:4000],
                "finding_summary": notes[:10_000],
                "publisher": "PTW owner validation",
                "credibility": .8,
                "research_type": "product_validation",
                "factual": True,
                "sample_size": sample_size,
                "timeframe": timeframe[:500],
                "limitations": limitations[:4000],
            },
            actor=actor,
            reasoning_summary="Recorded owner-supplied aggregate probe evidence separately from interpretation.",
            evidence_ids=(probe.id,),
        )
        metrics = self.ingest_metrics(
            experiment=probe,
            source=source,
            values={str(key): float(value) for key, value in values.items()},
            attribution_window=timeframe[:500],
        )
        observation, insight = self.evaluate(experiment=probe, hypothesis=hypothesis, metric_set=metrics)
        workspace = self.store.get_entity(str(probe.attributes["workspace_id"]))
        self.relate(workspace, RelationType.CONTAINS, observation)
        self.relate(workspace, RelationType.CONTAINS, insight)
        return observation, insight, metrics

    def decide_validation(
        self,
        *,
        workspace: Entity,
        action: str,
        rationale: str,
        actor: str,
        selected_mechanism_ids: Sequence[str] = (),
        product_loop: Sequence[str] = (),
    ) -> tuple[Entity, Entity | None]:
        self._require_kind(workspace, EntityKind.VALIDATION_WORKSPACE)
        if action not in self.THESIS_DECISIONS or not rationale.strip():
            raise ValueError("decision action and rationale are required")
        hypothesis = self.store.get_entity(str(workspace.attributes["hypothesis_id"]))
        hypothesis_edges = [edge for edge in self.store.relationships() if edge.source_id == hypothesis.id]
        mechanism_ids = {
            edge.target_id for edge in hypothesis_edges
            if edge.relation == RelationType.CONTAINS
            and self.store.get_entity(edge.target_id).kind == EntityKind.PRODUCT_MECHANISM
        }
        selected_ids = tuple(dict.fromkeys(str(value) for value in selected_mechanism_ids))
        if action == "mutate" and (not selected_ids or not set(selected_ids).issubset(mechanism_ids)):
            raise ValueError("mutate requires an explicit subset of the thesis mechanisms")
        cleaned_loop = tuple(str(value).strip() for value in product_loop if str(value).strip())
        if action == "pivot":
            if not 5 <= len(cleaned_loop) <= 8:
                raise ValueError("pivot requires a materially different 5-8 step product loop")
            if list(cleaned_loop) == list(hypothesis.attributes.get("product_loop") or []):
                raise ValueError("pivot product loop must differ from the current thesis")
        contained_ids = {
            edge.target_id for edge in self.store.relationships()
            if edge.source_id == workspace.id and edge.relation == RelationType.CONTAINS
        }
        insights = [item for item in self.store.entities(EntityKind.INSIGHT) if item.id in contained_ids]
        if action == "continue" and not insights:
            raise ValueError("continue requires at least one evaluated market probe")
        if insights:
            insight = max(insights, key=lambda item: item.created_at)
        else:
            insight = self.create_entity(
                EntityKind.INSIGHT,
                {"interpretation": rationale[:10_000], "scope": hypothesis.attributes.get("scope"), "owner_override": True},
                actor=actor,
                reasoning_summary="Owner recorded a scoped thesis decision before another probe.",
                evidence_ids=(hypothesis.id,),
            )
            self.relate(workspace, RelationType.CONTAINS, insight)
        prior_decisions = [item for item in self.store.entities(EntityKind.DECISION) if item.id in contained_ids]
        previous = max(prior_decisions, key=lambda item: item.created_at) if prior_decisions else None
        decision = self.decide(
            insight=insight,
            hypothesis=hypothesis,
            decision_key=f"validation:{workspace.id}",
            action=action,
            confidence=1.0,
            previous_decision=previous,
            approved_by=actor,
            rationale=rationale,
        )
        self.relate(workspace, RelationType.CONTAINS, decision)
        replacement = None
        if action in {"mutate", "pivot"}:
            replacement = self.create_entity(
                EntityKind.HYPOTHESIS,
                {
                    **dict(hypothesis.attributes),
                    "claim": f"{action.title()} of {hypothesis.attributes.get('claim', '')}: {rationale[:4000]}",
                    "status": "proposed",
                    "revision_reason": rationale[:4000],
                    "revision_action": action,
                    **({"product_loop": list(cleaned_loop)} if action == "pivot" else {}),
                },
                actor=actor,
                reasoning_summary=f"Created an append-only thesis {action} revision.",
                evidence_ids=(decision.id, hypothesis.id),
            )
            self.relate(replacement, RelationType.SUPERSEDES, hypothesis)
            for edge in hypothesis_edges:
                if edge.relation == RelationType.DERIVED_FROM:
                    self.relate(replacement, edge.relation, self.store.get_entity(edge.target_id))
                elif edge.relation == RelationType.CONTAINS and (
                    action == "pivot" or edge.target_id in selected_ids
                ):
                    self.relate(replacement, edge.relation, self.store.get_entity(edge.target_id))
        return decision, replacement

    def validation_snapshot(self, workspace: Entity) -> Mapping[str, Any]:
        self._require_kind(workspace, EntityKind.VALIDATION_WORKSPACE)
        contained = [
            self.store.get_entity(edge.target_id)
            for edge in self.store.relationships()
            if edge.source_id == workspace.id and edge.relation == RelationType.CONTAINS
        ]
        hypothesis = self.store.get_entity(str(workspace.attributes["hypothesis_id"]))
        mechanisms = [
            self.store.get_entity(edge.target_id).to_dict()
            for edge in self.store.relationships()
            if edge.source_id == hypothesis.id and edge.relation == RelationType.CONTAINS
            and self.store.get_entity(edge.target_id).kind == EntityKind.PRODUCT_MECHANISM
        ]
        superseded_probe_ids = {
            edge.target_id for edge in self.store.relationships()
            if edge.relation == RelationType.SUPERSEDES
            and self.store.get_entity(edge.source_id).kind == EntityKind.EXPERIMENT
        }
        return {
            "workspace": workspace.to_dict(),
            "hypothesis": hypothesis.to_dict(),
            "mechanisms": mechanisms,
            "probes": [
                {**item.to_dict(), "status": "superseded" if item.id in superseded_probe_ids else self._experiment_status(item) or "proposed"}
                for item in contained if item.kind == EntityKind.EXPERIMENT
            ],
            "observations": [item.to_dict() for item in contained if item.kind == EntityKind.OBSERVATION],
            "insights": [item.to_dict() for item in contained if item.kind == EntityKind.INSIGHT],
            "decisions": [item.to_dict() for item in contained if item.kind == EntityKind.DECISION],
        }

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
        return self._record_creative_feedback(
            creative=creative,
            rating=rating,
            comment=comment,
            actor=actor,
            feedback_type="owner_review",
            extra_attributes={},
        )

    def record_ad_estimate(
        self,
        *,
        creative: Entity,
        predicted_ctr: float,
        rating: int,
        comment: str,
        actor: str,
        artifact_digest: str | None = None,
        annotations: tuple[Mapping[str, Any], ...] = (),
        supersedes_feedback_id: str | None = None,
    ) -> tuple[Entity, tuple[Entity, ...]]:
        if not 0 <= predicted_ctr <= 100:
            raise ValueError("predicted CTR must be between 0 and 100 percent")
        return self._record_creative_feedback(
            creative=creative,
            rating=rating,
            comment=comment,
            actor=actor,
            feedback_type="ad_owner_estimate",
            extra_attributes={
                "predicted_link_ctr_percent": predicted_ctr,
                **({"artifact_digest": artifact_digest} if artifact_digest else {}),
                **({"annotations": list(annotations)} if annotations else {}),
            },
            supersedes_feedback_id=supersedes_feedback_id,
        )

    def record_annotated_feedback(
        self,
        *,
        creative: Entity,
        artifact_digest: str,
        rating: int,
        comment: str,
        annotations: tuple[Mapping[str, Any], ...],
        actor: str,
        supersedes_feedback_id: str | None = None,
    ) -> tuple[Entity, tuple[Entity, ...]]:
        return self._record_creative_feedback(
            creative=creative,
            rating=rating,
            comment=comment,
            actor=actor,
            feedback_type="owner_annotated_review",
            extra_attributes={"artifact_digest": artifact_digest, "annotations": list(annotations)},
            supersedes_feedback_id=supersedes_feedback_id,
        )

    def record_text_feedback(
        self,
        *,
        creative: Entity,
        artifact_digest: str,
        comment: str,
        actor: str,
        supersedes_feedback_id: str | None = None,
    ) -> tuple[Entity, tuple[Entity, ...]]:
        return self._record_creative_feedback(
            creative=creative,
            rating=None,
            comment=comment,
            actor=actor,
            feedback_type="owner_text_review",
            extra_attributes={"artifact_digest": artifact_digest, "annotations": []},
            supersedes_feedback_id=supersedes_feedback_id,
        )

    def _record_creative_feedback(
        self,
        *,
        creative: Entity,
        rating: int | None,
        comment: str,
        actor: str,
        feedback_type: str,
        extra_attributes: Mapping[str, Any],
        supersedes_feedback_id: str | None = None,
    ) -> tuple[Entity, tuple[Entity, ...]]:
        self._require_kind(creative, EntityKind.CREATIVE)
        if rating is not None and rating not in range(1, 6):
            raise ValueError("feedback rating must be an integer from 1 to 5")
        if rating is None and not comment.strip():
            raise ValueError("text feedback must not be empty")
        previous = tuple(
            item
            for item in self.store.entities(EntityKind.HUMAN_FEEDBACK)
            if item.attributes.get("creative_id") == creative.id
            and item.attributes.get("actor") == actor
        )
        duplicate = bool(previous)
        if duplicate and not supersedes_feedback_id:
            raise ValueError("feedback from this actor already exists for the creative")
        if supersedes_feedback_id and supersedes_feedback_id not in {item.id for item in previous}:
            raise ValueError("superseded feedback must be an earlier owner review of this creative")
        with self.store.transaction():
            feedback = self.create_entity(
                EntityKind.HUMAN_FEEDBACK,
                {
                    "creative_id": creative.id,
                    "rating": rating,
                    "comment": comment.strip()[:1000],
                    "actor": actor,
                    "feedback_type": feedback_type,
                    **dict(extra_attributes),
                },
                actor=actor,
                reasoning_summary="Recorded explicit owner feedback without treating it as an observation.",
                evidence_ids=(creative.id,),
            )
            self.relate(feedback, RelationType.EVALUATES, creative)
            if supersedes_feedback_id:
                self.relate(
                    feedback,
                    RelationType.SUPERSEDES,
                    self.store.get_entity(supersedes_feedback_id),
                )
            components = tuple(
                self.store.get_entity(edge.target_id)
                for edge in self.store.relationships()
                if edge.source_id == creative.id and edge.relation == RelationType.CONTAINS
            )
            updates: list[Entity] = []
            delta = (rating - 3) * 0.05 if rating is not None else 0.0
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
                        "algorithm": "owner_rating_linear_v1" if rating is not None else "owner_text_feedback_v1",
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
        rationale: str | None = None,
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
                "reasoning_summary": (rationale or "Decision follows the scoped insight and recorded evidence.")[:10_000],
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
