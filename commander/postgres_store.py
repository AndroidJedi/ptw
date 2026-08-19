"""PostgreSQL knowledge repository with a transactional outbox."""

from __future__ import annotations

import json
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Iterator, Mapping, Protocol

from .ids import new_uuid7
from .model import Entity, EntityKind, Relationship
from .checkpoint import SessionCheckpoint, checkpoint_checksum, normalize_checkpoint


class Cursor(Protocol):
    def execute(self, query: str, params: tuple[object, ...] = ()) -> Any: ...
    def fetchone(self) -> tuple[object, ...] | None: ...
    def fetchall(self) -> list[tuple[object, ...]]: ...
    def __enter__(self) -> "Cursor": ...
    def __exit__(self, *args: object) -> None: ...


class Connection(Protocol):
    def cursor(self) -> Cursor: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...


@dataclass(frozen=True, slots=True)
class OutboxMessage:
    id: str
    topic: str
    aggregate_id: str | None
    payload: Mapping[str, Any]
    attempts: int


@dataclass(frozen=True, slots=True)
class WorkspaceTaskAcknowledgement:
    entity_id: str
    task_id: str
    interpreted_scope: str
    workspace_session_id: str
    chat_id: int
    status: str
    telegram_message_id: int | None = None


def connect_postgres(connection_string: str) -> "PostgresKnowledgeStore":
    """Create the production adapter while keeping psycopg an optional import."""

    try:
        import psycopg  # type: ignore[import-not-found]
    except ImportError as error:
        raise RuntimeError(
            "PostgreSQL support requires: pip install -r requirements-commander.txt"
        ) from error
    return PostgresKnowledgeStore(psycopg.connect(connection_string, connect_timeout=5))


class PostgresKnowledgeStore:
    def __init__(self, connection: Connection) -> None:
        self.connection = connection
        self._transaction_depth = 0

    @contextmanager
    def transaction(self) -> Iterator["PostgresKnowledgeStore"]:
        outermost = self._transaction_depth == 0
        self._transaction_depth += 1
        try:
            yield self
            if outermost:
                self.connection.commit()
        except Exception:
            if outermost:
                self.connection.rollback()
            raise
        finally:
            self._transaction_depth -= 1

    def _write(self, operation: Callable[[Cursor], None]) -> None:
        if self._transaction_depth:
            with self.connection.cursor() as cursor:
                operation(cursor)
            return
        with self.transaction():
            with self.connection.cursor() as cursor:
                operation(cursor)

    def ping(self) -> None:
        """Verify the database and always close the probe transaction."""
        with self.transaction():
            with self.connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()

    def add_entity(self, entity: Entity) -> None:
        def operation(cursor: Cursor) -> None:
            attributes = json.dumps(dict(entity.attributes), sort_keys=True)
            cursor.execute(
                """INSERT INTO commander_entities (id, kind, created_at, attributes)
                   VALUES (%s, %s, %s, %s::jsonb)""",
                (entity.id, entity.kind.value, entity.created_at, attributes),
            )
            self._insert_projection(cursor, entity)
            self._insert_outbox(cursor, "commander.entity.created", entity.id, entity.to_dict())

        self._write(operation)

    def add_relationship(self, relationship: Relationship) -> None:
        def operation(cursor: Cursor) -> None:
            cursor.execute(
                """INSERT INTO commander_relationships
                   (id, source_id, relation, target_id, created_at, attributes)
                   VALUES (%s, %s, %s, %s, %s, %s::jsonb)""",
                (
                    relationship.id,
                    relationship.source_id,
                    relationship.relation.value,
                    relationship.target_id,
                    relationship.created_at,
                    json.dumps(dict(relationship.attributes), sort_keys=True),
                ),
            )
            if relationship.relation.value == "state_of":
                cursor.execute(
                    "SELECT kind, attributes FROM commander_entities WHERE id = %s",
                    (relationship.source_id,),
                )
                source = cursor.fetchone()
                if source is not None and str(source[0]) == EntityKind.EXPERIMENT_STATE.value:
                    attributes = self._json(source[1])
                    cursor.execute(
                        """INSERT INTO commander_experiment_states
                           (entity_id, experiment_id, state, previous_state, occurred_at)
                           VALUES (%s, %s, %s, %s, %s)""",
                        (
                            relationship.source_id,
                            relationship.target_id,
                            attributes["status"],
                            attributes.get("previous_status"),
                            relationship.created_at,
                        ),
                    )
            self._insert_outbox(
                cursor,
                "commander.relationship.created",
                relationship.source_id,
                relationship.to_dict(),
            )

        self._write(operation)

    def enqueue_outbox(
        self, topic: str, aggregate_id: str | None, payload: dict[str, object]
    ) -> str:
        message_id = new_uuid7()

        def operation(cursor: Cursor) -> None:
            cursor.execute(
                """INSERT INTO commander_outbox (id, topic, aggregate_id, payload)
                   VALUES (%s, %s, %s, %s::jsonb)""",
                (message_id, topic, aggregate_id, json.dumps(payload, sort_keys=True)),
            )

        self._write(operation)
        return message_id

    def register_workspace_task(
        self,
        *,
        task_id: str,
        interpreted_scope: str,
        workspace_session_id: str,
        chat_id: int,
    ) -> WorkspaceTaskAcknowledgement:
        """Durably register acceptance and its Telegram acknowledgement together."""

        entity_id = new_uuid7()
        outbox_id = new_uuid7()
        attributes = {
            "status": "queued",
            "external_task_id": task_id,
            "interpreted_scope": interpreted_scope,
            "workspace_session_id": workspace_session_id,
            "source": "codex_workspace",
        }
        acknowledgement = (
            f"{task_id} accepted.\n"
            f"Interpreted scope: {interpreted_scope}\n"
            "Execution is waiting for this acknowledgement to be delivered."
        )
        with self.transaction():
            with self.connection.cursor() as cursor:
                cursor.execute(
                    """SELECT entity_id, interpreted_scope, workspace_session_id,
                              telegram_chat_id, acknowledgement_status,
                              telegram_message_id
                       FROM commander_tasks WHERE external_task_id = %s FOR UPDATE""",
                    (task_id,),
                )
                existing = cursor.fetchone()
                if existing is not None:
                    if (
                        str(existing[1]) != interpreted_scope
                        or str(existing[2]) != workspace_session_id
                        or int(existing[3]) != chat_id
                    ):
                        raise ValueError(f"{task_id} is already registered with different details")
                    return WorkspaceTaskAcknowledgement(
                        entity_id=str(existing[0]),
                        task_id=task_id,
                        interpreted_scope=interpreted_scope,
                        workspace_session_id=workspace_session_id,
                        chat_id=chat_id,
                        status=str(existing[4]),
                        telegram_message_id=(
                            None if existing[5] is None else int(existing[5])
                        ),
                    )
                cursor.execute(
                    """INSERT INTO commander_entities (id, kind, attributes)
                       VALUES (%s, 'task', %s::jsonb)""",
                    (entity_id, json.dumps(attributes, sort_keys=True)),
                )
                cursor.execute(
                    """INSERT INTO commander_outbox
                       (id, topic, aggregate_id, payload)
                       VALUES (%s, 'telegram.send_message', %s, %s::jsonb)""",
                    (
                        outbox_id,
                        entity_id,
                        json.dumps(
                            {
                                "chat_id": chat_id,
                                "text": acknowledgement,
                                "workspace_task_id": task_id,
                            },
                            sort_keys=True,
                        ),
                    ),
                )
                cursor.execute(
                    """INSERT INTO commander_tasks
                       (entity_id, status, idempotency_key, external_task_id,
                        interpreted_scope, workspace_session_id, telegram_chat_id,
                        acknowledgement_status, acknowledgement_outbox_id)
                       VALUES (%s, 'queued', %s, %s, %s, %s, %s, 'pending', %s)""",
                    (
                        entity_id,
                        f"codex-workspace:{task_id}",
                        task_id,
                        interpreted_scope,
                        workspace_session_id,
                        chat_id,
                        outbox_id,
                    ),
                )
        return WorkspaceTaskAcknowledgement(
            entity_id=entity_id,
            task_id=task_id,
            interpreted_scope=interpreted_scope,
            workspace_session_id=workspace_session_id,
            chat_id=chat_id,
            status="pending",
        )

    def workspace_task_acknowledgement(self, task_id: str) -> WorkspaceTaskAcknowledgement:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """SELECT entity_id, interpreted_scope, workspace_session_id,
                          telegram_chat_id, acknowledgement_status,
                          telegram_message_id
                   FROM commander_tasks WHERE external_task_id = %s""",
                (task_id,),
            )
            row = cursor.fetchone()
        if row is None:
            raise KeyError(f"unknown workspace task: {task_id}")
        return WorkspaceTaskAcknowledgement(
            entity_id=str(row[0]),
            task_id=task_id,
            interpreted_scope=str(row[1]),
            workspace_session_id=str(row[2]),
            chat_id=int(row[3]),
            status=str(row[4]),
            telegram_message_id=None if row[5] is None else int(row[5]),
        )

    def mark_workspace_task_acknowledged(self, task_id: str, message_id: int) -> None:
        def operation(cursor: Cursor) -> None:
            cursor.execute(
                """UPDATE commander_tasks
                   SET acknowledgement_status = 'acknowledged',
                       acknowledged_at = clock_timestamp(),
                       telegram_message_id = %s
                   WHERE external_task_id = %s
                     AND acknowledgement_status = 'pending'""",
                (message_id, task_id),
            )

        self._write(operation)

    def save_session_checkpoint(self, request: Mapping[str, object]) -> SessionCheckpoint:
        """Append a bounded resume point; previous checkpoints remain evidence."""

        payload = normalize_checkpoint(request)
        checkpoint_id = new_uuid7()
        checksum = checkpoint_checksum(payload)

        def operation(cursor: Cursor) -> None:
            cursor.execute(
                """INSERT INTO commander_session_checkpoints
                   (id, scope, workspace_session_id, version, payload, checksum)
                   VALUES (%s, %s, %s, %s, %s::jsonb, %s)
                   RETURNING created_at""",
                (
                    checkpoint_id,
                    payload["scope"],
                    payload["workspace_session_id"],
                    payload["version"],
                    json.dumps(payload, sort_keys=True),
                    checksum,
                ),
            )

        self._write(operation)
        return self.session_checkpoint(checkpoint_id)

    def session_checkpoint(self, checkpoint_id: str) -> SessionCheckpoint:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """SELECT id, payload, checksum, created_at
                   FROM commander_session_checkpoints WHERE id = %s""",
                (checkpoint_id,),
            )
            row = cursor.fetchone()
        if row is None:
            raise KeyError(f"unknown session checkpoint: {checkpoint_id}")
        return self._checkpoint_from_row(row)

    def latest_session_checkpoint(self, scope: str = "commander") -> SessionCheckpoint:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """SELECT id, payload, checksum, created_at
                   FROM commander_session_checkpoints
                   WHERE scope = %s ORDER BY created_at DESC, id DESC LIMIT 1""",
                (scope,),
            )
            row = cursor.fetchone()
        if row is None:
            raise KeyError(f"no session checkpoint for scope: {scope}")
        return self._checkpoint_from_row(row)

    def _checkpoint_from_row(self, row: tuple[object, ...]) -> SessionCheckpoint:
        payload = self._json(row[1])
        return SessionCheckpoint(
            checkpoint_id=str(row[0]),
            scope=str(payload["scope"]),
            workspace_session_id=str(payload["workspace_session_id"]),
            agreed_decisions=tuple(payload["agreed_decisions"]),
            active_tasks=tuple(payload["active_tasks"]),
            active_issues=tuple(payload["active_issues"]),
            deployment_state=dict(payload["deployment_state"]),
            verification_evidence=tuple(payload["verification_evidence"]),
            next_action=str(payload["next_action"]),
            created_at=row[3],
            checksum=str(row[2]),
            version=int(payload["version"]),
        )

    def record_inbox_once(self, update_id: int) -> bool:
        if self._transaction_depth == 0:
            raise RuntimeError("record_inbox_once must run inside store.transaction()")
        with self.connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO commander_telegram_inbox (update_id)
                   VALUES (%s) ON CONFLICT (update_id) DO NOTHING
                   RETURNING update_id""",
                (update_id,),
            )
            return cursor.fetchone() is not None

    def record_telegram_delivery(self, chat_id: int, message_id: int, entity_id: str) -> None:
        def operation(cursor: Cursor) -> None:
            cursor.execute(
                """INSERT INTO commander_telegram_deliveries
                   (chat_id, message_id, entity_id)
                   VALUES (%s, %s, %s)
                   ON CONFLICT (chat_id, message_id) DO UPDATE
                   SET entity_id = EXCLUDED.entity_id""",
                (chat_id, message_id, entity_id),
            )

        self._write(operation)

    def telegram_delivery_entity(self, chat_id: int, message_id: int) -> str | None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """SELECT entity_id FROM commander_telegram_deliveries
                   WHERE chat_id = %s AND message_id = %s""",
                (chat_id, message_id),
            )
            row = cursor.fetchone()
        return None if row is None else str(row[0])

    def claim_outbox(
        self, *, topics: tuple[str, ...] = (), limit: int = 50
    ) -> tuple[OutboxMessage, ...]:
        """Lock and return pending messages inside the caller's transaction."""

        if self._transaction_depth == 0:
            raise RuntimeError("claim_outbox must run inside store.transaction()")
        with self.connection.cursor() as cursor:
            if topics:
                cursor.execute(
                    """SELECT id, topic, aggregate_id, payload, attempts
                       FROM commander_outbox
                       WHERE published_at IS NULL AND cancelled_at IS NULL
                         AND available_at <= clock_timestamp()
                         AND topic = ANY(%s)
                       ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT %s""",
                    (list(topics), limit),
                )
            else:
                cursor.execute(
                    """SELECT id, topic, aggregate_id, payload, attempts
                       FROM commander_outbox
                       WHERE published_at IS NULL AND cancelled_at IS NULL
                         AND available_at <= clock_timestamp()
                       ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT %s""",
                    (limit,),
                )
            rows = cursor.fetchall()
        return tuple(
            OutboxMessage(
                id=str(row[0]),
                topic=str(row[1]),
                aggregate_id=None if row[2] is None else str(row[2]),
                payload=self._json(row[3]),
                attempts=int(row[4]),
            )
            for row in rows
        )

    def mark_outbox_published(self, message_id: str) -> None:
        def operation(cursor: Cursor) -> None:
            cursor.execute(
                """UPDATE commander_outbox
                   SET published_at = clock_timestamp(), attempts = attempts + 1
                   WHERE id = %s AND published_at IS NULL""",
                (message_id,),
            )

        self._write(operation)

    def mark_outbox_failed(self, message_id: str, error_summary: str) -> None:
        def operation(cursor: Cursor) -> None:
            cursor.execute(
                """UPDATE commander_outbox
                   SET attempts = attempts + 1,
                       last_error = %s,
                       available_at = clock_timestamp()
                         + make_interval(secs => LEAST(300, power(2, LEAST(attempts, 8))::int))
                   WHERE id = %s AND published_at IS NULL""",
                (error_summary[:500], message_id),
            )

        self._write(operation)

    def get_entity(self, entity_id: str) -> Entity:
        with self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, kind, created_at, attributes FROM commander_entities WHERE id = %s",
                (entity_id,),
            )
            row = cursor.fetchone()
        if row is None:
            raise KeyError(f"unknown entity: {entity_id}")
        return self._entity(row)

    def entities(self, kind: EntityKind | None = None) -> tuple[Entity, ...]:
        with self.connection.cursor() as cursor:
            if kind is None:
                cursor.execute(
                    "SELECT id, kind, created_at, attributes FROM commander_entities ORDER BY created_at, id"
                )
            else:
                cursor.execute(
                    """SELECT id, kind, created_at, attributes FROM commander_entities
                       WHERE kind = %s ORDER BY created_at, id""",
                    (kind.value,),
                )
            rows = cursor.fetchall()
        return tuple(self._entity(row) for row in rows)

    def relationships(self) -> tuple[Relationship, ...]:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """SELECT id, source_id, relation, target_id, created_at, attributes
                   FROM commander_relationships ORDER BY created_at, id"""
            )
            rows = cursor.fetchall()
        return tuple(
            Relationship.from_dict(
                {
                    "id": str(row[0]),
                    "source_id": str(row[1]),
                    "relation": str(row[2]),
                    "target_id": str(row[3]),
                    "created_at": self._iso(row[4]),
                    "attributes": self._json(row[5]),
                }
            )
            for row in rows
        )

    def _insert_projection(self, cursor: Cursor, entity: Entity) -> None:
        attributes = entity.attributes
        if entity.kind == EntityKind.EXPERIMENT:
            cursor.execute(
                """INSERT INTO commander_experiments
                   (entity_id, budget_minor, approved_by, policy_version, policy_digest)
                   VALUES (%s, %s, %s, %s, %s)""",
                (
                    entity.id,
                    attributes["budget_minor"],
                    attributes.get("approved_by"),
                    attributes["policy_version"],
                    attributes["policy_digest"],
                ),
            )
        elif entity.kind == EntityKind.METRIC_SET:
            for name, value in attributes["values"].items():
                cursor.execute(
                    """INSERT INTO commander_metric_values (metric_set_id, name, value)
                       VALUES (%s, %s, %s)""",
                    (entity.id, name, value),
                )
        elif entity.kind == EntityKind.DECISION:
            cursor.execute(
                """INSERT INTO commander_decisions
                   (entity_id, decision_key, version, action, reasoning_summary, confidence)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (
                    entity.id,
                    attributes["decision_key"],
                    attributes["version"],
                    attributes["action"],
                    attributes["reasoning_summary"],
                    attributes["confidence"],
                ),
            )
        elif entity.kind == EntityKind.TASK:
            cursor.execute(
                """INSERT INTO commander_tasks (entity_id, status, idempotency_key)
                   VALUES (%s, %s, %s)""",
                (entity.id, attributes["status"], attributes.get("idempotency_key")),
            )
        elif entity.kind == EntityKind.POLICY_EVALUATION:
            cursor.execute(
                """INSERT INTO commander_policy_evaluations
                   (id, policy_version, policy_digest, outcome, summary)
                   VALUES (%s, %s, %s, %s, %s)""",
                (
                    entity.id,
                    attributes["policy_version"],
                    attributes["policy_digest"],
                    attributes["outcome"],
                    attributes["summary"],
                ),
            )

    @staticmethod
    def _insert_outbox(
        cursor: Cursor, topic: str, aggregate_id: str, payload: Mapping[str, Any]
    ) -> None:
        cursor.execute(
            """INSERT INTO commander_outbox (id, topic, aggregate_id, payload)
               VALUES (%s, %s, %s, %s::jsonb)""",
            (new_uuid7(), topic, aggregate_id, json.dumps(payload, sort_keys=True)),
        )

    @classmethod
    def _entity(cls, row: tuple[object, ...]) -> Entity:
        return Entity.from_dict(
            {
                "id": str(row[0]),
                "kind": str(row[1]),
                "created_at": cls._iso(row[2]),
                "attributes": cls._json(row[3]),
            }
        )

    @staticmethod
    def _json(value: object) -> Mapping[str, Any]:
        return json.loads(value) if isinstance(value, str) else dict(value)  # type: ignore[arg-type]

    @staticmethod
    def _iso(value: object) -> str:
        return value.isoformat() if isinstance(value, datetime) else str(value)
