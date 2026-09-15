"""Manual Instagram validation kits with exact Landing attribution."""

from __future__ import annotations

import csv
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import io
import json
import re
import threading
from typing import Any, Mapping, Sequence
from urllib.parse import parse_qs, urlsplit
from uuid import NAMESPACE_URL, UUID, uuid5
import zipfile

from commander.ids import new_uuid7
from .approved_posts import ApprovedPostSources, caption_with_url, normalized_uuid
from .local_brief_store import sha256_json, utc_now


TEST_STATES = {"prepared", "active", "completed", "abandoned"}
TERMINAL_STATES = {"completed", "abandoned"}
CSV_ALIASES = {
    "ad_name": {"ad name", "ad", "ad_name", "advertisement name"},
    "spend": {"amount spent", "spend", "amount_spent"},
    "impressions": {"impressions", "impression"},
    "link_clicks": {"link clicks", "link_clicks", "clicks (all)", "clicks"},
    "landing_page_views": {"landing page views", "landing_page_views", "website landing page views"},
}


def _clean_name(value: Any, label: str, maximum: int = 80) -> str:
    result = " ".join(str(value or "").split())
    if not 1 <= len(result) <= maximum:
        raise ValueError(f"{label} must contain 1-{maximum} characters")
    return result


def _integer(value: Any, label: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f"{label} must be an integer between {minimum} and {maximum}")
    return value


def _state(events: Sequence[Mapping[str, Any]]) -> str:
    actions = {str(item["action"]) for item in events}
    if "completed" in actions:
        return "completed"
    if "abandoned" in actions:
        return "abandoned"
    if "activated" in actions:
        return "active"
    return "prepared"


def _source_version_id(source: Mapping[str, Any]) -> str:
    return str(source.get("version_id") or uuid5(
        NAMESPACE_URL,
        f"ptw-studio-version:{source['creative_id']}:{source['version']}:{source['version_sha256']}",
    ))


class LocalInstagramValidationAuthority:
    def __init__(self, store: Any) -> None:
        self.store = store
        self._lock = threading.RLock()

    @contextmanager
    def lock(self, key: str):
        import fcntl
        directory = self.store.root / "instagram-validation-locks"
        directory.mkdir(exist_ok=True)
        with self._lock, (directory / hashlib.sha256(key.encode()).hexdigest()).open("a") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def _events(self, kind: str, identifier: str, field: str) -> list[dict[str, Any]]:
        return sorted(
            (item for item in self.store.list(kind) if item[field] == identifier),
            key=lambda item: item["created_at"],
        )

    def package(self, identifier: str) -> dict[str, Any]:
        value = self.store.get("instagram_manual_post_packages", normalized_uuid(identifier, "package_id"))
        return {**value, "events": self._events("instagram_manual_post_events", value["package_id"], "package_id")}

    def packages(self, project_id: str) -> list[dict[str, Any]]:
        return [self.package(item["package_id"]) for item in self.store.list("instagram_manual_post_packages") if item["project_id"] == project_id]

    def create_package(self, value: Mapping[str, Any], event: Mapping[str, Any]) -> tuple[dict[str, Any], bool]:
        with self._lock:
            prior = next((item for item in self.store.list("instagram_manual_post_packages") if item["request_id"] == value["request_id"]), None)
            if prior:
                if prior["request_sha256"] != value["request_sha256"]:
                    raise ValueError("request_id was reused with different manual Post input")
                return self.package(prior["package_id"]), False
            self.store.append("instagram_manual_post_packages", str(value["package_id"]), value)
            self.store.append("instagram_manual_post_events", str(event["event_id"]), event)
            return self.package(str(value["package_id"])), True

    def package_event(self, package_id: str, value: Mapping[str, Any]) -> tuple[dict[str, Any], bool]:
        with self._lock:
            package = self.package(package_id)
            prior = next((item for item in self.store.list("instagram_manual_post_events") if item["request_id"] == value["request_id"]), None)
            if prior:
                if prior["request_sha256"] != value["request_sha256"]:
                    raise ValueError("request_id was reused with different manual Post action")
                return self.package(package_id), False
            if any(item["action"] in {"published", "abandoned"} for item in package["events"]):
                raise RuntimeError("Manual Post package is already terminal")
            self.store.append("instagram_manual_post_events", str(value["event_id"]), value)
            return self.package(package_id), True

    def test(self, identifier: str) -> dict[str, Any]:
        value = self.store.get("instagram_validation_tests", normalized_uuid(identifier, "test_id"))
        arms = sorted((item for item in self.store.list("instagram_validation_arms") if item["test_id"] == identifier), key=lambda item: item["ordinal"])
        events = self._events("instagram_validation_test_events", identifier, "test_id")
        imports = sorted((item for item in self.store.list("instagram_validation_imports") if item["test_id"] == identifier), key=lambda item: item["created_at"], reverse=True)
        rows = [item for item in self.store.list("instagram_validation_import_rows") if item["import_id"] in {entry["import_id"] for entry in imports}]
        return {**value, "state": _state(events), "arms": arms, "events": events, "imports": imports, "import_rows": rows}

    def tests(self, project_id: str) -> list[dict[str, Any]]:
        return [self.test(item["test_id"]) for item in self.store.list("instagram_validation_tests") if item["project_id"] == project_id]

    def create_test(self, value: Mapping[str, Any], arms: Sequence[Mapping[str, Any]], event: Mapping[str, Any]) -> tuple[dict[str, Any], bool]:
        with self._lock:
            prior = next((item for item in self.store.list("instagram_validation_tests") if item["request_id"] == value["request_id"]), None)
            if prior:
                if prior["request_sha256"] != value["request_sha256"]:
                    raise ValueError("request_id was reused with different test input")
                return self.test(prior["test_id"]), False
            self.store.append("instagram_validation_tests", str(value["test_id"]), value)
            for arm in arms:
                self.store.append("instagram_validation_arms", str(arm["arm_id"]), arm)
            self.store.append("instagram_validation_test_events", str(event["event_id"]), event)
            return self.test(str(value["test_id"])), True

    def test_event(self, test_id: str, value: Mapping[str, Any]) -> tuple[dict[str, Any], bool]:
        with self._lock:
            test = self.test(test_id)
            prior = next((item for item in self.store.list("instagram_validation_test_events") if item["request_id"] == value["request_id"]), None)
            if prior:
                if prior["request_sha256"] != value["request_sha256"]:
                    raise ValueError("request_id was reused with different test action")
                return self.test(test_id), False
            action, current = str(value["action"]), test["state"]
            allowed = current == "prepared" and action in {"activated", "abandoned"} or current == "active" and action == "completed"
            if not allowed:
                raise RuntimeError(f"Cannot apply {action} while the test is {current}")
            if action == "activated" and any(item["state"] == "active" and item["test_id"] != test_id for item in self.tests(test["project_id"])):
                raise RuntimeError("This Project already has an active Instagram test")
            self.store.append("instagram_validation_test_events", str(value["event_id"]), value)
            return self.test(test_id), True

    def save_import(self, value: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], bool]:
        with self._lock:
            prior = next((item for item in self.store.list("instagram_validation_imports") if item["request_id"] == value["request_id"]), None)
            if prior:
                if prior["request_sha256"] != value["request_sha256"]:
                    raise ValueError("request_id was reused with different CSV input")
                return prior, False
            duplicate = next((item for item in self.store.list("instagram_validation_imports") if item["test_id"] == value["test_id"] and item["csv_sha256"] == value["csv_sha256"]), None)
            if duplicate:
                return duplicate, False
            self.store.append("instagram_validation_imports", str(value["import_id"]), value)
            for row in rows:
                self.store.append("instagram_validation_import_rows", str(row["row_id"]), row)
            return deepcopy(dict(value)), True


class DatabaseInstagramValidationAuthority:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    @contextmanager
    def connection(self):
        import psycopg
        with psycopg.connect(self.database_url, connect_timeout=5) as connection:
            yield connection

    @contextmanager
    def lock(self, key: str):
        with self.connection() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", ("instagram-validation:" + key,))
            yield

    @staticmethod
    def _edge(connection: Any, source: str, relation: str, target: str, attributes: Mapping[str, Any]) -> None:
        from psycopg.types.json import Jsonb
        connection.execute("INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,%s,%s,%s)", (UUID(new_uuid7()), UUID(source), relation, UUID(target), Jsonb(dict(attributes))))

    def package(self, identifier: str) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute("SELECT entity_id,request_id,request_sha256,project_id,source_creative_id,source_version_id,source_version,source_version_sha256,render_sha256,caption,caption_sha256,created_at FROM instagram_manual_post_packages WHERE entity_id=%s", (UUID(normalized_uuid(identifier, "package_id")),)).fetchone()
            if row is None:
                raise KeyError("Manual Post package was not found")
            events = connection.execute("SELECT entity_id,request_id,request_sha256,action,requested_by,created_at FROM instagram_manual_post_events WHERE package_id=%s ORDER BY created_at", (row[0],)).fetchall()
        return {"package_id": str(row[0]), "request_id": str(row[1]), "request_sha256": row[2], "project_id": str(row[3]), "source_creative_id": str(row[4]), "source_version_id": str(row[5]), "source_version": int(row[6]), "source_version_sha256": row[7], "render_sha256": row[8], "caption": row[9], "caption_sha256": row[10], "created_at": row[11].isoformat(), "events": [{"event_id": str(item[0]), "package_id": str(row[0]), "request_id": str(item[1]), "request_sha256": item[2], "action": item[3], "requested_by": item[4], "created_at": item[5].isoformat()} for item in events]}

    def packages(self, project_id: str) -> list[dict[str, Any]]:
        with self.connection() as connection:
            ids = [str(row[0]) for row in connection.execute("SELECT entity_id FROM instagram_manual_post_packages WHERE project_id=%s ORDER BY created_at DESC", (UUID(project_id),)).fetchall()]
        return [self.package(item) for item in ids]

    def create_package(self, value: Mapping[str, Any], event: Mapping[str, Any]) -> tuple[dict[str, Any], bool]:
        from psycopg.types.json import Jsonb
        with self.connection() as connection:
            prior = connection.execute("SELECT entity_id,request_sha256 FROM instagram_manual_post_packages WHERE request_id=%s", (UUID(str(value["request_id"])),)).fetchone()
            if prior:
                if prior[1] != value["request_sha256"]: raise ValueError("request_id was reused with different manual Post input")
                return self.package(str(prior[0])), False
            package_id, event_id = UUID(str(value["package_id"])), UUID(str(event["event_id"]))
            connection.execute("INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'instagram_manual_post_package',%s),(%s,'instagram_manual_post_event',%s)", (package_id, Jsonb({"project_id": value["project_id"]}), event_id, Jsonb({"action": "prepared"})))
            connection.execute("INSERT INTO instagram_manual_post_packages(entity_id,request_id,request_sha256,project_id,source_creative_id,source_version_id,source_version,source_version_sha256,render_sha256,caption,caption_sha256) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (package_id, UUID(str(value["request_id"])), value["request_sha256"], UUID(str(value["project_id"])), UUID(str(value["source_creative_id"])), UUID(str(value["source_version_id"])), value["source_version"], value["source_version_sha256"], value["render_sha256"], value["caption"], value["caption_sha256"]))
            connection.execute("INSERT INTO instagram_manual_post_events(entity_id,package_id,request_id,request_sha256,action,requested_by) VALUES(%s,%s,%s,%s,%s,%s)", (event_id, package_id, UUID(str(event["request_id"])), event["request_sha256"], event["action"], event["requested_by"]))
            self._edge(connection, value["project_id"], "contains", str(package_id), {"member": "instagram_manual_post_package"})
            self._edge(connection, str(package_id), "derived_from", value["source_version_id"], {"input": "approved_post"})
            self._edge(connection, str(package_id), "contains", str(event_id), {"member": "instagram_manual_post_event", "action": "prepared"})
        return self.package(str(value["package_id"])), True

    def package_event(self, package_id: str, value: Mapping[str, Any]) -> tuple[dict[str, Any], bool]:
        from psycopg.types.json import Jsonb
        package_id = normalized_uuid(package_id, "package_id")
        with self.connection() as connection:
            prior = connection.execute("SELECT package_id,request_sha256 FROM instagram_manual_post_events WHERE request_id=%s", (UUID(str(value["request_id"])),)).fetchone()
            if prior:
                if prior[1] != value["request_sha256"]: raise ValueError("request_id was reused with different manual Post action")
                return self.package(str(prior[0])), False
            terminal = connection.execute("SELECT 1 FROM instagram_manual_post_events WHERE package_id=%s AND action IN ('published','abandoned')", (UUID(package_id),)).fetchone()
            if terminal: raise RuntimeError("Manual Post package is already terminal")
            event_id = UUID(str(value["event_id"]))
            connection.execute("INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'instagram_manual_post_event',%s)", (event_id, Jsonb({"action": value["action"]})))
            connection.execute("INSERT INTO instagram_manual_post_events(entity_id,package_id,request_id,request_sha256,action,requested_by) VALUES(%s,%s,%s,%s,%s,%s)", (event_id, UUID(package_id), UUID(str(value["request_id"])), value["request_sha256"], value["action"], value["requested_by"]))
            self._edge(connection, package_id, "contains", str(event_id), {"member": "instagram_manual_post_event"})
        return self.package(package_id), True

    def test(self, identifier: str) -> dict[str, Any]:
        identifier = normalized_uuid(identifier, "test_id")
        with self.connection() as connection:
            row = connection.execute("SELECT entity_id,request_id,request_sha256,project_id,name,total_budget_minor,currency,duration_days,daily_budget_minor,landing_publication_id,landing_publication_event_id,landing_version_id,landing_version_sha256,canonical_url,campaign_name,ad_set_name,requested_by,created_at FROM instagram_validation_tests WHERE entity_id=%s", (UUID(identifier),)).fetchone()
            if row is None: raise KeyError("Instagram test was not found")
            arm_rows = connection.execute("SELECT entity_id,ordinal,source_creative_id,source_version_id,source_version,source_version_sha256,render_sha256,headline,primary_text,tracked_url,ad_name,created_at FROM instagram_validation_arms WHERE test_id=%s ORDER BY ordinal", (UUID(identifier),)).fetchall()
            event_rows = connection.execute("SELECT entity_id,request_id,request_sha256,action,requested_by,created_at FROM instagram_validation_test_events WHERE test_id=%s ORDER BY created_at", (UUID(identifier),)).fetchall()
            import_rows = connection.execute("SELECT entity_id,request_id,csv_sha256,mapping,ignored_rows,requested_by,created_at FROM instagram_validation_imports WHERE test_id=%s ORDER BY created_at DESC", (UUID(identifier),)).fetchall()
            result_rows = connection.execute("SELECT entity_id,import_id,arm_id,metrics,reporting_start,reporting_end,created_at FROM instagram_validation_import_rows WHERE import_id IN (SELECT entity_id FROM instagram_validation_imports WHERE test_id=%s)", (UUID(identifier),)).fetchall()
        events = [{"event_id": str(item[0]), "test_id": identifier, "request_id": str(item[1]), "request_sha256": item[2], "action": item[3], "requested_by": item[4], "created_at": item[5].isoformat()} for item in event_rows]
        return {"test_id": str(row[0]), "request_id": str(row[1]), "request_sha256": row[2], "project_id": str(row[3]), "name": row[4], "total_budget_minor": int(row[5]), "currency": row[6], "duration_days": int(row[7]), "daily_budget_minor": int(row[8]), "landing": {"publication_id": str(row[9]), "event_id": str(row[10]), "landing_version_id": str(row[11]), "landing_version_sha256": row[12], "canonical_url": row[13]}, "campaign_name": row[14], "ad_set_name": row[15], "requested_by": row[16], "created_at": row[17].isoformat(), "state": _state(events), "arms": [{"arm_id": str(item[0]), "test_id": identifier, "project_id": str(row[3]), "ordinal": int(item[1]), "source_creative_id": str(item[2]), "source_version_id": str(item[3]), "source_version": int(item[4]), "source_version_sha256": item[5], "render_sha256": item[6], "headline": item[7], "primary_text": item[8], "tracked_url": item[9], "ad_name": item[10], "created_at": item[11].isoformat()} for item in arm_rows], "events": events, "imports": [{"import_id": str(item[0]), "test_id": identifier, "request_id": str(item[1]), "csv_sha256": item[2], "mapping": dict(item[3]), "ignored_rows": int(item[4]), "requested_by": item[5], "created_at": item[6].isoformat()} for item in import_rows], "import_rows": [{"row_id": str(item[0]), "import_id": str(item[1]), "arm_id": str(item[2]), "metrics": dict(item[3]), "reporting_start": None if item[4] is None else item[4].isoformat(), "reporting_end": None if item[5] is None else item[5].isoformat(), "created_at": item[6].isoformat()} for item in result_rows]}

    def tests(self, project_id: str) -> list[dict[str, Any]]:
        with self.connection() as connection:
            ids = [str(row[0]) for row in connection.execute("SELECT entity_id FROM instagram_validation_tests WHERE project_id=%s ORDER BY created_at DESC", (UUID(project_id),)).fetchall()]
        return [self.test(item) for item in ids]

    def create_test(self, value: Mapping[str, Any], arms: Sequence[Mapping[str, Any]], event: Mapping[str, Any]) -> tuple[dict[str, Any], bool]:
        from psycopg.types.json import Jsonb
        with self.connection() as connection:
            prior = connection.execute("SELECT entity_id,request_sha256 FROM instagram_validation_tests WHERE request_id=%s", (UUID(str(value["request_id"])),)).fetchone()
            if prior:
                if prior[1] != value["request_sha256"]: raise ValueError("request_id was reused with different test input")
                return self.test(str(prior[0])), False
            test_id, event_id = UUID(str(value["test_id"])), UUID(str(event["event_id"]))
            connection.execute("INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'instagram_validation_test',%s),(%s,'instagram_validation_test_event',%s)", (test_id, Jsonb({"project_id": value["project_id"]}), event_id, Jsonb({"action": "prepared"})))
            landing = value["landing"]
            connection.execute("INSERT INTO instagram_validation_tests(entity_id,request_id,request_sha256,project_id,name,total_budget_minor,currency,duration_days,daily_budget_minor,landing_publication_id,landing_publication_event_id,landing_version_id,landing_version_sha256,canonical_url,campaign_name,ad_set_name,requested_by) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (test_id, UUID(str(value["request_id"])), value["request_sha256"], UUID(str(value["project_id"])), value["name"], value["total_budget_minor"], value["currency"], value["duration_days"], value["daily_budget_minor"], UUID(landing["publication_id"]), UUID(landing["event_id"]), UUID(landing["landing_version_id"]), landing["landing_version_sha256"], landing["canonical_url"], value["campaign_name"], value["ad_set_name"], value["requested_by"]))
            for arm in arms:
                arm_id = UUID(str(arm["arm_id"]))
                connection.execute("INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'instagram_validation_arm',%s)", (arm_id, Jsonb({"ordinal": arm["ordinal"]})))
                connection.execute("INSERT INTO instagram_validation_arms(entity_id,test_id,project_id,ordinal,source_creative_id,source_version_id,source_version,source_version_sha256,render_sha256,headline,primary_text,tracked_url,ad_name) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (arm_id, test_id, UUID(str(value["project_id"])), arm["ordinal"], UUID(str(arm["source_creative_id"])), UUID(str(arm["source_version_id"])), arm["source_version"], arm["source_version_sha256"], arm["render_sha256"], arm["headline"], arm["primary_text"], arm["tracked_url"], arm["ad_name"]))
                self._edge(connection, str(test_id), "contains", str(arm_id), {"member": "instagram_validation_arm"})
                self._edge(connection, str(arm_id), "derived_from", arm["source_version_id"], {"input": "approved_post"})
            connection.execute("INSERT INTO instagram_validation_test_events(entity_id,test_id,project_id,request_id,request_sha256,action,requested_by) VALUES(%s,%s,%s,%s,%s,'prepared',%s)", (event_id, test_id, UUID(str(value["project_id"])), UUID(str(event["request_id"])), event["request_sha256"], event["requested_by"]))
            self._edge(connection, value["project_id"], "contains", str(test_id), {"member": "instagram_validation_test"})
            self._edge(connection, str(test_id), "derived_from", landing["event_id"], {"input": "frozen_published_landing"})
            self._edge(connection, str(test_id), "contains", str(event_id), {"member": "instagram_validation_test_event", "action": "prepared"})
        return self.test(str(value["test_id"])), True

    def test_event(self, test_id: str, value: Mapping[str, Any]) -> tuple[dict[str, Any], bool]:
        from psycopg.types.json import Jsonb
        test_id = normalized_uuid(test_id, "test_id")
        with self.connection() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", ("instagram-test-project:" + str(value["project_id"]),))
            prior = connection.execute("SELECT test_id,request_sha256 FROM instagram_validation_test_events WHERE request_id=%s", (UUID(str(value["request_id"])),)).fetchone()
            if prior:
                if prior[1] != value["request_sha256"]: raise ValueError("request_id was reused with different test action")
                return self.test(str(prior[0])), False
            current = self.test(test_id)["state"]
            action = str(value["action"])
            allowed = current == "prepared" and action in {"activated", "abandoned"} or current == "active" and action == "completed"
            if not allowed: raise RuntimeError(f"Cannot apply {action} while the test is {current}")
            if action == "activated":
                active = connection.execute("SELECT event.test_id FROM instagram_validation_test_events event WHERE event.project_id=%s AND event.action='activated' AND NOT EXISTS (SELECT 1 FROM instagram_validation_test_events terminal WHERE terminal.test_id=event.test_id AND terminal.action IN ('completed','abandoned')) AND event.test_id<>%s LIMIT 1", (UUID(str(value["project_id"])), UUID(test_id))).fetchone()
                if active: raise RuntimeError("This Project already has an active Instagram test")
            event_id = UUID(str(value["event_id"]))
            connection.execute("INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'instagram_validation_test_event',%s)", (event_id, Jsonb({"action": action})))
            connection.execute("INSERT INTO instagram_validation_test_events(entity_id,test_id,project_id,request_id,request_sha256,action,requested_by) VALUES(%s,%s,%s,%s,%s,%s,%s)", (event_id, UUID(test_id), UUID(str(value["project_id"])), UUID(str(value["request_id"])), value["request_sha256"], action, value["requested_by"]))
            self._edge(connection, test_id, "contains", str(event_id), {"member": "instagram_validation_test_event", "action": action})
        return self.test(test_id), True

    def save_import(self, value: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], bool]:
        from psycopg.types.json import Jsonb

        def projection(row: Sequence[Any]) -> dict[str, Any]:
            return {
                "import_id": str(row[0]), "test_id": str(row[1]),
                "request_id": str(row[2]), "request_sha256": row[3],
                "csv_sha256": row[4], "mapping": dict(row[5]),
                "ignored_rows": int(row[6]), "requested_by": row[7],
                "created_at": row[8].isoformat(),
            }

        with self.connection() as connection:
            select = "SELECT entity_id,test_id,request_id,request_sha256,csv_sha256,mapping,ignored_rows,requested_by,created_at FROM instagram_validation_imports"
            prior = connection.execute(select + " WHERE request_id=%s", (UUID(str(value["request_id"])),)).fetchone()
            if prior:
                if prior[3] != value["request_sha256"]: raise ValueError("request_id was reused with different CSV input")
                return projection(prior), False
            duplicate = connection.execute(select + " WHERE test_id=%s AND csv_sha256=%s", (UUID(str(value["test_id"])), value["csv_sha256"])).fetchone()
            if duplicate: return projection(duplicate), False
            import_id = UUID(str(value["import_id"]))
            connection.execute("INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'instagram_validation_import',%s)", (import_id, Jsonb({"csv_sha256": value["csv_sha256"]})))
            connection.execute("INSERT INTO instagram_validation_imports(entity_id,test_id,request_id,request_sha256,csv_sha256,mapping,ignored_rows,requested_by) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)", (import_id, UUID(str(value["test_id"])), UUID(str(value["request_id"])), value["request_sha256"], value["csv_sha256"], Jsonb(dict(value["mapping"])), value["ignored_rows"], value["requested_by"]))
            self._edge(connection, str(value["test_id"]), "contains", str(import_id), {"member": "instagram_validation_import"})
            for row in rows:
                row_id = UUID(str(row["row_id"]))
                connection.execute("INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'instagram_validation_import_row',%s)", (row_id, Jsonb({"arm_id": row["arm_id"]})))
                connection.execute("INSERT INTO instagram_validation_import_rows(entity_id,import_id,arm_id,metrics,reporting_start,reporting_end) VALUES(%s,%s,%s,%s,%s,%s)", (row_id, import_id, UUID(str(row["arm_id"])), Jsonb(dict(row["metrics"])), row.get("reporting_start"), row.get("reporting_end")))
                self._edge(connection, str(import_id), "contains", str(row_id), {"member": "instagram_validation_import_row"})
                self._edge(connection, str(row_id), "evaluates", str(row["arm_id"]), {"input": "meta_ads_manager_csv"})
            stored = connection.execute(select + " WHERE entity_id=%s", (import_id,)).fetchone()
            assert stored is not None
            return projection(stored), True


class InstagramValidationService:
    def __init__(self, authority: Any, sources: ApprovedPostSources, analytics: Any) -> None:
        self.authority, self.sources, self.analytics = authority, sources, analytics

    def _attribution(self, source_id: str) -> dict[str, Any] | None:
        return self.analytics.attribution_projection(source_id)

    def _package_projection(self, package: Mapping[str, Any]) -> dict[str, Any]:
        attribution = self._attribution(str(package["package_id"]))
        actions = {item["action"] for item in package["events"]}
        state = "published" if "published" in actions else "abandoned" if "abandoned" in actions else "prepared"
        return {**deepcopy(dict(package)), "state": state, "tracked_url": None if attribution is None else attribution["tracked_url"]}

    def packages(self, project_id: str) -> dict[str, Any]:
        project_id = normalized_uuid(project_id, "project_id")
        self.sources.project(project_id)
        return {"items": [self._package_projection(item) for item in self.authority.packages(project_id)]}

    def create_package(self, project_id: str, request: Mapping[str, Any], actor: str) -> dict[str, Any]:
        if set(request) != {"request_id", "source"} or not isinstance(request.get("source"), Mapping) or set(request["source"]) != {"creative_id", "version"}:
            raise ValueError("Manual Post package fields are invalid")
        project_id, request_id = normalized_uuid(project_id, "project_id"), normalized_uuid(request["request_id"], "request_id")
        source = self.sources.source(project_id, str(request["source"]["creative_id"]), request["source"]["version"])
        landing = self.sources.landing(project_id)
        if not landing: raise RuntimeError("Publish one approved Landing version before preparing an Instagram Post")
        fingerprint = sha256_json({"project_id": project_id, "source": request["source"]})
        prepared = self.analytics.prepare_attribution(landing)
        assert prepared is not None
        package_id = new_uuid7()
        caption = caption_with_url(source["defaults"]["instagram_caption"], prepared["tracked_url"])
        value = {"package_id": package_id, "request_id": request_id, "request_sha256": fingerprint, "project_id": project_id, "source_creative_id": source["creative_id"], "source_version_id": _source_version_id(source), "source_version": source["version"], "source_version_sha256": source["version_sha256"], "render_sha256": source["render_sha256"], "caption": caption, "caption_sha256": hashlib.sha256(caption.encode()).hexdigest(), "created_at": utc_now()}
        event = {"event_id": new_uuid7(), "package_id": package_id, "request_id": request_id, "request_sha256": sha256_json({"package": package_id, "action": "prepared"}), "action": "prepared", "requested_by": actor, "created_at": utc_now()}
        with self.authority.lock("manual-request:" + request_id):
            stored, created = self.authority.create_package(value, event)
        existing = self.analytics.authority.attribution_for_source(stored["package_id"])
        if existing is None:
            if not created:
                tracked = stored["caption"].splitlines()[-1].strip()
                tokens = parse_qs(urlsplit(tracked).query).get("ptw_attribution") or []
                if len(tokens) != 1:
                    raise RuntimeError("Stored manual Post package has no valid attribution token")
                prepared = {"token": tokens[0], "token_sha256": hashlib.sha256(tokens[0].encode()).hexdigest(), "tracked_url": tracked}
            self.analytics.register_attribution(prepared=prepared, project_id=project_id, channel="organic", provider="instagram", source_entity_id=stored["package_id"], landing=landing)
        return {"package": self._package_projection(self.authority.package(stored["package_id"])), "created": created}

    def package_action(self, project_id: str, package_id: str, action: str, request: Mapping[str, Any], actor: str) -> dict[str, Any]:
        if action not in {"published", "abandoned"} or set(request) != {"request_id"}: raise ValueError("Manual Post action fields are invalid")
        project_id = normalized_uuid(project_id, "project_id")
        package_id = normalized_uuid(package_id, "package_id")
        package = self.authority.package(package_id)
        if package["project_id"] != project_id: raise KeyError("Manual Post package was not found in this Project")
        request_id = normalized_uuid(request["request_id"], "request_id")
        value = {"event_id": new_uuid7(), "package_id": package_id, "request_id": request_id, "request_sha256": sha256_json({"package_id": package_id, "action": action}), "action": action, "requested_by": actor, "created_at": utc_now()}
        stored, created = self.authority.package_event(package_id, value)
        return {"package": self._package_projection(stored), "created": created}

    def workspace(self, project_id: str) -> dict[str, Any]:
        project_id = normalized_uuid(project_id, "project_id")
        project = self.sources.project(project_id)
        tests = [self._test_projection(item) for item in self.authority.tests(project_id)]
        return {"schema": "ptw.instagram-validation.workspace.v1", "project_id": project_id, "project_name": project["name"], "sources": self.sources._sources(project_id), "landing": self.sources.landing(project_id), "tests": tests, "manual_packages": [self._package_projection(item) for item in self.authority.packages(project_id)], "fixed_setup": {"objective": "TRAFFIC", "destination": "WEBSITE", "optimization": "LANDING_PAGE_VIEWS", "call_to_action": "LEARN_MORE", "placements": ["INSTAGRAM_FEED"], "dynamic_creative": False, "standard_enhancements": False, "budget_strategy": "CAMPAIGN_BUDGET"}, "ads_manager_url": "https://adsmanager.facebook.com/adsmanager/manage/campaigns"}

    def create_test(self, project_id: str, request: Mapping[str, Any], actor: str) -> dict[str, Any]:
        required = {"request_id", "name", "total_budget_minor", "currency", "duration_days", "arms"}
        if set(request) != required: raise ValueError("Instagram test fields are invalid")
        project_id, request_id = normalized_uuid(project_id, "project_id"), normalized_uuid(request["request_id"], "request_id")
        self.sources.project(project_id)
        landing = self.sources.landing(project_id)
        if not landing: raise RuntimeError("Publish one approved Landing version before preparing a test")
        if not isinstance(request["arms"], list) or not 2 <= len(request["arms"]) <= 6: raise ValueError("Instagram test requires 2-6 approved Posts")
        budget = _integer(request["total_budget_minor"], "total_budget_minor", 1, 10_000_000_000)
        duration = _integer(request["duration_days"], "duration_days", 1, 30)
        currency = str(request["currency"]).upper()
        if not re.fullmatch(r"[A-Z]{3}", currency): raise ValueError("currency must be a three-letter code")
        selections: list[dict[str, Any]] = []
        seen: set[str] = set()
        for raw in request["arms"]:
            if not isinstance(raw, Mapping) or set(raw) != {"creative_id", "version"}: raise ValueError("Each arm must select one approved Post version")
            source = self.sources.source(project_id, str(raw["creative_id"]), raw["version"])
            source_id = _source_version_id(source)
            if source_id in seen: raise ValueError("Each test arm must use a different approved Post version")
            seen.add(source_id); selections.append(source)
        fingerprint = sha256_json({"project_id": project_id, **deepcopy(dict(request))})
        test_id = new_uuid7()
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
        stem = re.sub(r"[^A-Za-z0-9_-]+", "-", _clean_name(request["name"], "name")).strip("-")[:40] or "test"
        campaign_name = f"PTW-{stamp}-{stem}-{test_id[:8]}"
        arms: list[dict[str, Any]] = []
        prepared_by_arm: dict[str, dict[str, Any]] = {}
        for ordinal, source in enumerate(selections, 1):
            arm_id = new_uuid7(); prepared = self.analytics.prepare_attribution(landing); assert prepared is not None
            prepared_by_arm[arm_id] = prepared
            arms.append({"arm_id": arm_id, "test_id": test_id, "project_id": project_id, "ordinal": ordinal, "source_creative_id": source["creative_id"], "source_version_id": _source_version_id(source), "source_version": source["version"], "source_version_sha256": source["version_sha256"], "render_sha256": source["render_sha256"], "headline": source["defaults"]["headline"][:255], "primary_text": caption_with_url(source["defaults"]["instagram_caption"], prepared["tracked_url"]), "tracked_url": prepared["tracked_url"], "ad_name": f"{campaign_name}-AD-{ordinal:02d}", "created_at": utc_now()})
        value = {"test_id": test_id, "request_id": request_id, "request_sha256": fingerprint, "project_id": project_id, "name": _clean_name(request["name"], "name"), "total_budget_minor": budget, "currency": currency, "duration_days": duration, "daily_budget_minor": (budget + duration - 1) // duration, "landing": landing, "campaign_name": campaign_name, "ad_set_name": campaign_name + "-ADSET", "requested_by": actor, "created_at": utc_now()}
        event = {"event_id": new_uuid7(), "test_id": test_id, "project_id": project_id, "request_id": request_id, "request_sha256": sha256_json({"test_id": test_id, "action": "prepared"}), "action": "prepared", "requested_by": actor, "created_at": utc_now()}
        with self.authority.lock("test-request:" + request_id):
            stored, created = self.authority.create_test(value, arms, event)
        for arm in stored["arms"]:
            if self.analytics.authority.attribution_for_source(arm["arm_id"]) is None:
                prepared = prepared_by_arm.get(arm["arm_id"])
                if prepared is None:
                    tokens = parse_qs(urlsplit(arm["tracked_url"]).query).get("ptw_attribution") or []
                    if len(tokens) != 1:
                        raise RuntimeError("Stored test arm has no valid attribution token")
                    prepared = {"token": tokens[0], "token_sha256": hashlib.sha256(tokens[0].encode()).hexdigest(), "tracked_url": arm["tracked_url"]}
                self.analytics.register_attribution(prepared=prepared, project_id=project_id, channel="paid", provider="meta", source_entity_id=arm["arm_id"], landing=landing)
        return {"test": self._test_projection(self.authority.test(stored["test_id"])), "created": created}

    def transition(self, project_id: str, test_id: str, action: str, request: Mapping[str, Any], actor: str) -> dict[str, Any]:
        if action not in {"activated", "completed", "abandoned"} or set(request) != ({"request_id", "campaign_stopped"} if action == "completed" else {"request_id"}): raise ValueError("Instagram test action fields are invalid")
        if action == "completed" and request.get("campaign_stopped") is not True: raise ValueError("Confirm that the Meta campaign and ad set are stopped")
        project_id = normalized_uuid(project_id, "project_id")
        test_id = normalized_uuid(test_id, "test_id")
        test = self.authority.test(test_id)
        if test["project_id"] != project_id: raise KeyError("Instagram test was not found in this Project")
        request_id = normalized_uuid(request["request_id"], "request_id")
        value = {"event_id": new_uuid7(), "test_id": test_id, "project_id": test["project_id"], "request_id": request_id, "request_sha256": sha256_json({"test_id": test_id, "action": action, "campaign_stopped": request.get("campaign_stopped")}), "action": action, "requested_by": actor, "created_at": utc_now()}
        stored, created = self.authority.test_event(test_id, value)
        return {"test": self._test_projection(stored), "created": created}

    def assert_landing_mutation_allowed(self, project_id: str) -> None:
        if any(item["state"] == "active" for item in self.authority.tests(normalized_uuid(project_id, "project_id"))):
            raise RuntimeError("Finish or abandon the active Instagram test before changing the published Landing")

    @staticmethod
    def _header(value: str) -> str:
        value = re.sub(r"\([^)]*\)", "", value).strip().casefold().replace("_", " ")
        return " ".join(value.split())

    def preview_csv(self, project_id: str, test_id: str, csv_text: str) -> dict[str, Any]:
        test = self.authority.test(normalized_uuid(test_id, "test_id"))
        if test["project_id"] != normalized_uuid(project_id, "project_id"): raise KeyError("Instagram test was not found in this Project")
        if not isinstance(csv_text, str) or not csv_text.strip() or len(csv_text.encode()) > 5_000_000: raise ValueError("CSV must contain 1-5,000,000 bytes")
        reader = csv.DictReader(io.StringIO(csv_text.lstrip("\ufeff")))
        headers = list(reader.fieldnames or [])
        normalized = {self._header(item): item for item in headers}
        mapping = {field: next((normalized[alias] for alias in aliases if alias in normalized), None) for field, aliases in CSV_ALIASES.items()}
        if not mapping["ad_name"] or not mapping["spend"]: raise ValueError("CSV must include Ad name and Amount spent columns")
        arm_by_name = {item["ad_name"]: item for item in test["arms"]}
        matched: list[dict[str, Any]] = []; ignored: list[dict[str, Any]] = []
        for index, row in enumerate(reader, 2):
            name = str(row.get(mapping["ad_name"] or "", "")).strip()
            target = arm_by_name.get(name)
            summary = {"row": index, "ad_name": name, "matched_arm_id": None if target is None else target["arm_id"]}
            (matched if target else ignored).append(summary)
        return {"csv_sha256": hashlib.sha256(csv_text.encode()).hexdigest(), "headers": headers, "mapping": mapping, "matched_rows": matched, "ignored_rows": ignored, "can_import": bool(matched)}

    @staticmethod
    def _metric(value: Any) -> int:
        text = re.sub(r"[^0-9-]", "", str(value or "0"))
        try: return max(0, int(Decimal(text or "0")))
        except (InvalidOperation, ValueError): return 0

    @staticmethod
    def _money_minor(value: Any) -> int:
        text = re.sub(r"[^0-9.,-]", "", str(value or "0"))
        if "," in text and "." in text:
            decimal_separator = "," if text.rfind(",") > text.rfind(".") else "."
            thousands_separator = "." if decimal_separator == "," else ","
            text = text.replace(thousands_separator, "").replace(decimal_separator, ".")
        elif "," in text or "." in text:
            separator = "," if "," in text else "."
            pieces = text.split(separator)
            if len(pieces) == 2 and 1 <= len(pieces[1]) <= 2:
                text = pieces[0] + "." + pieces[1]
            else:
                text = "".join(pieces)
        try:
            return max(0, int((Decimal(text or "0") * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)))
        except InvalidOperation:
            return 0

    def import_csv(self, project_id: str, test_id: str, request: Mapping[str, Any], actor: str) -> dict[str, Any]:
        if set(request) != {"request_id", "csv_text", "accept_ignored_rows"}: raise ValueError("CSV import fields are invalid")
        project_id = normalized_uuid(project_id, "project_id")
        test_id = normalized_uuid(test_id, "test_id")
        preview = self.preview_csv(project_id, test_id, str(request["csv_text"]))
        if preview["ignored_rows"] and request["accept_ignored_rows"] is not True: raise RuntimeError("Confirm ignored CSV rows before importing")
        test = self.authority.test(test_id); mapping = preview["mapping"]
        arm_by_name = {item["ad_name"]: item for item in test["arms"]}
        aggregate: dict[str, dict[str, int]] = {}
        for row in csv.DictReader(io.StringIO(str(request["csv_text"]).lstrip("\ufeff"))):
            arm = arm_by_name.get(str(row.get(mapping["ad_name"] or "", "")).strip())
            if not arm: continue
            metrics = aggregate.setdefault(arm["arm_id"], {"spend_minor": 0, "impressions": 0, "link_clicks": 0, "landing_page_views": 0})
            metrics["spend_minor"] += self._money_minor(row.get(mapping["spend"] or "", "0"))
            for field in ("impressions", "link_clicks", "landing_page_views"):
                if mapping[field]: metrics[field] += self._metric(row.get(mapping[field] or ""))
        import_id = new_uuid7(); request_id = normalized_uuid(request["request_id"], "request_id")
        value = {"import_id": import_id, "test_id": test_id, "request_id": request_id, "request_sha256": sha256_json({"test_id": test_id, "csv_sha256": preview["csv_sha256"], "accept_ignored_rows": request["accept_ignored_rows"]}), "csv_sha256": preview["csv_sha256"], "mapping": mapping, "ignored_rows": len(preview["ignored_rows"]), "requested_by": actor, "created_at": utc_now()}
        rows = [{"row_id": new_uuid7(), "import_id": import_id, "arm_id": arm_id, "metrics": metrics, "reporting_start": None, "reporting_end": None, "created_at": utc_now()} for arm_id, metrics in aggregate.items()]
        with self.authority.lock("import-request:" + request_id):
            stored, created = self.authority.save_import(value, rows)
        return {"import": stored, "created": created, "test": self._test_projection(self.authority.test(test_id))}

    def _test_projection(self, test: Mapping[str, Any]) -> dict[str, Any]:
        rollups = self.analytics.authority.list_rollups([test["project_id"]], None)
        latest_import = test["imports"][0]["import_id"] if test.get("imports") else None
        import_by_arm = {row["arm_id"]: row["metrics"] for row in test.get("import_rows", []) if row["import_id"] == latest_import}
        arms = []
        for arm in test["arms"]:
            attribution = self.analytics.authority.attribution_for_source(arm["arm_id"])
            attribution_id = None if attribution is None else attribution["attribution_source_id"]
            funnel = {"landing_view": 0, "primary_cta_click": 0, "contact_click": 0}
            for rollup in rollups:
                if rollup.get("attribution_source_id") == attribution_id and rollup["event_type"] in funnel:
                    funnel[rollup["event_type"]] += int(rollup["cumulative_count"])
            paid = dict(import_by_arm.get(arm["arm_id"]) or {})
            spend = int(paid.get("spend_minor", 0)); clicks = funnel["primary_cta_click"]
            arms.append({**deepcopy(dict(arm)), "paid": paid, "funnel": funnel, "cost_per_primary_cta_minor": None if not clicks else round(spend / clicks)})
        eligible = [item for item in arms if item["cost_per_primary_cta_minor"] is not None]
        leader = min(eligible, key=lambda item: item["cost_per_primary_cta_minor"])["arm_id"] if eligible else None
        return {**deepcopy(dict(test)), "arms": arms, "current_leader_arm_id": leader, "winner_declared": False}

    def launch_kit(self, project_id: str, test_id: str) -> bytes:
        test = self.authority.test(normalized_uuid(test_id, "test_id"))
        if test["project_id"] != normalized_uuid(project_id, "project_id"): raise KeyError("Instagram test was not found in this Project")
        manifest = {"schema": "ptw.instagram-validation.launch-kit.v1", "test_id": test["test_id"], "campaign": {"name": test["campaign_name"], "objective": "Traffic", "budget_minor": test["total_budget_minor"], "daily_budget_minor": test["daily_budget_minor"], "currency": test["currency"], "duration_days": test["duration_days"]}, "ad_set": {"name": test["ad_set_name"], "destination": "Website", "optimization": "Landing page views", "placement": "Instagram Feed only"}, "ads": [{key: arm[key] for key in ("ordinal", "ad_name", "headline", "primary_text", "tracked_url", "source_creative_id", "source_version", "render_sha256")} for arm in test["arms"]]}
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as bundle:
            bundle.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            bundle.writestr("README_UK.txt", "Meta Ads Manager: 1 Campaign → 1 Ad Set → усі Ads. Objective Traffic; Website; Landing Page Views; Instagram Feed; Learn More; campaign budget; dynamic creative та enhancements OFF. Аудиторію задайте лише в Meta — PTW її не зберігає.\n")
            for arm in test["arms"]:
                rendered = self.sources.studio._workspace(arm["source_creative_id"]).version_render(arm["source_version"])
                if rendered["sha256"] != arm["render_sha256"]: raise RuntimeError("Approved Post render digest mismatch")
                stem = f"ad-{arm['ordinal']:02d}"
                bundle.writestr(stem + ".png", rendered["bytes"])
                bundle.writestr(
                    stem + ".txt",
                    f"Ad name: {arm['ad_name']}\n\nHeadline:\n{arm['headline']}\n\n"
                    f"Primary text (includes this Ad's exact tracked URL):\n{arm['primary_text']}\n",
                )
        return output.getvalue()
