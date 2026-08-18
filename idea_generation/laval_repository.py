"""PostgreSQL repository for inspectable and restartable Idea Laval runs."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Mapping, Sequence

from commander.ids import new_uuid7

from .laval_domain import LavalConfig, STAGES, json_safe, stage_index
from .store import PostgresStore


def _markdown(value: Any, *, title: str = "Idea Laval artifact") -> str:
    lines = [f"# {title}", ""]
    if isinstance(value, Mapping):
        for key, item in value.items():
            lines.extend((f"## {str(key).replace('_', ' ').title()}", ""))
            if isinstance(item, (Mapping, list, tuple)):
                lines.extend(("```json", json.dumps(json_safe(item), ensure_ascii=False, indent=2), "```", ""))
            else:
                lines.extend((str(item), ""))
    elif isinstance(value, (list, tuple)):
        lines.extend(("```json", json.dumps(json_safe(value), ensure_ascii=False, indent=2), "```", ""))
    else:
        lines.append(str(value))
    return "\n".join(lines).rstrip() + "\n"


class LavalRepository:
    def __init__(self, store: PostgresStore) -> None:
        self.store = store

    def create_run(
        self, raw_text: str, config: LavalConfig, *, actor: str = "owner",
        evidence_mode: str = "demo_fixture", provider_snapshot: Mapping[str, Any] | None = None,
        max_spend_usd: float = .005, reserved_spend_usd: float = .004,
    ) -> dict[str, Any]:
        raw_text = raw_text.strip()
        if not raw_text or len(raw_text) > 100_000:
            raise ValueError("owner idea must contain 1-100000 characters")
        run_id, owner_id = new_uuid7(), new_uuid7()
        with self.store.transaction() as connection:
            mission = connection.execute(
                "SELECT id FROM missions WHERE is_active=TRUE LIMIT 1"
            ).fetchone()
            if not mission:
                raise RuntimeError("active mission is not seeded")
            connection.execute(
                """INSERT INTO laval_runs(
                       id,mission_id,status,current_stage,config,approval_mode,approval_gates,created_by,
                       evidence_mode,provider_snapshot,max_spend_usd,reserved_spend_usd
                   ) VALUES(%s,%s,'pending','OWNER_DNA',%s::jsonb,%s,%s,%s,%s,%s::jsonb,%s,%s)""",
                (
                    run_id,
                    mission[0],
                    self.store.json(config.to_dict()),
                    config.approval_mode,
                    list(config.approval_gates),
                    actor,
                    evidence_mode,
                    self.store.json(provider_snapshot or {}),
                    max_spend_usd,
                    reserved_spend_usd,
                ),
            )
            connection.execute(
                "INSERT INTO laval_owner_ideas(id,run_id,raw_text) VALUES(%s,%s,%s)",
                (owner_id, run_id, raw_text),
            )
            connection.execute(
                "UPDATE laval_runs SET owner_idea_id=%s WHERE id=%s", (owner_id, run_id)
            )
            for ordinal, stage in enumerate(STAGES):
                status = "completed" if ordinal == 0 else "pending"
                artifact = {"owner_idea_id": owner_id, "raw_text": raw_text} if ordinal == 0 else None
                connection.execute(
                    """INSERT INTO laval_stage_runs(
                           run_id,stage,ordinal,status,started_at,completed_at,input_hash,attempt,artifact
                       ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)""",
                    (
                        run_id,
                        stage,
                        ordinal,
                        status,
                        datetime.now(timezone.utc) if ordinal == 0 else None,
                        datetime.now(timezone.utc) if ordinal == 0 else None,
                        hashlib.sha256(raw_text.encode()).hexdigest() if ordinal == 0 else None,
                        1 if ordinal == 0 else 0,
                        self.store.json(artifact) if artifact is not None else None,
                    ),
                )
        self.save_artifact(run_id, "OWNER_CAPTURE", "owner.json", {"owner_idea_id": owner_id, "raw_text": raw_text})
        return {"run_id": run_id, "owner_idea_id": owner_id}

    def run(self, run_id: str) -> dict[str, Any]:
        row = self.store.fetchone("SELECT * FROM laval_runs WHERE id=%s", (run_id,))
        if not row:
            raise KeyError("Laval run not found")
        return json_safe(row)

    def owner(self, run_id: str) -> dict[str, Any]:
        row = self.store.fetchone("SELECT * FROM laval_owner_ideas WHERE run_id=%s", (run_id,))
        if not row:
            raise KeyError("Laval owner idea not found")
        return json_safe(row)

    def list_runs(self, limit: int = 30) -> list[dict[str, Any]]:
        rows = self.store.fetchall(
            """SELECT r.*,left(o.raw_text,240) owner_preview,
                      (SELECT count(*) FROM laval_stage_runs s WHERE s.run_id=r.id AND s.status='completed') completed_stages,
                      (SELECT count(*) FROM laval_idea_variants v WHERE v.run_id=r.id) variant_count
               FROM laval_runs r JOIN laval_owner_ideas o ON o.run_id=r.id
               ORDER BY r.created_at DESC LIMIT %s""",
            (min(max(limit, 1), 100),),
        )
        return json_safe(rows)

    def stages(self, run_id: str) -> list[dict[str, Any]]:
        return json_safe(self.store.fetchall(
            "SELECT * FROM laval_stage_runs WHERE run_id=%s ORDER BY ordinal", (run_id,)
        ))

    def stage(self, run_id: str, stage: str) -> dict[str, Any]:
        row = self.store.fetchone(
            "SELECT * FROM laval_stage_runs WHERE run_id=%s AND stage=%s",
            (run_id, stage.upper()),
        )
        if not row:
            raise KeyError("Laval stage not found")
        return json_safe(row)

    def status(self, run_id: str) -> dict[str, Any]:
        run = self.run(run_id)
        stages = self.stages(run_id)
        costs = self.cost(run_id)
        return {"run": run, "stages": stages, "cost": costs}

    def start_stage(
        self, run_id: str, stage: str, digest: str, *, provider: str = "", model: str = ""
    ) -> int:
        row = self.store.fetchone(
            """UPDATE laval_stage_runs SET status='running',started_at=NOW(),completed_at=NULL,
                      input_hash=%s,attempt=attempt+1,provider=%s,model=%s,error=NULL,updated_at=NOW()
               WHERE run_id=%s AND stage=%s RETURNING attempt""",
            (digest, provider or None, model or None, run_id, stage),
        )
        if not row:
            raise KeyError("Laval stage not found")
        self.store.execute(
            "UPDATE laval_runs SET status='running',current_stage=%s,error_text=NULL,updated_at=NOW() WHERE id=%s RETURNING 1",
            (stage, run_id),
        )
        return int(row["attempt"])

    def complete_stage(
        self, run_id: str, stage: str, artifact: Mapping[str, Any] | Sequence[Any], *, metrics: Mapping[str, Any] | None = None, partial: bool = False
    ) -> None:
        if artifact is None:
            raise ValueError("completed Laval stage requires an artifact")
        payload = json_safe(artifact)
        self.save_artifact(run_id, stage, f"{stage.lower()}.json", payload)
        self.save_artifact(run_id, stage, f"{stage.lower()}.md", _markdown(payload, title=stage.replace("_", " ").title()))
        stage_cost = self.store.fetchone(
            """SELECT COALESCE(sum(request_count),0) request_count,
                      COALESCE(sum(input_tokens),0) input_tokens,
                      COALESCE(sum(output_tokens),0) output_tokens,
                      COALESCE(sum(amount_usd),0)::float amount_usd,
                      count(*) FILTER (WHERE cached) cached_events
               FROM laval_cost_events WHERE run_id=%s AND stage=%s""",
            (run_id, stage),
        ) or {}
        stage_cost = {
            "request_count": int(stage_cost.get("request_count") or 0),
            "input_tokens": int(stage_cost.get("input_tokens") or 0),
            "output_tokens": int(stage_cost.get("output_tokens") or 0),
            "amount_usd": float(stage_cost.get("amount_usd") or 0),
            "cached_events": int(stage_cost.get("cached_events") or 0),
        }
        self.store.execute(
            """UPDATE laval_stage_runs SET status=%s,completed_at=NOW(),artifact=%s::jsonb,
                      cost=%s::jsonb,metrics=%s::jsonb,error=NULL,updated_at=NOW()
               WHERE run_id=%s AND stage=%s RETURNING 1""",
            ("partial" if partial else "completed", self.store.json(payload), self.store.json(json_safe(stage_cost)), self.store.json(metrics or {}), run_id, stage),
        )

    def fail_stage(self, run_id: str, stage: str, error: Exception) -> None:
        payload = {"type": type(error).__name__, "message": str(error)[:4000]}
        self.store.execute(
            "UPDATE laval_stage_runs SET status='failed',error=%s::jsonb,completed_at=NOW(),updated_at=NOW() WHERE run_id=%s AND stage=%s RETURNING 1",
            (self.store.json(payload), run_id, stage),
        )
        self.store.execute(
            "UPDATE laval_runs SET status='failed',current_stage=%s,error_text=%s,updated_at=NOW() WHERE id=%s RETURNING 1",
            (stage, payload["message"], run_id),
        )

    def pause(self, run_id: str) -> None:
        self.store.execute(
            "UPDATE laval_runs SET status='paused',updated_at=NOW() WHERE id=%s AND status NOT IN ('completed','cancelled') RETURNING 1",
            (run_id,),
        )

    def pause_all(self) -> None:
        self.store.execute(
            "UPDATE laval_runs SET status='paused',updated_at=NOW() WHERE status IN ('pending','running') RETURNING 1"
        )

    def ready(self, run_id: str, *, through_stage: str | None = None) -> None:
        if through_stage is not None:
            stage_index(through_stage)
        self.store.execute(
            "UPDATE laval_runs SET status='pending',through_stage=%s,error_text=NULL,updated_at=NOW() WHERE id=%s AND status NOT IN ('completed','cancelled') RETURNING 1",
            (through_stage, run_id),
        )

    def approval_required(self, run_id: str, stage: str, digest: str) -> bool:
        run = self.run(run_id)
        if run["approval_mode"] == "automatic" or stage not in (run.get("approval_gates") or []):
            return False
        row = self.store.fetchone(
            "SELECT 1 ok FROM laval_approvals WHERE run_id=%s AND stage=%s AND input_hash=%s",
            (run_id, stage, digest),
        )
        return row is None

    def approve(self, run_id: str, stage: str, *, actor: str) -> dict[str, Any]:
        stage_row = self.stage(run_id, stage)
        if stage_row["status"] not in {"completed", "partial"} or not stage_row.get("input_hash"):
            raise ValueError("only a completed current stage can be approved")
        approval_id = new_uuid7()
        self.store.execute(
            """INSERT INTO laval_approvals(id,run_id,stage,input_hash,actor)
               VALUES(%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING 1""",
            (approval_id, run_id, stage, stage_row["input_hash"], actor),
        )
        self.ready(run_id)
        return {"approval_id": approval_id, "stage": stage, "input_hash": stage_row["input_hash"]}

    def finish_run(self, run_id: str, *, paused: bool = False) -> None:
        status = "paused" if paused else "completed"
        self.store.execute(
            "UPDATE laval_runs SET status=%s,current_stage=%s,completed_at=%s,updated_at=NOW() WHERE id=%s RETURNING 1",
            (status, self.run(run_id).get("current_stage"), None if paused else datetime.now(timezone.utc), run_id),
        )

    def await_provider(self, run_id: str, reason: str) -> None:
        self.store.execute(
            "UPDATE laval_runs SET status='paused',awaiting_reason=%s,updated_at=NOW() WHERE id=%s RETURNING 1",
            (reason[:500], run_id),
        )

    def enable_live_trends(self, run_id: str, provider: str) -> None:
        self.store.execute(
            """UPDATE laval_runs SET evidence_mode='live_complete',awaiting_reason=NULL,
                      provider_snapshot=jsonb_set(provider_snapshot,'{trends}',to_jsonb(%s::text),TRUE),
                      updated_at=NOW()
               WHERE id=%s AND evidence_mode='live_search_pending_trends' RETURNING 1""",
            (provider, run_id),
        )

    def reserve_provider_task(
        self, run_id: str, stage: str, item_key: str, provider: str,
        request: Mapping[str, Any], estimated_cost: float,
    ) -> dict[str, Any]:
        with self.store.transaction() as connection:
            existing = connection.execute(
                "SELECT * FROM laval_provider_tasks WHERE run_id=%s AND stage=%s AND item_key=%s FOR UPDATE",
                (run_id, stage, item_key),
            ).fetchone()
            if existing:
                columns = [item.name for item in connection.execute(
                    "SELECT * FROM laval_provider_tasks WHERE id=%s", (existing[0],)
                ).description]
                return json_safe(dict(zip(columns, existing)))
            run = connection.execute(
                "SELECT reserved_spend_usd FROM laval_runs WHERE id=%s FOR UPDATE", (run_id,)
            ).fetchone()
            if not run:
                raise KeyError("Laval run not found")
            committed = connection.execute(
                "SELECT COALESCE(sum(CASE WHEN status='completed' THEN actual_cost_usd ELSE reserved_cost_usd END),0) FROM laval_provider_tasks WHERE run_id=%s AND status<>'failed'",
                (run_id,),
            ).fetchone()[0]
            if float(committed) + estimated_cost > float(run[0]) + 1e-9:
                raise RuntimeError("DataForSEO $0.005 run cap: the $0.004 reservation budget is exhausted")
            task_id = new_uuid7()
            connection.execute(
                """INSERT INTO laval_provider_tasks(
                       id,run_id,stage,item_key,provider,status,request,reserved_cost_usd
                   ) VALUES(%s,%s,%s,%s,%s,'reserved',%s::jsonb,%s)""",
                (task_id, run_id, stage, item_key, provider, self.store.json(request), estimated_cost),
            )
        return self.provider_task(run_id, stage, item_key)

    def provider_task(self, run_id: str, stage: str, item_key: str) -> dict[str, Any] | None:
        row = self.store.fetchone(
            "SELECT * FROM laval_provider_tasks WHERE run_id=%s AND stage=%s AND item_key=%s",
            (run_id, stage, item_key),
        )
        return json_safe(row) if row else None

    def submit_provider_task(self, task_id: str, remote_task_id: str, actual_cost: float) -> None:
        self.store.execute(
            """UPDATE laval_provider_tasks SET remote_task_id=%s,status='submitted',
                      actual_cost_usd=%s,updated_at=NOW() WHERE id=%s RETURNING 1""",
            (remote_task_id, actual_cost, task_id),
        )

    def complete_provider_task(self, task_id: str, response: Mapping[str, Any]) -> None:
        self.store.execute(
            "UPDATE laval_provider_tasks SET status='completed',response=%s::jsonb,error=NULL,updated_at=NOW() WHERE id=%s RETURNING 1",
            (self.store.json(response), task_id),
        )

    def fail_provider_task(self, task_id: str, error: Exception | str) -> None:
        error_type = type(error).__name__ if isinstance(error, Exception) else "ProviderError"
        self.store.execute(
            "UPDATE laval_provider_tasks SET status='failed',error=%s::jsonb,updated_at=NOW() WHERE id=%s RETURNING 1",
            (self.store.json({"type": error_type, "message": str(error)[:500]}), task_id),
        )

    def record_provider_cost_once(self, task_id: str, operation: str) -> bool:
        with self.store.transaction() as connection:
            row = connection.execute(
                """UPDATE laval_provider_tasks SET cost_recorded=TRUE,updated_at=NOW()
                   WHERE id=%s AND status='completed' AND cost_recorded=FALSE
                   RETURNING run_id,stage,provider,actual_cost_usd,remote_task_id""",
                (task_id,),
            ).fetchone()
            if not row:
                return False
            connection.execute(
                """INSERT INTO laval_cost_events(
                       id,run_id,stage,provider,operation,request_count,amount_usd,cached,metadata
                   ) VALUES(%s,%s,%s,%s,%s,1,%s,FALSE,%s::jsonb)""",
                (new_uuid7(), row[0], row[1], row[2], operation, row[3], self.store.json({"remote_task_id": row[4]})),
            )
        return True

    def save_artifact(self, run_id: str, stage: str, name: str, value: Any) -> str:
        artifact_id = new_uuid7()
        is_text = isinstance(value, str)
        encoded = value if is_text else json.dumps(json_safe(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        digest = hashlib.sha256(encoded.encode()).hexdigest()
        self.store.execute(
            """INSERT INTO laval_artifacts(id,run_id,stage,name,media_type,sha256,content,text_content)
               VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb,%s)
               ON CONFLICT(run_id,stage,name,sha256) DO UPDATE SET name=EXCLUDED.name RETURNING 1""",
            (
                artifact_id,
                run_id,
                stage,
                name,
                "text/markdown" if is_text else "application/json",
                digest,
                None if is_text else encoded,
                value if is_text else None,
            ),
        )
        return digest

    def stage_item(
        self,
        run_id: str,
        stage: str,
        item_key: str,
        *,
        status: str,
        payload: Mapping[str, Any] | None = None,
        country: str | None = None,
        provider: str | None = None,
        digest: str | None = None,
        error: Mapping[str, Any] | None = None,
    ) -> None:
        self.store.execute(
            """INSERT INTO laval_stage_items(
                   id,run_id,stage,item_key,country,status,input_hash,attempt,provider,payload,error,
                   started_at,completed_at,updated_at
               ) VALUES(%s,%s,%s,%s,%s,%s,%s,1,%s,%s::jsonb,%s::jsonb,NOW(),
                        CASE WHEN %s IN ('completed','partial','failed') THEN NOW() END,NOW())
               ON CONFLICT(run_id,stage,item_key) DO UPDATE SET
                   country=EXCLUDED.country,status=EXCLUDED.status,input_hash=EXCLUDED.input_hash,
                   attempt=CASE WHEN EXCLUDED.status='running' THEN laval_stage_items.attempt+1 ELSE laval_stage_items.attempt END,
                   provider=EXCLUDED.provider,payload=EXCLUDED.payload,
                   error=EXCLUDED.error,started_at=CASE WHEN EXCLUDED.status='running' THEN NOW() ELSE laval_stage_items.started_at END,
                   completed_at=CASE WHEN EXCLUDED.status IN ('completed','partial','failed') THEN NOW() ELSE NULL END,
                   updated_at=NOW() RETURNING 1""",
            (
                new_uuid7(), run_id, stage, item_key, country, status, digest, provider,
                self.store.json(payload or {}), self.store.json(error) if error else None, status,
            ),
        )

    def stage_items(self, run_id: str, stage: str, *, country: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM laval_stage_items WHERE run_id=%s AND stage=%s"
        params: tuple[Any, ...] = (run_id, stage)
        if country:
            sql += " AND country=%s"
            params += (country,)
        return json_safe(self.store.fetchall(sql + " ORDER BY item_key", params))

    def evidence(self, run_id: str, *, competitor_id: str | None = None, source_type: str | None = None) -> list[dict[str, Any]]:
        clauses, params = ["run_id=%s"], [run_id]
        if competitor_id:
            clauses.append("competitor_id=%s")
            params.append(competitor_id)
        if source_type:
            clauses.append("source_type=%s")
            params.append(source_type)
        return json_safe(self.store.fetchall(
            "SELECT * FROM laval_evidence WHERE " + " AND ".join(clauses) + " ORDER BY retrieved_at,id",
            tuple(params),
        ))

    def add_evidence(self, run_id: str, item: Mapping[str, Any]) -> str:
        evidence_id = str(item.get("id") or new_uuid7())
        self.store.execute(
            """INSERT INTO laval_evidence(
                   id,run_id,source_type,source_url,source_title,publisher,competitor_id,country,
                   excerpt,claim,confidence,metadata,commander_source_id
               ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s) RETURNING 1""",
            (
                evidence_id, run_id, item["source_type"], item["source_url"], item["source_title"],
                item.get("publisher", ""), item.get("competitor_id"), item.get("country"),
                str(item.get("excerpt", ""))[:10_000], str(item.get("claim", ""))[:10_000],
                float(item.get("confidence", .5)), self.store.json(item.get("metadata") or {}),
                item.get("commander_source_id"),
            ),
        )
        return evidence_id

    def link_commander_sources(self, mapping: Mapping[str, str]) -> None:
        for evidence_id, source_id in mapping.items():
            self.store.execute(
                "UPDATE laval_evidence SET commander_source_id=%s WHERE id=%s RETURNING 1",
                (source_id, evidence_id),
            )

    def add_lineage(
        self, run_id: str, source_kind: str, source_id: str, relation: str, target_kind: str, target_id: str, attributes: Mapping[str, Any] | None = None
    ) -> None:
        self.store.execute(
            """INSERT INTO laval_lineage_edges(
                   id,run_id,source_kind,source_id,relation,target_kind,target_id,attributes
               ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
               ON CONFLICT DO NOTHING RETURNING 1""",
            (new_uuid7(), run_id, source_kind, source_id, relation, target_kind, target_id, self.store.json(attributes or {})),
        )

    def record_cost(
        self, run_id: str, stage: str, provider: str, operation: str, *, requests: int = 1, input_tokens: int = 0, output_tokens: int = 0, amount_usd: float = 0, cached: bool = False, metadata: Mapping[str, Any] | None = None
    ) -> None:
        self.store.execute(
            """INSERT INTO laval_cost_events(
                   id,run_id,stage,provider,operation,request_count,input_tokens,output_tokens,amount_usd,cached,metadata
               ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb) RETURNING 1""",
            (new_uuid7(), run_id, stage, provider, operation, requests, input_tokens, output_tokens, amount_usd, cached, self.store.json(metadata or {})),
        )

    def cost(self, run_id: str) -> dict[str, Any]:
        rows = self.store.fetchall(
            """SELECT stage,provider,operation,sum(request_count) request_count,
                      sum(input_tokens) input_tokens,sum(output_tokens) output_tokens,
                      sum(amount_usd)::float amount_usd,count(*) FILTER (WHERE cached) cached_events
               FROM laval_cost_events WHERE run_id=%s GROUP BY stage,provider,operation ORDER BY stage,provider,operation""",
            (run_id,),
        )
        run = self.run(run_id)
        provider = self.store.fetchone(
            """SELECT COALESCE(sum(reserved_cost_usd),0)::float projected,
                      COALESCE(sum(reserved_cost_usd) FILTER (WHERE status<>'failed'),0)::float reserved,
                      COALESCE(sum(actual_cost_usd) FILTER (WHERE status<>'failed'),0)::float actual
               FROM laval_provider_tasks WHERE run_id=%s""",
            (run_id,),
        ) or {}
        return {
            "items": json_safe(rows),
            "total_usd": round(sum(float(item["amount_usd"] or 0) for item in rows), 6),
            "provider_projected_usd": round(float(provider.get("projected") or 0), 6),
            "provider_reserved_usd": round(float(provider.get("reserved") or 0), 6),
            "provider_actual_usd": round(float(provider.get("actual") or 0), 6),
            "max_spend_usd": float(run.get("max_spend_usd") or .005),
        }

    def override(
        self, run_id: str, override_type: str, target_id: str, action: str, *, reason: str, actor: str, payload: Mapping[str, Any] | None = None
    ) -> str:
        override_id = new_uuid7()
        self.store.execute(
            """INSERT INTO laval_overrides(id,run_id,override_type,target_id,action,reason,payload,actor)
               VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb,%s) RETURNING 1""",
            (override_id, run_id, override_type, target_id, action, reason, self.store.json(payload or {}), actor),
        )
        return override_id

    def invalidate_from(self, run_id: str, stage: str, *, country: str | None = None) -> None:
        index = stage_index(stage)
        if index <= stage_index("SERP_DISCOVERY"):
            if country:
                self.store.execute("DELETE FROM laval_stage_items WHERE run_id=%s AND stage='SERP_DISCOVERY' AND country=%s RETURNING 1", (run_id, country))
                self.store.execute("DELETE FROM laval_evidence WHERE run_id=%s AND source_type='serp' AND country=%s RETURNING 1", (run_id, country))
            else:
                self.store.execute("DELETE FROM laval_stage_items WHERE run_id=%s AND stage='SERP_DISCOVERY' RETURNING 1", (run_id,))
                self.store.execute("DELETE FROM laval_evidence WHERE run_id=%s AND source_type='serp' RETURNING 1", (run_id,))
        if index <= stage_index("COMPETITOR_SELECTION"):
            self.store.execute("DELETE FROM laval_competitor_country_rankings WHERE run_id=%s RETURNING 1", (run_id,))
            self.store.execute("DELETE FROM laval_competitors WHERE run_id=%s RETURNING 1", (run_id,))
        if index <= stage_index("COMPETITOR_EVIDENCE"):
            self.store.execute("DELETE FROM laval_stage_items WHERE run_id=%s AND stage='COMPETITOR_EVIDENCE' RETURNING 1", (run_id,))
            self.store.execute("DELETE FROM laval_evidence WHERE run_id=%s AND source_type<>'serp' RETURNING 1", (run_id,))
        if index <= stage_index("COMPETITOR_DOSSIERS"):
            self.store.execute("DELETE FROM laval_competitor_dossiers WHERE run_id=%s RETURNING 1", (run_id,))
        if index <= stage_index("OPPORTUNITY_MATRIX"):
            self.store.execute("DELETE FROM laval_opportunities WHERE run_id=%s RETURNING 1", (run_id,))
        if index <= stage_index("TREND_QUERY_PLAN"):
            self.store.execute("DELETE FROM laval_trend_queries WHERE run_id=%s RETURNING 1", (run_id,))
        if index <= stage_index("GOOGLE_TRENDS_RESEARCH"):
            self.store.execute("DELETE FROM laval_stage_items WHERE run_id=%s AND stage='GOOGLE_TRENDS_RESEARCH' RETURNING 1", (run_id,))
            self.store.execute("DELETE FROM laval_evidence WHERE run_id=%s AND source_type='trend' RETURNING 1", (run_id,))
        if index <= stage_index("TREND_GATE"):
            self.store.execute("DELETE FROM laval_trend_scores WHERE run_id=%s RETURNING 1", (run_id,))
            self.store.execute("DELETE FROM laval_trend_discoveries WHERE run_id=%s RETURNING 1", (run_id,))
        if index <= stage_index("IDEA_EXPANSION"):
            self.store.execute("DELETE FROM laval_idea_variants WHERE run_id=%s RETURNING 1", (run_id,))
        if index <= stage_index("IDEA_EVALUATION"):
            self.store.execute("DELETE FROM laval_idea_scores WHERE run_id=%s RETURNING 1", (run_id,))
        stages = STAGES[index:]
        self.store.execute(
            """UPDATE laval_stage_runs SET status=CASE WHEN stage=%s THEN 'pending' ELSE 'stale' END,
                      artifact=NULL,error=NULL,completed_at=NULL,updated_at=NOW()
               WHERE run_id=%s AND stage=ANY(%s) RETURNING 1""",
            (stage, run_id, list(stages)),
        )
        self.store.execute(
            "UPDATE laval_runs SET status='pending',current_stage=%s,completed_at=NULL,error_text=NULL,updated_at=NOW() WHERE id=%s RETURNING 1",
            (stage, run_id),
        )

    def show(self, run_id: str, stage: str, *, view: str | None = None, country: str | None = None) -> dict[str, Any]:
        row = self.stage(run_id, stage)
        artifact = row.get("artifact")
        if artifact is None:
            if row.get("status") in {"completed", "partial"}:
                raise ValueError("artifact_missing: completed stage has no persisted artifact")
            return {"stage": row, "output": None, "items": self.stage_items(run_id, stage, country=country)}
        if view:
            if not isinstance(artifact, Mapping) or view not in artifact:
                raise KeyError(f"view {view!r} is not available")
            artifact = artifact[view]
        if country:
            code = country.upper()
            if isinstance(artifact, Mapping):
                if code in artifact:
                    artifact = artifact[code]
                else:
                    filtered = [item for item in artifact.get("items", []) if str(item.get("country", "")).upper() == code] if isinstance(artifact.get("items"), list) else []
                    artifact = {**artifact, "items": filtered, "country": code}
            elif isinstance(artifact, list):
                artifact = [item for item in artifact if isinstance(item, Mapping) and str(item.get("country", "")).upper() == code]
        return {"stage": row, "output": json_safe(artifact), "items": self.stage_items(run_id, stage, country=country)}

    def export(self, run_id: str, *, stage: str | None = None, format: str = "json") -> tuple[str, str, str]:
        if format not in {"json", "md"}:
            raise ValueError("export format must be json or md")
        if stage:
            payload: Any = self.show(run_id, stage)["output"]
            stem = stage.lower()
        else:
            run = self.run(run_id)
            payload = {
                "evidence_notice": {
                    "mode": run.get("evidence_mode", "demo_fixture"),
                    "label": {
                        "demo_fixture": "DEMO — NO LIVE RESEARCH",
                        "live_search_pending_trends": "LIVE SEARCH — WAITING FOR TRENDS",
                        "live_complete": "LIVE COMPLETE",
                    }.get(run.get("evidence_mode"), "DEMO — NO LIVE RESEARCH"),
                    "providers": run.get("provider_snapshot") or {},
                    "warning": "DEMO — NO LIVE RESEARCH" if run.get("evidence_mode") == "demo_fixture" else None,
                },
                "stages": {item["stage"]: item.get("artifact") for item in self.stages(run_id)},
            }
            stem = "all"
        if format == "json":
            content = json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n"
            return f"laval-{run_id}-{stem}.json", "application/json", content
        return f"laval-{run_id}-{stem}.md", "text/markdown; charset=utf-8", _markdown(payload, title=f"Idea Laval {stem}")
