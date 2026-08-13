"""Generic append-only knowledge entities and first-class relationships."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Mapping

from .ids import new_uuid7


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EntityKind(StrEnum):
    SOURCE = "source"
    HYPOTHESIS = "hypothesis"
    CREATIVE_COMPONENT = "creative_component"
    CREATIVE = "creative"
    CAMPAIGN = "campaign"
    AUDIENCE = "audience"
    EXPERIMENT = "experiment"
    EXPERIMENT_STATE = "experiment_state"
    METRIC_SET = "metric_set"
    OBSERVATION = "observation"
    INSIGHT = "insight"
    DECISION = "decision"
    KNOWLEDGE_ASSERTION = "knowledge_assertion"
    TASK = "task"
    ARTIFACT = "artifact"
    AUDIT_EVENT = "audit_event"
    POLICY_EVALUATION = "policy_evaluation"


class RelationType(StrEnum):
    CONTAINS = "contains"
    DERIVED_FROM = "derived_from"
    TESTS = "tests"
    TESTED_IN = "tested_in"
    MEASURED_BY = "measured_by"
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    SUPERSEDES = "supersedes"
    ADOPTED_AS = "adopted_as"
    GENERATED = "generated"
    SCHEDULED_BY = "scheduled_by"
    STATE_OF = "state_of"


@dataclass(frozen=True, slots=True)
class Entity:
    kind: EntityKind
    attributes: Mapping[str, Any]
    id: str = field(default_factory=new_uuid7)
    created_at: datetime = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "created_at": self.created_at.isoformat(),
            "attributes": dict(self.attributes),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Entity":
        return cls(
            id=str(value["id"]),
            kind=EntityKind(value["kind"]),
            created_at=datetime.fromisoformat(str(value["created_at"])),
            attributes=dict(value["attributes"]),
        )


@dataclass(frozen=True, slots=True)
class Relationship:
    source_id: str
    relation: RelationType
    target_id: str
    attributes: Mapping[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=new_uuid7)
    created_at: datetime = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "relation": self.relation.value,
            "target_id": self.target_id,
            "created_at": self.created_at.isoformat(),
            "attributes": dict(self.attributes),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Relationship":
        return cls(
            id=str(value["id"]),
            source_id=str(value["source_id"]),
            relation=RelationType(value["relation"]),
            target_id=str(value["target_id"]),
            created_at=datetime.fromisoformat(str(value["created_at"])),
            attributes=dict(value["attributes"]),
        )
