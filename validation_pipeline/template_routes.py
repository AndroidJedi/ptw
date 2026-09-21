"""Authenticated Templates routes; mounted only behind an owner dependency."""
from __future__ import annotations

import json
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from .template_authoring import TemplateAuthoringService, uuid
from .template_extensions import handoff
from .template_store import TemplateConflict


def run_summary(run: dict[str, Any]) -> dict[str, Any]:
    """Expose enough durable state to recover drafts without leaking authoring input."""

    failure = run.get("failure")
    safe_failure = None
    if isinstance(failure, dict):
        safe_failure = {
            "phase": str(failure.get("phase", "unknown"))[:20],
            "category": str(failure.get("category", "provider"))[:20],
            "model": str(failure.get("model", "unknown"))[:80],
            "reasoning_effort": str(failure.get("reasoning_effort", "unknown"))[:20],
            "attempt_count": min(2, max(1, int(failure.get("attempt_count", 1)))),
            "validation_error": str(failure.get("validation_error", ""))[:240],
        }
    previews = {}
    for key, preview in list((run.get("previews") or {}).items())[:4]:
        if not isinstance(preview, dict):
            continue
        previews[str(key)[:80]] = {
            "sha256": str(preview.get("sha256", ""))[:64],
            "definition_sha256": str(preview.get("definition_sha256", ""))[:64],
            "failure_count": min(99, len(preview.get("failures") or [])),
        }
    return {
        "run_id": run["run_id"],
        "scope": run["scope"],
        "status": run["status"],
        "phase": run.get("phase", "unknown"),
        "iterations": max(0, int(run.get("iterations", 0))),
        "state_sha256": run["state_sha256"],
        "error": str(run.get("error") or "")[:240] or None,
        **({"failure": safe_failure} if safe_failure else {}),
        "previews": previews,
    }


def template_router(service: TemplateAuthoringService, *, prefix: str, dependencies: list) -> APIRouter:
    if not dependencies:
        raise ValueError("Templates routes require owner authentication")
    def private_response(response: Response):
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"

    router = APIRouter(prefix=prefix, dependencies=[*dependencies, Depends(private_response)])

    async def body(request: Request) -> dict:
        limit = 11_200_000 if request.url.path.endswith('/references') else 64_000
        data = bytearray()
        async for part in request.stream():
            data.extend(part)
            if len(data) > limit:
                raise HTTPException(413, "Template request exceeds its bounded byte budget")
        try:
            value = json.loads(data)
            if not isinstance(value, dict):
                raise ValueError()
            return value
        except (ValueError, UnicodeDecodeError) as error:
            raise HTTPException(422, "Template request must be one JSON object") from error

    def invoke(fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except KeyError as error:
            raise HTTPException(404, "Template record is unavailable") from error
        except TemplateConflict as error:
            raise HTTPException(409, str(error)) from error
        except (ValueError, TypeError) as error:
            raise HTTPException(422, str(error)) from error
        except RuntimeError as error:
            raise HTTPException(503, "Template operation is temporarily unavailable") from error

    @router.get("")
    def gallery(surface: str | None = None):
        return invoke(service.gallery, surface)

    @router.get("/runs")
    def runs():
        return {"items": [run_summary(run) for run in service.store.list("run", 30)]}

    @router.post("/references")
    def upload(request: dict = Depends(body)):
        return invoke(service.references.upload, request)

    @router.post("/references/{reference_id}/discard")
    def discard(reference_id: str):
        invoke(service.references.discard, reference_id)
        return {"discarded": True}

    @router.post("/runs", status_code=202)
    def create(request: dict = Depends(body)):
        return invoke(service.start, request)

    @router.get("/runs/{run_id}")
    def progress(run_id: str):
        return invoke(lambda: service.store.get("run", uuid(run_id)))

    @router.post("/runs/{run_id}/resume", status_code=202)
    def resume(run_id: str, request: dict = Depends(body)):
        return invoke(service.resume, run_id, request)

    @router.post("/runs/{run_id}/decision")
    def decision(run_id: str, request: dict = Depends(body)):
        return invoke(service.decide, run_id, request)

    @router.get("/runs/{run_id}/capability-handoff")
    def capability(run_id: str):
        return invoke(lambda: handoff(service.store.get("run", uuid(run_id))))

    @router.get("/media/{digest}")
    def preview(digest: str):
        data = invoke(service.preview, digest)
        return Response(data, media_type="image/png", headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff", "X-PTW-Content-SHA256": digest, "ETag": f'"{digest}"'})

    @router.get("/{surface}/{template_id}/versions")
    def versions(surface: str, template_id: str):
        items = service.ensure_builtins() + service.store.list("version", 200)
        return {"items": [{k: item[k] for k in ("surface", "template_id", "template_version", "template_sha256")} for item in items if item["surface"] == surface and item["template_id"] == template_id]}

    @router.get("/{surface}/{template_id}/versions/{version}")
    def version(surface: str, template_id: str, version: int, sha256: str):
        return invoke(service.read, {"surface": surface, "template_id": template_id, "template_version": version, "template_sha256": sha256})

    @router.post("/{surface}/{template_id}/versions/{version}/edit", status_code=202)
    def edit(surface: str, template_id: str, version: int, request: dict = Depends(body)):
        if set(request) - {"request_id", "instruction", "reference_id", "base_sha256"} or not {"request_id", "instruction", "base_sha256"} <= set(request):
            raise HTTPException(422, "Template edit fields are invalid")
        return invoke(service.start, {"scope": surface, "source": {"surface": surface, "template_id": template_id,
            "template_version": version, "template_sha256": request["base_sha256"]},
            **{k: v for k, v in request.items() if k != "base_sha256"}})

    return router
