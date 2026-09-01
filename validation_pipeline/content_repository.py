"""PostgreSQL authority for owner-reviewed Creative generation."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
from typing import Any, Callable, Mapping, Sequence
from uuid import UUID
import zipfile

from commander.ids import new_uuid7

from .content import (
    CandidateV2, ContextBundleV1, OUTPUT_PROFILES, SLIDER_NAMES, StrategyTemplate,
    sha256_json,
)
from .review_notifications import NotificationAttempt


def _uuid(value: str) -> UUID:
    parsed = UUID(str(value))
    if parsed.version != 7:
        raise ValueError("Result entity IDs must be UUIDv7")
    return parsed


class ContentResultRepository:
    def __init__(self, authority: Any) -> None:
        self.authority = authority

    @staticmethod
    def _run_select() -> str:
        return """SELECT run.entity_id,run.request_id,run.parent_run_id,run.project_id,
                         run.brief_id,run.task_source_id,run.brand_kit_id,run.output_profile,
                         run.task,run.context_bundle,run.context_sha256,run.generation_kind,
                         run.reserved_creative_ids,run.generated_creative_ids,
                         run.review_creative_ids,run.carried_review_creative_ids,
                         run.approved_creative_id,run.tuned_creative_id,run.tuned_strategy_id,
                         run.status,run.current_stage,run.budget_state,
                         run.generator_skill_sha256,run.corpus_sha256,run.learning_snapshot_id,
                         run.notification_state,run.notification_receipt_id,
                         run.error_code,run.error_message,run.requested_by,run.deadline_at,
                         run.created_at,run.updated_at,run.completed_at,
                         (SELECT count(*) FROM content_creatives creative
                           WHERE creative.run_id=run.entity_id)
                    FROM content_generation_runs run"""

    @staticmethod
    def _run_row(row: Sequence[Any]) -> dict[str, Any]:
        stage_progress = {
            "queued": 0, "generating_creatives": min(90, int(row[34]) * 18),
            "awaiting_review": 100, "approved": 100, "superseded": 100, "failed": 100,
        }
        output_profile = str(row[7])
        return {
            "run_id": str(row[0]), "request_id": str(row[1]),
            "parent_run_id": None if row[2] is None else str(row[2]),
            "project_id": str(row[3]), "brief_id": str(row[4]),
            "task_source_id": str(row[5]), "brand_kit_id": str(row[6]),
            "output_profile": output_profile,
            "platform": "tiktok" if output_profile == "tiktok_photo_post_v1" else "instagram",
            "task": row[8], "context_bundle": dict(row[9]), "context_sha256": row[10],
            "generation_kind": row[11],
            "reserved_creative_ids": [str(item) for item in row[12]],
            "generated_creative_ids": [str(item) for item in row[13]],
            "review_creative_ids": [str(item) for item in row[14]],
            "carried_review_creative_ids": [str(item) for item in row[15]],
            "approved_creative_id": None if row[16] is None else str(row[16]),
            "tuned_creative_id": None if row[17] is None else str(row[17]),
            "tuned_strategy_id": row[18], "status": row[19], "current_stage": row[20],
            "budget_state": dict(row[21]), "generator_skill_sha256": row[22],
            "corpus_sha256": row[23], "learning_snapshot_id": str(row[24]),
            "notification_state": row[25],
            "notification_receipt_id": None if row[26] is None else str(row[26]),
            "error_code": row[27], "error_message": row[28], "requested_by": row[29],
            "deadline_at": row[30].isoformat(), "created_at": row[31].isoformat(),
            "updated_at": row[32].isoformat(),
            "completed_at": None if row[33] is None else row[33].isoformat(),
            "creative_count": int(row[34]), "progress_percent": stage_progress[row[20]],
            "maximum_minutes": 45,
        }

    def get_run(self, run_id: str) -> dict[str, Any]:
        with self.authority.connection() as connection:
            row = connection.execute(
                self._run_select() + " WHERE run.entity_id=%s", (UUID(run_id),),
            ).fetchone()
        if row is None:
            raise KeyError(run_id)
        return self._run_row(row)

    def list_runs(self, *, project_id: str, limit: int = 50) -> list[dict[str, Any]]:
        with self.authority.connection() as connection:
            rows = connection.execute(
                self._run_select()
                + " WHERE run.project_id=%s ORDER BY run.created_at DESC LIMIT %s",
                (UUID(project_id), min(100, max(1, limit))),
            ).fetchall()
        return [self._run_row(row) for row in rows]

    def _active_learning_rules(self, connection: Any, project_id: UUID) -> list[dict[str, Any]]:
        rows = connection.execute(
            """SELECT rule.entity_id,rule.rule_type,rule.strategy_id,rule.output_profile,
                      rule.instruction,rule.slider_values,rule.layout_patch,rule.exclusions,
                      rule.rule_sha256,
                      rule.supersedes_rule_id
                 FROM content_learning_rules rule
                WHERE rule.project_id=%s
                  AND NOT EXISTS (
                    SELECT 1 FROM content_learning_rules newer
                     WHERE newer.supersedes_rule_id=rule.entity_id
                  )
                ORDER BY rule.created_at,rule.entity_id""",
            (project_id,),
        ).fetchall()
        return [{
            "rule_id": str(row[0]), "rule_type": row[1], "strategy_id": row[2],
            "output_profile": row[3], "instruction": row[4],
            "slider_values": dict(row[5]), "layout_patch": list(row[6]),
            "exclusions": dict(row[7]), "sha256": row[8],
            "supersedes_rule_id": None if row[9] is None else str(row[9]),
        } for row in rows]

    def _snapshot_learning(self, connection: Any, project_id: UUID) -> tuple[UUID, dict[str, Any]]:
        from psycopg.types.json import Jsonb

        rules = self._active_learning_rules(connection, project_id)
        snapshot_id = UUID(new_uuid7())
        document = {
            "schema": "ptw.owner-learning-snapshot.v1", "project_id": str(project_id),
            "rules": rules,
        }
        connection.execute(
            "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'content_learning_snapshot',%s)",
            (snapshot_id, Jsonb({"schema_version": 1})),
        )
        connection.execute(
            """INSERT INTO content_learning_snapshots(entity_id,project_id,document,document_sha256)
               VALUES(%s,%s,%s,%s)""",
            (snapshot_id, project_id, Jsonb(document), sha256_json(document)),
        )
        return snapshot_id, document

    def create_run(
        self, *, request_id: str, brief_id: str, task: str, output_profile: str,
        context: ContextBundleV1, templates: Sequence[StrategyTemplate], requested_by: str,
        parent_run_id: str | None = None,
        revision_feedback: Mapping[str, Any] | None = None,
    ) -> tuple[dict[str, Any], bool]:
        from psycopg.types.json import Jsonb

        request_uuid = UUID(request_id)
        normalized_task = task.strip()
        if output_profile not in OUTPUT_PROFILES or not 1 <= len(normalized_task) <= 4_000:
            raise ValueError("Result run requires a supported profile and a 1-4000 character task")
        brief = self.authority.get_brief(brief_id)
        if not brief["approved"] or brief["status"] != "completed":
            raise ValueError("Result generation requires an approved completed Product Brief")
        if len(templates) != 5 or len({item.template_id for item in templates}) != 5:
            raise ValueError("Result generation requires five distinct active templates")
        kits = self.authority.list_project_brand_kits(brief["project_id"])
        if not kits:
            raise ValueError("Result generation requires a Project brand kit")
        with self.authority.connection() as connection:
            existing = connection.execute(
                self._run_select() + " WHERE run.request_id=%s", (request_uuid,),
            ).fetchone()
            if existing is not None:
                value = self._run_row(existing)
                if (
                    value["brief_id"] != brief_id or value["task"] != normalized_task
                    or value["output_profile"] != output_profile
                ):
                    raise ValueError("request_id was already used with different Result input")
                return value, False
            snapshot_id, learning = self._snapshot_learning(connection, UUID(brief["project_id"]))
            context_document = deepcopy(dict(context.document))
            context_document["owner_learning"] = learning
            for value in context_document["candidate_contexts"].values():
                value["owner_learning"] = learning
            context_sha256 = sha256_json(context_document)
            run_id, task_source_id = UUID(new_uuid7()), UUID(new_uuid7())
            creative_ids = [UUID(new_uuid7()) for _ in range(5)]
            task_digest = hashlib.sha256(normalized_task.encode()).hexdigest()
            for entity_id, kind, attributes in (
                (run_id, "content_run", {"schema_version": 2}),
                (task_source_id, "source", {"source_type": "owner_task"}),
                *[(item, "content_creative", {"reserved": True}) for item in creative_ids],
            ):
                connection.execute(
                    "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,%s,%s)",
                    (entity_id, kind, Jsonb(attributes)),
                )
            connection.execute(
                """INSERT INTO commander_sources(
                       entity_id,source_type,title,provider,external_id,content,content_sha256,metadata
                   ) VALUES(%s,'owner_task','Owner Result task','owner',%s,%s,%s,%s)""",
                (task_source_id, request_uuid.hex, normalized_task, task_digest, Jsonb({})),
            )
            versions = context_document["versions"]
            connection.execute(
                """INSERT INTO content_generation_runs(
                       entity_id,request_id,parent_run_id,project_id,brief_id,task_source_id,
                       brand_kit_id,output_profile,task,context_bundle,context_sha256,
                       generation_kind,reserved_creative_ids,status,current_stage,budget_state,
                       generator_skill_sha256,corpus_sha256,learning_snapshot_id,requested_by,
                       deadline_at
                   ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'initial',%s,
                            'queued','queued',%s,%s,%s,%s,%s,clock_timestamp()+interval '45 minutes')""",
                (
                    run_id, request_uuid, None if parent_run_id is None else UUID(parent_run_id),
                    UUID(brief["project_id"]), UUID(brief_id), task_source_id,
                    UUID(kits[0]["brand_kit_id"]), output_profile, normalized_task,
                    Jsonb(context_document), context_sha256, creative_ids,
                    Jsonb({"generation_remaining": 5, "graphic_generation_remaining": 1}),
                    versions["generator_skill_sha256"], versions["corpus_sha256"], snapshot_id,
                    requested_by,
                ),
            )
            for source, relation, target, attributes in (
                (run_id, "derived_from", UUID(brief_id), {"input": "product_brief"}),
                (run_id, "derived_from", snapshot_id, {"input": "owner_learning_snapshot"}),
                (UUID(brief["project_id"]), "contains", run_id, {"member": "content_run"}),
                *[(run_id, "contains", item, {"member": "reserved_creative"}) for item in creative_ids],
            ):
                connection.execute(
                    """INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes)
                       VALUES(%s,%s,%s,%s,%s)""",
                    (UUID(new_uuid7()), source, relation, target, Jsonb(attributes)),
                )
        return self.get_run(str(run_id)), True

    def set_stage(self, run_id: str, stage: str, *, status: str = "generating") -> dict[str, Any]:
        if stage not in {"queued", "generating_creatives", "awaiting_review", "approved", "superseded", "failed"}:
            raise ValueError("unknown Creative generation stage")
        with self.authority.connection() as connection:
            changed = connection.execute(
                """UPDATE content_generation_runs SET status=%s,current_stage=%s,
                          updated_at=clock_timestamp() WHERE entity_id=%s
                          AND status IN ('queued','generating')""",
                (status, stage, UUID(run_id)),
            ).rowcount
        if changed != 1 and self.get_run(run_id)["current_stage"] != stage:
            raise ValueError("run stage cannot move after owner review begins")
        return self.get_run(run_id)

    def consume_budget(self, run_id: str, key: str, amount: int = 1) -> dict[str, Any]:
        from psycopg.types.json import Jsonb

        if key not in {"generation_remaining", "graphic_generation_remaining"} or amount < 1:
            raise ValueError("unknown Result budget")
        with self.authority.connection() as connection:
            row = connection.execute(
                "SELECT budget_state FROM content_generation_runs WHERE entity_id=%s FOR UPDATE",
                (UUID(run_id),),
            ).fetchone()
            if row is None:
                raise KeyError(run_id)
            value = dict(row[0])
            if int(value.get(key, 0)) < amount:
                raise ValueError(f"Result run budget exhausted: {key}")
            value[key] = int(value[key]) - amount
            connection.execute(
                "UPDATE content_generation_runs SET budget_state=%s,updated_at=clock_timestamp() WHERE entity_id=%s",
                (Jsonb(value), UUID(run_id)),
            )
        return value

    def checkpoint(
        self, run_id: str, *, stage: str, target_id: str | None,
        payload: Mapping[str, Any],
    ) -> None:
        from psycopg.types.json import Jsonb

        with self.authority.connection() as connection:
            sequence = int(connection.execute(
                "SELECT COALESCE(max(sequence),0)+1 FROM content_generation_checkpoints WHERE run_id=%s",
                (UUID(run_id),),
            ).fetchone()[0])
            connection.execute(
                """INSERT INTO content_generation_checkpoints(
                       id,run_id,sequence,stage,target_id,payload,payload_sha256
                   ) VALUES(%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT(run_id,stage,target_id) DO NOTHING""",
                (
                    UUID(new_uuid7()), UUID(run_id), sequence, stage,
                    None if target_id is None else UUID(target_id),
                    Jsonb(dict(payload)), sha256_json(payload),
                ),
            )

    def start_invocation(
        self, target_id: str, *, mode: str, idempotency_key: str,
        request: Mapping[str, Any],
    ) -> tuple[str, str]:
        from psycopg.types.json import Jsonb

        if mode != "content_candidate_generation":
            raise ValueError("unsupported Result provider invocation mode")
        target_uuid, attempt_id, invocation_id = UUID(target_id), UUID(new_uuid7()), UUID(new_uuid7())
        with self.authority.connection() as connection:
            number = int(connection.execute(
                "SELECT COALESCE(max(attempt_number),0)+1 FROM validation_generation_attempts WHERE target_id=%s",
                (target_uuid,),
            ).fetchone()[0])
            connection.execute(
                """INSERT INTO validation_generation_attempts(id,target_id,stage,attempt_number,status)
                   VALUES(%s,%s,%s,%s,'started')""",
                (attempt_id, target_uuid, mode, number),
            )
            connection.execute(
                """INSERT INTO validation_provider_invocations(
                       id,target_id,attempt_id,provider,mode,idempotency_key,request_sha256,status,invocation
                   ) VALUES(%s,%s,%s,'structured_bridge',%s,%s,%s,'submitted',%s)""",
                (
                    invocation_id, target_uuid, attempt_id, mode, idempotency_key,
                    sha256_json(request), Jsonb({"logical_attempt": number}),
                ),
            )
        return str(attempt_id), str(invocation_id)

    def finish_invocation(
        self, attempt_id: str, invocation_id: str, *, response: Mapping[str, Any] | None,
        provenance: Mapping[str, Any], error: Exception | None = None,
    ) -> None:
        from psycopg.types.json import Jsonb

        with self.authority.connection() as connection:
            if error is None and response is not None:
                connection.execute(
                    """UPDATE validation_provider_invocations SET status='completed',response_sha256=%s,
                              invocation=%s,completed_at=clock_timestamp() WHERE id=%s""",
                    (sha256_json(response), Jsonb(dict(provenance)), UUID(invocation_id)),
                )
                connection.execute(
                    "UPDATE validation_generation_attempts SET status='completed',completed_at=clock_timestamp() WHERE id=%s",
                    (UUID(attempt_id),),
                )
            else:
                connection.execute(
                    """UPDATE validation_provider_invocations SET status='failed',invocation=%s,
                              completed_at=clock_timestamp() WHERE id=%s""",
                    (Jsonb({**dict(provenance), "error": type(error).__name__ if error else "unknown"}), UUID(invocation_id)),
                )
                connection.execute(
                    """UPDATE validation_generation_attempts SET status='failed',error_code=%s,
                              error_message=%s,completed_at=clock_timestamp() WHERE id=%s""",
                    (type(error).__name__ if error else "RuntimeError", str(error)[:1000], UUID(attempt_id)),
                )

    @staticmethod
    def _creative_select() -> str:
        return """SELECT creative.entity_id,creative.run_id,creative.slot,creative.round,
                         creative.generation_kind,creative.parent_creative_id,creative.template_id,
                         creative.template_version,creative.template_sha256,creative.hook_pressure,
                         creative.emotional_intensity,creative.conceptual_novelty,
                         creative.information_density,creative.visual_complexity,creative.parameters,
                         creative.config_sha256,creative.document,creative.document_sha256,
                         creative.recipe_id,creative.render_id,creative.provider_provenance,
                         creative.provider_invocation_id,creative.media_identity_sha256,
                         creative.response_sha256,creative.retry_count,creative.created_at
                    FROM content_creatives creative"""

    @staticmethod
    def _creative_row(row: Sequence[Any]) -> dict[str, Any]:
        return {
            "creative_id": str(row[0]), "run_id": str(row[1]), "slot": row[2],
            "round": int(row[3]), "generation_kind": row[4],
            "parent_creative_id": None if row[5] is None else str(row[5]),
            "template_id": row[6], "template_version": int(row[7]), "template_sha256": row[8],
            "parameters": {
                "hook_pressure": int(row[9]), "emotional_intensity": int(row[10]),
                "conceptual_novelty": int(row[11]), "information_density": int(row[12]),
                "visual_complexity": int(row[13]),
            },
            "parameter_document": dict(row[14]), "config_sha256": row[15],
            "document": dict(row[16]), "document_sha256": row[17],
            "recipe_id": None if row[18] is None else str(row[18]),
            "render_id": None if row[19] is None else str(row[19]),
            "provider_provenance": dict(row[20]), "provider_invocation_id": str(row[21]),
            "media_identity_sha256": row[22], "response_sha256": row[23],
            "retry_count": int(row[24]), "created_at": row[25].isoformat(),
        }

    def get_creative(self, creative_id: str) -> dict[str, Any]:
        with self.authority.connection() as connection:
            row = connection.execute(
                self._creative_select() + " WHERE creative.entity_id=%s", (UUID(creative_id),),
            ).fetchone()
        if row is None:
            raise KeyError(creative_id)
        value = self._creative_row(row)
        value["elements"] = self.creative_elements(creative_id)
        return value

    def list_creatives(self, run_id: str) -> list[dict[str, Any]]:
        with self.authority.connection() as connection:
            rows = connection.execute(
                self._creative_select() + " WHERE creative.run_id=%s ORDER BY creative.created_at",
                (UUID(run_id),),
            ).fetchall()
        values = [self._creative_row(row) for row in rows]
        for item in values:
            item["elements"] = self.creative_elements(item["creative_id"])
        return values

    def creative_elements(self, creative_id: str) -> list[dict[str, Any]]:
        with self.authority.connection() as connection:
            rows = connection.execute(
                """SELECT element.entity_id,element.display_alias,link.slot,link.ordinal,
                          element.element_type,element.payload,element.payload_sha256,
                          element.born_in_creative_id,link.reuse_mode
                     FROM content_creative_elements link
                     JOIN content_elements element ON element.entity_id=link.element_id
                    WHERE link.creative_id=%s ORDER BY link.ordinal,link.slot""",
                (UUID(creative_id),),
            ).fetchall()
        return [{
            "element_id": str(row[0]), "display_alias": row[1], "slot": row[2],
            "ordinal": int(row[3]), "element_type": row[4], "payload": dict(row[5]),
            "payload_sha256": row[6], "born_in_creative_id": str(row[7]),
            "reuse_mode": row[8],
        } for row in rows]

    def persist_creative(
        self, *, run_id: str, creative_id: str, slot: str, round_number: int,
        generation_kind: str, parent_creative_id: str | None, template: StrategyTemplate,
        parameters: Mapping[str, int], candidate: CandidateV2,
        elements: Sequence[Mapping[str, Any]], materialized: Mapping[str, Any],
        provider_provenance: Mapping[str, Any], provider_invocation_id: str,
    ) -> dict[str, Any]:
        from psycopg.types.json import Jsonb

        creative_uuid = _uuid(creative_id)
        if set(parameters) != set(SLIDER_NAMES):
            raise ValueError("Creative parameters must retain all five normalized sliders")
        recipe, render, preview = (
            materialized.get("recipe"), materialized.get("render"), materialized.get("preview"),
        )
        if (recipe is None) != (render is None) or (render is None) == (preview is None):
            raise ValueError("Creative requires exactly one materialized Studio render or text preview")
        media_source = materialized.get("media_source")
        media_identity_sha256 = None if media_source is None else sha256_json({
            "source_asset_id": str(media_source["source_asset_id"]),
            "bytes_sha256": str(media_source["bytes_sha256"]),
            "provider": str(media_source["provider"]),
            "external_id": str(media_source["external_id"]),
        })
        with self.authority.connection() as connection:
            reserved = connection.execute(
                "SELECT 1 FROM commander_entities WHERE id=%s AND kind='content_creative'",
                (creative_uuid,),
            ).fetchone()
            if reserved is None:
                raise ValueError("Creative UUID was not reserved by the server")
            connection.execute(
                """INSERT INTO content_creatives(
                       entity_id,run_id,slot,round,generation_kind,parent_creative_id,
                       template_id,template_version,template_sha256,hook_pressure,
                       emotional_intensity,conceptual_novelty,information_density,visual_complexity,
                       parameters,config_sha256,document,document_sha256,recipe_id,render_id,
                       provider_provenance,provider_invocation_id,media_identity_sha256,
                       response_sha256,retry_count
                   ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    creative_uuid, UUID(run_id), slot, round_number, generation_kind,
                    None if parent_creative_id is None else UUID(parent_creative_id),
                    template.template_id, template.version, template.digest,
                    *(int(parameters[name]) for name in SLIDER_NAMES),
                    Jsonb(dict(parameters)), sha256_json(parameters), Jsonb(dict(candidate.value)),
                    candidate.digest, None if recipe is None else UUID(recipe["recipe_id"]),
                    None if render is None else UUID(render["render_id"]),
                    Jsonb(dict(provider_provenance)), UUID(provider_invocation_id),
                    media_identity_sha256, candidate.digest,
                    int(provider_provenance.get("bridge_attempt", 1)) - 1,
                ),
            )
            for raw in elements:
                element_id = _uuid(str(raw["element_id"]))
                payload = dict(raw["payload"])
                connection.execute(
                    "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'content_element',%s)",
                    (element_id, Jsonb({"slot": raw["slot"], "schema_version": 1})),
                )
                connection.execute(
                    """INSERT INTO content_elements(
                           entity_id,run_id,display_alias,slot,element_type,ordinal,payload,
                           payload_sha256,born_in_creative_id
                       ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        element_id, UUID(run_id), raw["display_alias"], raw["slot"],
                        raw["element_type"], int(raw["ordinal"]), Jsonb(payload),
                        sha256_json(payload), creative_uuid,
                    ),
                )
                connection.execute(
                    """INSERT INTO content_creative_elements(
                           id,creative_id,element_id,slot,ordinal,reuse_mode
                       ) VALUES(%s,%s,%s,%s,%s,%s)""",
                    (
                        UUID(new_uuid7()), creative_uuid, element_id, raw["slot"],
                        int(raw["ordinal"]), raw["reuse_mode"],
                    ),
                )
                connection.execute(
                    """INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes)
                       VALUES(%s,%s,'contains',%s,%s)""",
                    (UUID(new_uuid7()), creative_uuid, element_id, Jsonb({"slot": raw["slot"]})),
                )
            if render is None:
                connection.execute(
                    """INSERT INTO content_creative_previews(
                           creative_id,mime_type,width,height,bytes,bytes_sha256,renderer_version
                       ) VALUES(%s,'image/jpeg',1080,1080,%s,%s,%s)""",
                    (creative_uuid, preview["bytes"], preview["sha256"], preview["renderer_version"]),
                )
            connection.execute(
                """UPDATE content_generation_runs
                      SET budget_state=jsonb_set(
                            budget_state,'{generation_remaining}',
                            to_jsonb((budget_state->>'generation_remaining')::int-1)
                          ),updated_at=clock_timestamp()
                    WHERE entity_id=%s""",
                (UUID(run_id),),
            )
        return self.get_creative(creative_id)

    def creative_preview(self, creative_id: str, *, expected_run_id: str | None = None) -> dict[str, Any]:
        creative = self.get_creative(creative_id)
        if expected_run_id is not None and not self._creative_visible_in_run(
            creative_id, creative["run_id"], expected_run_id,
        ):
            raise KeyError(creative_id)
        if creative["render_id"] is not None:
            return self.authority.render_asset(creative["render_id"])
        with self.authority.connection() as connection:
            row = connection.execute(
                """SELECT bytes,bytes_sha256,mime_type,width,height
                     FROM content_creative_previews WHERE creative_id=%s""",
                (UUID(creative_id),),
            ).fetchone()
        if row is None:
            raise KeyError(creative_id)
        return {
            "bytes": bytes(row[0]), "sha256": row[1], "mime_type": row[2],
            "width": int(row[3]), "height": int(row[4]),
        }

    def creative_preview_metadata(
        self, creative_id: str, *, expected_run_id: str | None = None,
    ) -> dict[str, Any]:
        creative = self.get_creative(creative_id)
        if expected_run_id is not None and not self._creative_visible_in_run(
            creative_id, creative["run_id"], expected_run_id,
        ):
            raise KeyError(creative_id)
        if creative["render_id"] is not None:
            render = self.authority.get_render(creative["render_id"])
            return {
                "sha256": render["bytes_sha256"], "mime_type": render["mime_type"],
                "width": render["width"], "height": render["height"],
            }
        with self.authority.connection() as connection:
            row = connection.execute(
                """SELECT bytes_sha256,mime_type,width,height
                     FROM content_creative_previews WHERE creative_id=%s""",
                (UUID(creative_id),),
            ).fetchone()
        if row is None:
            raise KeyError(creative_id)
        return {
            "sha256": row[0], "mime_type": row[1],
            "width": int(row[2]), "height": int(row[3]),
        }

    def _creative_visible_in_run(
        self, creative_id: str, creative_run_id: str, requested_run_id: str,
    ) -> bool:
        if creative_run_id == requested_run_id:
            return True
        run = self.get_run(requested_run_id)
        return creative_id in set(run.get("review_creative_ids") or [])

    def creative_export(self, run_id: str, creative_id: str) -> dict[str, Any]:
        run = self.get_run(run_id)
        if run["status"] != "approved" or run["approved_creative_id"] != creative_id:
            raise ValueError("only the approved Creative has an unlocked export package")
        creative = self.get_creative(creative_id)
        if creative_id not in set(run["review_creative_ids"]):
            raise KeyError(creative_id)
        asset = self.creative_preview(creative_id, expected_run_id=run_id)
        extension = "jpg" if asset["mime_type"] == "image/jpeg" else "png"
        manifest = {
            "schema": "ptw.approved-creative-export.v1",
            "run_id": run_id,
            "creative_id": creative_id,
            "project_id": run["project_id"],
            "brief_id": run["brief_id"],
            "platform": run["platform"],
            "document": creative["document"],
            "document_sha256": creative["document_sha256"],
            "asset": {
                "filename": f"post.{extension}", "mime_type": asset["mime_type"],
                "sha256": asset["sha256"], "width": asset["width"], "height": asset["height"],
            },
        }
        output = BytesIO()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for name, data in (
                (f"post.{extension}", asset["bytes"]),
                ("owner-review.json", json.dumps(
                    manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                ).encode("utf-8")),
            ):
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, data)
        data = output.getvalue()
        with self.authority.connection() as connection:
            from psycopg.types.json import Jsonb

            outcome_id = UUID(new_uuid7())
            connection.execute(
                "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'content_outcome',%s)",
                (outcome_id, Jsonb({"event_type": "downloaded"})),
            )
            connection.execute(
                """INSERT INTO content_generation_outcomes(
                       entity_id,run_id,creative_id,event_type,source_type,payload
                   ) VALUES(%s,%s,%s,'downloaded','owner',%s)""",
                (outcome_id, UUID(run_id), UUID(creative_id), Jsonb({"package_sha256": hashlib.sha256(data).hexdigest()})),
            )
        return {"bytes": data, "sha256": hashlib.sha256(data).hexdigest()}

    def mark_awaiting_review(self, run_id: str, creative_ids: Sequence[str]) -> dict[str, Any]:
        if len(creative_ids) not in {1, 5} or len(set(creative_ids)) != len(creative_ids):
            raise ValueError("generated Creative IDs do not match the run kind")
        run = self.get_run(run_id)
        if run["generation_kind"] == "tune":
            if len(creative_ids) != 1 or run["tuned_creative_id"] not in run["carried_review_creative_ids"]:
                raise ValueError("tune must generate one replacement for its selected slot")
            review_ids = [
                creative_ids[0] if item == run["tuned_creative_id"] else item
                for item in run["carried_review_creative_ids"]
            ]
        else:
            if len(creative_ids) != 5:
                raise ValueError("initial and regenerate-all runs require five Creatives")
            review_ids = list(creative_ids)
        with self.authority.connection() as connection:
            connection.execute(
                """UPDATE content_generation_runs SET generated_creative_ids=%s,
                          review_creative_ids=%s,status='awaiting_review',
                          current_stage='awaiting_review',completed_at=clock_timestamp(),
                          updated_at=clock_timestamp() WHERE entity_id=%s AND status='generating'""",
                ([UUID(item) for item in creative_ids], [UUID(item) for item in review_ids], UUID(run_id)),
            )
            if run["parent_run_id"] is not None:
                connection.execute(
                    """UPDATE content_generation_runs SET status='superseded',current_stage='superseded',
                              updated_at=clock_timestamp() WHERE entity_id=%s AND status='awaiting_review'""",
                    (UUID(run["parent_run_id"]),),
                )
                connection.execute(
                    """UPDATE content_review_actions SET status='completed',updated_at=clock_timestamp()
                         WHERE child_run_id=%s AND status='processing'""",
                    (UUID(run_id),),
                )
        return self.get_run(run_id)

    def get_review(self, run_id: str) -> dict[str, Any]:
        run = self.get_run(run_id)
        if run["status"] not in {"awaiting_review", "approved", "superseded"}:
            raise ValueError("run has no reviewable Creative set")
        with self.authority.connection() as connection:
            action_rows = connection.execute(
                """SELECT entity_id,request_id,action_type,status,selected_creative_id,comment,
                          child_run_id,created_at,updated_at
                     FROM content_review_actions WHERE run_id=%s ORDER BY created_at""",
                (UUID(run_id),),
            ).fetchall()
            receipt = None
            if run["notification_receipt_id"]:
                row = connection.execute(
                    """SELECT entity_id,status,attempt_count,provider_message_id,error_code,error_message,
                              created_at,updated_at FROM telegram_delivery_receipts WHERE entity_id=%s""",
                    (UUID(run["notification_receipt_id"]),),
                ).fetchone()
                if row:
                    receipt = {
                        "receipt_id": str(row[0]), "status": row[1], "attempt_count": int(row[2]),
                        "provider_message_id": row[3], "error_code": row[4], "error_message": row[5],
                        "created_at": row[6].isoformat(), "updated_at": row[7].isoformat(),
                    }
            rules = self._active_learning_rules(connection, UUID(run["project_id"]))
        actions = [{
            "action_id": str(row[0]), "request_id": str(row[1]), "action_type": row[2],
            "status": row[3], "creative_id": None if row[4] is None else str(row[4]),
            "comment": row[5], "child_run_id": None if row[6] is None else str(row[6]),
            "created_at": row[7].isoformat(), "updated_at": row[8].isoformat(),
        } for row in action_rows]
        creatives = []
        for creative_id in run["review_creative_ids"]:
            creative = self.get_creative(creative_id)
            preview = self.creative_preview_metadata(creative_id, expected_run_id=run_id)
            creatives.append({
                **creative,
                "preview": {
                    **preview,
                    "asset_url": f"/api/v1/content-runs/{run_id}/creatives/{creative_id}/asset",
                },
            })
        return {
            "schema": "ptw.owner-creative-review.v1", "run": run,
            "creatives": creatives,
            "owner_actions": actions, "notification": receipt, "applied_project_rules": rules,
        }

    def deliver_review_notification(
        self, run_id: str, *, notifier: Any, manual_retry: bool,
    ) -> dict[str, Any]:
        from psycopg.types.json import Jsonb

        run = self.get_run(run_id)
        if run["status"] != "awaiting_review":
            raise ValueError("review notification requires an awaiting-review run")
        with self.authority.connection() as connection:
            if run["notification_receipt_id"] is None:
                receipt_id = UUID(new_uuid7())
                connection.execute(
                    "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'telegram_delivery_receipt',%s)",
                    (receipt_id, Jsonb({"notification_type": "owner_review"})),
                )
                connection.execute(
                    """INSERT INTO telegram_delivery_receipts(entity_id,run_id,status)
                       VALUES(%s,%s,'pending')""",
                    (receipt_id, UUID(run_id)),
                )
                connection.execute(
                    """UPDATE content_generation_runs SET notification_state='pending',
                              notification_receipt_id=%s,updated_at=clock_timestamp()
                         WHERE entity_id=%s""",
                    (receipt_id, UUID(run_id)),
                )
                connection.execute(
                    """INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes)
                       VALUES(%s,%s,'contains',%s,%s)""",
                    (UUID(new_uuid7()), UUID(run_id), receipt_id, Jsonb({"member": "notification_receipt"})),
                )
            else:
                receipt_id = UUID(run["notification_receipt_id"])
            project = connection.execute(
                "SELECT name FROM validation_projects WHERE entity_id=%s", (UUID(run["project_id"]),),
            ).fetchone()
            current = connection.execute(
                "SELECT status,attempt_count FROM telegram_delivery_receipts WHERE entity_id=%s",
                (receipt_id,),
            ).fetchone()
        if current[0] == "delivered":
            return self.get_review(run_id)["notification"]
        event = {
            "schema": "ptw.owner-review-notification.v1", "notification_id": str(receipt_id),
            "run_id": run_id, "project_id": run["project_id"], "project_name": project[0],
            "platform": run["platform"], "creative_count": 5,
        }
        result: NotificationAttempt | None = None
        maximum_attempts = 1 if manual_retry else max(0, 3 - int(current[1]))
        for _ in range(maximum_attempts):
            result = notifier.notify(event)
            with self.authority.connection() as connection:
                connection.execute(
                    """UPDATE telegram_delivery_receipts SET status=%s,attempt_count=attempt_count+1,
                              provider_message_id=%s,error_code=%s,error_message=%s,
                              updated_at=clock_timestamp() WHERE entity_id=%s""",
                    (
                        result.status, result.provider_message_id, result.error_code,
                        result.error_message, receipt_id,
                    ),
                )
                connection.execute(
                    """UPDATE content_generation_runs SET notification_state=%s,
                              updated_at=clock_timestamp() WHERE entity_id=%s""",
                    (result.status, UUID(run_id)),
                )
            if result.status != "definite_failure":
                break
        return self.get_review(run_id)["notification"]

    def _append_rule(
        self, connection: Any, *, run: Mapping[str, Any], feedback_id: UUID,
        rule_type: str, strategy_id: str | None = None, output_profile: str | None = None,
        instruction: str | None = None, layout_patch: Sequence[Mapping[str, Any]] = (),
        exclusions: Mapping[str, Any] | None = None,
        slider_values: Mapping[str, int] | None = None,
    ) -> UUID:
        from psycopg.types.json import Jsonb

        previous = connection.execute(
            """SELECT entity_id FROM content_learning_rules
                WHERE project_id=%s AND rule_type=%s
                  AND strategy_id IS NOT DISTINCT FROM %s
                  AND output_profile IS NOT DISTINCT FROM %s
                  AND NOT EXISTS (
                    SELECT 1 FROM content_learning_rules newer
                     WHERE newer.supersedes_rule_id=content_learning_rules.entity_id
                  ) ORDER BY created_at DESC LIMIT 1""",
            (UUID(run["project_id"]), rule_type, strategy_id, output_profile),
        ).fetchone()
        rule_id = UUID(new_uuid7())
        body = {
            "rule_type": rule_type, "strategy_id": strategy_id,
            "output_profile": output_profile, "instruction": instruction,
            "slider_values": dict(slider_values or {}),
            "layout_patch": [dict(item) for item in layout_patch],
            "exclusions": dict(exclusions or {}),
        }
        connection.execute(
            "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'content_learning_rule',%s)",
            (rule_id, Jsonb({"schema_version": 1})),
        )
        connection.execute(
            """INSERT INTO content_learning_rules(
                   entity_id,project_id,feedback_id,rule_type,strategy_id,output_profile,
                   instruction,slider_values,layout_patch,exclusions,supersedes_rule_id,rule_sha256
               ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                rule_id, UUID(run["project_id"]), feedback_id, rule_type, strategy_id,
                output_profile, instruction, Jsonb(body["slider_values"]),
                Jsonb(body["layout_patch"]),
                Jsonb(body["exclusions"]), None if previous is None else previous[0],
                sha256_json(body),
            ),
        )
        connection.execute(
            """INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes)
               VALUES(%s,%s,'derived_from',%s,'{}')""",
            (UUID(new_uuid7()), rule_id, feedback_id),
        )
        if previous is not None:
            connection.execute(
                """INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes)
                   VALUES(%s,%s,'supersedes',%s,'{}')""",
                (UUID(new_uuid7()), rule_id, previous[0]),
            )
        return rule_id

    def _action_existing(self, connection: Any, request_id: UUID) -> Mapping[str, Any] | None:
        row = connection.execute(
            """SELECT entity_id,run_id,action_type,status,selected_creative_id,comment,child_run_id
                 FROM content_review_actions WHERE request_id=%s""",
            (request_id,),
        ).fetchone()
        return None if row is None else {
            "action_id": str(row[0]), "run_id": str(row[1]), "action_type": row[2],
            "status": row[3], "creative_id": None if row[4] is None else str(row[4]),
            "comment": row[5], "child_run_id": None if row[6] is None else str(row[6]),
        }

    @staticmethod
    def _assert_no_processing_action(connection: Any, run_id: UUID) -> None:
        active = connection.execute(
            "SELECT 1 FROM content_review_actions WHERE run_id=%s AND status='processing' LIMIT 1",
            (run_id,),
        ).fetchone()
        if active is not None:
            raise RuntimeError("another owner review action is already in progress")

    def approve_review(
        self, *, run_id: str, request_id: str, creative_id: str, requested_by: str,
    ) -> dict[str, Any]:
        from psycopg.types.json import Jsonb

        run = self.get_run(run_id)
        request_uuid, creative_uuid = UUID(request_id), UUID(creative_id)
        with self.authority.connection() as connection:
            existing = self._action_existing(connection, request_uuid)
            if existing is not None:
                if existing["run_id"] != run_id or existing["creative_id"] != creative_id:
                    raise ValueError("request_id was reused with different review input")
                return {"run": self.get_run(run_id), "action": existing}
            locked = connection.execute(
                "SELECT status,review_creative_ids FROM content_generation_runs WHERE entity_id=%s FOR UPDATE",
                (UUID(run_id),),
            ).fetchone()
            existing = self._action_existing(connection, request_uuid)
            if existing is not None:
                if existing["run_id"] != run_id or existing["creative_id"] != creative_id:
                    raise ValueError("request_id was reused with different review input")
                return {"run": self.get_run(run_id), "action": existing}
            if locked is None or locked[0] != "awaiting_review":
                raise RuntimeError("owner review action is stale")
            self._assert_no_processing_action(connection, UUID(run_id))
            if creative_uuid not in locked[1]:
                raise ValueError("approved Creative is outside this review set")
            creative = self.get_creative(creative_id)
            action_id, feedback_id, weight_id, outcome_id, approval_id = (
                UUID(new_uuid7()) for _ in range(5)
            )
            for entity_id, kind, attrs in (
                (action_id, "content_review_action", {"action_type": "approve"}),
                (feedback_id, "human_feedback", {"domain": "content_creative", "decision": "accepted"}),
                (weight_id, "weight_update", {"component": "content_creative", "delta": 1}),
                (outcome_id, "content_outcome", {"event_type": "owner_accepted"}),
                (approval_id, "content_creative_approval", {"decision": "approved"}),
            ):
                connection.execute(
                    "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,%s,%s)",
                    (entity_id, kind, Jsonb(attrs)),
                )
            connection.execute(
                """INSERT INTO content_review_actions(
                       entity_id,request_id,run_id,action_type,status,selected_creative_id,
                       requested_by,completed_at
                   ) VALUES(%s,%s,%s,'approve','completed',%s,%s,clock_timestamp())""",
                (action_id, request_uuid, UUID(run_id), creative_uuid, requested_by),
            )
            connection.execute(
                """INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes)
                   VALUES(%s,%s,'contains',%s,%s)""",
                (
                    UUID(new_uuid7()), UUID(run_id), action_id,
                    Jsonb({"member": "owner_review_action"}),
                ),
            )
            connection.execute(
                """INSERT INTO commander_human_feedback(entity_id,target_id,domain,section_id,instruction,actor)
                   VALUES(%s,%s,'content_creative','owner_review','accepted',%s)""",
                (feedback_id, creative_uuid, requested_by),
            )
            connection.execute(
                """INSERT INTO commander_weight_updates(entity_id,feedback_id,component,delta,reason)
                   VALUES(%s,%s,'content_creative',1,'Owner approved this Creative direction')""",
                (weight_id, feedback_id),
            )
            connection.execute(
                """INSERT INTO content_generation_outcomes(entity_id,run_id,creative_id,event_type,source_type)
                   VALUES(%s,%s,%s,'accepted','owner')""",
                (outcome_id, UUID(run_id), creative_uuid),
            )
            connection.execute(
                """INSERT INTO content_creative_approvals(
                       entity_id,creative_id,feedback_id,approved_by
                   ) VALUES(%s,%s,%s,%s)""",
                (approval_id, creative_uuid, feedback_id, requested_by),
            )
            layout_patch: list[dict[str, Any]] = []
            recipe = self.authority.get_creative_recipe(creative_id)
            if recipe is not None:
                modifiers = list(recipe["document"].get("modifiers") or [])
                if len(modifiers) == 1:
                    layout_patch = [
                        dict(item)
                        for item in modifiers[0]["params"].get("component_patch") or []
                    ]
            self._append_rule(
                connection, run=run, feedback_id=feedback_id, rule_type="preferred_direction",
                strategy_id=creative["template_id"],
                instruction=f"Prefer owner-approved strategy {creative['template_id']} with its saved sliders.",
                slider_values=creative["parameters"],
            )
            self._append_rule(
                connection, run=run, feedback_id=feedback_id, rule_type="preferred_layout",
                strategy_id=creative["template_id"], output_profile=run["output_profile"],
                layout_patch=layout_patch,
            )
            connection.execute(
                """UPDATE content_generation_runs SET status='approved',current_stage='approved',
                          approved_creative_id=%s,updated_at=clock_timestamp()
                     WHERE entity_id=%s""",
                (creative_uuid, UUID(run_id)),
            )
            for source, relation, target in (
                (feedback_id, "evaluates", creative_uuid),
                (feedback_id, "contains", weight_id),
                (weight_id, "adjusts", creative_uuid),
                (outcome_id, "derived_from", feedback_id),
                (approval_id, "derived_from", feedback_id),
            ):
                connection.execute(
                    """INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes)
                       VALUES(%s,%s,%s,%s,'{}')""",
                    (UUID(new_uuid7()), source, relation, target),
                )
        return {"run": self.get_run(run_id), "action": {"action_id": str(action_id)}}

    def _create_child_run(
        self, connection: Any, *, parent: Mapping[str, Any], request_id: UUID,
        generation_kind: str, requested_by: str, selected: Mapping[str, Any] | None,
        revision_instruction: Mapping[str, Any],
    ) -> UUID:
        from psycopg.types.json import Jsonb

        run_id, snapshot_id = UUID(new_uuid7()), UUID(new_uuid7())
        reserve_count = 1 if generation_kind == "tune" else 5
        creative_ids = [UUID(new_uuid7()) for _ in range(reserve_count)]
        context = deepcopy(parent["context_bundle"])
        context["revision_instruction"] = dict(revision_instruction)
        learning = {
            "schema": "ptw.owner-learning-snapshot.v1", "project_id": parent["project_id"],
            "rules": self._active_learning_rules(connection, UUID(parent["project_id"])),
        }
        context["owner_learning"] = learning
        for candidate_context in context["candidate_contexts"].values():
            candidate_context["owner_learning"] = learning
            candidate_context["revision_instruction"] = dict(revision_instruction)
        connection.execute(
            "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'content_learning_snapshot',%s)",
            (snapshot_id, Jsonb({"schema_version": 1})),
        )
        connection.execute(
            """INSERT INTO content_learning_snapshots(entity_id,project_id,document,document_sha256)
               VALUES(%s,%s,%s,%s)""",
            (snapshot_id, UUID(parent["project_id"]), Jsonb(learning), sha256_json(learning)),
        )
        for entity_id, kind, attributes in (
            (run_id, "content_run", {"schema_version": 2}),
            *[(item, "content_creative", {"reserved": True}) for item in creative_ids],
        ):
            connection.execute(
                "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,%s,%s)",
                (entity_id, kind, Jsonb(attributes)),
            )
        connection.execute(
            """INSERT INTO content_generation_runs(
                   entity_id,request_id,parent_run_id,project_id,brief_id,task_source_id,
                   brand_kit_id,output_profile,task,context_bundle,context_sha256,generation_kind,
                   reserved_creative_ids,carried_review_creative_ids,tuned_creative_id,
                   tuned_strategy_id,status,current_stage,budget_state,generator_skill_sha256,
                   corpus_sha256,learning_snapshot_id,requested_by,deadline_at
               ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                        'queued','queued',%s,%s,%s,%s,%s,clock_timestamp()+interval '45 minutes')""",
            (
                run_id, request_id, UUID(parent["run_id"]), UUID(parent["project_id"]),
                UUID(parent["brief_id"]), UUID(parent["task_source_id"]),
                UUID(parent["brand_kit_id"]), parent["output_profile"], parent["task"],
                Jsonb(context), sha256_json(context), generation_kind, creative_ids,
                [UUID(item) for item in parent["review_creative_ids"]],
                None if selected is None else UUID(selected["creative_id"]),
                None if selected is None else selected["template_id"],
                Jsonb({"generation_remaining": reserve_count, "graphic_generation_remaining": 1}),
                parent["generator_skill_sha256"], parent["corpus_sha256"], snapshot_id,
                requested_by,
            ),
        )
        lineage: list[tuple[UUID, str, UUID, dict[str, Any]]] = [
            (run_id, "derived_from", UUID(parent["run_id"]), {"input": "parent_review_run"}),
            (run_id, "derived_from", snapshot_id, {"input": "owner_learning_snapshot"}),
            (UUID(parent["project_id"]), "contains", run_id, {"member": "content_run"}),
            *[
                (run_id, "contains", item, {"member": "reserved_creative"})
                for item in creative_ids
            ],
        ]
        feedback_ids: list[UUID] = []
        if revision_instruction.get("feedback_id"):
            feedback_ids.append(UUID(str(revision_instruction["feedback_id"])))
        feedback_ids.extend(
            UUID(str(item)) for item in revision_instruction.get("feedback_ids") or []
        )
        lineage.extend(
            (run_id, "derived_from", feedback_id, {"input": "owner_feedback"})
            for feedback_id in feedback_ids
        )
        for source, relation, target, attributes in lineage:
            connection.execute(
                """INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes)
                   VALUES(%s,%s,%s,%s,%s)""",
                (UUID(new_uuid7()), source, relation, target, Jsonb(attributes)),
            )
        return run_id

    def create_tune(
        self, *, run_id: str, request_id: str, creative_id: str, comment: str,
        requested_by: str, create_run: Callable[..., Any],
    ) -> tuple[dict[str, Any], bool]:
        from psycopg.types.json import Jsonb

        del create_run
        normalized = " ".join(comment.split())
        if not 3 <= len(normalized) <= 2_000:
            raise ValueError("tune comment must contain 3-2000 characters")
        parent, selected = self.get_run(run_id), self.get_creative(creative_id)
        request_uuid = UUID(request_id)
        with self.authority.connection() as connection:
            existing = self._action_existing(connection, request_uuid)
            if existing is not None:
                if existing["comment"] != normalized or existing["creative_id"] != creative_id:
                    raise ValueError("request_id was reused with different tune input")
                return self.get_run(existing["child_run_id"]), False
            locked = connection.execute(
                "SELECT status,review_creative_ids FROM content_generation_runs WHERE entity_id=%s FOR UPDATE",
                (UUID(run_id),),
            ).fetchone()
            existing = self._action_existing(connection, request_uuid)
            if existing is not None:
                if existing["comment"] != normalized or existing["creative_id"] != creative_id:
                    raise ValueError("request_id was reused with different tune input")
                return self.get_run(existing["child_run_id"]), False
            if locked is None or locked[0] != "awaiting_review" or UUID(creative_id) not in locked[1]:
                raise RuntimeError("owner review action is stale")
            self._assert_no_processing_action(connection, UUID(run_id))
            action_id, feedback_id, weight_id = (UUID(new_uuid7()) for _ in range(3))
            for entity_id, kind, attrs in (
                (action_id, "content_review_action", {"action_type": "tune"}),
                (feedback_id, "human_feedback", {"decision": "tune_requested"}),
                (weight_id, "weight_update", {"delta": 1}),
            ):
                connection.execute(
                    "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,%s,%s)",
                    (entity_id, kind, Jsonb(attrs)),
                )
            connection.execute(
                """INSERT INTO commander_human_feedback(entity_id,target_id,domain,section_id,instruction,actor)
                   VALUES(%s,%s,'content_creative','owner_review',%s,%s)""",
                (feedback_id, UUID(creative_id), normalized, requested_by),
            )
            connection.execute(
                """INSERT INTO commander_weight_updates(entity_id,feedback_id,component,delta,reason)
                   VALUES(%s,%s,'content_creative',1,'Owner selected this direction for tuning')""",
                (weight_id, feedback_id),
            )
            for source, relation, target in (
                (feedback_id, "evaluates", UUID(creative_id)),
                (feedback_id, "contains", weight_id),
                (weight_id, "adjusts", UUID(creative_id)),
            ):
                connection.execute(
                    """INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes)
                       VALUES(%s,%s,%s,%s,'{}')""",
                    (UUID(new_uuid7()), source, relation, target),
                )
            self._append_rule(
                connection, run=parent, feedback_id=feedback_id, rule_type="tune_instruction",
                strategy_id=selected["template_id"], instruction=normalized,
            )
            revision = {
                "schema_version": 1, "feedback_id": str(feedback_id), "parent_run_id": run_id,
                "creative_id": creative_id, "comment": normalized,
            }
            child_id = self._create_child_run(
                connection, parent=parent, request_id=request_uuid, generation_kind="tune",
                requested_by=requested_by, selected=selected, revision_instruction=revision,
            )
            connection.execute(
                """INSERT INTO content_review_actions(
                       entity_id,request_id,run_id,action_type,status,selected_creative_id,
                       comment,child_run_id,requested_by
                   ) VALUES(%s,%s,%s,'tune','processing',%s,%s,%s,%s)""",
                (action_id, request_uuid, UUID(run_id), UUID(creative_id), normalized, child_id, requested_by),
            )
            connection.execute(
                """INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes)
                   VALUES(%s,%s,'contains',%s,%s)""",
                (
                    UUID(new_uuid7()), UUID(run_id), action_id,
                    Jsonb({"member": "owner_review_action"}),
                ),
            )
        return self.get_run(str(child_id)), True

    def create_regenerate_all(
        self, *, run_id: str, request_id: str, requested_by: str,
        create_run: Callable[..., Any],
    ) -> tuple[dict[str, Any], bool]:
        from psycopg.types.json import Jsonb

        del create_run
        parent, request_uuid = self.get_run(run_id), UUID(request_id)
        with self.authority.connection() as connection:
            existing = self._action_existing(connection, request_uuid)
            if existing is not None:
                return self.get_run(existing["child_run_id"]), False
            locked = connection.execute(
                "SELECT status FROM content_generation_runs WHERE entity_id=%s FOR UPDATE",
                (UUID(run_id),),
            ).fetchone()
            existing = self._action_existing(connection, request_uuid)
            if existing is not None:
                return self.get_run(existing["child_run_id"]), False
            if locked is None or locked[0] != "awaiting_review":
                raise RuntimeError("owner review action is stale")
            self._assert_no_processing_action(connection, UUID(run_id))
            action_id = UUID(new_uuid7())
            connection.execute(
                "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'content_review_action',%s)",
                (action_id, Jsonb({"action_type": "regenerate_all"})),
            )
            parent_creatives = [
                self.get_creative(creative_id) for creative_id in parent["review_creative_ids"]
            ]
            exclusions = {
                "creative_ids": parent["review_creative_ids"],
                "document_sha256": [item["document_sha256"] for item in parent_creatives],
                "render_sha256": [
                    self.creative_preview_metadata(item["creative_id"])["sha256"]
                    for item in parent_creatives
                ],
                "media_sha256": [
                    item["media_identity_sha256"] for item in parent_creatives
                    if item["media_identity_sha256"] is not None
                ],
                "provider_invocation_ids": [
                    item["provider_invocation_id"] for item in parent_creatives
                ],
            }
            feedback_ids: list[str] = []
            for creative_id in parent["review_creative_ids"]:
                feedback_id, weight_id = UUID(new_uuid7()), UUID(new_uuid7())
                feedback_ids.append(str(feedback_id))
                connection.execute(
                    "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'human_feedback',%s)",
                    (feedback_id, Jsonb({"decision": "rejected"})),
                )
                connection.execute(
                    "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'weight_update',%s)",
                    (weight_id, Jsonb({"delta": -1})),
                )
                connection.execute(
                    """INSERT INTO commander_human_feedback(entity_id,target_id,domain,section_id,instruction,actor)
                       VALUES(%s,%s,'content_creative','owner_review','regenerate_all',%s)""",
                    (feedback_id, UUID(creative_id), requested_by),
                )
                connection.execute(
                    """INSERT INTO commander_weight_updates(entity_id,feedback_id,component,delta,reason)
                       VALUES(%s,%s,'content_creative',-1,'Owner rejected the complete review set')""",
                    (weight_id, feedback_id),
                )
                for source, relation, target in (
                    (feedback_id, "evaluates", UUID(creative_id)),
                    (feedback_id, "contains", weight_id),
                    (weight_id, "adjusts", UUID(creative_id)),
                ):
                    connection.execute(
                        """INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes)
                           VALUES(%s,%s,%s,%s,'{}')""",
                        (UUID(new_uuid7()), source, relation, target),
                    )
            self._append_rule(
                connection, run=parent, feedback_id=UUID(feedback_ids[0]),
                rule_type="exploration_exclusions", exclusions=exclusions,
            )
            revision = {
                "schema_version": 1, "action": "regenerate_all",
                "feedback_ids": feedback_ids, "excluded_identities": exclusions,
            }
            child_id = self._create_child_run(
                connection, parent=parent, request_id=request_uuid,
                generation_kind="regenerate_all", requested_by=requested_by,
                selected=None, revision_instruction=revision,
            )
            connection.execute(
                """INSERT INTO content_review_actions(
                       entity_id,request_id,run_id,action_type,status,child_run_id,requested_by
                   ) VALUES(%s,%s,%s,'regenerate_all','processing',%s,%s)""",
                (action_id, request_uuid, UUID(run_id), child_id, requested_by),
            )
            connection.execute(
                """INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes)
                   VALUES(%s,%s,'contains',%s,%s)""",
                (
                    UUID(new_uuid7()), UUID(run_id), action_id,
                    Jsonb({"member": "owner_review_action"}),
                ),
            )
        return self.get_run(str(child_id)), True

    def fail_run(self, run_id: str, error: Exception) -> dict[str, Any]:
        from psycopg.types.json import Jsonb

        with self.authority.connection() as connection:
            connection.execute(
                """UPDATE content_generation_runs SET status='failed',current_stage='failed',
                          error_code=%s,error_message=%s,completed_at=clock_timestamp(),
                          updated_at=clock_timestamp()
                     WHERE entity_id=%s AND status IN ('queued','generating')""",
                (type(error).__name__, str(error)[:2_000], UUID(run_id)),
            )
            connection.execute(
                """UPDATE content_review_actions SET status='failed',failure=%s,
                          completed_at=clock_timestamp(),updated_at=clock_timestamp()
                     WHERE child_run_id=%s AND status='processing'""",
                (Jsonb({
                    "error_code": type(error).__name__,
                    "error_message": str(error)[:2_000],
                }), UUID(run_id)),
            )
        return self.get_run(run_id)

    def recoverable_runs(self) -> list[str]:
        with self.authority.connection() as connection:
            rows = connection.execute(
                """SELECT entity_id FROM content_generation_runs
                    WHERE status IN ('queued','generating') ORDER BY created_at"""
            ).fetchall()
        return [str(row[0]) for row in rows]

    def recoverable_notification_runs(self) -> list[str]:
        with self.authority.connection() as connection:
            rows = connection.execute(
                """SELECT entity_id FROM content_generation_runs
                    WHERE status='awaiting_review' AND (
                      notification_state='pending' OR (
                        notification_state='definite_failure'
                        AND COALESCE((SELECT attempt_count FROM telegram_delivery_receipts
                                      WHERE entity_id=notification_receipt_id),0)<3
                      )
                    )
                    ORDER BY created_at"""
            ).fetchall()
        return [str(row[0]) for row in rows]
