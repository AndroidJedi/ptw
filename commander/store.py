"""Repository ports and a replayable local prototype adapter."""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Protocol

from .model import Entity, EntityKind, Relationship


class KnowledgeStore(Protocol):
    def add_entity(self, entity: Entity) -> None: ...
    def add_relationship(self, relationship: Relationship) -> None: ...
    def get_entity(self, entity_id: str) -> Entity: ...
    def entities(self, kind: EntityKind | None = None) -> tuple[Entity, ...]: ...
    def relationships(self) -> tuple[Relationship, ...]: ...
    def transaction(self): ...
    def enqueue_outbox(self, topic: str, aggregate_id: str | None, payload: dict[str, object]) -> str: ...


class MemoryKnowledgeStore:
    def __init__(self) -> None:
        self._entities: dict[str, Entity] = {}
        self._relationships: dict[str, Relationship] = {}
        self.outbox: list[dict[str, object]] = []
        self.telegram_deliveries: dict[tuple[int, int], str] = {}

    def add_entity(self, entity: Entity) -> None:
        if entity.id in self._entities:
            raise ValueError(f"entity is immutable and already exists: {entity.id}")
        self._entities[entity.id] = entity

    def add_relationship(self, relationship: Relationship) -> None:
        if relationship.id in self._relationships:
            raise ValueError(f"relationship already exists: {relationship.id}")
        if relationship.source_id not in self._entities:
            raise ValueError(f"unknown relationship source: {relationship.source_id}")
        if relationship.target_id not in self._entities:
            raise ValueError(f"unknown relationship target: {relationship.target_id}")
        duplicate = any(
            edge.source_id == relationship.source_id
            and edge.relation == relationship.relation
            and edge.target_id == relationship.target_id
            for edge in self._relationships.values()
        )
        if duplicate:
            raise ValueError("duplicate relationship")
        self._relationships[relationship.id] = relationship

    def get_entity(self, entity_id: str) -> Entity:
        try:
            return self._entities[entity_id]
        except KeyError as error:
            raise KeyError(f"unknown entity: {entity_id}") from error

    def entities(self, kind: EntityKind | None = None) -> tuple[Entity, ...]:
        values: Iterable[Entity] = self._entities.values()
        if kind is not None:
            values = (entity for entity in values if entity.kind == kind)
        return tuple(values)

    def relationships(self) -> tuple[Relationship, ...]:
        return tuple(self._relationships.values())

    @contextmanager
    def transaction(self):
        # The in-memory adapter is only for deterministic single-process tests.
        yield self

    def enqueue_outbox(
        self, topic: str, aggregate_id: str | None, payload: dict[str, object]
    ) -> str:
        from .ids import new_uuid7

        message_id = new_uuid7()
        self.outbox.append(
            {"id": message_id, "topic": topic, "aggregate_id": aggregate_id, "payload": payload}
        )
        return message_id

    def record_telegram_delivery(self, chat_id: int, message_id: int, entity_id: str) -> None:
        self.get_entity(entity_id)
        self.telegram_deliveries[(chat_id, message_id)] = entity_id

    def telegram_delivery_entity(self, chat_id: int, message_id: int) -> str | None:
        return self.telegram_deliveries.get((chat_id, message_id))


class JsonlKnowledgeStore(MemoryKnowledgeStore):
    """Single-process append log used only for local vertical validation."""

    def __init__(self, directory: Path) -> None:
        super().__init__()
        self.directory = directory
        self.event_path = directory / "events.jsonl"
        self.projection_path = directory / "projection.json"
        directory.mkdir(parents=True, exist_ok=True)
        if self.event_path.exists():
            self._replay()

    def _replay(self) -> None:
        for line in self.event_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            event = json.loads(line)
            if event["type"] == "entity_added":
                super().add_entity(Entity.from_dict(event["entity"]))
            elif event["type"] == "relationship_added":
                super().add_relationship(Relationship.from_dict(event["relationship"]))
            else:
                raise ValueError(f"unknown store event type: {event['type']}")

    def add_entity(self, entity: Entity) -> None:
        super().add_entity(entity)
        self._append({"type": "entity_added", "entity": entity.to_dict()})

    def add_relationship(self, relationship: Relationship) -> None:
        super().add_relationship(relationship)
        self._append(
            {"type": "relationship_added", "relationship": relationship.to_dict()}
        )

    def _append(self, event: dict[str, object]) -> None:
        encoded = json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n"
        with self.event_path.open("a", encoding="utf-8") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        self._write_projection()

    def _write_projection(self) -> None:
        value = {
            "entities": [entity.to_dict() for entity in self.entities()],
            "relationships": [edge.to_dict() for edge in self.relationships()],
        }
        temporary = self.projection_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(self.projection_path)
