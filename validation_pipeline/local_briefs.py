"""Local Product Brief creation, correction, approval, and restart recovery."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Callable, Mapping
from uuid import UUID

from commander.ids import new_uuid7

from .domain import ProductBriefV1, infer_language, product_brief_schema
from .local_brief_store import LocalBriefStore, sha256_json, utc_now
from .local_codex import LocalCodexStructuredProvider, sanitized
from .service import load_product_brief_skill, product_brief_system_prompt


def _uuid(value: str, name: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as error:
        raise ValueError(f"{name} must be a UUID") from error


def _compact(value: str, name: str, minimum: int, maximum: int) -> str:
    result = " ".join(str(value or "").split())
    if not minimum <= len(result) <= maximum:
        raise ValueError(f"{name} must contain {minimum}-{maximum} characters")
    return result


class LocalBriefService:
    """Durable loopback Product Brief orchestration."""

    def __init__(
        self, *, store: LocalBriefStore, provider: LocalCodexStructuredProvider,
        repository_root: Path, on_project_created: Callable[[str], Any] | None = None,
    ) -> None:
        self.store = store
        self.provider = provider
        skill_path = repository_root / "skills/product-brief-generator/SKILL.md"
        self.product_context = load_product_brief_skill(skill_path)
        self.on_project_created = on_project_created

    def _record_invocation(
        self, *, target_id: str, mode: str, input_payload: Mapping[str, Any],
        response: Mapping[str, Any] | None, invocation: Mapping[str, Any] | None,
        error: Exception | None = None,
    ) -> str:
        invocation_id = new_uuid7()
        value = {
            "invocation_id": invocation_id, "target_id": target_id, "mode": mode,
            "input": sanitized(input_payload),
            "input_sha256": sha256_json(sanitized(input_payload)),
            "response": None if response is None else sanitized(response),
            "response_sha256": None if response is None else sha256_json(response),
            "provenance": sanitized(invocation or {}),
            "status": "failed" if error else "completed",
            "error_type": None if error is None else type(error).__name__,
            "error_message": None if error is None else str(error)[:1000],
            "created_at": utc_now(),
        }
        self.store.append("provider_invocations", invocation_id, value)
        self.store.edge(
            source_id=target_id, relation="used_provider_invocation",
            target_id=invocation_id,
        )
        return invocation_id

    def _provider_call(self, *, target_id: str, mode: str, **kwargs: Any) -> dict[str, Any]:
        payload = dict(kwargs["input_payload"])
        try:
            result = self.provider.call(mode=mode, **kwargs)
        except Exception as error:
            self._record_invocation(
                target_id=target_id, mode=mode, input_payload=payload,
                response=None, invocation={"attempts": getattr(error, "attempts", [])},
                error=error,
            )
            raise
        invocation_id = self._record_invocation(
            target_id=target_id, mode=mode, input_payload=payload,
            response=result["response"], invocation=result["invocation"],
        )
        return {**result, "invocation_id": invocation_id}

    def _project(self, project_id: str) -> dict[str, Any]:
        value = self.store.get("projects", _uuid(project_id, "project_id"))
        briefs = [item for item in self.store.list("briefs") if item["project_id"] == project_id]
        latest = briefs[0] if briefs else None
        return {
            **value,
            "latest_brief_id": None if latest is None else latest["brief_id"],
            "latest_brief_status": None if latest is None else latest["status"],
            "brief_count": len(briefs),
        }

    def list_projects(self, limit: int = 100) -> list[dict[str, Any]]:
        return [self._project(item["project_id"]) for item in self.store.list("projects")[:limit]]

    def rename_project(self, project_id: str, name: str) -> dict[str, Any]:
        project = self._project(project_id)
        updated = {
            **{key: value for key, value in project.items() if key not in {
                "latest_brief_id", "latest_brief_status", "brief_count",
            }},
            "name": _compact(name, "Project name", 1, 160),
            "name_source": "owner", "updated_at": utc_now(),
        }
        self.store.append("projects", project_id, updated)
        return self._project(project_id)

    def create_brief(
        self, *, request_id: str, raw_idea: str, required_language: str,
        requested_by: str,
    ) -> tuple[dict[str, Any], dict[str, Any], bool]:
        request_id = _uuid(request_id, "request_id")
        raw_idea = _compact(raw_idea, "raw_idea", 1, 10_000)
        if required_language not in {"uk", "en"}:
            raise ValueError("required_language must be uk or en")
        project_id, created = self.store.reserve_request(
            scope="brief-create", request_id=request_id,
            fingerprint={
                "request_id": request_id, "raw_idea": raw_idea,
                "required_language": required_language,
            },
        )
        if not created:
            project = self._project(project_id)
            brief = next(item for item in self.store.list("briefs") if item["request_id"] == request_id)
            return project, brief, False
        source_id, brief_id = new_uuid7(), new_uuid7()
        now = utc_now()
        project = {
            "project_id": project_id, "request_id": request_id,
            "owner_idea_source_id": source_id, "name": raw_idea[:80],
            "name_source": "raw_idea", "requested_by": requested_by,
            "created_at": now, "updated_at": now,
        }
        source = {
            "source_id": source_id, "project_id": project_id, "kind": "owner_idea",
            "content": raw_idea, "sha256": hashlib.sha256(raw_idea.encode()).hexdigest(),
            "required_language": required_language, "created_at": now,
        }
        brief = {
            "brief_id": brief_id, "project_id": project_id,
            "project_name": project["name"], "request_id": request_id,
            "owner_idea_source_id": source_id, "raw_idea": raw_idea,
            "base_brief_id": None, "feedback_id": None,
            "required_language": required_language, "status": "queued",
            "document": None, "document_sha256": None, "failure_count": 0,
            "approved": False, "created_at": now, "updated_at": now,
        }
        self.store.append("projects", project_id, project)
        self.store.append("sources", source_id, source)
        self.store.append("briefs", brief_id, brief)
        self.store.edge(source_id=project_id, relation="contains", target_id=source_id)
        self.store.edge(source_id=project_id, relation="contains", target_id=brief_id)
        self.store.edge(source_id=brief_id, relation="derived_from", target_id=source_id)
        if self.on_project_created is not None:
            self.on_project_created(project_id)
        return self._project(project_id), brief, True

    def generate_brief(self, brief_id: str) -> dict[str, Any]:
        brief = self.store.get("briefs", _uuid(brief_id, "brief_id"))
        if brief["status"] not in {"queued", "failed"}:
            return brief
        generating = {**brief, "status": "generating", "updated_at": utc_now()}
        self.store.append("briefs", brief_id, generating)
        base = None
        correction = None
        mode = "product_brief"
        if brief.get("base_brief_id"):
            base = self.store.get("briefs", brief["base_brief_id"])["document"]
            correction = self.store.get("feedback", brief["feedback_id"])["comment"]
            mode = "product_brief_revision"
        source = self.store.get("sources", brief["owner_idea_source_id"])
        required_language = str(
            source.get("required_language")
            or (base or {}).get("language")
            or (brief.get("document") or {}).get("language")
            or infer_language(brief["raw_idea"])
        )
        payload = {
            "brief_id": brief_id, "raw_idea": brief["raw_idea"],
            "required_language": required_language, "base_brief": base,
            "owner_correction": correction,
        }
        try:
            result = self._provider_call(
                target_id=brief_id, mode=mode,
                system_prompt=product_brief_system_prompt(self.product_context, required_language),
                input_payload=payload, output_schema=product_brief_schema(required_language),
                idempotency_key=f"{brief_id}:{mode}",
                prompt_version=f"local-product-brief-v2:{mode}",
                response_validator=lambda value: ProductBriefV1.from_dict(
                    value, raw_idea=brief["raw_idea"],
                    required_language=required_language,
                ).to_dict(),
            )
            document = ProductBriefV1.from_dict(
                result["response"], raw_idea=brief["raw_idea"],
                required_language=required_language,
            )
            completed = {
                **generating, "status": "completed", "document": document.to_dict(),
                "document_sha256": document.digest,
                "quality_gates": document.quality_gates,
                "provider_invocation_id": result["invocation_id"],
                "updated_at": utc_now(), **document.to_dict(),
            }
            self.store.append("briefs", brief_id, completed)
            project = self.store.get("projects", brief["project_id"])
            if project["name_source"] != "owner":
                self.store.append("projects", brief["project_id"], {
                    **project, "name": document.to_dict()["product"],
                    "name_source": "product_brief", "updated_at": utc_now(),
                })
            return self.store.get("briefs", brief_id)
        except Exception as error:
            failed = {
                **generating, "status": "failed",
                "failure_count": int(brief["failure_count"]) + 1,
                "error_code": type(error).__name__,
                "error_message": str(error)[:1000], "updated_at": utc_now(),
            }
            self.store.append("briefs", brief_id, failed)
            return failed

    def list_briefs(self, project_id: str | None, limit: int = 100) -> list[dict[str, Any]]:
        if project_id is not None:
            project_id = _uuid(project_id, "project_id")
        values = [
            item for item in self.store.list("briefs")
            if project_id is None or item["project_id"] == project_id
        ]
        for item in values:
            item["project_name"] = self._project(item["project_id"])["name"]
        return values[:limit]

    def get_brief(self, brief_id: str) -> dict[str, Any]:
        value = self.store.get("briefs", _uuid(brief_id, "brief_id"))
        return {**value, "project_name": self._project(value["project_id"])["name"]}

    def correct_brief(
        self, brief_id: str, *, request_id: str, instruction: str,
        requested_by: str,
    ) -> tuple[dict[str, Any], bool]:
        base = self.get_brief(brief_id)
        if base["status"] != "completed":
            raise ValueError("only a completed Product Brief can be corrected")
        request_id = _uuid(request_id, "request_id")
        instruction = _compact(instruction, "instruction", 1, 2000)
        replacement_id, created = self.store.reserve_request(
            scope="brief-correction", request_id=request_id,
            fingerprint={"base_brief_id": brief_id, "instruction": instruction},
        )
        if not created:
            return self.get_brief(replacement_id), False
        feedback_id, weight_update_id = new_uuid7(), new_uuid7()
        feedback = {
            "feedback_id": feedback_id, "project_id": base["project_id"],
            "brief_id": brief_id, "decision": "correction", "comment": instruction,
            "weight_update_id": weight_update_id,
            "requested_by": requested_by, "created_at": utc_now(),
        }
        weight_update = {
            "weight_update_id": weight_update_id,
            "project_id": base["project_id"], "brief_id": brief_id,
            "feedback_id": feedback_id, "component": "product_brief",
            "delta": 0.0, "reason": instruction, "append_only": True,
            "created_at": utc_now(),
        }
        excluded = {
            "product", "target_audience", "main_pain", "promise", "key_benefits",
            "cta", "trust_strategy", "offer", "document", "document_sha256",
            "quality_gates", "provider_invocation_id", "project_name",
        }
        replacement = {
            **{key: value for key, value in base.items() if key not in excluded},
            "brief_id": replacement_id, "request_id": request_id,
            "base_brief_id": brief_id, "feedback_id": feedback_id,
            "status": "queued", "document": None, "document_sha256": None,
            "failure_count": 0, "approved": False,
            "created_at": utc_now(), "updated_at": utc_now(),
        }
        self.store.append("feedback", feedback_id, feedback)
        self.store.append("weight_updates", weight_update_id, weight_update)
        self.store.append("briefs", replacement_id, replacement)
        self.store.edge(
            source_id=base["project_id"], relation="contains", target_id=replacement_id,
        )
        self.store.edge(source_id=feedback_id, relation="evaluates", target_id=brief_id)
        self.store.edge(
            source_id=feedback_id, relation="contains", target_id=weight_update_id,
        )
        self.store.edge(
            source_id=weight_update_id, relation="adjusts", target_id=feedback_id,
        )
        self.store.edge(source_id=replacement_id, relation="supersedes", target_id=brief_id)
        self.store.edge(source_id=replacement_id, relation="derived_from", target_id=feedback_id)
        return self.get_brief(replacement_id), True

    def retry_brief(self, brief_id: str) -> dict[str, Any]:
        brief = self.get_brief(brief_id)
        if brief["status"] != "failed":
            raise ValueError("only a failed Product Brief can be retried")
        queued = {
            **brief, "status": "queued", "error_code": None,
            "error_message": None, "updated_at": utc_now(),
        }
        queued.pop("project_name", None)
        self.store.append("briefs", brief_id, queued)
        return queued

    def approve_brief(self, brief_id: str, requested_by: str) -> tuple[dict[str, Any], bool]:
        brief = self.get_brief(brief_id)
        if brief["status"] != "completed" or not brief.get("document"):
            raise ValueError("only a completed Product Brief can be approved")
        if brief.get("approved"):
            return brief, False
        approval_id = new_uuid7()
        self.store.append("approvals", approval_id, {
            "approval_id": approval_id, "brief_id": brief_id, "authority": "owner",
            "honor_confirmed": True, "requested_by": requested_by,
            "created_at": utc_now(),
        })
        updated = {
            **brief, "approved": True, "approval_id": approval_id,
            "updated_at": utc_now(),
        }
        updated.pop("project_name", None)
        self.store.append("briefs", brief_id, updated)
        return self.get_brief(brief_id), True

    def recover_interrupted(self) -> list[str]:
        briefs: list[str] = []
        for brief in self.store.list("briefs"):
            if brief.get("status") != "generating":
                continue
            self.store.append("briefs", brief["brief_id"], {
                **brief, "status": "queued", "recovered_after_restart": True,
                "updated_at": utc_now(),
            })
            briefs.append(brief["brief_id"])
        return briefs
