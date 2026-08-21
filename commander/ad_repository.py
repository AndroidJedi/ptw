"""Durable operational projections for the ten-context ad workflow."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from typing import Any, Mapping, Protocol

from .ad_provider import AdContextSnapshot, AdCreativeSpec
from .postgres_store import PostgresKnowledgeStore


@dataclass(frozen=True, slots=True)
class AdBatchRecord:
    campaign_id: str
    source_id: str
    chat_id: int
    requested_by: str
    external_idea_id: int
    status: str
    brand_kit_id: str | None = None
    current_position: int | None = None
    last_error: str | None = None


@dataclass(frozen=True, slots=True)
class AdSlotRecord:
    batch_id: str
    position: int
    context: AdContextSnapshot
    status: str
    spec: AdCreativeSpec | None = None
    hypothesis_id: str | None = None
    creative_id: str | None = None
    artifact_id: str | None = None
    visual_path: str | None = None
    final_path: str | None = None
    predicted_ctr: float | None = None
    rating: int | None = None
    owner_comment: str = ""
    feedback_id: str | None = None
    conclusion_id: str | None = None
    last_error: str | None = None


class AdWorkflowRepository(Protocol):
    def active_contexts(self) -> tuple[AdContextSnapshot, ...]: ...
    def contexts(self) -> tuple[Mapping[str, Any], ...]: ...
    def context(self, code: str) -> Mapping[str, Any]: ...
    def context_history(self, code: str) -> tuple[Mapping[str, Any], ...]: ...
    def revise_context(self, code: str, *, name: str, prompt: str, actor: str, note: str) -> int: ...
    def set_context_active(self, code: str, active: bool) -> None: ...
    def idempotent_batch(self, key: str) -> str | None: ...
    def create_batch(self, batch: AdBatchRecord, key: str, contexts: tuple[AdContextSnapshot, ...]) -> None: ...
    def batch(self, batch_id: str) -> AdBatchRecord: ...
    def latest_batch(self, chat_id: int) -> AdBatchRecord: ...
    def slots(self, batch_id: str) -> tuple[AdSlotRecord, ...]: ...
    def slot(self, batch_id: str, position: int) -> AdSlotRecord: ...
    def slot_by_creative(self, creative_id: str) -> AdSlotRecord: ...
    def claim_generation(self) -> AdBatchRecord | None: ...
    def save_spec(self, batch_id: str, position: int, spec: AdCreativeSpec) -> None: ...
    def save_generated(self, batch_id: str, position: int, *, hypothesis_id: str, creative_id: str, artifact_id: str, visual_path: str, final_path: str) -> None: ...
    def finish_generation(self, batch_id: str) -> None: ...
    def fail(self, batch_id: str, position: int, error: str) -> None: ...
    def activate_review(self, chat_id: int) -> AdSlotRecord | None: ...
    def save_estimate(self, creative_id: str, *, predicted_ctr: float, rating: int, comment: str, feedback_id: str) -> AdSlotRecord: ...
    def save_review_projection(self, *, feedback_id: str, creative_id: str, artifact_digest: str, rating: int, comment: str, predicted_ctr: float | None, annotations: tuple[Mapping[str, Any], ...], supersedes_feedback_id: str | None = None) -> None: ...
    def claim_conclusion(self) -> AdSlotRecord | None: ...
    def finish_conclusion(self, creative_id: str, conclusion_id: str) -> AdSlotRecord | None: ...
    def continue_batch(self, batch_id: str) -> None: ...
    def record_execution(self, *, batch_id: str, position: int, phase: str, attempt: int, status: str, model: str, request_digest: str, response: Mapping[str, Any] | None = None, error: str | None = None) -> None: ...
    def metric_import_exists(self, source_system: str, import_id: str) -> bool: ...
    def record_metric_import(self, *, source_id: str, batch_id: str, source_system: str, import_id: str, captured_at: datetime, attribution_window: str) -> None: ...


class PostgresAdWorkflowRepository:
    def __init__(self, store: PostgresKnowledgeStore) -> None:
        self.store = store

    def active_contexts(self) -> tuple[AdContextSnapshot, ...]:
        rows = self._rows(
            "SELECT code,version,name,prompt_text FROM commander_ad_contexts "
            "WHERE active ORDER BY sort_order"
        )
        return tuple(AdContextSnapshot(str(r[0]), int(r[1]), str(r[2]), str(r[3])) for r in rows)

    def contexts(self) -> tuple[Mapping[str, Any], ...]:
        rows = self._rows(
            "SELECT code,name,prompt_text,active,sort_order,version,updated_at "
            "FROM commander_ad_contexts ORDER BY sort_order"
        )
        return tuple(
            {
                "code": str(r[0]), "name": str(r[1]), "prompt": str(r[2]),
                "active": bool(r[3]), "sort_order": int(r[4]), "version": int(r[5]),
                "updated_at": r[6],
            }
            for r in rows
        )

    def context(self, code: str) -> Mapping[str, Any]:
        rows = self._rows(
            "SELECT code,name,prompt_text,active,sort_order,version FROM commander_ad_contexts WHERE code=%s",
            (code.upper(),),
        )
        if not rows:
            raise KeyError(f"unknown ad context: {code}")
        row = rows[0]
        return {
            "code": str(row[0]), "name": str(row[1]), "prompt": str(row[2]),
            "active": bool(row[3]), "sort_order": int(row[4]), "version": int(row[5]),
        }

    def context_history(self, code: str) -> tuple[Mapping[str, Any], ...]:
        rows = self._rows(
            """SELECT r.version,r.name,r.prompt_text,r.changed_by,r.change_note,r.created_at
               FROM commander_ad_context_revisions r
               JOIN commander_ad_contexts c ON c.id=r.context_id
               WHERE c.code=%s ORDER BY r.version""",
            (code.upper(),),
        )
        return tuple(
            {
                "version": int(r[0]), "name": str(r[1]), "prompt": str(r[2]),
                "changed_by": str(r[3]), "change_note": r[4], "created_at": r[5],
            }
            for r in rows
        )

    def revise_context(
        self, code: str, *, name: str, prompt: str, actor: str, note: str
    ) -> int:
        if not name.strip() or not prompt.strip():
            raise ValueError("ad context name and prompt are required")
        with self.store.transaction():
            with self.store.connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id,version FROM commander_ad_contexts WHERE code=%s FOR UPDATE",
                    (code.upper(),),
                )
                row = cursor.fetchone()
                if row is None:
                    raise KeyError(f"unknown ad context: {code}")
                version = int(row[1]) + 1
                cursor.execute(
                    """UPDATE commander_ad_contexts SET name=%s,prompt_text=%s,version=%s,
                       updated_at=clock_timestamp() WHERE id=%s""",
                    (name.strip(), prompt.strip(), version, row[0]),
                )
                cursor.execute(
                    """INSERT INTO commander_ad_context_revisions
                       (context_id,version,name,prompt_text,changed_by,change_note)
                       VALUES (%s,%s,%s,%s,%s,%s)""",
                    (row[0], version, name.strip(), prompt.strip(), actor, note),
                )
        return version

    def set_context_active(self, code: str, active: bool) -> None:
        self.context(code)
        self._execute(
            "UPDATE commander_ad_contexts SET active=%s,updated_at=clock_timestamp() "
            "WHERE code=%s",
            (active, code.upper()),
        )

    def idempotent_batch(self, key: str) -> str | None:
        rows = self._rows(
            "SELECT campaign_id FROM commander_ad_batches WHERE idempotency_key=%s", (key,)
        )
        return str(rows[0][0]) if rows else None

    def create_batch(
        self,
        batch: AdBatchRecord,
        key: str,
        contexts: tuple[AdContextSnapshot, ...],
    ) -> None:
        if len(contexts) != 10:
            raise ValueError("ad generation requires exactly 10 active contexts")
        with self.store.transaction():
            with self.store.connection.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO commander_ad_batches
                       (campaign_id,source_id,chat_id,requested_by,external_idea_id,
                        idempotency_key,status,brand_kit_id)
                       VALUES (%s,%s,%s,%s,%s,%s,'queued',%s)""",
                    (
                        batch.campaign_id, batch.source_id, batch.chat_id,
                        batch.requested_by, batch.external_idea_id, key,
                        batch.brand_kit_id,
                    ),
                )
                for position, context in enumerate(contexts, 1):
                    cursor.execute(
                        """INSERT INTO commander_ad_slots
                           (batch_id,position,context_code,context_version,context_name,context_prompt)
                           VALUES (%s,%s,%s,%s,%s,%s)""",
                        (
                            batch.campaign_id, position, context.code, context.version,
                            context.name, context.prompt,
                        ),
                    )

    def batch(self, batch_id: str) -> AdBatchRecord:
        rows = self._rows(
            """SELECT campaign_id,source_id,chat_id,requested_by,external_idea_id,
                      status,brand_kit_id,current_position,last_error
               FROM commander_ad_batches WHERE campaign_id=%s""",
            (batch_id,),
        )
        if not rows:
            raise KeyError(f"unknown ad batch: {batch_id}")
        row = rows[0]
        return AdBatchRecord(
            str(row[0]), str(row[1]), int(row[2]), str(row[3]), int(row[4]),
            str(row[5]), None if row[6] is None else str(row[6]),
            None if row[7] is None else int(row[7]),
            None if row[8] is None else str(row[8]),
        )

    def latest_batch(self, chat_id: int) -> AdBatchRecord:
        rows = self._rows(
            "SELECT campaign_id FROM commander_ad_batches WHERE chat_id=%s "
            "ORDER BY created_at DESC LIMIT 1",
            (chat_id,),
        )
        if not rows:
            raise KeyError("this chat has no ad batches")
        return self.batch(str(rows[0][0]))

    def slots(self, batch_id: str) -> tuple[AdSlotRecord, ...]:
        return tuple(self._slot(row) for row in self._rows(
            self._slot_select() + " WHERE batch_id=%s ORDER BY position", (batch_id,)
        ))

    def slot(self, batch_id: str, position: int) -> AdSlotRecord:
        rows = self._rows(
            self._slot_select() + " WHERE batch_id=%s AND position=%s",
            (batch_id, position),
        )
        if not rows:
            raise KeyError(f"unknown ad slot: {batch_id}/{position}")
        return self._slot(rows[0])

    def slot_by_creative(self, creative_id: str) -> AdSlotRecord:
        rows = self._rows(self._slot_select() + " WHERE creative_id=%s", (creative_id,))
        if not rows:
            raise KeyError(f"creative is not part of an ad batch: {creative_id}")
        return self._slot(rows[0])

    def claim_generation(self) -> AdBatchRecord | None:
        with self.store.transaction():
            with self.store.connection.cursor() as cursor:
                cursor.execute(
                    """SELECT campaign_id FROM commander_ad_batches
                       WHERE status='queued' OR
                         (status='generating' AND locked_at < clock_timestamp()-interval '10 minutes')
                       ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1"""
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                cursor.execute(
                    """UPDATE commander_ad_batches SET status='generating',locked_at=clock_timestamp(),
                       attempts=attempts+1,last_error=NULL,updated_at=clock_timestamp()
                       WHERE campaign_id=%s""",
                    (row[0],),
                )
                batch_id = str(row[0])
        return self.batch(batch_id)

    def save_spec(self, batch_id: str, position: int, spec: AdCreativeSpec) -> None:
        self._execute(
            """UPDATE commander_ad_slots SET spec=%s::jsonb,status='spec_ready',
               last_error=NULL,updated_at=clock_timestamp() WHERE batch_id=%s AND position=%s""",
            (json.dumps(spec.to_dict(), sort_keys=True), batch_id, position),
        )

    def save_generated(
        self,
        batch_id: str,
        position: int,
        *,
        hypothesis_id: str,
        creative_id: str,
        artifact_id: str,
        visual_path: str,
        final_path: str,
    ) -> None:
        with self.store.transaction():
            with self.store.connection.cursor() as cursor:
                cursor.execute(
                    """UPDATE commander_ad_slots SET hypothesis_id=%s,creative_id=%s,artifact_id=%s,
                       visual_path=%s,final_path=%s,status='generated',last_error=NULL,
                       locked_at=NULL,updated_at=clock_timestamp()
                       WHERE batch_id=%s AND position=%s AND creative_id IS NULL
                       RETURNING creative_id""",
                    (
                        hypothesis_id, creative_id, artifact_id, visual_path, final_path,
                        batch_id, position,
                    ),
                )
                if cursor.fetchone() is None:
                    raise ValueError("ad slot already has a generated Creative")

    def finish_generation(self, batch_id: str) -> None:
        rows = self._rows(
            "SELECT count(*) FROM commander_ad_slots WHERE batch_id=%s AND status='generated'",
            (batch_id,),
        )
        if int(rows[0][0]) != 10:
            raise RuntimeError("ad review requires exactly 10 generated images")
        self._execute(
            """UPDATE commander_ad_batches SET status='review_ready',locked_at=NULL,
               last_error=NULL,updated_at=clock_timestamp() WHERE campaign_id=%s""",
            (batch_id,),
        )

    def fail(self, batch_id: str, position: int, error: str) -> None:
        with self.store.transaction():
            with self.store.connection.cursor() as cursor:
                cursor.execute(
                    """UPDATE commander_ad_slots SET status='failed',last_error=%s,locked_at=NULL,
                       attempts=attempts+1,updated_at=clock_timestamp()
                       WHERE batch_id=%s AND position=%s""",
                    (error[:500], batch_id, position),
                )
                cursor.execute(
                    """UPDATE commander_ad_batches SET status='failed',last_error=%s,locked_at=NULL,
                       updated_at=clock_timestamp() WHERE campaign_id=%s""",
                    (error[:500], batch_id),
                )

    def activate_review(self, chat_id: int) -> AdSlotRecord | None:
        with self.store.transaction():
            with self.store.connection.cursor() as cursor:
                cursor.execute(
                    """SELECT 1 FROM commander_ad_batches
                       WHERE chat_id=%s AND status IN ('awaiting_owner','concluding') LIMIT 1""",
                    (chat_id,),
                )
                if cursor.fetchone() is not None:
                    return None
                cursor.execute(
                    """SELECT campaign_id FROM commander_ad_batches
                       WHERE chat_id=%s AND status='review_ready'
                       ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1""",
                    (chat_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                batch_id = str(row[0])
                cursor.execute(
                    """UPDATE commander_ad_batches SET status='awaiting_owner',current_position=1,
                       updated_at=clock_timestamp() WHERE campaign_id=%s""",
                    (batch_id,),
                )
                cursor.execute(
                    """UPDATE commander_ad_slots SET status='delivered',updated_at=clock_timestamp()
                       WHERE batch_id=%s AND position=1""",
                    (batch_id,),
                )
        return self.slot(batch_id, 1)

    def save_estimate(
        self,
        creative_id: str,
        *,
        predicted_ctr: float,
        rating: int,
        comment: str,
        feedback_id: str,
    ) -> AdSlotRecord:
        with self.store.transaction():
            with self.store.connection.cursor() as cursor:
                cursor.execute(
                    """SELECT s.batch_id,s.position,b.status,b.current_position,s.feedback_id
                       FROM commander_ad_slots s JOIN commander_ad_batches b ON b.campaign_id=s.batch_id
                       WHERE s.creative_id=%s FOR UPDATE""",
                    (creative_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    raise KeyError(f"creative is not part of an ad batch: {creative_id}")
                if str(row[2]) != "awaiting_owner" or int(row[1]) != int(row[3]):
                    raise ValueError("estimate must reply to the currently active ad image")
                if row[4] is not None:
                    raise ValueError("this ad image already has an owner estimate")
                cursor.execute(
                    """UPDATE commander_ad_slots SET predicted_ctr=%s,rating=%s,owner_comment=%s,
                       feedback_id=%s,status='conclusion_pending',updated_at=clock_timestamp()
                       WHERE creative_id=%s""",
                    (predicted_ctr, rating, comment[:1000], feedback_id, creative_id),
                )
                cursor.execute(
                    """UPDATE commander_ad_batches SET status='concluding',updated_at=clock_timestamp()
                       WHERE campaign_id=%s""",
                    (row[0],),
                )
        return self.slot_by_creative(creative_id)

    def save_review_projection(
        self,
        *,
        feedback_id: str,
        creative_id: str,
        artifact_digest: str,
        rating: int,
        comment: str,
        predicted_ctr: float | None,
        annotations: tuple[Mapping[str, Any], ...],
        supersedes_feedback_id: str | None = None,
    ) -> None:
        rows = self._rows(
            """SELECT artifact.attributes->>'sha256'
               FROM commander_relationships edge
               JOIN commander_entities artifact ON artifact.id=edge.target_id
               WHERE edge.source_id=%s AND edge.relation='generated'
                 AND artifact.kind='artifact' AND artifact.attributes->>'sha256'=%s""",
            (creative_id, artifact_digest),
        )
        if not rows:
            raise ValueError("artifact digest does not belong to the Creative")
        self._execute(
            """INSERT INTO commander_creative_reviews(
                   feedback_id,creative_id,artifact_digest,rating,overall_comment,
                   predicted_ctr,annotations,supersedes_feedback_id
               ) VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb,%s)""",
            (feedback_id, creative_id, artifact_digest, rating, comment[:1000],
             predicted_ctr, json.dumps(list(annotations), ensure_ascii=False), supersedes_feedback_id),
        )

    def claim_conclusion(self) -> AdSlotRecord | None:
        with self.store.transaction():
            with self.store.connection.cursor() as cursor:
                cursor.execute(
                    """SELECT batch_id,position FROM commander_ad_slots
                       WHERE status='conclusion_pending' OR
                         (status='concluding' AND locked_at < clock_timestamp()-interval '10 minutes')
                       ORDER BY updated_at FOR UPDATE SKIP LOCKED LIMIT 1"""
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                cursor.execute(
                    """UPDATE commander_ad_slots SET status='concluding',locked_at=clock_timestamp(),
                       attempts=attempts+1,last_error=NULL,updated_at=clock_timestamp()
                       WHERE batch_id=%s AND position=%s""",
                    (row[0], row[1]),
                )
                batch_id, position = str(row[0]), int(row[1])
        return self.slot(batch_id, position)

    def finish_conclusion(self, creative_id: str, conclusion_id: str) -> AdSlotRecord | None:
        with self.store.transaction():
            with self.store.connection.cursor() as cursor:
                cursor.execute(
                    """SELECT batch_id,position FROM commander_ad_slots
                       WHERE creative_id=%s FOR UPDATE""",
                    (creative_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    raise KeyError(f"unknown ad creative: {creative_id}")
                batch_id, position = str(row[0]), int(row[1])
                cursor.execute(
                    """UPDATE commander_ad_slots SET conclusion_id=%s,status='completed',
                       locked_at=NULL,last_error=NULL,updated_at=clock_timestamp()
                       WHERE creative_id=%s AND conclusion_id IS NULL
                       RETURNING conclusion_id""",
                    (conclusion_id, creative_id),
                )
                if cursor.fetchone() is None:
                    raise ValueError("this Creative already has a context conclusion")
                if position == 10:
                    cursor.execute(
                        """UPDATE commander_ad_batches SET status='completed',current_position=NULL,
                           last_error=NULL,updated_at=clock_timestamp() WHERE campaign_id=%s""",
                        (batch_id,),
                    )
                    return None
                next_position = position + 1
                cursor.execute(
                    """UPDATE commander_ad_slots SET status='delivered',updated_at=clock_timestamp()
                       WHERE batch_id=%s AND position=%s""",
                    (batch_id, next_position),
                )
                cursor.execute(
                    """UPDATE commander_ad_batches SET status='awaiting_owner',current_position=%s,
                       updated_at=clock_timestamp() WHERE campaign_id=%s""",
                    (next_position, batch_id),
                )
        return self.slot(batch_id, next_position)

    def continue_batch(self, batch_id: str) -> None:
        failed = [slot for slot in self.slots(batch_id) if slot.status == "failed"]
        if len(failed) != 1:
            raise ValueError("ad batch has no single failed step to continue")
        slot = failed[0]
        if slot.feedback_id:
            slot_status, batch_status = "conclusion_pending", "concluding"
        else:
            slot_status, batch_status = ("spec_ready" if slot.spec else "pending"), "queued"
        with self.store.transaction():
            with self.store.connection.cursor() as cursor:
                cursor.execute(
                    """UPDATE commander_ad_slots SET status=%s,last_error=NULL,locked_at=NULL,
                       updated_at=clock_timestamp() WHERE batch_id=%s AND position=%s""",
                    (slot_status, batch_id, slot.position),
                )
                cursor.execute(
                    """UPDATE commander_ad_batches SET status=%s,last_error=NULL,locked_at=NULL,
                       updated_at=clock_timestamp() WHERE campaign_id=%s""",
                    (batch_status, batch_id),
                )

    def record_execution(
        self,
        *,
        batch_id: str,
        position: int,
        phase: str,
        attempt: int,
        status: str,
        model: str,
        request_digest: str,
        response: Mapping[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        from .ids import new_uuid7

        self._execute(
            """INSERT INTO commander_ad_executions
               (id,batch_id,position,phase,attempt,status,model_name,request_digest,
                response,error_text,completed_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,
                       CASE WHEN %s='running' THEN NULL ELSE clock_timestamp() END)""",
            (
                new_uuid7(), batch_id, position, phase, attempt, status, model,
                request_digest, None if response is None else json.dumps(dict(response)),
                None if error is None else error[:500], status,
            ),
        )

    def metric_import_exists(self, source_system: str, import_id: str) -> bool:
        return bool(self._rows(
            "SELECT 1 FROM commander_ad_metric_imports WHERE source_system=%s AND import_id=%s",
            (source_system, import_id),
        ))

    def record_metric_import(
        self,
        *,
        source_id: str,
        batch_id: str,
        source_system: str,
        import_id: str,
        captured_at: datetime,
        attribution_window: str,
    ) -> None:
        self._execute(
            """INSERT INTO commander_ad_metric_imports
               (source_id,batch_id,source_system,import_id,captured_at,attribution_window)
               VALUES (%s,%s,%s,%s,%s,%s)""",
            (source_id, batch_id, source_system, import_id, captured_at, attribution_window),
        )

    def _execute(self, sql: str, params: tuple[Any, ...]) -> None:
        with self.store.connection.cursor() as cursor:
            cursor.execute(sql, params)
        if self.store._transaction_depth == 0:
            self.store.connection.commit()

    def _rows(self, sql: str, params: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
        with self.store.connection.cursor() as cursor:
            cursor.execute(sql, params)
            return list(cursor.fetchall())

    @staticmethod
    def _slot_select() -> str:
        return (
            "SELECT batch_id,position,context_code,context_version,context_name,context_prompt,"
            "status,spec,hypothesis_id,creative_id,artifact_id,visual_path,final_path,"
            "predicted_ctr,rating,owner_comment,feedback_id,conclusion_id,last_error "
            "FROM commander_ad_slots"
        )

    @staticmethod
    def _slot(row: tuple[Any, ...]) -> AdSlotRecord:
        raw_spec = row[7]
        if isinstance(raw_spec, str):
            raw_spec = json.loads(raw_spec)
        spec = None if raw_spec is None else AdCreativeSpec.from_mapping(dict(raw_spec))
        return AdSlotRecord(
            batch_id=str(row[0]),
            position=int(row[1]),
            context=AdContextSnapshot(str(row[2]), int(row[3]), str(row[4]), str(row[5])),
            status=str(row[6]),
            spec=spec,
            hypothesis_id=None if row[8] is None else str(row[8]),
            creative_id=None if row[9] is None else str(row[9]),
            artifact_id=None if row[10] is None else str(row[10]),
            visual_path=None if row[11] is None else str(row[11]),
            final_path=None if row[12] is None else str(row[12]),
            predicted_ctr=None if row[13] is None else float(row[13]),
            rating=None if row[14] is None else int(row[14]),
            owner_comment="" if row[15] is None else str(row[15]),
            feedback_id=None if row[16] is None else str(row[16]),
            conclusion_id=None if row[17] is None else str(row[17]),
            last_error=None if row[18] is None else str(row[18]),
        )


class MemoryAdWorkflowRepository:
    """Deterministic workflow projection used by unit tests."""

    DEFAULT_CONTEXTS = (
        ("A01", "Pain and urgency"), ("A02", "Desired outcome"),
        ("A03", "Contrarian reframe"), ("A04", "Mechanism"),
        ("A05", "Concrete use case"), ("A06", "Status quo comparison"),
        ("A07", "Identity and emotion"), ("A08", "Credibility and proof"),
        ("A09", "Pattern interrupt"), ("A10", "Direct-response CTA"),
    )

    def __init__(self) -> None:
        self._contexts = {
            code: {"code": code, "name": name, "prompt": name, "active": True,
                   "sort_order": index, "version": 1}
            for index, (code, name) in enumerate(self.DEFAULT_CONTEXTS, 1)
        }
        self._history = {code: [dict(value)] for code, value in self._contexts.items()}
        self._batches: dict[str, AdBatchRecord] = {}
        self._keys: dict[str, str] = {}
        self._slots: dict[tuple[str, int], AdSlotRecord] = {}
        self.executions: list[Mapping[str, Any]] = []
        self.imports: set[tuple[str, str]] = set()
        self.reviews: list[Mapping[str, Any]] = []

    def active_contexts(self) -> tuple[AdContextSnapshot, ...]:
        values = [v for v in self._contexts.values() if v["active"]]
        values.sort(key=lambda v: v["sort_order"])
        return tuple(AdContextSnapshot(v["code"], v["version"], v["name"], v["prompt"]) for v in values)

    def contexts(self) -> tuple[Mapping[str, Any], ...]:
        return tuple(dict(v) for v in sorted(self._contexts.values(), key=lambda x: x["sort_order"]))

    def context(self, code: str) -> Mapping[str, Any]:
        try:
            return dict(self._contexts[code.upper()])
        except KeyError as error:
            raise KeyError(f"unknown ad context: {code}") from error

    def context_history(self, code: str) -> tuple[Mapping[str, Any], ...]:
        return tuple(dict(v) for v in self._history[code.upper()])

    def revise_context(self, code: str, *, name: str, prompt: str, actor: str, note: str) -> int:
        value = self._contexts[code.upper()]
        value.update(name=name, prompt=prompt, version=value["version"] + 1)
        self._history[code.upper()].append({**value, "changed_by": actor, "change_note": note})
        return int(value["version"])

    def set_context_active(self, code: str, active: bool) -> None:
        self._contexts[code.upper()]["active"] = active

    def idempotent_batch(self, key: str) -> str | None:
        return self._keys.get(key)

    def create_batch(self, batch: AdBatchRecord, key: str, contexts: tuple[AdContextSnapshot, ...]) -> None:
        if len(contexts) != 10:
            raise ValueError("ad generation requires exactly 10 active contexts")
        self._batches[batch.campaign_id] = batch
        self._keys[key] = batch.campaign_id
        for position, context in enumerate(contexts, 1):
            self._slots[(batch.campaign_id, position)] = AdSlotRecord(
                batch.campaign_id, position, context, "pending"
            )

    def batch(self, batch_id: str) -> AdBatchRecord:
        try:
            return self._batches[batch_id]
        except KeyError as error:
            raise KeyError(f"unknown ad batch: {batch_id}") from error

    def latest_batch(self, chat_id: int) -> AdBatchRecord:
        values = [item for item in self._batches.values() if item.chat_id == chat_id]
        if not values:
            raise KeyError("this chat has no ad batches")
        return values[-1]

    def slots(self, batch_id: str) -> tuple[AdSlotRecord, ...]:
        return tuple(self._slots[(batch_id, pos)] for pos in range(1, 11))

    def slot(self, batch_id: str, position: int) -> AdSlotRecord:
        return self._slots[(batch_id, position)]

    def slot_by_creative(self, creative_id: str) -> AdSlotRecord:
        try:
            return next(slot for slot in self._slots.values() if slot.creative_id == creative_id)
        except StopIteration as error:
            raise KeyError(f"creative is not part of an ad batch: {creative_id}") from error

    def claim_generation(self) -> AdBatchRecord | None:
        batch = next((b for b in self._batches.values() if b.status == "queued"), None)
        if batch is None:
            return None
        return self._replace_batch(batch, status="generating")

    def save_spec(self, batch_id: str, position: int, spec: AdCreativeSpec) -> None:
        self._replace_slot(self.slot(batch_id, position), spec=spec, status="spec_ready")

    def save_generated(self, batch_id: str, position: int, **values: Any) -> None:
        slot = self.slot(batch_id, position)
        if slot.creative_id is not None:
            raise ValueError("ad slot already has a generated Creative")
        self._replace_slot(slot, status="generated", **values)

    def finish_generation(self, batch_id: str) -> None:
        if sum(s.status == "generated" for s in self.slots(batch_id)) != 10:
            raise RuntimeError("ad review requires exactly 10 generated images")
        self._replace_batch(self.batch(batch_id), status="review_ready")

    def fail(self, batch_id: str, position: int, error: str) -> None:
        self._replace_slot(self.slot(batch_id, position), status="failed", last_error=error)
        self._replace_batch(self.batch(batch_id), status="failed", last_error=error)

    def activate_review(self, chat_id: int) -> AdSlotRecord | None:
        if any(b.chat_id == chat_id and b.status in {"awaiting_owner", "concluding"} for b in self._batches.values()):
            return None
        batch = next((b for b in self._batches.values() if b.chat_id == chat_id and b.status == "review_ready"), None)
        if batch is None:
            return None
        self._replace_batch(batch, status="awaiting_owner", current_position=1)
        return self._replace_slot(self.slot(batch.campaign_id, 1), status="delivered")

    def save_estimate(self, creative_id: str, *, predicted_ctr: float, rating: int, comment: str, feedback_id: str) -> AdSlotRecord:
        slot = self.slot_by_creative(creative_id)
        batch = self.batch(slot.batch_id)
        if batch.status != "awaiting_owner" or batch.current_position != slot.position:
            raise ValueError("estimate must reply to the currently active ad image")
        updated = self._replace_slot(slot, predicted_ctr=predicted_ctr, rating=rating,
                                     owner_comment=comment, feedback_id=feedback_id,
                                     status="conclusion_pending")
        self._replace_batch(batch, status="concluding")
        return updated

    def save_review_projection(self, **values: Any) -> None:
        self.reviews.append(dict(values))

    def claim_conclusion(self) -> AdSlotRecord | None:
        slot = next((s for s in self._slots.values() if s.status == "conclusion_pending"), None)
        return None if slot is None else self._replace_slot(slot, status="concluding")

    def finish_conclusion(self, creative_id: str, conclusion_id: str) -> AdSlotRecord | None:
        slot = self.slot_by_creative(creative_id)
        if slot.conclusion_id is not None:
            raise ValueError("this Creative already has a context conclusion")
        self._replace_slot(slot, status="completed", conclusion_id=conclusion_id)
        batch = self.batch(slot.batch_id)
        if slot.position == 10:
            self._replace_batch(batch, status="completed", current_position=None)
            return None
        next_slot = self._replace_slot(self.slot(slot.batch_id, slot.position + 1), status="delivered")
        self._replace_batch(batch, status="awaiting_owner", current_position=next_slot.position)
        return next_slot

    def continue_batch(self, batch_id: str) -> None:
        slot = next(s for s in self.slots(batch_id) if s.status == "failed")
        if slot.feedback_id:
            self._replace_slot(slot, status="conclusion_pending", last_error=None)
            self._replace_batch(self.batch(batch_id), status="concluding", last_error=None)
        else:
            self._replace_slot(slot, status="spec_ready" if slot.spec else "pending", last_error=None)
            self._replace_batch(self.batch(batch_id), status="queued", last_error=None)

    def record_execution(self, **values: Any) -> None:
        self.executions.append(dict(values))

    def metric_import_exists(self, source_system: str, import_id: str) -> bool:
        return (source_system, import_id) in self.imports

    def record_metric_import(self, **values: Any) -> None:
        self.imports.add((str(values["source_system"]), str(values["import_id"])))

    def _replace_batch(self, batch: AdBatchRecord, **changes: Any) -> AdBatchRecord:
        values = {name: getattr(batch, name) for name in batch.__dataclass_fields__}
        values.update(changes)
        result = AdBatchRecord(**values)
        self._batches[batch.campaign_id] = result
        return result

    def _replace_slot(self, slot: AdSlotRecord, **changes: Any) -> AdSlotRecord:
        values = {name: getattr(slot, name) for name in slot.__dataclass_fields__}
        values.update(changes)
        result = AdSlotRecord(**values)
        self._slots[(slot.batch_id, slot.position)] = result
        return result
