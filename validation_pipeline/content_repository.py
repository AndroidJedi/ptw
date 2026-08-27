"""PostgreSQL authority for immutable Result runs, candidates, passes, and outcomes."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence
from uuid import UUID

from commander.ids import new_uuid7

from .content import (
    CandidateV2, ContextBundleV1, OUTPUT_PROFILES, SLIDER_NAMES, StrategyTemplate,
    canonical_json, sha256_json,
)


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
        return """SELECT run.entity_id,run.request_id,run.parent_run_id,run.project_id,run.brief_id,
                         run.task_source_id,run.brand_kit_id,run.output_profile,run.task,
                         run.context_bundle,run.context_sha256,run.initial_candidate_ids,
                         run.critic_pass_ids,run.status,
                         run.current_stage,run.budget_state,run.generator_skill_sha256,
                         run.critic_skill_sha256,run.corpus_sha256,run.final_result_id,
                         run.error_code,run.error_message,run.requested_by,run.deadline_at,
                         run.created_at,run.updated_at,run.completed_at,
                         (SELECT count(*) FROM content_candidates candidate
                           WHERE candidate.run_id=run.entity_id),
                         (SELECT count(*) FROM content_critic_passes pass
                           WHERE pass.run_id=run.entity_id)
                    FROM content_generation_runs run"""

    @staticmethod
    def _run_row(row: Sequence[Any]) -> dict[str, Any]:
        candidate_count, critic_count = int(row[27]), int(row[28])
        stage_progress = {
            "queued": 0, "initial_candidates": min(35, candidate_count * 7),
            "critic_pass_1": 45, "critic_pass_2": 67, "critic_pass_3": 86,
            "materializing_result": 95, "completed": 100, "failed": 100,
        }
        return {
            "run_id": str(row[0]), "request_id": str(row[1]),
            "parent_run_id": None if row[2] is None else str(row[2]),
            "project_id": str(row[3]), "brief_id": str(row[4]),
            "task_source_id": str(row[5]), "brand_kit_id": str(row[6]),
            "output_profile": row[7], "task": row[8], "context_bundle": dict(row[9]),
            "context_sha256": row[10], "initial_candidate_ids": [str(item) for item in row[11]],
            "critic_pass_ids": [str(item) for item in row[12]],
            "status": row[13], "current_stage": row[14], "budget_state": dict(row[15]),
            "generator_skill_sha256": row[16], "critic_skill_sha256": row[17],
            "corpus_sha256": row[18],
            "final_result_id": None if row[19] is None else str(row[19]),
            "error_code": row[20], "error_message": row[21], "requested_by": row[22],
            "deadline_at": row[23].isoformat(), "created_at": row[24].isoformat(),
            "updated_at": row[25].isoformat(),
            "completed_at": None if row[26] is None else row[26].isoformat(),
            "candidate_count": candidate_count, "critic_pass_count": critic_count,
            "progress_percent": stage_progress[row[14]],
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
                self._run_select() + " WHERE run.project_id=%s ORDER BY run.created_at DESC LIMIT %s",
                (UUID(project_id), min(100, max(1, limit))),
            ).fetchall()
        return [self._run_row(row) for row in rows]

    def create_run(
        self, *, request_id: str, brief_id: str, task: str, output_profile: str,
        context: ContextBundleV1, templates: Sequence[StrategyTemplate], requested_by: str,
        parent_run_id: str | None = None,
    ) -> tuple[dict[str, Any], bool]:
        from psycopg.types.json import Jsonb

        request_uuid = UUID(request_id)
        normalized_task = task.strip()
        if output_profile not in OUTPUT_PROFILES or not 1 <= len(normalized_task) <= 4000:
            raise ValueError("Result run requires a supported profile and a 1-4000 character task")
        brief = self.authority.get_brief(brief_id)
        if not brief["approved"] or brief["status"] != "completed":
            raise ValueError("Result generation requires an approved completed Product Brief")
        if len(templates) != 5 or len({item.template_id for item in templates}) != 5:
            raise ValueError("Result generation requires five distinct active templates")
        kits = self.authority.list_project_brand_kits(brief["project_id"])
        if not kits:
            raise ValueError("Result generation requires a Project brand kit")
        brand_kit = kits[0]
        if context.document["brief"]["brief_id"] != brief_id:
            raise ValueError("Result context does not match the selected Brief")
        if context.document["brand_kit"]["brand_kit_id"] != brand_kit["brand_kit_id"]:
            raise ValueError("Result context does not match the latest Project brand kit")
        parent_uuid = None if parent_run_id is None else UUID(parent_run_id)
        with self.authority.connection() as connection:
            existing = connection.execute(
                self._run_select() + " WHERE run.request_id=%s", (request_uuid,),
            ).fetchone()
            if existing is not None:
                value = self._run_row(existing)
                if (
                    value["brief_id"] != brief_id or value["task"] != normalized_task
                    or value["output_profile"] != output_profile or value["parent_run_id"] != parent_run_id
                ):
                    raise ValueError("request_id was already used with different Result input")
                return value, False
            if parent_uuid is not None:
                parent = connection.execute(
                    "SELECT brief_id,project_id,task,output_profile FROM content_generation_runs WHERE entity_id=%s",
                    (parent_uuid,),
                ).fetchone()
                if parent is None:
                    raise KeyError(parent_run_id)
                if (
                    parent[0] != UUID(brief_id) or parent[1] != UUID(brief["project_id"])
                    or parent[2] != normalized_task or parent[3] != output_profile
                ):
                    raise ValueError("a Result retry must preserve its parent source, task, and profile")
            run_id, task_source_id = UUID(new_uuid7()), UUID(new_uuid7())
            candidate_ids = [UUID(new_uuid7()) for _ in range(5)]
            critic_pass_ids = [UUID(new_uuid7()) for _ in range(3)]
            task_digest = hashlib.sha256(normalized_task.encode()).hexdigest()
            versions = context.document["versions"]
            budget = {
                "initial_generation_remaining": 5,
                "improvement_generation_remaining": 4,
                "critic_calls_remaining": 3,
                "graphic_generation_remaining": 1,
                "json_retry_per_call": 1,
            }
            connection.execute(
                "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'source',%s)",
                (task_source_id, Jsonb({"source_type": "owner_task", "schema_version": 1})),
            )
            connection.execute(
                """INSERT INTO commander_sources(
                       entity_id,source_type,title,provider,external_id,content,content_sha256,metadata
                   ) VALUES(%s,'owner_task','Result task','owner',%s,%s,%s,%s)""",
                (task_source_id, request_uuid.hex, normalized_task, task_digest, Jsonb({
                    "project_id": brief["project_id"], "brief_id": brief_id,
                    "output_profile": output_profile,
                })),
            )
            connection.execute(
                "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'content_run',%s)",
                (run_id, Jsonb({"schema_version": 1, "output_profile": output_profile})),
            )
            for index, candidate_id in enumerate(candidate_ids, start=1):
                connection.execute(
                    "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'content_candidate',%s)",
                    (candidate_id, Jsonb({"reserved": True, "initial_ordinal": index})),
                )
            for pass_number, pass_id in enumerate(critic_pass_ids, start=1):
                connection.execute(
                    "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'content_critic_pass',%s)",
                    (pass_id, Jsonb({"reserved": True, "pass_number": pass_number})),
                )
            connection.execute(
                """INSERT INTO content_generation_runs(
                       entity_id,request_id,parent_run_id,project_id,brief_id,task_source_id,
                       brand_kit_id,output_profile,task,context_bundle,context_sha256,
                       initial_candidate_ids,critic_pass_ids,status,current_stage,budget_state,
                       generator_skill_sha256,critic_skill_sha256,corpus_sha256,
                       requested_by,deadline_at
                   ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                            'queued','queued',%s,%s,%s,%s,%s,clock_timestamp()+interval '45 minutes')""",
                (
                    run_id, request_uuid, parent_uuid, UUID(brief["project_id"]), UUID(brief_id),
                    task_source_id, UUID(brand_kit["brand_kit_id"]), output_profile, normalized_task,
                    Jsonb(dict(context.document)), context.digest, candidate_ids, critic_pass_ids,
                    Jsonb(budget),
                    versions["generator_skill_sha256"], versions["critic_skill_sha256"],
                    versions["corpus_sha256"], requested_by,
                ),
            )
            edges = [
                (run_id, "derived_from", UUID(brief_id), {"input": "approved_product_brief"}),
                (run_id, "derived_from", task_source_id, {"input": "owner_task"}),
                (run_id, "derived_from", UUID(brand_kit["brand_kit_id"]), {"input": "brand_kit"}),
                (UUID(brief["project_id"]), "contains", run_id, {"member": "content_run"}),
                *[(run_id, "contains", candidate_id, {"member": "reserved_initial_candidate", "ordinal": index})
                  for index, candidate_id in enumerate(candidate_ids, start=1)],
                *[(run_id, "contains", pass_id, {"member": "reserved_critic_pass", "pass": pass_number})
                  for pass_number, pass_id in enumerate(critic_pass_ids, start=1)],
                *([(run_id, "rerun_of", parent_uuid, {})] if parent_uuid is not None else []),
            ]
            for item in context.document["approved_sources"]:
                if item.get("source_asset_id"):
                    edges.append((run_id, "derived_from", UUID(item["source_asset_id"]), {"input": "approved_project_source"}))
            for source, relation, target, attributes in edges:
                connection.execute(
                    "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,%s,%s,%s)",
                    (UUID(new_uuid7()), source, relation, target, Jsonb(attributes)),
                )
        return self.get_run(str(run_id)), True

    def set_stage(self, run_id: str, stage: str, *, status: str = "generating") -> dict[str, Any]:
        allowed = {
            "queued", "initial_candidates", "critic_pass_1", "critic_pass_2",
            "critic_pass_3", "materializing_result", "completed", "failed",
        }
        if stage not in allowed or status not in {"queued", "generating", "completed", "failed"}:
            raise ValueError("unsupported Result run stage transition")
        with self.authority.connection() as connection:
            changed = connection.execute(
                """UPDATE content_generation_runs SET status=%s,current_stage=%s,
                          updated_at=clock_timestamp()
                    WHERE entity_id=%s AND status IN ('queued','generating')""",
                (status, stage, UUID(run_id)),
            ).rowcount
        if changed != 1:
            raise ValueError("Result run is not in a mutable state")
        return self.get_run(run_id)

    def consume_budget(self, run_id: str, key: str, amount: int = 1) -> dict[str, Any]:
        from psycopg.types.json import Jsonb

        if key not in {
            "initial_generation_remaining", "improvement_generation_remaining",
            "critic_calls_remaining", "graphic_generation_remaining",
        } or amount < 1:
            raise ValueError("unknown Result budget counter")
        with self.authority.connection() as connection:
            row = connection.execute(
                "SELECT budget_state FROM content_generation_runs WHERE entity_id=%s FOR UPDATE",
                (UUID(run_id),),
            ).fetchone()
            if row is None:
                raise KeyError(run_id)
            budget = dict(row[0])
            remaining = int(budget.get(key, 0))
            if remaining < amount:
                raise ValueError(f"Result run budget exhausted: {key}")
            budget[key] = remaining - amount
            connection.execute(
                "UPDATE content_generation_runs SET budget_state=%s,updated_at=clock_timestamp() WHERE entity_id=%s",
                (Jsonb(budget), UUID(run_id)),
            )
        return budget

    def checkpoint(
        self, run_id: str, *, stage: str, target_id: str | None, payload: Mapping[str, Any],
    ) -> None:
        from psycopg.types.json import Jsonb

        with self.authority.connection() as connection:
            if connection.execute(
                "SELECT 1 FROM content_generation_runs WHERE entity_id=%s FOR UPDATE", (UUID(run_id),),
            ).fetchone() is None:
                raise KeyError(run_id)
            target_uuid = None if target_id is None else UUID(target_id)
            digest = sha256_json(payload)
            existing = connection.execute(
                """SELECT payload_sha256 FROM content_generation_checkpoints
                    WHERE run_id=%s AND stage=%s AND target_id IS NOT DISTINCT FROM %s""",
                (UUID(run_id), stage, target_uuid),
            ).fetchone()
            if existing is not None:
                if existing[0] != digest:
                    raise ValueError("Result checkpoint payload cannot change")
                return
            sequence = int(connection.execute(
                "SELECT COALESCE(max(sequence),0)+1 FROM content_generation_checkpoints WHERE run_id=%s",
                (UUID(run_id),),
            ).fetchone()[0])
            connection.execute(
                """INSERT INTO content_generation_checkpoints(
                       id,run_id,sequence,stage,target_id,payload,payload_sha256
                   ) VALUES(%s,%s,%s,%s,%s,%s,%s)""",
                (
                    UUID(new_uuid7()), UUID(run_id), sequence, stage,
                    target_uuid, Jsonb(dict(payload)), digest,
                ),
            )

    def reserve_candidate(self, run_id: str, *, attributes: Mapping[str, Any]) -> str:
        from psycopg.types.json import Jsonb

        candidate_id = UUID(new_uuid7())
        with self.authority.connection() as connection:
            connection.execute(
                "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'content_candidate',%s)",
                (candidate_id, Jsonb({"reserved": True, **dict(attributes)})),
            )
            connection.execute(
                "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,'contains',%s,%s)",
                (UUID(new_uuid7()), UUID(run_id), candidate_id, Jsonb({"member": "reserved_improvement_candidate"})),
            )
        return str(candidate_id)

    def start_invocation(self, target_id: str, *, mode: str, idempotency_key: str, request: Mapping[str, Any]) -> tuple[str, str]:
        from psycopg.types.json import Jsonb

        if mode not in {"content_candidate_generation", "content_result_critic"}:
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
                              invocation=%s,completed_at=clock_timestamp() WHERE id=%s AND status='submitted'""",
                    (sha256_json(response), Jsonb(dict(provenance)), UUID(invocation_id)),
                )
                connection.execute(
                    "UPDATE validation_generation_attempts SET status='completed',completed_at=clock_timestamp() WHERE id=%s AND status='started'",
                    (UUID(attempt_id),),
                )
            else:
                connection.execute(
                    """UPDATE validation_provider_invocations SET status='failed',invocation=%s,
                              completed_at=clock_timestamp() WHERE id=%s AND status='submitted'""",
                    (Jsonb({**dict(provenance), "error": type(error).__name__ if error else "unknown"}), UUID(invocation_id)),
                )
                connection.execute(
                    """UPDATE validation_generation_attempts SET status='failed',error_code=%s,
                              error_message=%s,completed_at=clock_timestamp() WHERE id=%s AND status='started'""",
                    (type(error).__name__ if error else "RuntimeError", str(error)[:1000] if error else "unknown", UUID(attempt_id)),
                )

    @staticmethod
    def _candidate_select() -> str:
        return """SELECT candidate.entity_id,candidate.run_id,candidate.alias,candidate.round,
                         candidate.generation_kind,candidate.parent_candidate_id,candidate.template_id,
                         candidate.template_version,candidate.template_sha256,candidate.hook_pressure,
                         candidate.emotional_intensity,candidate.conceptual_novelty,
                         candidate.information_density,candidate.visual_complexity,candidate.parameters,
                         candidate.config_sha256,candidate.document,candidate.document_sha256,
                         candidate.recipe_id,candidate.render_id,candidate.provider_provenance,
                         candidate.response_sha256,candidate.retry_count,candidate.created_at
                    FROM content_candidates candidate"""

    @staticmethod
    def _candidate_row(row: Sequence[Any]) -> dict[str, Any]:
        return {
            "candidate_id": str(row[0]), "run_id": str(row[1]), "alias": row[2],
            "round": int(row[3]), "generation_kind": row[4],
            "parent_candidate_id": None if row[5] is None else str(row[5]),
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
            "provider_provenance": dict(row[20]), "response_sha256": row[21],
            "retry_count": int(row[22]), "created_at": row[23].isoformat(),
        }

    def get_candidate(self, candidate_id: str) -> dict[str, Any]:
        with self.authority.connection() as connection:
            row = connection.execute(
                self._candidate_select() + " WHERE candidate.entity_id=%s", (UUID(candidate_id),),
            ).fetchone()
        if row is None:
            raise KeyError(candidate_id)
        value = self._candidate_row(row)
        value["elements"] = self.candidate_elements(candidate_id)
        return value

    def list_candidates(self, run_id: str) -> list[dict[str, Any]]:
        with self.authority.connection() as connection:
            rows = connection.execute(
                self._candidate_select() + " WHERE candidate.run_id=%s ORDER BY candidate.created_at",
                (UUID(run_id),),
            ).fetchall()
        values = [self._candidate_row(row) for row in rows]
        for item in values:
            item["elements"] = self.candidate_elements(item["candidate_id"])
        return values

    def candidate_elements(self, candidate_id: str) -> list[dict[str, Any]]:
        with self.authority.connection() as connection:
            rows = connection.execute(
                """SELECT element.entity_id,element.display_alias,link.slot,link.ordinal,
                          element.element_type,element.payload,element.payload_sha256,
                          element.born_in_candidate_id,link.reuse_mode
                     FROM content_candidate_elements link
                     JOIN content_elements element ON element.entity_id=link.element_id
                    WHERE link.candidate_id=%s ORDER BY link.ordinal,link.slot""",
                (UUID(candidate_id),),
            ).fetchall()
        return [{
            "element_id": str(row[0]), "display_alias": row[1], "slot": row[2],
            "ordinal": int(row[3]), "element_type": row[4], "payload": dict(row[5]),
            "payload_sha256": row[6], "born_in_candidate_id": str(row[7]),
            "reuse_mode": row[8],
        } for row in rows]

    def persist_candidate(
        self, *, run_id: str, candidate_id: str, alias: str, round_number: int,
        generation_kind: str, parent_candidate_id: str | None, template: StrategyTemplate,
        parameters: Mapping[str, int], candidate: CandidateV2, elements: Sequence[Mapping[str, Any]],
        materialized: Mapping[str, Any], provider_provenance: Mapping[str, Any],
    ) -> dict[str, Any]:
        from psycopg.types.json import Jsonb

        candidate_uuid = _uuid(candidate_id)
        if set(parameters) != set(SLIDER_NAMES):
            raise ValueError("candidate parameters must retain all five normalized sliders")
        recipe = materialized.get("recipe")
        render = materialized.get("render")
        preview = materialized.get("preview")
        if (recipe is None) != (render is None):
            raise ValueError("Result candidate recipe and render must be materialized together")
        if (render is None) == (preview is None):
            raise ValueError("Result candidate requires exactly one Studio render or text preview")
        with self.authority.connection() as connection:
            budget_row = connection.execute(
                "SELECT budget_state FROM content_generation_runs WHERE entity_id=%s FOR UPDATE",
                (UUID(run_id),),
            ).fetchone()
            if budget_row is None:
                raise KeyError(run_id)
            budget = dict(budget_row[0])
            budget_key = (
                "initial_generation_remaining" if generation_kind == "initial"
                else "improvement_generation_remaining"
            )
            if int(budget.get(budget_key, 0)) < 1:
                raise ValueError(f"Result run budget exhausted: {budget_key}")
            reserved = connection.execute(
                "SELECT 1 FROM commander_entities WHERE id=%s AND kind='content_candidate'",
                (candidate_uuid,),
            ).fetchone()
            if reserved is None:
                raise ValueError("candidate UUID was not reserved by the server")
            connection.execute(
                """INSERT INTO content_candidates(
                       entity_id,run_id,alias,round,generation_kind,parent_candidate_id,
                       template_id,template_version,template_sha256,hook_pressure,
                       emotional_intensity,conceptual_novelty,information_density,visual_complexity,
                       parameters,config_sha256,document,document_sha256,recipe_id,render_id,
                       provider_provenance,response_sha256,retry_count
                   ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    candidate_uuid, UUID(run_id), alias, round_number, generation_kind,
                    None if parent_candidate_id is None else UUID(parent_candidate_id),
                    template.template_id, template.version, template.digest,
                    *(int(parameters[name]) for name in SLIDER_NAMES),
                    Jsonb(dict(parameters)), sha256_json(parameters), Jsonb(dict(candidate.value)),
                    candidate.digest, None if recipe is None else UUID(recipe["recipe_id"]),
                    None if render is None else UUID(render["render_id"]),
                    Jsonb(dict(provider_provenance)), candidate.digest,
                    int(provider_provenance.get("bridge_attempt", 1)) - 1,
                ),
            )
            known_elements: set[UUID] = set()
            for raw in elements:
                element_id = _uuid(str(raw["element_id"]))
                reuse_mode = str(raw["reuse_mode"])
                existing = connection.execute(
                    "SELECT run_id FROM content_elements WHERE entity_id=%s", (element_id,),
                ).fetchone()
                if existing is None:
                    payload = dict(raw["payload"])
                    connection.execute(
                        "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'content_element',%s)",
                        (element_id, Jsonb({"slot": raw["slot"], "schema_version": 1})),
                    )
                    connection.execute(
                        """INSERT INTO content_elements(
                               entity_id,run_id,display_alias,slot,element_type,ordinal,payload,
                               payload_sha256,born_in_candidate_id
                           ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (
                            element_id, UUID(run_id), raw["display_alias"], raw["slot"],
                            raw["element_type"], int(raw["ordinal"]), Jsonb(payload),
                            sha256_json(payload), candidate_uuid,
                        ),
                    )
                    for source_id in raw.get("source_element_ids") or []:
                        relation = "supersedes" if reuse_mode == "replacement" else "derived_from"
                        connection.execute(
                            "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,%s,%s,%s)",
                            (UUID(new_uuid7()), element_id, relation, UUID(source_id), Jsonb({"mode": reuse_mode})),
                        )
                elif existing[0] != UUID(run_id) or reuse_mode != "reuse_exact":
                    raise ValueError("only exact reuse may associate an existing element in the same run")
                if element_id in known_elements:
                    raise ValueError("candidate cannot associate one element more than once")
                known_elements.add(element_id)
                connection.execute(
                    """INSERT INTO content_candidate_elements(
                           id,candidate_id,element_id,slot,ordinal,reuse_mode
                       ) VALUES(%s,%s,%s,%s,%s,%s)""",
                    (
                        UUID(new_uuid7()), candidate_uuid, element_id, raw["slot"],
                        int(raw["ordinal"]), reuse_mode,
                    ),
                )
                connection.execute(
                    "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,'contains',%s,%s)",
                    (UUID(new_uuid7()), candidate_uuid, element_id, Jsonb({"slot": raw["slot"], "reuse_mode": reuse_mode})),
                )
            if parent_candidate_id is not None:
                connection.execute(
                    "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,'derived_from',%s,%s)",
                    (UUID(new_uuid7()), candidate_uuid, UUID(parent_candidate_id), Jsonb({"generation_kind": generation_kind})),
                )
            if render is not None:
                connection.execute(
                    "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,'contains',%s,%s)",
                    (UUID(new_uuid7()), candidate_uuid, UUID(recipe["recipe_id"]), Jsonb({"artifact": "composition_recipe"})),
                )
                connection.execute(
                    "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,'contains',%s,%s)",
                    (UUID(new_uuid7()), candidate_uuid, UUID(render["render_id"]), Jsonb({"artifact": "exact_render"})),
                )
            else:
                connection.execute(
                    """INSERT INTO content_candidate_previews(
                           candidate_id,mime_type,width,height,bytes,bytes_sha256,renderer_version
                       ) VALUES(%s,'image/jpeg',1080,1080,%s,%s,%s)""",
                    (candidate_uuid, preview["bytes"], preview["sha256"], preview["renderer_version"]),
                )
            media_source = materialized.get("media_source")
            if media_source is not None:
                media_id = UUID(str(media_source["source_asset_id"]))
                for source, attributes in (
                    (candidate_uuid, {"input": "resolved_media_source"}),
                    (UUID(run_id), {"input": "used_project_source"}),
                ):
                    connection.execute(
                        "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) "
                        "VALUES(%s,%s,'derived_from',%s,%s) "
                        "ON CONFLICT(source_id,relation,target_id) DO NOTHING",
                        (UUID(new_uuid7()), source, media_id, Jsonb(attributes)),
                    )
            budget[budget_key] = int(budget[budget_key]) - 1
            connection.execute(
                "UPDATE content_generation_runs SET budget_state=%s,updated_at=clock_timestamp() WHERE entity_id=%s",
                (Jsonb(budget), UUID(run_id)),
            )
        return self.get_candidate(candidate_id)

    def candidate_preview_metadata(self, candidate_id: str) -> dict[str, Any]:
        with self.authority.connection() as connection:
            row = connection.execute(
                """SELECT candidate.run_id,
                          COALESCE(render.bytes_sha256,preview.bytes_sha256),
                          COALESCE(render.mime_type,preview.mime_type),
                          COALESCE(render.width,preview.width),
                          COALESCE(render.height,preview.height)
                     FROM content_candidates candidate
                     LEFT JOIN studio_renders render ON render.entity_id=candidate.render_id
                     LEFT JOIN content_candidate_previews preview ON preview.candidate_id=candidate.entity_id
                    WHERE candidate.entity_id=%s""",
                (UUID(candidate_id),),
            ).fetchone()
        if row is None or row[1] is None:
            raise KeyError(candidate_id)
        return {
            "run_id": str(row[0]), "sha256": row[1], "mime_type": row[2],
            "width": int(row[3]), "height": int(row[4]),
        }

    def candidate_preview(self, candidate_id: str, *, expected_run_id: str | None = None) -> dict[str, Any]:
        metadata = self.candidate_preview_metadata(candidate_id)
        if expected_run_id is not None and metadata["run_id"] != expected_run_id:
            raise KeyError(candidate_id)
        with self.authority.connection() as connection:
            row = connection.execute(
                "SELECT render_id FROM content_candidates WHERE entity_id=%s",
                (UUID(candidate_id),),
            ).fetchone()
        if row is None:
            raise KeyError(candidate_id)
        if row[0] is not None:
            value = self.authority.render_asset(str(row[0]))
            return {
                "bytes": value["bytes"], "sha256": value["sha256"], "mime_type": value["mime_type"],
                "width": 1080, "height": 1080,
            }
        with self.authority.connection() as connection:
            row = connection.execute(
                "SELECT bytes,bytes_sha256,mime_type,width,height FROM content_candidate_previews WHERE candidate_id=%s",
                (UUID(candidate_id),),
            ).fetchone()
        if row is None:
            raise KeyError(candidate_id)
        return {
            "bytes": bytes(row[0]), "sha256": row[1], "mime_type": row[2],
            "width": int(row[3]), "height": int(row[4]),
        }

    def reserve_critic_pass(self, run_id: str, pass_number: int) -> str:
        if pass_number not in {1, 2, 3}:
            raise ValueError("critic pass number must be one, two, or three")
        with self.authority.connection() as connection:
            existing = connection.execute(
                "SELECT entity_id FROM content_critic_passes WHERE run_id=%s AND pass_number=%s",
                (UUID(run_id), pass_number),
            ).fetchone()
            if existing is not None:
                return str(existing[0])
            row = connection.execute(
                "SELECT critic_pass_ids[%s] FROM content_generation_runs WHERE entity_id=%s",
                (pass_number, UUID(run_id)),
            ).fetchone()
        if row is None or row[0] is None:
            raise KeyError(run_id)
        return str(row[0])

    def persist_critic_pass(
        self, *, pass_id: str, run_id: str, value: Mapping[str, Any],
        provider_provenance: Mapping[str, Any],
    ) -> dict[str, Any]:
        from psycopg.types.json import Jsonb

        active_ids = [UUID(item) for item in value["ranking"]]
        by_id = {item["candidate_id"]: item for item in value["evaluations"]}
        hard_gates = {candidate_id: by_id[candidate_id]["hard_gates"] for candidate_id in value["ranking"]}
        element_scores = {candidate_id: by_id[candidate_id]["element_scores"] for candidate_id in value["ranking"]}
        candidate_scores = {candidate_id: {
            "scores": by_id[candidate_id]["scores"],
            "complexity": by_id[candidate_id]["complexity"],
            "weighted_total": by_id[candidate_id]["weighted_total"],
            "eligible": by_id[candidate_id]["eligible"],
            "reason_codes": by_id[candidate_id]["reason_codes"],
        } for candidate_id in value["ranking"]}
        with self.authority.connection() as connection:
            budget_row = connection.execute(
                "SELECT budget_state FROM content_generation_runs WHERE entity_id=%s FOR UPDATE",
                (UUID(run_id),),
            ).fetchone()
            if budget_row is None:
                raise KeyError(run_id)
            budget = dict(budget_row[0])
            if int(budget.get("critic_calls_remaining", 0)) < 1:
                raise ValueError("Result run budget exhausted: critic_calls_remaining")
            connection.execute(
                """INSERT INTO content_critic_passes(
                       entity_id,run_id,pass_number,active_candidate_ids,hard_gates,element_scores,
                       candidate_scores,ranking,pairwise_results,observations,provider_provenance,response_sha256
                       ,final_selection
                   ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    UUID(pass_id), UUID(run_id), int(value["pass"]), active_ids,
                    Jsonb(hard_gates), Jsonb(element_scores), Jsonb(candidate_scores), active_ids,
                    Jsonb(value["pairwise"]), Jsonb(value["observations"]),
                    Jsonb(dict(provider_provenance)), sha256_json(value),
                    None if value["final_selection"] is None else Jsonb(value["final_selection"]),
                ),
            )
            for candidate_id in active_ids:
                connection.execute(
                    "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,'evaluates',%s,%s)",
                    (UUID(new_uuid7()), UUID(pass_id), candidate_id, Jsonb({"scope": "candidate"})),
                )
                for element_id in element_scores[str(candidate_id)]:
                    connection.execute(
                        "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) "
                        "VALUES(%s,%s,'evaluates',%s,%s) ON CONFLICT(source_id,relation,target_id) DO NOTHING",
                        (
                            UUID(new_uuid7()), UUID(pass_id), UUID(element_id),
                            Jsonb({"scope": "element", "candidate_id": str(candidate_id)}),
                        ),
                    )
            for ordinal, action in enumerate(value["actions"]):
                action_id = UUID(new_uuid7())
                reserved_candidate_id = (
                    None if action["action_type"] == "discard" else UUID(new_uuid7())
                )
                connection.execute(
                    "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'content_improvement_action',%s)",
                    (action_id, Jsonb({"action_type": action["action_type"]})),
                )
                if reserved_candidate_id is not None:
                    connection.execute(
                        "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'content_candidate',%s)",
                        (reserved_candidate_id, Jsonb({
                            "reserved": True, "improvement_action_id": str(action_id),
                        })),
                    )
                    connection.execute(
                        "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,'contains',%s,%s)",
                        (UUID(new_uuid7()), UUID(run_id), reserved_candidate_id, Jsonb({
                            "member": "reserved_improvement_candidate", "action_id": str(action_id),
                        })),
                    )
                current = None
                if action.get("base_candidate_id"):
                    current = self.get_candidate(action["base_candidate_id"])["parameters"]
                deltas = None
                if action.get("slider_values") is not None and current is not None:
                    deltas = {
                        name: [current[name], action["slider_values"][name]]
                        for name in SLIDER_NAMES if current[name] != action["slider_values"][name]
                    }
                connection.execute(
                    """INSERT INTO content_improvement_actions(
                           entity_id,run_id,critic_pass_id,ordinal,action_type,base_candidate_id,
                           locked_element_ids,target_element_ids,source_element_ids,parameter_deltas,
                           command,reserved_candidate_id,status
                       ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'queued')""",
                    (
                        action_id, UUID(run_id), UUID(pass_id), ordinal, action["action_type"],
                        None if action.get("base_candidate_id") is None else UUID(action["base_candidate_id"]),
                        [UUID(item) for item in action["locked_element_ids"]],
                        [UUID(item) for item in action["target_element_ids"]],
                        [UUID(item) for item in action["source_element_ids"]],
                        None if deltas is None else Jsonb(deltas), Jsonb(action), reserved_candidate_id,
                    ),
                )
                connection.execute(
                    "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,'contains',%s,%s)",
                    (UUID(new_uuid7()), UUID(pass_id), action_id, Jsonb({"member": "improvement_action", "ordinal": ordinal})),
                )
            budget["critic_calls_remaining"] = int(budget["critic_calls_remaining"]) - 1
            connection.execute(
                "UPDATE content_generation_runs SET budget_state=%s,updated_at=clock_timestamp() WHERE entity_id=%s",
                (Jsonb(budget), UUID(run_id)),
            )
        return {"pass_id": pass_id, **dict(value)}

    def list_actions(self, pass_id: str) -> list[dict[str, Any]]:
        with self.authority.connection() as connection:
            rows = connection.execute(
                """SELECT entity_id,run_id,critic_pass_id,ordinal,action_type,base_candidate_id,
                          locked_element_ids,target_element_ids,source_element_ids,parameter_deltas,
                          command,reserved_candidate_id,status,output_candidate_id,failure,
                          created_at,updated_at,completed_at
                     FROM content_improvement_actions WHERE critic_pass_id=%s ORDER BY ordinal""",
                (UUID(pass_id),),
            ).fetchall()
        return [{
            "action_id": str(row[0]), "run_id": str(row[1]), "pass_id": str(row[2]),
            "ordinal": int(row[3]), "action_type": row[4],
            "base_candidate_id": None if row[5] is None else str(row[5]),
            "locked_element_ids": [str(item) for item in row[6]],
            "target_element_ids": [str(item) for item in row[7]],
            "source_element_ids": [str(item) for item in row[8]],
            "parameter_deltas": None if row[9] is None else dict(row[9]),
            "command": dict(row[10]),
            "reserved_candidate_id": None if row[11] is None else str(row[11]),
            "status": row[12],
            "output_candidate_id": None if row[13] is None else str(row[13]),
            "failure": None if row[14] is None else dict(row[14]),
            "created_at": row[15].isoformat(), "updated_at": row[16].isoformat(),
            "completed_at": None if row[17] is None else row[17].isoformat(),
        } for row in rows]

    def get_critic_pass(self, run_id: str, pass_number: int) -> dict[str, Any] | None:
        with self.authority.connection() as connection:
            row = connection.execute(
                """SELECT entity_id,active_candidate_ids,hard_gates,element_scores,candidate_scores,
                          ranking,pairwise_results,observations,provider_provenance,response_sha256,
                          final_selection,created_at
                     FROM content_critic_passes WHERE run_id=%s AND pass_number=%s""",
                (UUID(run_id), pass_number),
            ).fetchone()
        if row is None:
            return None
        ranking = [str(item) for item in row[5]]
        hard_gates, element_scores, candidate_scores = dict(row[2]), dict(row[3]), dict(row[4])
        evaluations = []
        for candidate_id in ranking:
            score = dict(candidate_scores[candidate_id])
            evaluations.append({
                "candidate_id": candidate_id,
                "hard_gates": dict(hard_gates[candidate_id]),
                "element_scores": dict(element_scores[candidate_id]),
                "scores": dict(score["scores"]), "complexity": score["complexity"],
                "weighted_total": int(score["weighted_total"]),
                "eligible": bool(score["eligible"]),
                "reason_codes": list(score["reason_codes"]),
            })
        return {
            "pass_id": str(row[0]), "pass": pass_number,
            "active_candidate_ids": [str(item) for item in row[1]],
            "evaluations": evaluations, "ranking": ranking,
            "pairwise": list(row[6]), "observations": list(row[7]),
            "provider_provenance": dict(row[8]), "response_sha256": row[9],
            "final_selection": None if row[10] is None else dict(row[10]),
            "created_at": row[11].isoformat(), "actions": self.list_actions(str(row[0])),
        }

    def start_action(self, action_id: str) -> None:
        with self.authority.connection() as connection:
            changed = connection.execute(
                "UPDATE content_improvement_actions SET status='executing',updated_at=clock_timestamp() WHERE entity_id=%s AND status='queued'",
                (UUID(action_id),),
            ).rowcount
            current = connection.execute(
                "SELECT status FROM content_improvement_actions WHERE entity_id=%s", (UUID(action_id),),
            ).fetchone()
        if changed != 1 and (current is None or current[0] != "executing"):
            raise ValueError("Result improvement action is not queued")

    def discard_action(self, action_id: str, *, reason: str) -> None:
        with self.authority.connection() as connection:
            changed = connection.execute(
                """UPDATE content_improvement_actions SET status='discarded',
                          updated_at=clock_timestamp(),completed_at=clock_timestamp()
                    WHERE entity_id=%s AND status IN ('queued','executing')""",
                (UUID(action_id),),
            ).rowcount
        if changed != 1:
            raise ValueError(f"Result improvement action cannot be discarded: {reason[:300]}")

    def finish_action(
        self, action_id: str, *, output_candidate_id: str | None = None, error: Exception | None = None,
    ) -> None:
        from psycopg.types.json import Jsonb

        if (output_candidate_id is None) == (error is None):
            raise ValueError("action completion requires exactly one output candidate or failure")
        with self.authority.connection() as connection:
            changed = connection.execute(
                """UPDATE content_improvement_actions SET status=%s,output_candidate_id=%s,failure=%s,
                          updated_at=clock_timestamp(),completed_at=clock_timestamp()
                    WHERE entity_id=%s AND status='executing'""",
                (
                    "completed" if error is None else "failed",
                    None if output_candidate_id is None else UUID(output_candidate_id),
                    None if error is None else Jsonb({"code": type(error).__name__, "message": str(error)[:1000]}),
                    UUID(action_id),
                ),
            ).rowcount
        if changed != 1:
            raise ValueError("Result improvement action is not executing")

    def finalize(
        self, run_id: str, *, selected_candidate_id: str, decision_summary: Sequence[str],
    ) -> dict[str, Any]:
        from psycopg.types.json import Jsonb

        candidate = self.get_candidate(selected_candidate_id)
        if candidate["run_id"] != run_id:
            raise ValueError("final candidate does not belong to this Result run")
        elements = candidate["elements"]
        final_map = {
            f"F1.{item['slot'].upper()}.{item['ordinal'] + 1:02d}": {
                "element_id": item["element_id"], "source_alias": item["display_alias"],
                "mode": item["reuse_mode"],
            } for item in elements
        }
        summary = [str(item).strip() for item in decision_summary]
        if not 2 <= len(summary) <= 4 or any(not 1 <= len(item) <= 300 for item in summary):
            raise ValueError("final Result summary requires two to four concise observations")
        creative_id = UUID(new_uuid7())
        result_document = {
            "schema_version": 1, "selected_candidate_id": selected_candidate_id,
            "content": candidate["document"], "final_element_map": final_map,
            "decision_summary": summary, "recipe_id": candidate["recipe_id"],
            "render_id": candidate["render_id"],
        }
        with self.authority.connection() as connection:
            run = connection.execute(
                "SELECT status FROM content_generation_runs WHERE entity_id=%s FOR UPDATE",
                (UUID(run_id),),
            ).fetchone()
            if run is None:
                raise KeyError(run_id)
            if run[0] not in {"queued", "generating"}:
                raise ValueError("Result run is already terminal")
            connection.execute(
                "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'content_result',%s)",
                (creative_id, Jsonb({"schema_version": 1, "artifact_type": "creative"})),
            )
            connection.execute(
                """INSERT INTO content_results(
                       creative_id,run_id,selected_candidate_id,recipe_id,render_id,
                       final_element_map,decision_summary,result_sha256
                   ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    creative_id, UUID(run_id), UUID(selected_candidate_id),
                    None if candidate["recipe_id"] is None else UUID(candidate["recipe_id"]),
                    None if candidate["render_id"] is None else UUID(candidate["render_id"]),
                    Jsonb(final_map), Jsonb(summary), sha256_json(result_document),
                ),
            )
            connection.execute(
                """UPDATE content_generation_runs SET status='completed',current_stage='completed',
                          final_result_id=%s,updated_at=clock_timestamp(),completed_at=clock_timestamp()
                    WHERE entity_id=%s""",
                (creative_id, UUID(run_id)),
            )
            edges = [
                (UUID(run_id), "contains", creative_id, {"member": "final_result_creative"}),
                (creative_id, "derived_from", UUID(selected_candidate_id), {"input": "selected_candidate"}),
                *[(creative_id, "derived_from", UUID(item["element_id"]), {
                    "input": "final_element", "alias": item["display_alias"], "reuse_mode": item["reuse_mode"],
                }) for item in elements],
            ]
            for source, relation, target, attributes in edges:
                connection.execute(
                    "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,%s,%s,%s)",
                    (UUID(new_uuid7()), source, relation, target, Jsonb(attributes)),
                )
        return self.get_result(run_id)

    def fail_run(self, run_id: str, error: Exception) -> dict[str, Any]:
        with self.authority.connection() as connection:
            connection.execute(
                """UPDATE content_generation_runs SET status='failed',current_stage='failed',
                          error_code=%s,error_message=%s,updated_at=clock_timestamp()
                    WHERE entity_id=%s AND status IN ('queued','generating')""",
                (type(error).__name__, str(error)[:1000], UUID(run_id)),
            )
        self.checkpoint(run_id, stage="failed", target_id=None, payload={
            "error_code": type(error).__name__, "error_message": str(error)[:1000],
        })
        return self.get_run(run_id)

    def get_result(self, run_id: str) -> dict[str, Any]:
        with self.authority.connection() as connection:
            row = connection.execute(
                """SELECT result.creative_id,result.run_id,result.selected_candidate_id,
                          result.recipe_id,result.render_id,result.final_element_map,
                          result.decision_summary,result.result_sha256,result.created_at,
                          candidate.document,candidate.document_sha256,render.bytes_sha256
                     FROM content_results result
                     JOIN content_candidates candidate ON candidate.entity_id=result.selected_candidate_id
                     LEFT JOIN studio_renders render ON render.entity_id=result.render_id
                    WHERE result.run_id=%s""",
                (UUID(run_id),),
            ).fetchone()
        if row is None:
            raise KeyError(run_id)
        return {
            "creative_id": str(row[0]), "run_id": str(row[1]),
            "selected_candidate_id": str(row[2]),
            "recipe_id": None if row[3] is None else str(row[3]),
            "render_id": None if row[4] is None else str(row[4]),
            "final_element_map": dict(row[5]), "decision_summary": list(row[6]),
            "result_sha256": row[7], "created_at": row[8].isoformat(),
            "content": dict(row[9]), "content_sha256": row[10],
            "asset_sha256": row[11],
            "asset_url": None if row[4] is None else f"/api/v1/content-runs/{run_id}/result/asset",
        }

    def result_asset(self, run_id: str) -> dict[str, Any]:
        result = self.get_result(run_id)
        if not result["render_id"]:
            raise KeyError(run_id)
        return self.authority.render_asset(result["render_id"])

    def record_feedback(
        self, run_id: str, *, decision: str, comment: str | None, requested_by: str,
    ) -> dict[str, Any]:
        from psycopg.types.json import Jsonb

        if decision not in {"accepted", "rejected"}:
            raise ValueError("Result feedback decision must be accepted or rejected")
        normalized = "" if comment is None else comment.strip()
        if len(normalized) > 2000:
            raise ValueError("Result feedback comment must contain at most 2000 characters")
        result = self.get_result(run_id)
        creative_id = UUID(result["creative_id"])
        feedback_id, weight_id, outcome_id = (UUID(new_uuid7()) for _ in range(3))
        instruction = normalized or ("Owner accepted the Result." if decision == "accepted" else "Owner rejected the Result.")
        lesson = (
            f"Review the {decision} Result and generalize the owner comment without copying artifact details: "
            f"{instruction}"
        )[:500]
        with self.authority.connection() as connection:
            for entity_id, kind, attributes in (
                (feedback_id, "human_feedback", {"domain": "content_result", "decision": decision}),
                (weight_id, "weight_update", {"component": "content_result", "delta": 0}),
                (outcome_id, "content_outcome", {"event_type": decision}),
            ):
                connection.execute(
                    "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,%s,%s)",
                    (entity_id, kind, Jsonb(attributes)),
                )
            connection.execute(
                """INSERT INTO commander_human_feedback(
                       entity_id,target_id,domain,section_id,instruction,actor
                   ) VALUES(%s,%s,'content_result','overall',%s,%s)""",
                (feedback_id, creative_id, instruction, requested_by),
            )
            connection.execute(
                """INSERT INTO commander_weight_updates(entity_id,feedback_id,component,delta,reason)
                   VALUES(%s,%s,'content_result',0,'Owner Result feedback requires reviewed skill proposals')""",
                (weight_id, feedback_id),
            )
            connection.execute(
                """INSERT INTO content_generation_outcomes(
                       entity_id,run_id,creative_id,event_type,payload,source_type,source_id
                   ) VALUES(%s,%s,%s,%s,%s,'owner',%s)""",
                (outcome_id, UUID(run_id), creative_id, decision, Jsonb({"comment": normalized}), requested_by),
            )
            proposal_ids: list[str] = []
            for target_skill in ("content-candidate-generator", "content-result-critic"):
                proposal_id = UUID(new_uuid7())
                proposal_ids.append(str(proposal_id))
                connection.execute(
                    """INSERT INTO content_generation_skill_proposals(
                           id,feedback_id,creative_id,target_skill,lesson,status
                       ) VALUES(%s,%s,%s,%s,%s,'pending')""",
                    (proposal_id, feedback_id, creative_id, target_skill, lesson),
                )
            for source, relation, target, attributes in (
                (feedback_id, "evaluates", creative_id, {"decision": decision}),
                (feedback_id, "contains", weight_id, {"member": "zero_delta_weight_update"}),
                (weight_id, "adjusts", feedback_id, {"delta": 0}),
                (UUID(run_id), "contains", outcome_id, {"member": "content_outcome"}),
            ):
                connection.execute(
                    "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,%s,%s,%s)",
                    (UUID(new_uuid7()), source, relation, target, Jsonb(attributes)),
                )
        return {
            "feedback_id": str(feedback_id), "creative_id": str(creative_id),
            "weight_update_id": str(weight_id), "outcome_id": str(outcome_id),
            "proposal_ids": proposal_ids, "decision": decision,
        }

    def record_outcome(
        self, run_id: str, *, event_type: str, requested_by: str,
    ) -> dict[str, Any]:
        from psycopg.types.json import Jsonb

        if event_type not in {"downloaded", "used"}:
            raise ValueError("only download/use Result events are owner-recordable")
        result = self.get_result(run_id)
        outcome_id = UUID(new_uuid7())
        with self.authority.connection() as connection:
            connection.execute(
                "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'content_outcome',%s)",
                (outcome_id, Jsonb({"event_type": event_type})),
            )
            connection.execute(
                """INSERT INTO content_generation_outcomes(
                       entity_id,run_id,creative_id,event_type,payload,source_type,source_id
                   ) VALUES(%s,%s,%s,%s,'{}'::jsonb,'owner',%s)""",
                (outcome_id, UUID(run_id), UUID(result["creative_id"]), event_type, requested_by),
            )
            connection.execute(
                "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,'contains',%s,%s)",
                (UUID(new_uuid7()), UUID(run_id), outcome_id, Jsonb({"member": "content_outcome"})),
            )
        return {"outcome_id": str(outcome_id), "creative_id": result["creative_id"], "event_type": event_type}

    def debug(self, run_id: str) -> dict[str, Any]:
        run = self.get_run(run_id)
        candidates = self.list_candidates(run_id)
        for candidate in candidates:
            preview = self.candidate_preview_metadata(candidate["candidate_id"])
            candidate["preview"] = {
                "asset_url": (
                    f"/api/v1/content-runs/{run_id}/candidates/"
                    f"{candidate['candidate_id']}/asset"
                ),
                "sha256": preview["sha256"], "mime_type": preview["mime_type"],
                "width": preview["width"], "height": preview["height"],
            }
        with self.authority.connection() as connection:
            passes = connection.execute(
                """SELECT entity_id,pass_number,active_candidate_ids,hard_gates,element_scores,
                          candidate_scores,ranking,pairwise_results,observations,provider_provenance,
                          response_sha256,created_at,final_selection
                     FROM content_critic_passes WHERE run_id=%s ORDER BY pass_number""",
                (UUID(run_id),),
            ).fetchall()
            checkpoints = connection.execute(
                """SELECT sequence,stage,target_id,payload,payload_sha256,created_at
                     FROM content_generation_checkpoints WHERE run_id=%s ORDER BY sequence LIMIT 200""",
                (UUID(run_id),),
            ).fetchall()
            graph = connection.execute(
                """SELECT source_id,relation,target_id,attributes,created_at
                     FROM commander_relationships
                    WHERE source_id=%s OR source_id IN (
                        SELECT entity_id FROM content_candidates WHERE run_id=%s
                    ) OR source_id IN (
                        SELECT entity_id FROM content_critic_passes WHERE run_id=%s
                    ) ORDER BY created_at LIMIT 500""",
                (UUID(run_id), UUID(run_id), UUID(run_id)),
            ).fetchall()
        return {
            "run": run,
            "context": {
                "context_sha256": run["context_sha256"],
                "template_versions": run["context_bundle"]["template_versions"],
                "tool_catalog_sha256": run["context_bundle"]["tool_catalog_sha256"],
                "versions": run["context_bundle"]["versions"],
                "candidate_example_ids": {
                    template_id: value["writing"]["example_ids"]
                    for template_id, value in run["context_bundle"]["candidate_contexts"].items()
                },
            },
            "candidates": candidates,
            "critic_passes": [{
                "pass_id": str(row[0]), "pass_number": int(row[1]),
                "active_candidate_ids": [str(item) for item in row[2]],
                "hard_gates": dict(row[3]), "element_scores": dict(row[4]),
                "candidate_scores": dict(row[5]), "ranking": [str(item) for item in row[6]],
                "pairwise_results": list(row[7]), "observations": list(row[8]),
                "provider_provenance": dict(row[9]), "response_sha256": row[10],
                "created_at": row[11].isoformat(),
                "final_selection": None if row[12] is None else dict(row[12]),
                "actions": self.list_actions(str(row[0])),
            } for row in passes],
            "checkpoints": [{
                "sequence": int(row[0]), "stage": row[1],
                "target_id": None if row[2] is None else str(row[2]),
                "payload": dict(row[3]), "payload_sha256": row[4],
                "created_at": row[5].isoformat(),
            } for row in checkpoints],
            "graph": [{
                "source_id": str(row[0]), "relation": row[1], "target_id": str(row[2]),
                "attributes": dict(row[3]), "created_at": row[4].isoformat(),
            } for row in graph],
            "result": None if run["final_result_id"] is None else self.get_result(run_id),
        }

    def recoverable_runs(self) -> list[str]:
        with self.authority.connection() as connection:
            rows = connection.execute(
                """SELECT entity_id FROM content_generation_runs
                    WHERE status IN ('queued','generating') AND deadline_at > clock_timestamp()
                    ORDER BY created_at LIMIT 20"""
            ).fetchall()
            connection.execute(
                """UPDATE content_generation_runs SET status='failed',current_stage='failed',
                          error_code='DeadlineExceeded',error_message='Result run exceeded the 45-minute limit',
                          updated_at=clock_timestamp()
                    WHERE status IN ('queued','generating') AND deadline_at <= clock_timestamp()"""
            )
        return [str(row[0]) for row in rows]
