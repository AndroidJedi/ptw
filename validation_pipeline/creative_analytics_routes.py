"""Public ingestion and owner routes for creative analytics."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from fastapi import APIRouter, HTTPException, Query
from fastapi.params import Depends as DependsParameter


def _fail(error: Exception) -> HTTPException:
    if isinstance(error, KeyError):
        return HTTPException(status_code=404, detail=str(error).strip("'"))
    if isinstance(error, RuntimeError):
        return HTTPException(status_code=409, detail=str(error))
    return HTTPException(status_code=400, detail=str(error))


def creative_analytics_public_router(
    service: Any, *, prefix: str,
    dependencies: Sequence[DependsParameter] = (),
) -> APIRouter:
    router = APIRouter(prefix=prefix, dependencies=list(dependencies))

    @router.post("/events", status_code=202)
    def event(request: Mapping[str, Any]) -> dict[str, Any]:
        try:
            return service.record_landing_event(request)
        except (KeyError, ValueError, RuntimeError) as error:
            raise _fail(error) from error

    return router


def creative_analytics_owner_router(
    service: Any, *, prefix: str,
    dependencies: Sequence[DependsParameter] = (),
) -> APIRouter:
    router = APIRouter(prefix=prefix, dependencies=list(dependencies))

    def fields(request: Mapping[str, Any], expected: set[str], message: str) -> None:
        if set(request) != expected:
            raise HTTPException(status_code=400, detail=message)

    def project_scope(scope: str) -> str | None:
        return None if scope == "global" else scope

    @router.get("/{scope}/workspace")
    def workspace(scope: str, window: int = Query(default=30)) -> dict[str, Any]:
        try:
            return service.workspace(project_id=project_scope(scope), window=window)
        except (KeyError, ValueError, RuntimeError) as error:
            raise _fail(error) from error

    @router.post("/{scope}/refresh")
    def refresh(scope: str, request: Mapping[str, Any]) -> dict[str, Any]:
        fields(request, {"provider", "backfill"}, "Analytics refresh fields are invalid")
        if not isinstance(request["backfill"], bool):
            raise HTTPException(status_code=400, detail="Analytics backfill flag must be boolean")
        try:
            return service.refresh(
                project_id=project_scope(scope), provider=str(request["provider"]),
                backfill=request["backfill"],
            )
        except (KeyError, ValueError, RuntimeError) as error:
            raise _fail(error) from error

    @router.post("/{scope}/learning-runs")
    def learning_run(scope: str, request: Mapping[str, Any]) -> dict[str, Any]:
        fields(request, {"request_id", "surface"}, "Creative learning run fields are invalid")
        try:
            return service.run_learning(
                project_id=project_scope(scope), request_id=str(request["request_id"]),
                surface=str(request["surface"]),
            )
        except (KeyError, ValueError, RuntimeError) as error:
            raise _fail(error) from error

    @router.post("/{scope}/learning-runs/{run_id}/decision")
    def decision(scope: str, run_id: str, request: Mapping[str, Any]) -> dict[str, Any]:
        fields(request, {"request_id", "decision", "rules"}, "Creative learning decision fields are invalid")
        if not isinstance(request["rules"], list):
            raise HTTPException(status_code=400, detail="Creative learning rules must be a list")
        try:
            return service.decide(
                project_id=project_scope(scope), run_id=run_id,
                request_id=str(request["request_id"]), decision=str(request["decision"]),
                rules=request["rules"], actor="owner-web",
            )
        except (KeyError, ValueError, RuntimeError) as error:
            raise _fail(error) from error

    @router.post("/{scope}/skills/revisions")
    def revise(scope: str, request: Mapping[str, Any]) -> dict[str, Any]:
        fields(request, {"request_id", "rule"}, "Creative Skill revision fields are invalid")
        if not isinstance(request["rule"], Mapping):
            raise HTTPException(status_code=400, detail="Creative Skill rule must be an object")
        try:
            return service.revise_rule(
                project_id=project_scope(scope), request_id=str(request["request_id"]),
                rule=request["rule"], actor="owner-web",
            )
        except (KeyError, ValueError, RuntimeError) as error:
            raise _fail(error) from error

    @router.post("/{scope}/skills/{rule_id}/delete")
    def delete(scope: str, rule_id: str, request: Mapping[str, Any]) -> dict[str, Any]:
        fields(request, {"request_id"}, "Creative Skill delete fields are invalid")
        try:
            return service.revise_rule(
                project_id=project_scope(scope), request_id=str(request["request_id"]),
                rule={"rule_id": rule_id}, actor="owner-web", delete=True,
            )
        except (KeyError, ValueError, RuntimeError) as error:
            raise _fail(error) from error

    return router
