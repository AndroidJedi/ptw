from __future__ import annotations

import base64
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Iterator, Mapping


def localized(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping) and set(value) >= {"en", "uk"}:
        return {"en": value["en"], "uk": value["uk"]}
    return {"en": value, "uk": value}


def cursor_encode(value: int) -> str:
    return base64.urlsafe_b64encode(json.dumps({"id": value}).encode()).decode().rstrip("=")


def cursor_decode(value: str | None) -> int:
    if not value:
        return 2**63 - 1
    try:
        padded = value + "=" * (-len(value) % 4)
        result = json.loads(base64.urlsafe_b64decode(padded))
        return int(result["id"])
    except Exception as error:
        raise ValueError("invalid cursor") from error


class DomainReadModels:
    def __init__(self, idea_database_url: str, commander_database_url: str) -> None:
        self.idea_database_url = idea_database_url
        self.commander_database_url = commander_database_url

    @contextmanager
    def _connect(self, url: str) -> Iterator[Any]:
        import psycopg
        from psycopg.rows import dict_row
        with psycopg.connect(url, row_factory=dict_row) as connection:
            yield connection

    def mission(self) -> dict[str, Any]:
        with self._connect(self.idea_database_url) as connection:
            row = connection.execute(
                "SELECT code,name,name_i18n,status,activated_at,deadline_at FROM missions WHERE is_active=TRUE LIMIT 1"
            ).fetchone()
        if not row:
            raise RuntimeError("active mission is not seeded")
        return {
            "code": row["code"], "name": localized(row["name_i18n"] or row["name"]),
            "status": row["status"], "activated_at": row["activated_at"].isoformat(),
            "deadline_at": row["deadline_at"].isoformat(),
        }

    def overview(self, jobs: dict[str, Any]) -> dict[str, Any]:
        with self._connect(self.idea_database_url) as connection:
            trend = connection.execute(
                """SELECT g.number generation,max(s.aggregate_score)::float best,
                          avg(s.aggregate_score)::float average
                   FROM generations g JOIN idea_scores s ON s.generation_id=g.id
                   WHERE g.status='completed' GROUP BY g.number ORDER BY g.number DESC LIMIT 20"""
            ).fetchall()
        with self._connect(self.commander_database_url) as connection:
            pending = connection.execute(
                "SELECT count(*) n FROM commander_ad_slots WHERE creative_id IS NOT NULL AND feedback_id IS NULL"
            ).fetchone()["n"]
            db_ok = connection.execute("SELECT 1 ok").fetchone()["ok"] == 1
        return {
            "mission": self.mission(),
            "health": {"idea_db": "ok", "commander_db": "ok" if db_ok else "error", "gateway": "ok"},
            "idea_score_trend": list(reversed([dict(row) for row in trend])),
            "pending_reviews": pending,
            "jobs": jobs,
        }

    def ideas(self, *, limit: int, cursor: str | None) -> dict[str, Any]:
        before = cursor_decode(cursor)
        with self._connect(self.idea_database_url) as connection:
            rows = connection.execute(
                """SELECT i.id,g.number generation,i.mode,i.title,i.one_liner,
                          i.title_i18n,i.one_liner_i18n,i.details,s.aggregate_score::float score
                   FROM ideas i JOIN generations g ON g.id=i.generation_id
                   LEFT JOIN idea_scores s ON s.idea_id=i.id
                   WHERE i.id < %s ORDER BY i.id DESC LIMIT %s""", (before, limit + 1),
            ).fetchall()
        more = len(rows) > limit
        rows = rows[:limit]
        items = [{
            "id": row["id"], "generation": row["generation"], "mode": row["mode"], "score": row["score"],
            "title": localized(row["title_i18n"] or row["title"]),
            "one_liner": localized(row["one_liner_i18n"] or row["one_liner"]),
            "details": {key: localized(value) for key, value in (row["details"] or {}).items()},
        } for row in rows]
        return {"items": items, "next_cursor": cursor_encode(int(rows[-1]["id"])) if more and rows else None}

    def contexts(self, *, kind: str) -> list[dict[str, Any]]:
        with self._connect(self.idea_database_url if kind == "idea" else self.commander_database_url) as connection:
            if kind == "idea":
                rows = connection.execute(
                    """SELECT c.code,c.name,c.prompt_text,c.active,c.version,c.sort_order,
                              COALESCE(json_agg(json_build_object('version',r.version,'name',r.name,'prompt',r.prompt_text,
                              'changed_by',r.changed_by,'note',r.change_note,'created_at',r.created_at)
                              ORDER BY r.version) FILTER (WHERE r.id IS NOT NULL),'[]') revisions
                       FROM contexts c LEFT JOIN context_revisions r ON r.context_id=c.id
                       GROUP BY c.id ORDER BY c.sort_order"""
                ).fetchall()
            else:
                rows = connection.execute(
                    """SELECT c.code,c.name,c.prompt_text,c.active,c.version,c.sort_order,
                              COALESCE(json_agg(json_build_object('version',r.version,'name',r.name,'prompt',r.prompt_text,
                              'changed_by',r.changed_by,'note',r.change_note,'created_at',r.created_at)
                              ORDER BY r.version) FILTER (WHERE r.id IS NOT NULL),'[]') revisions
                       FROM commander_ad_contexts c LEFT JOIN commander_ad_context_revisions r ON r.context_id=c.id
                       GROUP BY c.id ORDER BY c.sort_order"""
                ).fetchall()
        return [dict(row) for row in rows]

    def revise_context(
        self, *, kind: str, code: str, name: str, prompt: str, actor: str, note: str
    ) -> dict[str, Any]:
        if not name.strip() or not prompt.strip() or len(prompt) > 20_000:
            raise ValueError("context name and 1-20000 character prompt are required")
        if kind == "post":
            from commander.ad_repository import PostgresAdWorkflowRepository
            from commander.postgres_store import connect_postgres
            store = connect_postgres(self.commander_database_url)
            try:
                version = PostgresAdWorkflowRepository(store).revise_context(
                    code, name=name, prompt=prompt, actor=actor, note=note,
                )
            finally:
                store.connection.close()
            return {"code": code.upper(), "version": version}
        if kind != "idea":
            raise ValueError("context kind must be idea or post")
        with self._connect(self.idea_database_url) as connection:
            row = connection.execute(
                "SELECT id,version FROM contexts WHERE code=%s FOR UPDATE", (code.upper(),)
            ).fetchone()
            if not row:
                raise KeyError(code)
            version = int(row["version"]) + 1
            connection.execute(
                "UPDATE contexts SET name=%s,prompt_text=%s,version=%s,updated_at=now() WHERE id=%s",
                (name.strip(), prompt.strip(), version, row["id"]),
            )
            connection.execute(
                """INSERT INTO context_revisions(context_id,version,name,prompt_text,changed_by,change_note)
                   VALUES(%s,%s,%s,%s,%s,%s)""",
                (row["id"], version, name.strip(), prompt.strip(), actor, note[:1000]),
            )
        return {"code": code.upper(), "version": version}

    def posts(self, *, limit: int, review_status: str | None) -> dict[str, Any]:
        review_clause = (
            "AND review.feedback_id IS NULL" if review_status == "pending"
            else "AND review.feedback_id IS NOT NULL" if review_status == "reviewed"
            else ""
        )
        with self._connect(self.commander_database_url) as connection:
            rows = connection.execute(
                f"""SELECT slot.creative_id uuid,slot.batch_id,slot.position,slot.status,
                            creative.attributes creative_attributes,artifact.attributes artifact_attributes,
                            review.feedback_id latest_feedback_id,review.rating,
                            review.predicted_ctr::float predicted_ctr,review.created_at reviewed_at
                     FROM commander_ad_slots slot
                     JOIN commander_entities creative ON creative.id=slot.creative_id
                     JOIN commander_relationships edge ON edge.source_id=creative.id AND edge.relation='generated'
                     JOIN commander_entities artifact ON artifact.id=edge.target_id AND artifact.kind='artifact'
                     LEFT JOIN LATERAL (
                       SELECT feedback_id,rating,predicted_ctr,created_at
                       FROM commander_creative_reviews
                       WHERE creative_id=creative.id ORDER BY created_at DESC LIMIT 1
                     ) review ON TRUE
                     WHERE slot.creative_id IS NOT NULL {review_clause}
                     ORDER BY slot.updated_at,slot.position LIMIT %s""", (limit,),
            ).fetchall()
        items = []
        for row in rows:
            spec = (row["creative_attributes"] or {}).get("spec") or {}
            i18n = spec.get("i18n") or {}
            title = i18n.get("concept_name") or localized(spec.get("concept_name") or "Creative")
            digest = str((row["artifact_attributes"] or {}).get("sha256", ""))
            items.append({
                "uuid": str(row["uuid"]), "batch_id": str(row["batch_id"]), "position": row["position"],
                "review_status": "reviewed" if row["latest_feedback_id"] else "pending",
                "artifact_digest": digest, "image_url": f"/api/v1/artifacts/{digest}", "title": title,
                "latest_feedback_id": str(row["latest_feedback_id"]) if row["latest_feedback_id"] else None,
                "rating": row["rating"], "predicted_ctr": row["predicted_ctr"],
                "reviewed_at": row["reviewed_at"].isoformat() if row["reviewed_at"] else None,
            })
        remaining = max(0, limit - len(items))
        if remaining:
            with self._connect(self.commander_database_url) as connection:
                singles = connection.execute(
                    """SELECT creative.id uuid,creative.attributes creative_attributes,
                              artifact.attributes artifact_attributes,
                              hook.attributes->>'value' hook,
                              review.feedback_id latest_feedback_id,review.rating,
                              review.predicted_ctr::float predicted_ctr,review.created_at reviewed_at
                       FROM commander_entities creative
                       JOIN commander_relationships generated ON generated.source_id=creative.id AND generated.relation='generated'
                       JOIN commander_entities artifact ON artifact.id=generated.target_id AND artifact.kind='artifact'
                       LEFT JOIN LATERAL (
                         SELECT component.attributes FROM commander_relationships contains
                         JOIN commander_entities component ON component.id=contains.target_id
                         WHERE contains.source_id=creative.id AND contains.relation='contains'
                           AND component.kind='creative_component' AND component.attributes->>'component_kind'='hook'
                         LIMIT 1
                       ) hook ON TRUE
                       LEFT JOIN LATERAL (
                         SELECT feedback_id,rating,predicted_ctr,created_at
                         FROM commander_creative_reviews
                         WHERE creative_id=creative.id ORDER BY created_at DESC LIMIT 1
                       ) review ON TRUE
                       WHERE creative.kind='creative'
                         AND NOT (creative.attributes ? 'ad_batch_id')
                         AND (%s IS NULL OR (%s='pending' AND review.feedback_id IS NULL)
                              OR (%s='reviewed' AND review.feedback_id IS NOT NULL))
                       ORDER BY creative.created_at DESC LIMIT %s""",
                    (review_status, review_status, review_status, remaining),
                ).fetchall()
            for row in singles:
                digest = str((row["artifact_attributes"] or {}).get("sha256", ""))
                items.append({
                    "uuid": str(row["uuid"]),
                    "review_status": "reviewed" if row["latest_feedback_id"] else "pending",
                    "artifact_digest": digest, "image_url": f"/api/v1/artifacts/{digest}",
                    "title": localized(row["hook"] or "Creative"),
                    "latest_feedback_id": str(row["latest_feedback_id"]) if row["latest_feedback_id"] else None,
                    "rating": row["rating"], "predicted_ctr": row["predicted_ctr"],
                    "reviewed_at": row["reviewed_at"].isoformat() if row["reviewed_at"] else None,
                })
        return {"items": items, "next_cursor": None}

    def idea_snapshot(self, idea_id: int | None = None) -> dict[str, Any]:
        with self._connect(self.idea_database_url) as connection:
            if idea_id is None:
                row = connection.execute(
                    """SELECT i.*,g.number generation_number,s.aggregate_score::float aggregate_score
                       FROM ideas i JOIN generations g ON g.id=i.generation_id
                       LEFT JOIN idea_scores s ON s.idea_id=i.id
                       WHERE g.status='completed' ORDER BY s.aggregate_score DESC NULLS LAST,i.id DESC LIMIT 1"""
                ).fetchone()
            else:
                row = connection.execute(
                    """SELECT i.*,g.number generation_number,s.aggregate_score::float aggregate_score
                       FROM ideas i JOIN generations g ON g.id=i.generation_id
                       LEFT JOIN idea_scores s ON s.idea_id=i.id WHERE i.id=%s""", (idea_id,),
                ).fetchone()
        if not row:
            raise KeyError("no completed idea is available")
        return {
            "id": row["id"], "title": row["title"], "one_liner": row["one_liner"],
            "details": row["details"], "mode": row["mode"], "parent_ids": row["parent_ids"],
            "generation_number": row["generation_number"], "aggregate_score": row["aggregate_score"],
            "created_at": row["created_at"].isoformat(),
        }

    def create_post_batch(
        self, *, idea_id: int | None, chat_id: int, actor: str, policy_path: Path, asset_directory: Path
    ) -> dict[str, Any]:
        from commander.ad_generation import AdGenerationEngine
        from commander.ad_provider import UnavailableAdProvider
        from commander.ad_repository import PostgresAdWorkflowRepository
        from commander.policy import CommanderPolicy
        from commander.postgres_store import connect_postgres
        from commander.service import Commander

        idea = self.idea_snapshot(idea_id)
        store = connect_postgres(self.commander_database_url)
        try:
            commander = Commander(store, CommanderPolicy.load(policy_path))
            engine = AdGenerationEngine(
                commander, PostgresAdWorkflowRepository(store),
                UnavailableAdProvider("generation runs in commander-ad-worker"), asset_directory,
            )
            batch = engine.enqueue_batch(
                idea_snapshot=idea, chat_id=chat_id, requested_by=actor,
                idempotency_key=f"web:{actor}:{datetime.now(timezone.utc).isoformat()}",
            )
            return {"batch_id": batch.campaign_id, "status": batch.status, "idea_id": idea["id"]}
        finally:
            store.connection.close()

    def create_single_post(
        self, *, request_text: str, actor: str, policy_path: Path, asset_directory: Path
    ) -> dict[str, Any]:
        from commander.creative_service import CreativeProductionService
        from commander.policy import CommanderPolicy
        from commander.postgres_store import connect_postgres
        from commander.renderer import InstagramPostRenderer
        from commander.service import Commander

        if not request_text.strip() or len(request_text) > 1500:
            raise ValueError("post request must be 1-1500 characters")
        store = connect_postgres(self.commander_database_url)
        try:
            commander = Commander(store, CommanderPolicy.load(policy_path))
            service = CreativeProductionService(commander, InstagramPostRenderer(asset_directory / "generated"))
            with store.transaction():
                creative, artifact, _path = service.create_instagram_post(
                    request_text=request_text, requested_by=actor,
                )
            return {"uuid": creative.id, "artifact_digest": artifact.attributes["sha256"], "review_status": "pending"}
        finally:
            store.connection.close()

    def artifact_path(self, digest: str, asset_root: Path) -> Path:
        with self._connect(self.commander_database_url) as connection:
            row = connection.execute(
                "SELECT attributes->>'storage_uri' path FROM commander_entities WHERE kind='artifact' AND attributes->>'sha256'=%s",
                (digest,),
            ).fetchone()
        if not row:
            raise KeyError(digest)
        candidate = Path(row["path"]).resolve()
        root = asset_root.resolve()
        if candidate != root and root not in candidate.parents:
            raise PermissionError("artifact path is outside Commander assets")
        return candidate

    def review(
        self,
        *,
        creative_id: str,
        artifact_digest: str,
        rating: int,
        comment: str,
        predicted_ctr: float | None,
        annotations: tuple[Mapping[str, Any], ...],
        actor: str,
        policy_path: Path,
        asset_directory: Path,
        supersedes_feedback_id: str | None = None,
    ) -> dict[str, Any]:
        from commander.ad_generation import AdGenerationEngine
        from commander.ad_provider import UnavailableAdProvider
        from commander.ad_repository import PostgresAdWorkflowRepository
        from commander.policy import CommanderPolicy
        from commander.postgres_store import connect_postgres
        from commander.service import Commander

        store = connect_postgres(self.commander_database_url)
        try:
            commander = Commander(store, CommanderPolicy.load(policy_path))
            repository = PostgresAdWorkflowRepository(store)
            if supersedes_feedback_id:
                creative = store.get_entity(creative_id)
                with store.transaction():
                    if predicted_ctr is None:
                        feedback, updates = commander.record_annotated_feedback(
                            creative=creative, artifact_digest=artifact_digest, rating=rating,
                            comment=comment, annotations=annotations, actor=actor,
                            supersedes_feedback_id=supersedes_feedback_id,
                        )
                    else:
                        feedback, updates = commander.record_ad_estimate(
                            creative=creative, artifact_digest=artifact_digest,
                            predicted_ctr=predicted_ctr, rating=rating, comment=comment,
                            annotations=annotations, actor=actor,
                            supersedes_feedback_id=supersedes_feedback_id,
                        )
                    repository.save_review_projection(
                        feedback_id=feedback.id, creative_id=creative_id,
                        artifact_digest=artifact_digest, rating=rating, comment=comment,
                        predicted_ctr=predicted_ctr, annotations=annotations,
                        supersedes_feedback_id=supersedes_feedback_id,
                    )
                return {
                    "feedback_id": feedback.id,
                    "weight_update_ids": [item.id for item in updates],
                    "supersedes_feedback_id": supersedes_feedback_id,
                    "next": None,
                }
            try:
                slot = repository.slot_by_creative(creative_id)
            except KeyError:
                creative = store.get_entity(creative_id)
                with store.transaction():
                    feedback, updates = commander.record_annotated_feedback(
                        creative=creative, artifact_digest=artifact_digest, rating=rating,
                        comment=comment, annotations=annotations, actor=actor,
                    )
                    repository.save_review_projection(
                        feedback_id=feedback.id, creative_id=creative_id, artifact_digest=artifact_digest,
                        rating=rating, comment=comment, predicted_ctr=None, annotations=annotations,
                    )
                return {"feedback_id": feedback.id, "weight_update_ids": [item.id for item in updates], "next": None}
            if predicted_ctr is None:
                raise ValueError("10-variant reviews require predicted_ctr")
            engine = AdGenerationEngine(
                commander, repository, UnavailableAdProvider("review-only gateway"), asset_directory,
            )
            result = engine.record_estimate(
                creative_id=creative_id, predicted_ctr=predicted_ctr, rating=rating,
                comment=comment, actor=actor, artifact_digest=artifact_digest, annotations=annotations,
            )
            return {"feedback_id": result.feedback_id, "batch_id": result.batch_id, "position": result.position, "next": "producing_context_conclusion"}
        finally:
            store.connection.close()

    def creative_reviews(self, creative_id: str) -> list[dict[str, Any]]:
        with self._connect(self.commander_database_url) as connection:
            rows = connection.execute(
                """SELECT feedback_id,artifact_digest,rating,overall_comment,predicted_ctr,
                          annotations,supersedes_feedback_id,created_at
                   FROM commander_creative_reviews
                   WHERE creative_id=%s ORDER BY created_at DESC LIMIT 50""",
                (creative_id,),
            ).fetchall()
        return [
            {
                **dict(row),
                "feedback_id": str(row["feedback_id"]),
                "supersedes_feedback_id": str(row["supersedes_feedback_id"])
                if row["supersedes_feedback_id"] else None,
                "predicted_ctr": float(row["predicted_ctr"])
                if row["predicted_ctr"] is not None else None,
                "created_at": row["created_at"].isoformat(),
            }
            for row in rows
        ]

    @staticmethod
    def docs(root: Path, limit: int) -> list[dict[str, str]]:
        allowed = [
            root / "README.md", root / "DESIGN_RULES.md", root / "docs/README.md",
            root / "docs/architecture/commander-architecture-review.md",
            root / "docs/architecture/commander-current-state.md",
            root / "docs/architecture/creative-feedback-learning.md",
            root / "docs/architecture/ad-image-estimation-loop.md",
            root / "docs/operations/owner-control-plane.md",
            root / "docs/operations/disaster-recovery.md",
        ]
        items = []
        for path in allowed[:limit]:
            if path.is_file():
                body = path.read_text()
                title = next((line.removeprefix("# ") for line in body.splitlines() if line.startswith("# ")), path.name)
                items.append({"path": str(path.relative_to(root)), "title": title, "body": body})
        return items
