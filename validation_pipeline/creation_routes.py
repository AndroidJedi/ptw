"""Owner-authenticated unified creation API."""
import hashlib
import json
import re
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from .creation_export import export_bundle
from .template_store import TemplateConflict


def creation_router(service, *, prefix, dependencies):
    if not dependencies:
        raise ValueError("Creation Studio requires owner authentication")
    def private(response: Response):
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
    router = APIRouter(prefix=prefix, dependencies=[*dependencies, Depends(private)])

    async def body(request):
        data = bytearray()
        limit = 11_200_000 if request.url.path.endswith("/references") else 40_000
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > limit:
                raise HTTPException(413, "Creation input is too large")
        try:
            value = json.loads(data)
            if not isinstance(value, dict):
                raise ValueError()
            return value
        except (ValueError, UnicodeDecodeError) as error:
            raise HTTPException(422, "Creation input must be a JSON object") from error

    def invoke(fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except KeyError as error:
            raise HTTPException(404, "Creation is unavailable") from error
        except TemplateConflict as error:
            raise HTTPException(409, str(error)) from error
        except (ValueError, TypeError) as error:
            raise HTTPException(422, str(error)) from error

    @router.get("/runs")
    def runs():
        fields = ("run_id", "mode", "scope", "status", "instruction", "language", "error")
        return {"items": [{k: r[k] for k in fields} for r in service.store.list("run", 100)]}

    @router.get("/designs")
    def designs():
        return service.designs()

    @router.post("/imports")
    async def import_template(request: Request):
        return service.describe(invoke(service.import_template, await body(request)))

    @router.post("/references")
    async def upload(request: Request):
        return invoke(service.references.upload, await body(request))

    @router.post("/runs", status_code=202)
    async def create(request: Request):
        return service.describe(invoke(service.start, await body(request)))

    @router.get("/runs/{identifier}")
    def get(identifier: str):
        return service.describe(invoke(service.get, identifier))

    @router.post("/runs/{identifier}/{action}", status_code=202)
    async def mutate(identifier: str, action: str, request: Request):
        return service.describe(invoke(service.mutate, identifier, await body(request), action=action))

    @router.get("/media/{digest}")
    def media(digest: str):
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise HTTPException(422, "Invalid media digest")
        data = invoke(service.read_media, digest)
        return Response(data, media_type="image/png", headers={"Cache-Control": "private, no-store", "X-PTW-Content-SHA256": digest, "X-Content-Type-Options": "nosniff"})

    @router.get("/runs/{identifier}/export")
    def export(identifier: str):
        data = invoke(export_bundle, service, invoke(service.get, identifier))
        return Response(data, media_type="application/zip", headers={"Cache-Control": "private, no-store", "Content-Disposition": 'attachment; filename="natal-studio.zip"', "X-PTW-Content-SHA256": hashlib.sha256(data).hexdigest(), "X-Content-Type-Options": "nosniff"})
    return router
