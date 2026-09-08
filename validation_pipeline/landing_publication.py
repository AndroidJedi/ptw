"""Stable path publication for immutable, approved Landing versions."""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import re
from typing import Any, Callable, Iterator, Mapping, Sequence
from uuid import UUID

from commander.ids import new_uuid7
from .local_brief_store import utc_now
from .landing_workspace import normalize_configuration, normalize_content


PUBLICATION_SCHEMA = "ptw.landing.publication.v1"
NAMESPACES = ("ai", "la", "wa")
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
VISUAL_SLOTS = ("hero_visual", "visual_break_visual")


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def normalized_namespace(value: str) -> str:
    result = str(value or "")
    if result not in NAMESPACES:
        raise ValueError("Landing namespace must be ai, la, or wa")
    return result


def normalized_slug(value: str) -> str:
    result = str(value or "")
    if not 3 <= len(result) <= 63 or SLUG.fullmatch(result) is None:
        raise ValueError("Landing slug must be 3-63 lowercase Latin letters, numbers, or single hyphens")
    return result


def normalized_uuid(value: str, name: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as error:
        raise ValueError(f"{name} must be a UUID") from error


def selected_assets(record: Mapping[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in record.get("assets") or []:
        if not isinstance(item, Mapping):
            continue
        slot, digest = item.get("slot"), item.get("sha256")
        if slot in VISUAL_SLOTS and isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest):
            result[str(slot)] = digest
    if set(result) != set(VISUAL_SLOTS):
        raise RuntimeError("Published Landing version does not contain both selected visuals")
    return result


def public_snapshot(publication: Mapping[str, Any], project_name: str, event: Mapping[str, Any], record: Mapping[str, Any]) -> dict[str, Any]:
    namespace, slug = str(publication["namespace"]), str(publication["slug"])
    version_sha256 = str(event["landing_version_sha256"])
    assets = selected_assets(record)
    prefix = f"/api/v1/public/landings/{namespace}/{slug}/versions/{version_sha256}/assets"
    configuration = normalize_configuration(record["configuration"])
    content = normalize_content(record["content"])
    return {
        "canonical_url": f"https://natal-service.com/{namespace}/{slug}",
        "project_name": project_name,
        "configuration": configuration,
        "content": content,
        "assets": {
            slot: f"{prefix}/{slot}/{digest}.png" for slot, digest in assets.items()
        },
        "version_sha256": version_sha256,
        "published_at": event["created_at"],
    }


class DatabaseLandingPublicationAuthority:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    @contextmanager
    def connection(self) -> Iterator[Any]:
        import psycopg
        with psycopg.connect(self.database_url, connect_timeout=5) as connection:
            yield connection

    @staticmethod
    def _publication_row(row: Sequence[Any]) -> dict[str, Any]:
        return {
            "publication_id": str(row[0]), "project_id": str(row[1]),
            "namespace": row[2], "slug": row[3], "status": row[4],
            "current_event_id": None if row[5] is None else str(row[5]),
            "requested_by": row[6], "created_at": row[7].isoformat(),
            "updated_at": row[8].isoformat(),
        }

    @staticmethod
    def _event_row(row: Sequence[Any]) -> dict[str, Any]:
        return {
            "event_id": str(row[0]), "publication_id": str(row[1]),
            "request_id": str(row[2]), "sequence": int(row[3]), "action": row[4],
            "landing_id": None if row[5] is None else str(row[5]),
            "landing_version_id": None if row[6] is None else str(row[6]),
            "landing_version": None if row[7] is None else int(row[7]),
            "landing_version_sha256": row[8], "requested_by": row[9],
            "created_at": row[10].isoformat(),
        }

    @staticmethod
    def _publication_select() -> str:
        return """SELECT entity_id,project_id,namespace,slug,status,current_event_id,
                         requested_by,created_at,updated_at FROM landing_publications"""

    @staticmethod
    def _event_select() -> str:
        return """SELECT entity_id,publication_id,request_id,sequence,action,landing_id,
                         landing_version_id,landing_version,landing_version_sha256,
                         requested_by,created_at FROM landing_publication_events"""

    def _events(self, publication_id: str) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                self._event_select() + " WHERE publication_id=%s ORDER BY sequence DESC",
                (UUID(publication_id),),
            ).fetchall()
        return [self._event_row(row) for row in rows]

    def get(self, project_id: str) -> dict[str, Any] | None:
        project_id = normalized_uuid(project_id, "project_id")
        with self.connection() as connection:
            row = connection.execute(
                self._publication_select() + " WHERE project_id=%s", (UUID(project_id),)
            ).fetchone()
        if row is None:
            return None
        publication = self._publication_row(row)
        publication["schema"] = PUBLICATION_SCHEMA
        publication["canonical_url"] = f"https://natal-service.com/{publication['namespace']}/{publication['slug']}"
        publication["events"] = self._events(publication["publication_id"])
        return publication

    def availability(self, project_id: str, namespace: str, slug: str) -> dict[str, Any]:
        project_id = normalized_uuid(project_id, "project_id")
        namespace, slug = normalized_namespace(namespace), normalized_slug(slug)
        with self.connection() as connection:
            if connection.execute("SELECT 1 FROM validation_projects WHERE entity_id=%s", (UUID(project_id),)).fetchone() is None:
                raise KeyError(project_id)
            row = connection.execute(
                "SELECT project_id FROM landing_publications WHERE namespace=%s AND slug=%s",
                (namespace, slug),
            ).fetchone()
        return {
            "namespace": namespace, "slug": slug,
            "available": row is None or str(row[0]) == project_id,
        }

    def _request_event(self, request_id: str, request_sha256: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(
                self._event_select() + " WHERE request_id=%s", (UUID(request_id),)
            ).fetchone()
            if row is None:
                return None
            existing_sha = connection.execute(
                "SELECT request_sha256 FROM landing_publication_events WHERE request_id=%s",
                (UUID(request_id),),
            ).fetchone()[0]
        if existing_sha != request_sha256:
            raise ValueError("request_id was already used with different publication input")
        return self._event_row(row)

    def publish(
        self, *, project_id: str, request_id: str, landing_id: str, version: int,
        namespace: str | None, slug: str | None, requested_by: str,
    ) -> dict[str, Any]:
        from psycopg.errors import UniqueViolation
        from psycopg.types.json import Jsonb

        project_id = normalized_uuid(project_id, "project_id")
        landing_id = normalized_uuid(landing_id, "landing_id")
        request_id = normalized_uuid(request_id, "request_id")
        if isinstance(version, bool) or not isinstance(version, int) or version < 1:
            raise ValueError("Landing version must be a positive integer")
        normalized_input = {
            "action": "publish", "project_id": project_id, "landing_id": landing_id,
            "version": version, "namespace": namespace, "slug": slug,
        }
        request_sha256 = sha256_json(normalized_input)
        prior = self._request_event(request_id, request_sha256)
        if prior is not None:
            return {"publication": self.get(project_id), "event": prior, "created": False}
        try:
            with self.connection() as connection:
                connection.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (f"landing-publication-request:{request_id}",))
                connection.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (f"landing-publication:{project_id}",))
                duplicate_row = connection.execute(
                    self._event_select() + " WHERE request_id=%s", (UUID(request_id),)
                ).fetchone()
                if duplicate_row is not None:
                    duplicate_sha = connection.execute(
                        "SELECT request_sha256 FROM landing_publication_events WHERE request_id=%s",
                        (UUID(request_id),),
                    ).fetchone()[0]
                    if duplicate_sha != request_sha256:
                        raise ValueError("request_id was already used with different publication input")
                    return {"publication": self.get(project_id), "event": self._event_row(duplicate_row), "created": False}
                project = connection.execute("SELECT name FROM validation_projects WHERE entity_id=%s", (UUID(project_id),)).fetchone()
                if project is None:
                    raise KeyError(project_id)
                publication_row = connection.execute(
                    self._publication_select() + " WHERE project_id=%s", (UUID(project_id),)
                ).fetchone()
                if publication_row is None:
                    if namespace is None or slug is None:
                        raise ValueError("First publication requires namespace and slug")
                    lane, path_slug = normalized_namespace(namespace), normalized_slug(slug)
                    publication_id = new_uuid7()
                    connection.execute(
                        "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'landing_publication',%s)",
                        (UUID(publication_id), Jsonb({"schema_version": 1, "namespace": lane, "slug": path_slug})),
                    )
                    connection.execute(
                        """INSERT INTO landing_publications(entity_id,project_id,namespace,slug,status,requested_by)
                           VALUES(%s,%s,%s,%s,'unpublished',%s)""",
                        (UUID(publication_id), UUID(project_id), lane, path_slug, requested_by),
                    )
                    self._edge(connection, project_id, "contains", publication_id, {"member": "landing_publication"})
                else:
                    publication = self._publication_row(publication_row)
                    publication_id = publication["publication_id"]
                    if namespace is not None and normalized_namespace(namespace) != publication["namespace"]:
                        raise ValueError("Project public namespace is permanently reserved")
                    if slug is not None and normalized_slug(slug) != publication["slug"]:
                        raise ValueError("Project public slug is permanently reserved")
                version_row = connection.execute(
                    """SELECT version.entity_id,version.version_sha256
                       FROM landing_versions version
                       JOIN landing_workspaces page ON page.entity_id=version.landing_id
                       WHERE page.project_id=%s AND page.entity_id=%s AND version.version=%s""",
                    (UUID(project_id), UUID(landing_id), version),
                ).fetchone()
                if version_row is None:
                    raise ValueError("Only an approved Landing version from this Project can be published")
                sequence = int(connection.execute(
                    "SELECT count(*)+1 FROM landing_publication_events WHERE publication_id=%s",
                    (UUID(publication_id),),
                ).fetchone()[0])
                event_id = new_uuid7()
                connection.execute(
                    "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'landing_publication_event',%s)",
                    (UUID(event_id), Jsonb({"schema_version": 1, "action": "publish", "sequence": sequence})),
                )
                connection.execute(
                    """INSERT INTO landing_publication_events(
                           entity_id,publication_id,request_id,request_sha256,sequence,action,
                           landing_id,landing_version_id,landing_version,landing_version_sha256,requested_by
                       ) VALUES(%s,%s,%s,%s,%s,'publish',%s,%s,%s,%s,%s)""",
                    (UUID(event_id), UUID(publication_id), UUID(request_id), request_sha256, sequence,
                     UUID(landing_id), version_row[0], version, version_row[1], requested_by),
                )
                connection.execute(
                    "UPDATE landing_publications SET status='published',current_event_id=%s,updated_at=clock_timestamp() WHERE entity_id=%s",
                    (UUID(event_id), UUID(publication_id)),
                )
                self._edge(connection, publication_id, "contains", event_id, {"member": "landing_publication_event", "action": "publish"})
                self._edge(connection, event_id, "derived_from", str(version_row[0]), {"input": "approved_landing_version", "version": version, "sha256": version_row[1]})
                connection.execute(
                    "INSERT INTO commander_audit_events(id,actor,action,target_id,details) VALUES(%s,%s,'landing.publish',%s,%s)",
                    (UUID(new_uuid7()), requested_by, UUID(publication_id), Jsonb({"event_id": event_id, "landing_id": landing_id, "version": version})),
                )
        except UniqueViolation as error:
            raise ValueError("That Landing namespace and slug are already reserved") from error
        publication = self.get(project_id)
        assert publication is not None
        return {"publication": publication, "event": publication["events"][0], "created": True}

    def unpublish(self, *, project_id: str, request_id: str, requested_by: str) -> dict[str, Any]:
        from psycopg.types.json import Jsonb

        project_id = normalized_uuid(project_id, "project_id")
        request_id = normalized_uuid(request_id, "request_id")
        request_sha256 = sha256_json({"action": "unpublish", "project_id": project_id})
        prior = self._request_event(request_id, request_sha256)
        if prior is not None:
            return {"publication": self.get(project_id), "event": prior, "created": False}
        with self.connection() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (f"landing-publication-request:{request_id}",))
            connection.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (f"landing-publication:{project_id}",))
            duplicate_row = connection.execute(
                self._event_select() + " WHERE request_id=%s", (UUID(request_id),)
            ).fetchone()
            if duplicate_row is not None:
                duplicate_sha = connection.execute(
                    "SELECT request_sha256 FROM landing_publication_events WHERE request_id=%s",
                    (UUID(request_id),),
                ).fetchone()[0]
                if duplicate_sha != request_sha256:
                    raise ValueError("request_id was already used with different publication input")
                return {"publication": self.get(project_id), "event": self._event_row(duplicate_row), "created": False}
            row = connection.execute(
                self._publication_select() + " WHERE project_id=%s FOR UPDATE", (UUID(project_id),)
            ).fetchone()
            if row is None:
                raise KeyError(project_id)
            publication = self._publication_row(row)
            if publication["status"] == "unpublished":
                return {"publication": self.get(project_id), "event": None, "created": False}
            sequence = int(connection.execute(
                "SELECT count(*)+1 FROM landing_publication_events WHERE publication_id=%s",
                (UUID(publication["publication_id"]),),
            ).fetchone()[0])
            event_id = new_uuid7()
            connection.execute(
                "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'landing_publication_event',%s)",
                (UUID(event_id), Jsonb({"schema_version": 1, "action": "unpublish", "sequence": sequence})),
            )
            connection.execute(
                """INSERT INTO landing_publication_events(
                       entity_id,publication_id,request_id,request_sha256,sequence,action,requested_by
                   ) VALUES(%s,%s,%s,%s,%s,'unpublish',%s)""",
                (UUID(event_id), UUID(publication["publication_id"]), UUID(request_id), request_sha256, sequence, requested_by),
            )
            connection.execute(
                "UPDATE landing_publications SET status='unpublished',current_event_id=%s,updated_at=clock_timestamp() WHERE entity_id=%s",
                (UUID(event_id), UUID(publication["publication_id"])),
            )
            self._edge(connection, publication["publication_id"], "contains", event_id, {"member": "landing_publication_event", "action": "unpublish"})
            connection.execute(
                "INSERT INTO commander_audit_events(id,actor,action,target_id,details) VALUES(%s,%s,'landing.unpublish',%s,%s)",
                (UUID(new_uuid7()), requested_by, UUID(publication["publication_id"]), Jsonb({"event_id": event_id})),
            )
        current = self.get(project_id)
        assert current is not None
        return {"publication": current, "event": current["events"][0], "created": True}

    @staticmethod
    def _edge(connection: Any, source: str, relation: str, target: str, attributes: Mapping[str, Any]) -> None:
        from psycopg.types.json import Jsonb
        connection.execute(
            "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,%s,%s,%s)",
            (UUID(new_uuid7()), UUID(source), relation, UUID(target), Jsonb(dict(attributes))),
        )

    def _active(self, namespace: str, slug: str) -> tuple[dict[str, Any], dict[str, Any], str, dict[str, Any]]:
        namespace, slug = normalized_namespace(namespace), normalized_slug(slug)
        with self.connection() as connection:
            row = connection.execute(
                """SELECT publication.entity_id,publication.project_id,publication.namespace,
                          publication.slug,publication.status,publication.current_event_id,
                          publication.requested_by,publication.created_at,publication.updated_at,
                          project.name,event.entity_id,event.publication_id,event.request_id,event.sequence,
                          event.action,event.landing_id,event.landing_version_id,event.landing_version,
                          event.landing_version_sha256,event.requested_by,event.created_at,version.record
                   FROM landing_publications publication
                   JOIN validation_projects project ON project.entity_id=publication.project_id
                   JOIN landing_publication_events event ON event.entity_id=publication.current_event_id
                   JOIN landing_versions version ON version.entity_id=event.landing_version_id
                   WHERE publication.namespace=%s AND publication.slug=%s AND publication.status='published'
                     AND event.action='publish'""",
                (namespace, slug),
            ).fetchone()
        if row is None:
            raise KeyError("Published Landing was not found")
        publication = self._publication_row(row[:9])
        event = self._event_row(row[10:21])
        record = dict(row[21])
        if record.get("version_sha256") != event["landing_version_sha256"]:
            raise RuntimeError("Published Landing version digest mismatch")
        return publication, event, str(row[9]), record

    def snapshot(self, namespace: str, slug: str) -> dict[str, Any]:
        publication, event, project_name, record = self._active(namespace, slug)
        return public_snapshot(publication, project_name, event, record)

    def asset(self, namespace: str, slug: str, version_sha256: str, slot: str, digest: str) -> dict[str, Any]:
        if slot not in VISUAL_SLOTS or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise KeyError("Published Landing asset was not found")
        publication, event, _project_name, record = self._active(namespace, slug)
        if event["landing_version_sha256"] != version_sha256 or selected_assets(record).get(slot) != digest:
            raise KeyError("Published Landing asset was not found")
        with self.connection() as connection:
            row = connection.execute(
                "SELECT content,mime_type FROM landing_assets WHERE landing_id=%s AND slot=%s AND content_sha256=%s",
                (UUID(event["landing_id"]), slot, digest),
            ).fetchone()
        if row is None or hashlib.sha256(bytes(row[0])).hexdigest() != digest:
            raise RuntimeError("Published Landing asset digest mismatch")
        return {"bytes": bytes(row[0]), "mime_type": row[1], "sha256": digest}


class LocalLandingPublicationAuthority:
    """Loopback parity over the append-only local store."""

    def __init__(self, store: Any, workspace_for: Callable[[str], Any]) -> None:
        self.store = store
        self.workspace_for = workspace_for

    def _publication(self, project_id: str) -> dict[str, Any] | None:
        return next((item for item in self.store.list("landing_publications") if item["project_id"] == project_id), None)

    def _events(self, publication_id: str) -> list[dict[str, Any]]:
        return sorted(
            (item for item in self.store.list("landing_publication_events") if item["publication_id"] == publication_id),
            key=lambda item: item["sequence"], reverse=True,
        )

    def get(self, project_id: str) -> dict[str, Any] | None:
        project_id = normalized_uuid(project_id, "project_id")
        item = self._publication(project_id)
        if item is None:
            return None
        return {**item, "schema": PUBLICATION_SCHEMA, "canonical_url": f"https://natal-service.com/{item['namespace']}/{item['slug']}", "events": self._events(item["publication_id"])}

    def availability(self, project_id: str, namespace: str, slug: str) -> dict[str, Any]:
        project_id = normalized_uuid(project_id, "project_id")
        self.store.get("projects", project_id)
        namespace, slug = normalized_namespace(namespace), normalized_slug(slug)
        match = next((item for item in self.store.list("landing_publications") if item["namespace"] == namespace and item["slug"] == slug), None)
        return {"namespace": namespace, "slug": slug, "available": match is None or match["project_id"] == project_id}

    def _version(self, project_id: str, landing_id: str, version: int) -> dict[str, Any]:
        page = self.store.get("landing_pages", landing_id)
        if page["project_id"] != project_id:
            raise ValueError("Only an approved Landing version from this Project can be published")
        match = next((item for item in self.store.list("landing_versions") if item["landing_id"] == landing_id and item["version"] == version), None)
        if match is None:
            raise ValueError("Only an approved Landing version from this Project can be published")
        return match

    def publish(self, *, project_id: str, request_id: str, landing_id: str, version: int, namespace: str | None, slug: str | None, requested_by: str) -> dict[str, Any]:
        project_id, landing_id = normalized_uuid(project_id, "project_id"), normalized_uuid(landing_id, "landing_id")
        request_id = normalized_uuid(request_id, "request_id")
        if isinstance(version, bool) or not isinstance(version, int) or version < 1:
            raise ValueError("Landing version must be a positive integer")
        publication = self._publication(project_id)
        if publication is None:
            if namespace is None or slug is None:
                raise ValueError("First publication requires namespace and slug")
            namespace, slug = normalized_namespace(namespace), normalized_slug(slug)
            if not self.availability(project_id, namespace, slug)["available"]:
                raise ValueError("That Landing namespace and slug are already reserved")
        elif (namespace is not None and normalized_namespace(namespace) != publication["namespace"]) or (slug is not None and normalized_slug(slug) != publication["slug"]):
            raise ValueError("Project public URL is permanently reserved")
        version_item = self._version(project_id, landing_id, version)
        fingerprint = {"action": "publish", "project_id": project_id, "landing_id": landing_id, "version": version, "namespace": namespace, "slug": slug}
        event_id, created = self.store.reserve_request(scope="landing-publication", request_id=request_id, fingerprint=fingerprint)
        if not created:
            event = self.store.get("landing_publication_events", event_id)
            return {"publication": self.get(project_id), "event": event, "created": False}
        now = utc_now()
        if publication is None:
            publication_id = new_uuid7()
            publication = {"publication_id": publication_id, "project_id": project_id, "namespace": namespace, "slug": slug, "status": "unpublished", "current_event_id": None, "requested_by": requested_by, "created_at": now, "updated_at": now}
            self.store.append("landing_publications", publication_id, publication)
            self.store.edge(source_id=project_id, relation="contains", target_id=publication_id, evidence={"member": "landing_publication"})
        event = {"event_id": event_id, "publication_id": publication["publication_id"], "request_id": request_id, "sequence": len(self._events(publication["publication_id"])) + 1, "action": "publish", "landing_id": landing_id, "landing_version_id": version_item["version_id"], "landing_version": version, "landing_version_sha256": version_item["version_sha256"], "requested_by": requested_by, "created_at": now}
        self.store.append("landing_publication_events", event_id, event)
        self.store.append("landing_publications", publication["publication_id"], {**publication, "status": "published", "current_event_id": event_id, "updated_at": now})
        self.store.edge(source_id=publication["publication_id"], relation="contains", target_id=event_id, evidence={"action": "publish"})
        self.store.edge(source_id=event_id, relation="derived_from", target_id=version_item["version_id"], evidence={"version": version, "sha256": version_item["version_sha256"]})
        return {"publication": self.get(project_id), "event": event, "created": True}

    def unpublish(self, *, project_id: str, request_id: str, requested_by: str) -> dict[str, Any]:
        project_id, request_id = normalized_uuid(project_id, "project_id"), normalized_uuid(request_id, "request_id")
        fingerprint = {"action": "unpublish", "project_id": project_id}
        prior_event_id = self.store.lookup_request(
            scope="landing-publication", request_id=request_id, fingerprint=fingerprint,
        )
        if prior_event_id is not None:
            return {
                "publication": self.get(project_id),
                "event": self.store.get("landing_publication_events", prior_event_id),
                "created": False,
            }
        publication = self._publication(project_id)
        if publication is None:
            raise KeyError(project_id)
        if publication["status"] == "unpublished":
            return {"publication": self.get(project_id), "event": None, "created": False}
        event_id, created = self.store.reserve_request(
            scope="landing-publication", request_id=request_id, fingerprint=fingerprint,
        )
        if not created:
            event = self.store.get("landing_publication_events", event_id)
            return {"publication": self.get(project_id), "event": event, "created": False}
        now = utc_now()
        event = {"event_id": event_id, "publication_id": publication["publication_id"], "request_id": request_id, "sequence": len(self._events(publication["publication_id"])) + 1, "action": "unpublish", "landing_id": None, "landing_version_id": None, "landing_version": None, "landing_version_sha256": None, "requested_by": requested_by, "created_at": now}
        self.store.append("landing_publication_events", event_id, event)
        self.store.append("landing_publications", publication["publication_id"], {**publication, "status": "unpublished", "current_event_id": event_id, "updated_at": now})
        self.store.edge(source_id=publication["publication_id"], relation="contains", target_id=event_id, evidence={"action": "unpublish"})
        return {"publication": self.get(project_id), "event": event, "created": True}

    def _active(self, namespace: str, slug: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
        namespace, slug = normalized_namespace(namespace), normalized_slug(slug)
        publication = next((item for item in self.store.list("landing_publications") if item["namespace"] == namespace and item["slug"] == slug and item["status"] == "published"), None)
        if publication is None:
            raise KeyError("Published Landing was not found")
        event = self.store.get("landing_publication_events", publication["current_event_id"])
        version = self.store.get("landing_versions", event["landing_version_id"])
        return publication, event, self.store.get("projects", publication["project_id"]), version["record"]

    def snapshot(self, namespace: str, slug: str) -> dict[str, Any]:
        publication, event, project, record = self._active(namespace, slug)
        return public_snapshot(publication, project["name"], event, record)

    def asset(self, namespace: str, slug: str, version_sha256: str, slot: str, digest: str) -> dict[str, Any]:
        _publication, event, _project, record = self._active(namespace, slug)
        if event["landing_version_sha256"] != version_sha256 or selected_assets(record).get(slot) != digest:
            raise KeyError("Published Landing asset was not found")
        return self.workspace_for(event["landing_id"]).visual_image(slot, digest)
