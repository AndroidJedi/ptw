from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping


def localized(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping) and set(value) >= {"en", "uk"}:
        return {"en": value["en"], "uk": value["uk"]}
    return {"en": value, "uk": value}


class DomainReadModels:
    def __init__(self, idea_database_url: str, commander_database_url: str) -> None:
        self.idea_database_url = idea_database_url
        self.commander_database_url = commander_database_url

    @contextmanager
    def _connect(self, url: str) -> Iterator[Any]:
        import psycopg
        from psycopg.rows import dict_row
        with psycopg.connect(url, row_factory=dict_row, connect_timeout=5) as connection:
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
            laval = connection.execute(
                """SELECT count(*)::int total,
                          count(*) FILTER (WHERE status IN ('pending','running','paused'))::int active,
                          count(*) FILTER (WHERE status='completed')::int completed
                   FROM laval_runs"""
            ).fetchone()
            branding = connection.execute(
                """SELECT count(*)::int total,
                          count(*) FILTER (WHERE status IN ('pending','running','paused','awaiting_review'))::int active,
                          count(*) FILTER (WHERE status='completed')::int completed
                   FROM brand_runs"""
            ).fetchone()
        with self._connect(self.commander_database_url) as connection:
            db_ok = connection.execute("SELECT 1 ok").fetchone()["ok"] == 1
        return {
            "mission": self.mission(),
            "health": {"idea_db": "ok", "commander_db": "ok" if db_ok else "error", "gateway": "ok"},
            "laval_runs": dict(laval),
            "branding_runs": dict(branding),
            "jobs": jobs,
        }

    def brand_review_target(self, run_id: str, direction_id: str) -> dict[str, Any]:
        with self._connect(self.idea_database_url) as connection:
            row = connection.execute(
                """SELECT d.id,d.run_id,d.creative_id,d.artifact_digest,
                          review.feedback_id latest_feedback_id
                   FROM brand_directions d
                   LEFT JOIN LATERAL (
                     SELECT feedback_id FROM commander_creative_reviews
                     WHERE creative_id=d.creative_id ORDER BY created_at DESC LIMIT 1
                   ) review ON TRUE
                   WHERE d.run_id=%s AND d.id=%s""",
                (run_id, direction_id),
            ).fetchone()
        if not row or not row["creative_id"] or not row["artifact_digest"]:
            raise KeyError("Brand logo is not available for review")
        return {
            "direction_id": str(row["id"]),
            "run_id": str(row["run_id"]),
            "creative_id": str(row["creative_id"]),
            "artifact_digest": str(row["artifact_digest"]),
            "latest_feedback_id": str(row["latest_feedback_id"])
            if row["latest_feedback_id"]
            else None,
        }

    def brand_project_review_target(self, project_id: str) -> dict[str, Any]:
        with self._connect(self.idea_database_url) as connection:
            row = connection.execute(
                """SELECT kit.source_laval_run_id,kit.logo_creative_id,
                          kit.logo_artifact_digest,kit.project_version,
                          kit.commander_brand_kit_id,review.feedback_id latest_feedback_id
                   FROM brand_kits kit
                   LEFT JOIN LATERAL (
                     SELECT feedback_id FROM commander_creative_reviews
                     WHERE creative_id=kit.logo_creative_id
                     ORDER BY created_at DESC LIMIT 1
                   ) review ON TRUE
                   WHERE kit.source_laval_run_id=%s AND kit.status='approved'
                   ORDER BY kit.project_version DESC LIMIT 1""",
                (project_id,),
            ).fetchone()
        if not row:
            raise KeyError("Brand Project has no active approved logo")
        return {
            "project_id": str(row["source_laval_run_id"]),
            "creative_id": str(row["logo_creative_id"]),
            "artifact_digest": str(row["logo_artifact_digest"]),
            "kit_version": int(row["project_version"]),
            "brand_kit_id": str(row["commander_brand_kit_id"]),
            "latest_feedback_id": str(row["latest_feedback_id"])
            if row["latest_feedback_id"] else None,
        }

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
            single_review_clause = (
                "AND review.feedback_id IS NULL" if review_status == "pending"
                else "AND review.feedback_id IS NOT NULL" if review_status == "reviewed"
                else ""
            )
            with self._connect(self.commander_database_url) as connection:
                singles = connection.execute(
                    f"""SELECT creative.id uuid,creative.attributes creative_attributes,
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
                         {single_review_clause}
                       ORDER BY creative.created_at DESC LIMIT %s""",
                    (remaining,),
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
        rating: int | None,
        comment: str,
        predicted_ctr: float | None,
        annotations: tuple[Mapping[str, Any], ...],
        decision: str = "changes",
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
            if decision not in {"changes", "approve"}:
                raise ValueError("review decision must be changes or approve")
            if decision == "approve":
                if predicted_ctr is not None or rating is not None or annotations:
                    raise ValueError("logo approval cannot include rating, estimate, or annotations")
                comment = "Approved without changes."
            if supersedes_feedback_id:
                creative = store.get_entity(creative_id)
                with store.transaction():
                    if decision == "approve":
                        feedback, updates = commander.record_logo_approval(
                            creative=creative, artifact_digest=artifact_digest,
                            actor=actor,
                            supersedes_feedback_id=supersedes_feedback_id,
                        )
                    elif predicted_ctr is None and rating is None:
                        feedback, updates = commander.record_text_feedback(
                            creative=creative, artifact_digest=artifact_digest,
                            comment=comment, actor=actor,
                            supersedes_feedback_id=supersedes_feedback_id,
                        )
                    elif predicted_ctr is None:
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
                    if decision == "approve":
                        feedback, updates = commander.record_logo_approval(
                            creative=creative, artifact_digest=artifact_digest,
                            actor=actor,
                        )
                    elif rating is None:
                        feedback, updates = commander.record_text_feedback(
                            creative=creative, artifact_digest=artifact_digest,
                            comment=comment, actor=actor,
                        )
                    else:
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
            if rating is None:
                raise ValueError("10-variant reviews require rating")
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
            root / "docs/architecture/branding-v1.md",
            root / "docs/architecture/branding-kit-component-manifest.md",
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
