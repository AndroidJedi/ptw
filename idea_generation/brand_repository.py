"""Durable projections for restartable Branding v1 runs."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from commander.ids import new_uuid7

from .brand_domain import BRAND_PIPELINE_VERSION, BRAND_STAGES, public_https_url, stable_hash
from .laval_domain import json_safe
from .store import PostgresStore


class BrandRepository:
    def __init__(self, store: PostgresStore) -> None:
        self.store = store

    def _snapshot(self, laval_run_id: str) -> dict[str, Any]:
        run = self.store.fetchone(
            "SELECT * FROM laval_runs WHERE id=%s", (laval_run_id,)
        )
        if not run:
            raise KeyError("completed Idea case not found")
        if run["status"] != "completed" or run["evidence_mode"] == "demo_fixture":
            raise ValueError("Branding requires a completed live Idea case")
        if run.get("pipeline_version") != "mechanism_thesis_v1":
            raise ValueError("Branding requires a completed mechanism/thesis Idea case")
        owner = self.store.fetchone("SELECT * FROM laval_owner_ideas WHERE run_id=%s", (laval_run_id,))
        theses = self.store.fetchall(
            """SELECT * FROM laval_product_theses
               WHERE run_id=%s
               ORDER BY recommended DESC,
                        CASE verdict WHEN 'survives' THEN 0 WHEN 'weak' THEN 1 ELSE 2 END,
                        created_at,id""",
            (laval_run_id,),
        )
        mechanism_ids = list(dict.fromkeys(str(value) for thesis in theses for value in thesis.get("mechanism_ids") or []))
        mechanisms = self.store.fetchall(
            "SELECT * FROM laval_product_mechanisms WHERE id=ANY(%s::uuid[]) ORDER BY mechanism_type,id",
            (mechanism_ids,),
        ) if mechanism_ids else []
        competitors = self.store.fetchall(
            """SELECT id,name,domain,url,result_type,score,components
               FROM laval_competitors WHERE run_id=%s AND selected
               ORDER BY score DESC,id""",
            (laval_run_id,),
        )
        evidence = self.store.fetchall(
            """SELECT id,source_type,source_url,source_title,publisher,claim,excerpt,
                      confidence,metadata,commander_source_id
               FROM laval_evidence WHERE run_id=%s
               ORDER BY confidence DESC,retrieved_at,id""",
            (laval_run_id,),
        )
        observations = self.store.fetchall(
            """SELECT id,observation_type,statement,video_ids,evidence_ids,confidence,
                      independent_creator_count
               FROM laval_behavior_observations WHERE run_id=%s
               ORDER BY confidence DESC,id""",
            (laval_run_id,),
        )
        quality = self.store.fetchone(
            """SELECT count(*) FILTER (WHERE result_status='success')::int successful,
                      count(*)::int attempted
               FROM laval_llm_invocations WHERE run_id=%s""",
            (laval_run_id,),
        ) or {"successful": 0, "attempted": 0}
        return json_safe({
            "idea_run_id": laval_run_id,
            "owner_idea": str((owner or {}).get("raw_text") or ""),
            "theses": theses,
            "mechanisms": mechanisms,
            "competitors": competitors,
            "evidence": evidence,
            "behavior_observations": observations,
            "quality": quality,
            "recommended_thesis_id": next((str(item["id"]) for item in theses if item.get("recommended")), None),
            "surviving_thesis_ids": [str(item["id"]) for item in theses if item.get("verdict") == "survives"],
            "hypothesis_ids": [str(item["commander_hypothesis_id"]) for item in theses if item.get("commander_hypothesis_id")],
            "commander_source_ids": list(dict.fromkeys(
                str(item["commander_source_id"]) for item in evidence if item.get("commander_source_id")
            )),
        })

    def candidates(self, limit: int = 30) -> dict[str, Any]:
        rows = self.store.fetchall(
            """SELECT r.id,r.created_at,left(o.raw_text,500) owner_idea
               FROM laval_runs r JOIN laval_owner_ideas o ON o.run_id=r.id
               WHERE r.status='completed' AND r.evidence_mode<>'demo_fixture'
                 AND r.pipeline_version='mechanism_thesis_v1'
               ORDER BY r.completed_at DESC NULLS LAST,r.created_at DESC LIMIT %s""",
            (min(max(limit, 1), 100),),
        )
        items = []
        for row in rows:
            snapshot = self._snapshot(str(row["id"]))
            kit = self.store.fetchone(
                """SELECT k.commander_brand_kit_id,k.status,k.approved_at,d.name
                   FROM brand_kits k JOIN brand_runs b ON b.id=k.run_id
                   JOIN brand_directions d ON d.id=k.direction_id
                   WHERE b.source_laval_run_id=%s
                   ORDER BY k.approved_at DESC LIMIT 1""",
                (row["id"],),
            )
            items.append({
                "idea_run_id": str(row["id"]),
                "owner_idea": row["owner_idea"],
                "created_at": row["created_at"].isoformat(),
                "theses": snapshot["theses"],
                "mechanisms": snapshot["mechanisms"],
                "quality": snapshot["quality"],
                "recommended_thesis_id": snapshot["recommended_thesis_id"],
                "surviving_thesis_count": len(snapshot["surviving_thesis_ids"]),
                "active_brand_kit": json_safe(kit) if kit else None,
            })
        return {"items": items, "next_cursor": None}

    @staticmethod
    def _manual_transcripts(values: object) -> list[dict[str, str]]:
        if values is None:
            return []
        if not isinstance(values, list) or len(values) > 5:
            raise ValueError("manual_transcripts must contain at most five items")
        result = []
        for raw in values:
            if not isinstance(raw, Mapping):
                raise ValueError("each manual transcript must be an object")
            url = str(raw.get("video_url") or "").strip()
            if not url.startswith(("https://www.youtube.com/", "https://youtube.com/", "https://youtu.be/")):
                raise ValueError("manual transcript video_url must be an HTTPS YouTube URL")
            transcript = str(raw.get("transcript") or "").strip()
            if not 1 <= len(transcript) <= 10_000:
                raise ValueError("manual transcript text must contain 1-10000 characters")
            result.append({"video_url": url, "title": str(raw.get("title") or "Owner transcript")[:1000], "transcript": transcript})
        return result

    def create(
        self,
        laval_run_id: str,
        *,
        run_id: str | None = None,
        constraints_text: str,
        reference_urls: object,
        manual_transcripts: object,
        actor: str,
        provider_snapshot: Mapping[str, Any],
        intent: str = "initial",
        client_request_id: str | None = None,
    ) -> dict[str, Any]:
        if intent not in {"initial", "full_rebuild"}:
            raise ValueError("Branding create intent must be initial or full_rebuild")
        request_id = str(client_request_id or "").strip() or None
        if request_id and len(request_id) > 200:
            raise ValueError("client_request_id must contain at most 200 characters")
        if intent == "full_rebuild" and not request_id:
            raise ValueError("full_rebuild requires a retained client_request_id")
        snapshot = self._snapshot(laval_run_id)
        if not isinstance(reference_urls, list) or len(reference_urls) > 10:
            raise ValueError("reference_urls must contain at most ten items")
        references = list(dict.fromkeys(public_https_url(str(value), resolve=False) for value in reference_urls))
        transcripts = self._manual_transcripts(manual_transcripts)
        constraints = constraints_text.strip()
        if len(constraints) > 4000:
            raise ValueError("brand constraints must contain at most 4000 characters")
        run_id = run_id or new_uuid7()
        snapshot_hash = stable_hash(snapshot)
        with self.store.transaction() as connection:
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtext(%s))", (laval_run_id,)
            )
            if request_id:
                existing = connection.execute(
                    """SELECT id,status,project_version FROM brand_runs
                       WHERE source_laval_run_id=%s AND client_request_id=%s""",
                    (laval_run_id, request_id),
                ).fetchone()
                if existing:
                    return {
                        "run_id": str(existing[0]), "status": str(existing[1]),
                        "project_version": int(existing[2]), "existing": True,
                    }
            if intent == "initial":
                existing = connection.execute(
                    """SELECT id,status FROM brand_runs
                       WHERE source_laval_run_id=%s ORDER BY project_version,created_at LIMIT 1""",
                    (laval_run_id,),
                ).fetchone()
                if existing:
                    raise ValueError(
                        "Brand Project already exists; open its history or use intent=full_rebuild"
                    )
            version = int(connection.execute(
                "SELECT COALESCE(max(project_version),0)+1 FROM brand_runs WHERE source_laval_run_id=%s",
                (laval_run_id,),
            ).fetchone()[0])
            connection.execute(
                """INSERT INTO brand_runs(
                       id,source_laval_run_id,status,current_stage,source_snapshot_hash,
                       source_snapshot,constraints_text,reference_urls,manual_transcripts,
                       provider_snapshot,created_by,project_version,create_intent,client_request_id
                   ) VALUES(%s,%s,'pending','REFERENCE_PLAN',%s,%s::jsonb,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s,%s,%s)""",
                (run_id, laval_run_id, snapshot_hash, self.store.json(snapshot), constraints,
                 self.store.json(references), self.store.json(transcripts),
                 self.store.json(provider_snapshot), actor, version, intent, request_id),
            )
            now = datetime.now(timezone.utc)
            for ordinal, stage in enumerate(BRAND_STAGES):
                completed = stage == "CASE_SNAPSHOT"
                artifact = snapshot if completed else None
                connection.execute(
                    """INSERT INTO brand_stage_runs(
                           run_id,stage,ordinal,status,input_hash,attempt,artifact,started_at,completed_at
                       ) VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)""",
                    (run_id, stage, ordinal, "completed" if completed else "pending",
                     snapshot_hash if completed else None, 1 if completed else 0,
                     self.store.json(artifact) if artifact else None,
                     now if completed else None, now if completed else None),
                )
            connection.execute(
                "INSERT INTO brand_run_actions(id,run_id,action,actor,details) VALUES(%s,%s,'created',%s,%s::jsonb)",
                (new_uuid7(), run_id, actor, self.store.json({
                    "source_laval_run_id": laval_run_id,
                    "project_version": version,
                    "intent": intent,
                    "client_request_id": request_id,
                })),
            )
        return {
            "run_id": run_id, "status": "pending", "existing": False,
            "project_id": laval_run_id, "project_version": version,
        }

    def existing_create(
        self, laval_run_id: str, *, intent: str, client_request_id: str | None,
    ) -> dict[str, Any] | None:
        request_id = str(client_request_id or "").strip() or None
        if request_id:
            row = self.store.fetchone(
                """SELECT id,status,project_version FROM brand_runs
                   WHERE source_laval_run_id=%s AND client_request_id=%s""",
                (laval_run_id, request_id),
            )
            if row:
                return {**json_safe(row), "idempotent": True}
        if intent == "initial":
            row = self.store.fetchone(
                """SELECT id,status,project_version FROM brand_runs
                   WHERE source_laval_run_id=%s ORDER BY project_version,created_at LIMIT 1""",
                (laval_run_id,),
            )
            return {**json_safe(row), "project_exists": True} if row else None
        return None

    def run(self, run_id: str) -> dict[str, Any]:
        row = self.store.fetchone("SELECT * FROM brand_runs WHERE id=%s", (run_id,))
        if not row:
            raise KeyError("Branding run not found")
        return json_safe(row)

    def list(self, limit: int = 30) -> dict[str, Any]:
        rows = self.store.fetchall(
            """SELECT b.*,left(o.raw_text,240) owner_preview,
                      (SELECT count(*) FROM brand_stage_runs s WHERE s.run_id=b.id AND s.status='completed') completed_stages,
                      (SELECT count(*) FROM brand_directions d WHERE d.run_id=b.id) direction_count
               FROM brand_runs b JOIN laval_owner_ideas o ON o.run_id=b.source_laval_run_id
               ORDER BY b.created_at DESC LIMIT %s""",
            (min(max(limit, 1), 100),),
        )
        return {"items": json_safe(rows), "next_cursor": None}

    def active_kit(self, source_laval_run_id: str) -> dict[str, Any]:
        row = self.store.fetchone(
            """SELECT k.*,d.name,d.manifest direction_manifest
               FROM brand_kits k JOIN brand_directions d ON d.id=k.direction_id
               WHERE k.source_laval_run_id=%s AND k.status='approved'
               ORDER BY k.project_version DESC,k.approved_at DESC LIMIT 1""",
            (source_laval_run_id,),
        )
        if not row:
            raise KeyError("Brand Project has no active approved kit")
        return json_safe(row)

    def project(self, source_laval_run_id: str) -> dict[str, Any]:
        idea = self.store.fetchone(
            """SELECT r.id,left(o.raw_text,4000) owner_idea,r.created_at idea_created_at
               FROM laval_runs r JOIN laval_owner_ideas o ON o.run_id=r.id
               WHERE r.id=%s""",
            (source_laval_run_id,),
        )
        if not idea:
            raise KeyError("Brand Project not found")
        runs = self.store.fetchall(
            """SELECT b.*,
                      (SELECT count(*) FROM brand_stage_runs s WHERE s.run_id=b.id AND s.status='completed') completed_stages,
                      (SELECT d.artifact_digest FROM brand_directions d WHERE d.run_id=b.id AND d.artifact_digest IS NOT NULL ORDER BY d.ordinal LIMIT 1) logo_thumbnail_digest
               FROM brand_runs b WHERE b.source_laval_run_id=%s
               ORDER BY b.project_version,b.created_at""",
            (source_laval_run_id,),
        )
        kits = self.store.fetchall(
            """SELECT k.*,d.name,d.manifest direction_manifest
               FROM brand_kits k JOIN brand_directions d ON d.id=k.direction_id
               WHERE k.source_laval_run_id=%s
               ORDER BY k.project_version DESC,k.approved_at DESC""",
            (source_laval_run_id,),
        )
        revisions = self.store.fetchall(
            """SELECT revision.*,review.overall_comment feedback
               FROM brand_kit_logo_revisions revision
               LEFT JOIN commander_creative_reviews review
                 ON review.feedback_id=revision.feedback_id
               WHERE revision.source_laval_run_id=%s
               ORDER BY revision.created_at DESC LIMIT 30""",
            (source_laval_run_id,),
        )
        active = next((item for item in kits if item["status"] == "approved"), None)
        versions = [
            {
                "kind": "run", "version": item["project_version"],
                "run_id": item["id"], "status": item["status"],
                "logo_thumbnail_digest": item.get("logo_thumbnail_digest"),
                "created_at": item["created_at"], "updated_at": item["updated_at"],
            }
            for item in runs
        ] + [
            {
                "kind": "kit", "version": item["project_version"],
                "kit_id": item["id"], "status": item["status"],
                "logo_thumbnail_digest": item.get("logo_artifact_digest"),
                "created_at": item["approved_at"], "updated_at": item["approved_at"],
            }
            for item in kits
        ] + [
            {
                "kind": "logo_revision", "version": item["proposed_project_version"],
                "revision_id": item["id"], "status": item["status"],
                "logo_thumbnail_digest": (
                    item.get("artifact_digest") or item.get("source_artifact_digest")
                ),
                "created_at": item["created_at"], "updated_at": item["updated_at"],
            }
            for item in revisions
        ]
        return json_safe({
            "id": source_laval_run_id,
            "source_idea": {
                "run_id": str(idea["id"]), "owner_idea": idea["owner_idea"],
                "created_at": idea["idea_created_at"],
            },
            "status": (
                "revision_review" if any(item["status"] == "completed" for item in revisions)
                else "revision_running" if any(item["status"] in {"pending", "running"} for item in revisions)
                else "active" if active else "draft"
            ),
            "active_kit": active,
            "kits": kits,
            "runs": runs,
            "logo_revisions": revisions,
            "versions": sorted(
                versions,
                key=lambda item: (
                    int(item["version"]),
                    {"run": 0, "logo_revision": 1, "kit": 2}[str(item["kind"])],
                ),
            )[-100:],
            "created_at": runs[0]["created_at"] if runs else idea["idea_created_at"],
            "updated_at": max(
                [item["updated_at"] for item in runs]
                + [item["updated_at"] for item in revisions]
                + [item["approved_at"] for item in kits]
                + [idea["idea_created_at"]]
            ),
        })

    def projects(self, limit: int = 30) -> dict[str, Any]:
        rows = self.store.fetchall(
            """SELECT source_laval_run_id,max(updated_at) updated_at
               FROM brand_runs GROUP BY source_laval_run_id
               ORDER BY max(updated_at) DESC LIMIT %s""",
            (min(max(limit, 1), 100),),
        )
        return {
            "items": [self.project(str(row["source_laval_run_id"])) for row in rows],
            "next_cursor": None,
        }

    def stages(self, run_id: str) -> list[dict[str, Any]]:
        self.run(run_id)
        return json_safe(self.store.fetchall(
            "SELECT * FROM brand_stage_runs WHERE run_id=%s ORDER BY ordinal", (run_id,)
        ))

    def stage(self, run_id: str, stage: str) -> dict[str, Any]:
        row = self.store.fetchone(
            "SELECT * FROM brand_stage_runs WHERE run_id=%s AND stage=%s", (run_id, stage.upper())
        )
        if not row:
            raise KeyError("Branding stage not found")
        return json_safe(row)

    def status(self, run_id: str) -> dict[str, Any]:
        self.refresh_source_staleness(run_id)
        return {
            "run": self.run(run_id),
            "stages": self.stages(run_id),
            "directions": self.directions(run_id),
            "cost": self.cost(run_id),
        }

    def refresh_source_staleness(self, run_id: str) -> bool:
        run = self.run(run_id)
        try:
            stale = stable_hash(self._snapshot(str(run["source_laval_run_id"]))) != run["source_snapshot_hash"]
        except (KeyError, ValueError):
            stale = True
        if stale and not run.get("source_stale"):
            with self.store.transaction() as connection:
                connection.execute("UPDATE brand_runs SET source_stale=TRUE,updated_at=NOW() WHERE id=%s", (run_id,))
                connection.execute("UPDATE brand_kits SET status='stale' WHERE run_id=%s AND status='approved'", (run_id,))
                if connection.execute(
                    "SELECT to_regclass('commander_entities')"
                ).fetchone()[0] is not None:
                    connection.execute(
                        """UPDATE commander_entities e
                           SET attributes=jsonb_set(e.attributes,'{status}','\"stale\"'::jsonb,TRUE)
                           FROM brand_kits k WHERE k.run_id=%s
                             AND e.id=k.commander_brand_kit_id""",
                        (run_id,),
                    )
        return stale

    def ready(self, run_id: str) -> None:
        run = self.run(run_id)
        if run["status"] not in {"pending", "paused", "failed"}:
            raise ValueError("Branding run cannot be started from its current state")
        self.store.execute(
            "UPDATE brand_runs SET status='running',error_text=NULL,updated_at=NOW() WHERE id=%s RETURNING 1",
            (run_id,),
        )

    def ready_after_restart(self, run_id: str) -> None:
        self.run(run_id)
        self.store.execute(
            """UPDATE brand_runs SET status='running',error_text=NULL,updated_at=NOW()
               WHERE id=%s AND status IN ('pending','running') RETURNING 1""",
            (run_id,),
        )

    def record_action(
        self, run_id: str, action: str, *, actor: str, details: Mapping[str, Any] | None = None
    ) -> None:
        self.store.execute(
            """INSERT INTO brand_run_actions(id,run_id,action,actor,details)
               VALUES(%s,%s,%s,%s,%s::jsonb) RETURNING 1""",
            (new_uuid7(), run_id, action, actor, self.store.json(details or {})),
        )

    def pause(self, run_id: str, *, actor: str = "owner") -> None:
        self.run(run_id)
        with self.store.transaction() as connection:
            connection.execute("UPDATE brand_runs SET status='paused',updated_at=NOW() WHERE id=%s AND status IN ('pending','running','failed')", (run_id,))
            connection.execute(
                """UPDATE brand_stage_runs SET status='paused',updated_at=NOW()
                   WHERE run_id=%s AND status='running'""",
                (run_id,),
            )
            connection.execute("INSERT INTO brand_run_actions(id,run_id,action,actor) VALUES(%s,%s,'paused',%s)", (new_uuid7(), run_id, actor))

    def pause_stage(self, run_id: str, stage: str) -> None:
        self.store.execute(
            """UPDATE brand_stage_runs SET status='paused',updated_at=NOW()
               WHERE run_id=%s AND stage=%s AND status IN ('running','paused') RETURNING 1""",
            (run_id, stage),
        )

    def pause_all(self, *, actor: str = "emergency-stop") -> None:
        rows = self.store.fetchall(
            "SELECT id FROM brand_runs WHERE status IN ('pending','running')"
        )
        for row in rows:
            self.pause(str(row["id"]), actor=actor)

    def prepare_stage(self, run_id: str, stage: str, input_hash: str, *, provider: str, model: str) -> int:
        with self.store.transaction() as connection:
            row = connection.execute(
                """UPDATE brand_stage_runs SET status='running',input_hash=%s,
                          attempt=attempt+CASE WHEN status='paused' THEN 0 ELSE 1 END,
                          provider=%s,model=%s,error=NULL,started_at=NOW(),updated_at=NOW()
                   WHERE run_id=%s AND stage=%s RETURNING attempt""",
                (input_hash, provider, model, run_id, stage),
            ).fetchone()
            if not row:
                raise KeyError("Branding stage not found")
            connection.execute("UPDATE brand_runs SET status='running',current_stage=%s,updated_at=NOW() WHERE id=%s", (stage, run_id))
            return int(row[0])

    def complete_stage(self, run_id: str, stage: str, artifact: Any, metrics: Mapping[str, Any] | None = None) -> None:
        with self.store.transaction() as connection:
            connection.execute(
                """UPDATE brand_stage_runs SET status='completed',artifact=%s::jsonb,metrics=%s::jsonb,
                          error=NULL,completed_at=NOW(),updated_at=NOW()
                   WHERE run_id=%s AND stage=%s""",
                (self.store.json(artifact), self.store.json(metrics or {}), run_id, stage),
            )
            ordinal = BRAND_STAGES.index(stage)
            next_stage = BRAND_STAGES[min(ordinal + 1, len(BRAND_STAGES) - 1)]
            connection.execute("UPDATE brand_runs SET current_stage=%s,updated_at=NOW() WHERE id=%s", (next_stage, run_id))

    def fail_stage(self, run_id: str, stage: str, error: Exception) -> None:
        bounded = {"type": type(error).__name__, "message": str(error)[:1000]}
        with self.store.transaction() as connection:
            connection.execute("UPDATE brand_stage_runs SET status='failed',error=%s::jsonb,updated_at=NOW() WHERE run_id=%s AND stage=%s", (self.store.json(bounded), run_id, stage))
            connection.execute("UPDATE brand_runs SET status='failed',current_stage=%s,error_text=%s,updated_at=NOW() WHERE id=%s", (stage, bounded["message"], run_id))
            connection.execute("INSERT INTO brand_run_actions(id,run_id,action,actor,details) VALUES(%s,%s,'failed','brand-runner',%s::jsonb)", (new_uuid7(), run_id, self.store.json({"stage": stage, **bounded})))

    def await_review(self, run_id: str) -> None:
        with self.store.transaction() as connection:
            connection.execute("UPDATE brand_runs SET status='awaiting_review',current_stage='OWNER_REVIEW',updated_at=NOW() WHERE id=%s", (run_id,))
            connection.execute("UPDATE brand_stage_runs SET status='paused',updated_at=NOW() WHERE run_id=%s AND stage='OWNER_REVIEW'", (run_id,))

    def add_source(self, run_id: str, source_type: str, source_url: str, title: str, excerpt: str, metadata: Mapping[str, Any]) -> str:
        existing = self.store.fetchone("SELECT id FROM brand_sources WHERE run_id=%s AND source_type=%s AND source_url=%s", (run_id, source_type, source_url))
        if existing:
            return str(existing["id"])
        source_id = new_uuid7()
        self.store.execute(
            """INSERT INTO brand_sources(id,run_id,source_type,source_url,title,excerpt,metadata)
               VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb) RETURNING 1""",
            (source_id, run_id, source_type, source_url[:4000], title[:1000], excerpt[:30_000], self.store.json(metadata)),
        )
        return source_id

    def sources(self, run_id: str) -> list[dict[str, Any]]:
        return json_safe(self.store.fetchall("SELECT * FROM brand_sources WHERE run_id=%s ORDER BY created_at,id", (run_id,)))

    def link_sources(self, mapping: Mapping[str, str]) -> None:
        for external_id, commander_id in mapping.items():
            self.store.execute("UPDATE brand_sources SET commander_source_id=%s WHERE id=%s RETURNING 1", (commander_id, external_id))

    def replace_directions(self, run_id: str, values: Sequence[Mapping[str, Any]]) -> None:
        if len(values) != 3:
            raise ValueError("Branding must produce exactly three directions")
        with self.store.transaction() as connection:
            if connection.execute("SELECT 1 FROM brand_directions WHERE run_id=%s AND creative_id IS NOT NULL LIMIT 1", (run_id,)).fetchone():
                raise ValueError("published logo directions cannot be replaced; create a new Branding run")
            connection.execute("DELETE FROM brand_directions WHERE run_id=%s", (run_id,))
            for ordinal, value in enumerate(values, 1):
                connection.execute(
                    """INSERT INTO brand_directions(id,run_id,ordinal,name,manifest,status)
                       VALUES(%s,%s,%s,%s,%s::jsonb,'draft')""",
                    (new_uuid7(), run_id, ordinal, str(value["name"]), self.store.json(value)),
                )

    def save_evaluations(self, run_id: str, evaluations: Mapping[str, Mapping[str, Any]]) -> None:
        with self.store.transaction() as connection:
            for direction in connection.execute("SELECT id,name FROM brand_directions WHERE run_id=%s", (run_id,)).fetchall():
                evaluation = evaluations.get(str(direction[1]))
                if not evaluation:
                    raise ValueError("every brand direction requires evaluation")
                connection.execute("UPDATE brand_directions SET evaluation=%s::jsonb,status='evaluated',updated_at=NOW() WHERE id=%s", (self.store.json(evaluation), direction[0]))

    def save_logo(self, direction_id: str, *, path: Path, digest: str, graph: Mapping[str, str]) -> None:
        self.store.execute(
            """UPDATE brand_directions SET status='awaiting_review',logo_path=%s,artifact_digest=%s,
                      commander_direction_id=%s,creative_id=%s,artifact_id=%s,updated_at=NOW()
               WHERE id=%s RETURNING 1""",
            (str(path), digest, graph["direction_id"], graph["creative_id"], graph["artifact_id"], direction_id),
        )

    def directions(self, run_id: str) -> list[dict[str, Any]]:
        self.run(run_id)
        rows = self.store.fetchall(
            """SELECT d.*,
                      r.feedback_id latest_feedback_id,r.rating,r.overall_comment,
                      r.annotations,r.created_at reviewed_at,r.feedback_type,
                      revision.id regeneration_id,
                      revision.status regeneration_status,
                      revision.feedback_id regeneration_feedback_id,
                      revision.error regeneration_error,
                      revision.strategy regeneration_strategy,
                      revision.reference_used regeneration_reference_used,
                      revision.compliance regeneration_compliance,
                      revision.created_at regeneration_requested_at,
                      revision.completed_at regeneration_completed_at,
                      CASE WHEN t.id IS NULL THEN NULL ELSE jsonb_build_object(
                        'provider',t.provider,
                        'requested_model',t.response->>'requested_model',
                        'resolved_model',t.response->>'resolved_model',
                        'request_id',t.response->>'request_id',
                        'prompt',t.response->>'prompt'
                      ) END generation_provenance
               FROM brand_directions d
               LEFT JOIN LATERAL (
                 SELECT review.feedback_id,review.rating,review.overall_comment,
                        review.annotations,review.created_at,
                        feedback.attributes->>'feedback_type' feedback_type
                 FROM commander_creative_reviews review
                 JOIN commander_entities feedback ON feedback.id=review.feedback_id
                 WHERE review.creative_id=d.creative_id
                 ORDER BY review.created_at DESC LIMIT 1
               ) r ON TRUE
               LEFT JOIN LATERAL (
                 SELECT id,status,feedback_id,error,strategy,reference_used,
                        compliance,created_at,completed_at
                 FROM brand_logo_revisions WHERE direction_id=d.id
                 ORDER BY revision DESC LIMIT 1
               ) revision ON TRUE
               LEFT JOIN brand_provider_tasks t
                 ON t.run_id=d.run_id AND t.stage='LOGO_GENERATION'
                AND t.response_digest=d.artifact_digest AND t.status='completed'
               WHERE d.run_id=%s ORDER BY d.ordinal""",
            (run_id,),
        )
        for row in rows:
            if row.get("regeneration_id"):
                compliance = row.get("regeneration_compliance") or {}
                row["regeneration_verification"] = (
                    "verified" if compliance.get("passed") is True
                    else "failed_compliance" if compliance.get("passed") is False
                    else "legacy_unverified"
                )
            row["review_state"] = (
                "approved"
                if row.get("feedback_type") == "owner_logo_approval"
                else "changes_requested"
                if row.get("latest_feedback_id")
                else "pending"
            )
            if row.get("latest_feedback_id"):
                self.store.execute(
                    """UPDATE brand_directions SET latest_feedback_id=%s,reviewed_at=%s,
                              status=CASE
                                WHEN status='approved' THEN status
                                WHEN %s='owner_logo_approval' THEN 'reviewed'
                                ELSE 'awaiting_review'
                              END,updated_at=NOW()
                       WHERE id=%s RETURNING 1""",
                    (
                        row["latest_feedback_id"], row["reviewed_at"],
                        row.get("feedback_type"), row["id"],
                    ),
                )
        return json_safe(rows)

    def direction(self, run_id: str, direction_id: str) -> dict[str, Any]:
        item = next((item for item in self.directions(run_id) if item["id"] == direction_id), None)
        if not item:
            raise KeyError("Brand direction not found")
        return item

    def reviewed(self, run_id: str) -> bool:
        directions = self.directions(run_id)
        return len(directions) == 3 and all(
            item.get("review_state") == "approved" for item in directions
        )

    def feedback_context(self, feedback_id: str, creative_id: str) -> dict[str, Any]:
        row = self.store.fetchone(
            """SELECT review.feedback_id,review.creative_id,review.rating,
                      review.overall_comment,review.annotations,
                      feedback.attributes->>'feedback_type' feedback_type
               FROM commander_creative_reviews review
               JOIN commander_entities feedback ON feedback.id=review.feedback_id
               WHERE review.feedback_id=%s AND review.creative_id=%s""",
            (feedback_id, creative_id),
        )
        if not row:
            raise KeyError("logo feedback is not attached to the current Creative")
        if row.get("feedback_type") == "owner_logo_approval":
            raise ValueError("approved logos require new correction feedback before regeneration")
        comments = [str(row.get("overall_comment") or "").strip()]
        for annotation in row.get("annotations") or []:
            if isinstance(annotation, Mapping):
                comments.append(str(annotation.get("comment") or "").strip())
        comments = [value for value in comments if value]
        rating = row.get("rating")
        instruction = "\n".join(comments)
        if rating is not None:
            instruction = (
                f"Legacy owner rating: {int(rating)}/5. "
                + (instruction or "Create a materially stronger and clearer alternative.")
            )
        if not instruction:
            raise ValueError("logo correction feedback has no actionable text")
        return {**json_safe(row), "instruction": instruction[:2000]}

    def queue_logo_revision(
        self, run_id: str, direction_id: str, feedback_id: str, *,
        actor: str, provider: str, model: str,
    ) -> dict[str, Any]:
        run = self.run(run_id)
        if run["status"] != "awaiting_review":
            raise ValueError("logo regeneration is available only during owner review")
        direction = self.direction(run_id, direction_id)
        if direction.get("review_state") != "changes_requested":
            raise ValueError("the current logo has no unapplied correction feedback")
        if str(direction.get("latest_feedback_id") or "") != feedback_id:
            raise ValueError("only the latest current-logo feedback can regenerate it")
        feedback = self.feedback_context(feedback_id, str(direction["creative_id"]))
        existing = self.store.fetchone(
            "SELECT * FROM brand_logo_revisions WHERE feedback_id=%s", (feedback_id,)
        )
        if existing:
            if existing["status"] == "failed":
                self.store.execute(
                    """UPDATE brand_logo_revisions SET status='pending',error=NULL,
                              started_at=NULL,completed_at=NULL,updated_at=NOW()
                       WHERE id=%s RETURNING 1""",
                    (existing["id"],),
                )
                existing = self.store.fetchone(
                    "SELECT * FROM brand_logo_revisions WHERE id=%s", (existing["id"],)
                )
            if existing["status"] in {"pending", "running"}:
                self.store.execute(
                    """UPDATE brand_runs SET status='running',current_stage='OWNER_REVIEW',
                              error_text=NULL,updated_at=NOW() WHERE id=%s RETURNING 1""",
                    (run_id,),
                )
            return json_safe(existing)
        active = self.store.fetchone(
            """SELECT id FROM brand_logo_revisions
               WHERE direction_id=%s AND status IN ('pending','running') LIMIT 1""",
            (direction_id,),
        )
        if active:
            raise ValueError("this logo is already being regenerated")
        revision_id = new_uuid7()
        revision = int(direction.get("revision") or 1) + 1
        input_hash = stable_hash(
            direction["manifest"], direction["artifact_digest"], feedback["instruction"]
        )
        with self.store.transaction() as connection:
            connection.execute(
                """INSERT INTO brand_logo_revisions(
                       id,run_id,direction_id,revision,feedback_id,
                       source_creative_id,source_artifact_id,source_artifact_digest,
                       source_logo_path,status,input_hash,provider,model,actor
                   ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,'pending',%s,%s,%s,%s)""",
                (
                    revision_id, run_id, direction_id, revision, feedback_id,
                    direction["creative_id"], direction["artifact_id"],
                    direction["artifact_digest"], direction["logo_path"],
                    input_hash, provider, model, actor,
                ),
            )
            connection.execute(
                """INSERT INTO brand_run_actions(id,run_id,action,actor,details)
                   VALUES(%s,%s,'logo_revision_requested',%s,%s::jsonb)""",
                (
                    new_uuid7(), run_id, actor,
                    self.store.json({
                        "direction_id": direction_id,
                        "revision_id": revision_id,
                        "feedback_id": feedback_id,
                    }),
                ),
            )
            connection.execute(
                """UPDATE brand_runs SET status='running',current_stage='OWNER_REVIEW',
                          error_text=NULL,updated_at=NOW() WHERE id=%s""",
                (run_id,),
            )
        return json_safe(self.store.fetchone(
            "SELECT * FROM brand_logo_revisions WHERE id=%s", (revision_id,)
        ))

    def logo_revision(self, revision_id: str) -> dict[str, Any]:
        row = self.store.fetchone(
            "SELECT * FROM brand_logo_revisions WHERE id=%s", (revision_id,)
        )
        if not row:
            raise KeyError("Brand logo revision not found")
        return json_safe(row)

    def pending_logo_revision(self, run_id: str | None = None) -> dict[str, Any] | None:
        row = self.store.fetchone(
            """SELECT * FROM brand_logo_revisions
               WHERE status IN ('pending','running')
                 AND (%s::uuid IS NULL OR run_id=%s::uuid)
               ORDER BY created_at LIMIT 1""",
            (run_id, run_id),
        )
        return json_safe(row) if row else None

    def start_logo_revision(self, revision_id: str) -> dict[str, Any]:
        self.store.execute(
            """UPDATE brand_logo_revisions SET status='running',
                      attempt=attempt+CASE WHEN status='pending' THEN 1 ELSE 0 END,error=NULL,
                      started_at=COALESCE(started_at,NOW()),updated_at=NOW()
               WHERE id=%s AND status IN ('pending','running') RETURNING 1""",
            (revision_id,),
        )
        return self.logo_revision(revision_id)

    def plan_logo_revision(self, revision_id: str, plan: Mapping[str, Any]) -> None:
        self.store.execute(
            """UPDATE brand_logo_revisions SET strategy=%s,requested_change=%s,
                      literal_text=%s,invariants=%s::jsonb,updated_at=NOW()
               WHERE id=%s RETURNING 1""",
            (
                plan["strategy"], plan["requested_change"], plan.get("literal_text"),
                self.store.json(plan.get("invariants") or []), revision_id,
            ),
        )

    def complete_logo_revision(
        self, revision_id: str, *, path: Path, digest: str,
        graph: Mapping[str, str], compliance: Mapping[str, Any],
        reference_used: bool, reference_trace: Mapping[str, Any],
    ) -> None:
        revision = self.logo_revision(revision_id)
        with self.store.transaction() as connection:
            connection.execute(
                """UPDATE brand_logo_revisions SET status='completed',creative_id=%s,
                          artifact_id=%s,artifact_digest=%s,logo_path=%s,error=NULL,
                          compliance=%s::jsonb,reference_used=%s,reference_trace=%s::jsonb,
                          completed_at=NOW(),updated_at=NOW()
                   WHERE id=%s""",
                (
                    graph["creative_id"], graph["artifact_id"], digest,
                    str(path), self.store.json(compliance), reference_used,
                    self.store.json(reference_trace), revision_id,
                ),
            )
            connection.execute(
                """UPDATE brand_directions SET revision=%s,creative_id=%s,artifact_id=%s,
                          artifact_digest=%s,logo_path=%s,latest_feedback_id=NULL,
                          reviewed_at=NULL,status='awaiting_review',updated_at=NOW()
                   WHERE id=%s""",
                (
                    revision["revision"], graph["creative_id"], graph["artifact_id"],
                    digest, str(path), revision["direction_id"],
                ),
            )
            connection.execute(
                """INSERT INTO brand_run_actions(id,run_id,action,actor,details)
                   VALUES(%s,%s,'logo_regenerated','brand-runner',%s::jsonb)""",
                (
                    new_uuid7(), revision["run_id"],
                    self.store.json({
                        "direction_id": str(revision["direction_id"]),
                        "revision_id": revision_id,
                        "revision": revision["revision"],
                    }),
                ),
            )
            connection.execute(
                """UPDATE brand_runs SET status='awaiting_review',current_stage='OWNER_REVIEW',
                          error_text=NULL,updated_at=NOW() WHERE id=%s""",
                (revision["run_id"],),
            )

    def fail_logo_revision(self, revision_id: str, error: Exception) -> None:
        revision = self.logo_revision(revision_id)
        bounded = {"type": type(error).__name__, "message": str(error)[:1000]}
        with self.store.transaction() as connection:
            connection.execute(
                """UPDATE brand_logo_revisions SET status='failed',error=%s::jsonb,
                          completed_at=NOW(),updated_at=NOW() WHERE id=%s""",
                (self.store.json(bounded), revision_id),
            )
            connection.execute(
                """INSERT INTO brand_run_actions(id,run_id,action,actor,details)
                   VALUES(%s,%s,'logo_revision_failed','brand-runner',%s::jsonb)""",
                (
                    new_uuid7(), revision["run_id"],
                    self.store.json({
                        "direction_id": str(revision["direction_id"]),
                        "revision_id": revision_id,
                        **bounded,
                    }),
                ),
            )
            connection.execute(
                """UPDATE brand_runs SET status='awaiting_review',current_stage='OWNER_REVIEW',
                          error_text=%s,updated_at=NOW()
                   WHERE id=%s AND status<>'paused'""",
                (bounded["message"], revision["run_id"]),
            )

    def pause_logo_revision(self, revision_id: str) -> None:
        self.store.execute(
            """UPDATE brand_logo_revisions SET status='pending',
                      attempt=GREATEST(attempt-1,0),updated_at=NOW()
               WHERE id=%s AND status='running' RETURNING 1""",
            (revision_id,),
        )

    def save_kit(
        self, run_id: str, direction_id: str, *, kit_id: str, commander_kit_id: str,
        previous_kit_id: str | None, manifest: Mapping[str, Any], zip_path: Path,
        zip_digest: str, actor: str,
    ) -> None:
        with self.store.transaction() as connection:
            run = connection.execute(
                "SELECT source_laval_run_id FROM brand_runs WHERE id=%s FOR UPDATE",
                (run_id,),
            ).fetchone()
            direction = connection.execute(
                "SELECT creative_id,artifact_id,artifact_digest,logo_path FROM brand_directions WHERE id=%s",
                (direction_id,),
            ).fetchone()
            if not run or not direction or not all(direction):
                raise ValueError("selected Brand Kit logo is incomplete")
            source_laval_run_id = str(run[0])
            project_version = int(connection.execute(
                "SELECT COALESCE(max(project_version),0)+1 FROM brand_kits WHERE source_laval_run_id=%s",
                (source_laval_run_id,),
            ).fetchone()[0])
            previous_local = connection.execute(
                """SELECT id FROM brand_kits
                   WHERE source_laval_run_id=%s AND status='approved' FOR UPDATE""",
                (source_laval_run_id,),
            ).fetchone()
            connection.execute(
                "UPDATE brand_kits SET status='superseded' WHERE source_laval_run_id=%s AND status='approved'",
                (source_laval_run_id,),
            )
            connection.execute(
                """INSERT INTO brand_kits(
                       id,run_id,direction_id,commander_brand_kit_id,previous_commander_brand_kit_id,
                       manifest,zip_digest,zip_path,status,approved_by,source_laval_run_id,
                       project_version,supersedes_kit_id,logo_creative_id,logo_artifact_id,
                       logo_artifact_digest,logo_path
                   ) VALUES(%s,%s,%s,%s,%s,%s::jsonb,%s,%s,'approved',%s,%s,%s,%s,%s,%s,%s,%s)""",
                (kit_id, run_id, direction_id, commander_kit_id, previous_kit_id,
                 self.store.json(manifest), zip_digest, str(zip_path), actor,
                 source_laval_run_id, project_version,
                 str(previous_local[0]) if previous_local else None,
                 direction[0], direction[1], direction[2], direction[3]),
            )
            connection.execute("UPDATE brand_directions SET status='approved',updated_at=NOW() WHERE id=%s", (direction_id,))
            connection.execute("UPDATE brand_directions SET status='superseded',updated_at=NOW() WHERE run_id=%s AND id<>%s", (run_id, direction_id))
            connection.execute("UPDATE brand_runs SET selected_direction_id=%s,commander_brand_kit_id=%s,status='completed',current_stage='KIT_ASSEMBLY',completed_at=NOW(),updated_at=NOW() WHERE id=%s", (direction_id, commander_kit_id, run_id))
            connection.execute("UPDATE brand_stage_runs SET status='completed',artifact=%s::jsonb,completed_at=NOW(),updated_at=NOW() WHERE run_id=%s AND stage='OWNER_REVIEW'", (self.store.json({"selected_direction_id": direction_id}), run_id))
            connection.execute("UPDATE brand_stage_runs SET status='completed',artifact=%s::jsonb,completed_at=NOW(),updated_at=NOW() WHERE run_id=%s AND stage='KIT_ASSEMBLY'", (self.store.json({"brand_kit_id": commander_kit_id, "zip_digest": zip_digest}), run_id))
            connection.execute("INSERT INTO brand_run_actions(id,run_id,action,actor,details) VALUES(%s,%s,'approved',%s,%s::jsonb)", (new_uuid7(), run_id, actor, self.store.json({"direction_id": direction_id, "brand_kit_id": commander_kit_id})))

    def kit(self, kit_id: str) -> dict[str, Any]:
        row = self.store.fetchone(
            """SELECT k.*,d.name,d.manifest direction_manifest,b.source_stale
               FROM brand_kits k JOIN brand_directions d ON d.id=k.direction_id
               JOIN brand_runs b ON b.id=k.run_id
               WHERE k.commander_brand_kit_id=%s OR k.id=%s""",
            (kit_id, kit_id),
        )
        if not row:
            raise KeyError("Brand Kit not found")
        return json_safe(row)

    def queue_kit_logo_revision(
        self, source_laval_run_id: str, feedback_id: str, *, client_request_id: str,
        actor: str, provider: str, model: str,
    ) -> dict[str, Any]:
        request_id = client_request_id.strip()
        if not request_id or len(request_id) > 200:
            raise ValueError("logo revision requires a retained client_request_id")
        kit = self.active_kit(source_laval_run_id)
        feedback = self.feedback_context(feedback_id, str(kit["logo_creative_id"]))
        existing = self.store.fetchone(
            """SELECT * FROM brand_kit_logo_revisions
               WHERE source_laval_run_id=%s AND client_request_id=%s""",
            (source_laval_run_id, request_id),
        )
        if existing:
            return json_safe(existing)
        active = self.store.fetchone(
            """SELECT id FROM brand_kit_logo_revisions
               WHERE source_laval_run_id=%s AND status IN ('pending','running','completed') LIMIT 1""",
            (source_laval_run_id,),
        )
        if active:
            raise ValueError("this Brand Project already has a logo revision awaiting review")
        revision_id = new_uuid7()
        proposed_version = int(kit["project_version"]) + 1
        input_hash = stable_hash(
            kit["id"], kit["logo_artifact_digest"], feedback["instruction"], request_id
        )
        self.store.execute(
            """INSERT INTO brand_kit_logo_revisions(
                   id,source_laval_run_id,base_kit_id,proposed_project_version,
                   feedback_id,client_request_id,source_creative_id,source_artifact_id,
                   source_artifact_digest,source_logo_path,status,input_hash,provider,model,actor
               ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'pending',%s,%s,%s,%s) RETURNING 1""",
            (
                revision_id, source_laval_run_id, kit["id"], proposed_version,
                feedback_id, request_id, kit["logo_creative_id"], kit["logo_artifact_id"],
                kit["logo_artifact_digest"], kit["logo_path"], input_hash,
                provider, model, actor,
            ),
        )
        return self.kit_logo_revision(revision_id)

    def kit_logo_revision(self, revision_id: str) -> dict[str, Any]:
        row = self.store.fetchone(
            """SELECT revision.*,review.overall_comment feedback
               FROM brand_kit_logo_revisions revision
               LEFT JOIN commander_creative_reviews review
                 ON review.feedback_id=revision.feedback_id
               WHERE revision.id=%s""",
            (revision_id,),
        )
        if not row:
            raise KeyError("Brand Kit logo revision not found")
        return json_safe(row)

    def pending_kit_logo_revision(self) -> dict[str, Any] | None:
        row = self.store.fetchone(
            """SELECT * FROM brand_kit_logo_revisions
               WHERE status IN ('pending','running') ORDER BY created_at LIMIT 1"""
        )
        return json_safe(row) if row else None

    def start_kit_logo_revision(self, revision_id: str) -> dict[str, Any]:
        self.store.execute(
            """UPDATE brand_kit_logo_revisions SET status='running',attempt=attempt+1,
                      error=NULL,started_at=COALESCE(started_at,NOW()),updated_at=NOW()
               WHERE id=%s AND status IN ('pending','running') AND attempt<2 RETURNING 1""",
            (revision_id,),
        )
        return self.kit_logo_revision(revision_id)

    def plan_kit_logo_revision(self, revision_id: str, plan: Mapping[str, Any]) -> None:
        self.store.execute(
            """UPDATE brand_kit_logo_revisions SET strategy=%s,requested_change=%s,
                      literal_text=%s,invariants=%s::jsonb,structural_change=%s,updated_at=NOW()
               WHERE id=%s RETURNING 1""",
            (
                plan["strategy"], plan["requested_change"], plan.get("literal_text"),
                self.store.json(plan.get("invariants") or []),
                bool(plan.get("structural_change")), revision_id,
            ),
        )

    def retry_kit_logo_revision(self, revision_id: str, error: Exception) -> None:
        bounded = {"type": type(error).__name__, "message": str(error)[:1000]}
        self.store.execute(
            """UPDATE brand_kit_logo_revisions SET status='pending',error=%s::jsonb,
                      compliance=%s::jsonb,updated_at=NOW() WHERE id=%s RETURNING 1""",
            (self.store.json(bounded), self.store.json({"passed": False, "reason": bounded["message"]}), revision_id),
        )

    def complete_kit_logo_revision(
        self, revision_id: str, *, path: Path, digest: str,
        graph: Mapping[str, str], compliance: Mapping[str, Any],
        reference_used: bool, reference_trace: Mapping[str, Any],
    ) -> None:
        self.store.execute(
            """UPDATE brand_kit_logo_revisions SET status='completed',creative_id=%s,
                      artifact_id=%s,artifact_digest=%s,logo_path=%s,compliance=%s::jsonb,
                      reference_used=%s,reference_trace=%s::jsonb,error=NULL,
                      completed_at=NOW(),updated_at=NOW() WHERE id=%s RETURNING 1""",
            (
                graph["creative_id"], graph["artifact_id"], digest, str(path),
                self.store.json(compliance), reference_used,
                self.store.json(reference_trace), revision_id,
            ),
        )

    def fail_kit_logo_revision(self, revision_id: str, error: Exception) -> None:
        bounded = {"type": type(error).__name__, "message": str(error)[:1000]}
        self.store.execute(
            """UPDATE brand_kit_logo_revisions SET status='failed',error=%s::jsonb,
                      compliance=jsonb_set(compliance,'{passed}','false'::jsonb,true),
                      completed_at=NOW(),updated_at=NOW() WHERE id=%s RETURNING 1""",
            (self.store.json(bounded), revision_id),
        )

    def requeue_kit_logo_revision(self, revision_id: str) -> dict[str, Any]:
        revision = self.kit_logo_revision(revision_id)
        if revision["status"] != "failed":
            raise ValueError("only a failed logo revision can be retried")
        with self.store.transaction() as connection:
            connection.execute(
                """UPDATE brand_kit_logo_revisions SET status='pending',attempt=0,error=NULL,
                          compliance='{}'::jsonb,started_at=NULL,completed_at=NULL,updated_at=NOW()
                   WHERE id=%s""",
                (revision_id,),
            )
            # A user-authorized retry is a new generation cycle. Keep the
            # original automatic attempts auditable, but force new provider
            # calls instead of replaying their cached failed candidates.
            connection.execute(
                """UPDATE brand_provider_tasks
                      SET status='failed',error_text='owner-authorized logo revision retry',
                          updated_at=NOW()
                    WHERE run_id=(
                              SELECT k.run_id FROM brand_kits k WHERE k.id=%s
                          )
                      AND stage='LOGO_GENERATION'
                      AND item_key LIKE %s""",
                (
                    revision["base_kit_id"],
                    f"kit-logo-revision:{revision_id}:%",
                ),
            )
        return self.kit_logo_revision(revision_id)

    def reject_kit_logo_revision(self, revision_id: str, *, actor: str) -> dict[str, Any]:
        revision = self.kit_logo_revision(revision_id)
        if revision["status"] != "completed":
            raise ValueError("only a completed logo candidate can be rejected")
        self.store.execute(
            """UPDATE brand_kit_logo_revisions SET status='rejected',reviewed_at=NOW(),
                      updated_at=NOW() WHERE id=%s RETURNING 1""",
            (revision_id,),
        )
        return self.kit_logo_revision(revision_id)

    def approve_kit_logo_revision(
        self, revision_id: str, *, kit_id: str, commander_kit_id: str,
        zip_path: Path, zip_digest: str, manifest: Mapping[str, Any], actor: str,
    ) -> dict[str, Any]:
        revision = self.kit_logo_revision(revision_id)
        if revision["status"] != "completed" or revision.get("compliance", {}).get("passed") is not True:
            raise ValueError("only a compliant completed logo candidate can be approved")
        base = self.kit(str(revision["base_kit_id"]))
        with self.store.transaction() as connection:
            connection.execute(
                "UPDATE brand_kits SET status='superseded' WHERE id=%s AND status='approved'",
                (base["id"],),
            )
            connection.execute(
                """INSERT INTO brand_kits(
                       id,run_id,direction_id,commander_brand_kit_id,previous_commander_brand_kit_id,
                       manifest,zip_digest,zip_path,status,approved_by,source_laval_run_id,
                       project_version,supersedes_kit_id,logo_creative_id,logo_artifact_id,
                       logo_artifact_digest,logo_path
                   ) VALUES(%s,%s,%s,%s,%s,%s::jsonb,%s,%s,'approved',%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    kit_id, base["run_id"], base["direction_id"], commander_kit_id,
                    base["commander_brand_kit_id"], self.store.json(manifest), zip_digest,
                    str(zip_path), actor, revision["source_laval_run_id"],
                    revision["proposed_project_version"], base["id"],
                    revision["creative_id"], revision["artifact_id"],
                    revision["artifact_digest"], revision["logo_path"],
                ),
            )
            connection.execute(
                """UPDATE brand_kit_logo_revisions SET status='approved',approved_kit_id=%s,
                          reviewed_at=NOW(),updated_at=NOW() WHERE id=%s""",
                (kit_id, revision_id),
            )
        return self.kit(kit_id)

    def artifact_path(self, digest: str, asset_root: Path) -> tuple[Path, str]:
        row = self.store.fetchone(
            """SELECT logo_path path,'image/png' mime FROM brand_directions WHERE artifact_digest=%s
               UNION ALL
               SELECT source_logo_path path,'image/png' mime
                 FROM brand_logo_revisions WHERE source_artifact_digest=%s
               UNION ALL
               SELECT logo_path path,'image/png' mime
                 FROM brand_logo_revisions WHERE artifact_digest=%s
               UNION ALL
               SELECT source_logo_path path,'image/png' mime
                 FROM brand_kit_logo_revisions WHERE source_artifact_digest=%s
               UNION ALL
               SELECT logo_path path,'image/png' mime
                 FROM brand_kit_logo_revisions WHERE artifact_digest=%s
               UNION ALL
               SELECT logo_path path,'image/png' mime FROM brand_kits WHERE logo_artifact_digest=%s
               UNION ALL
               SELECT zip_path path,'application/zip' mime FROM brand_kits WHERE zip_digest=%s
               LIMIT 1""",
            (digest, digest, digest, digest, digest, digest, digest),
        )
        if not row:
            raise KeyError("Branding artifact not found")
        path = Path(str(row["path"])).resolve()
        root = asset_root.resolve()
        if path != root and root not in path.parents:
            raise PermissionError("Branding artifact path is outside asset root")
        return path, str(row["mime"])

    def cost(self, run_id: str) -> dict[str, Any]:
        rows = self.store.fetchall(
            """SELECT stage,provider,operation,sum(request_count)::int request_count,
                      sum(input_tokens)::int input_tokens,sum(output_tokens)::int output_tokens,
                      sum(amount_usd)::float amount_usd
               FROM brand_cost_events WHERE run_id=%s GROUP BY stage,provider,operation
               ORDER BY stage,provider,operation""",
            (run_id,),
        )
        return {"items": json_safe(rows), "total_usd": round(sum(float(item["amount_usd"] or 0) for item in rows), 6)}

    def record_cost(
        self, run_id: str, stage: str, provider: str, operation: str, *,
        requests: int = 1, input_tokens: int = 0, output_tokens: int = 0,
        amount_usd: float = 0, metadata: Mapping[str, Any] | None = None,
    ) -> None:
        self.store.execute(
            """INSERT INTO brand_cost_events(
                   id,run_id,stage,provider,operation,request_count,input_tokens,
                   output_tokens,amount_usd,metadata
               ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb) RETURNING 1""",
            (
                new_uuid7(), run_id, stage, provider, operation, requests,
                input_tokens, output_tokens, amount_usd,
                self.store.json(metadata or {}),
            ),
        )

    def invalidate_from(self, run_id: str, stage: str, *, actor: str) -> None:
        stage = stage.upper()
        if stage not in BRAND_STAGES[1:8]:
            raise ValueError("only pre-review Branding stages may be rerun")
        run = self.run(run_id)
        if run["status"] == "completed":
            raise ValueError("approved Brand Kits are immutable; create a new Branding run")
        index = BRAND_STAGES.index(stage)
        with self.store.transaction() as connection:
            if connection.execute("SELECT 1 FROM brand_directions WHERE run_id=%s AND creative_id IS NOT NULL LIMIT 1", (run_id,)).fetchone():
                raise ValueError("published logo history cannot be invalidated; create a new Branding run")
            connection.execute(
                """UPDATE brand_stage_runs SET status=CASE WHEN stage=%s THEN 'pending' ELSE 'stale' END,
                          artifact=NULL,error=NULL,completed_at=NULL,updated_at=NOW()
                   WHERE run_id=%s AND ordinal>=%s""",
                (stage, run_id, index),
            )
            connection.execute("DELETE FROM brand_directions WHERE run_id=%s", (run_id,))
            connection.execute(
                """UPDATE brand_provider_tasks
                      SET status='failed',response=NULL,response_digest=NULL,
                          error_text='owner-authorized stage rerun',updated_at=NOW()
                    WHERE run_id=%s AND stage=ANY(%s::text[])""",
                (run_id, list(BRAND_STAGES[index:8])),
            )
            connection.execute("UPDATE brand_runs SET status='pending',current_stage=%s,error_text=NULL,updated_at=NOW() WHERE id=%s", (stage, run_id))
            connection.execute("INSERT INTO brand_run_actions(id,run_id,action,actor,details) VALUES(%s,%s,'rerun',%s,%s::jsonb)", (new_uuid7(), run_id, actor, self.store.json({"stage": stage})))
