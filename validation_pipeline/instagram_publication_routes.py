"""Owner publication routes and narrowly scoped temporary delivery media."""
from typing import Any, Mapping, Sequence
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException
from fastapi.params import Depends as DependsParameter
from fastapi.responses import Response


def instagram_router(service: Any, *, prefix: str, dependencies: Sequence[DependsParameter] = ()) -> APIRouter:
    router = APIRouter(prefix=prefix, dependencies=list(dependencies))

    def invoke(fn: Any, *args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except KeyError as error:
            raise HTTPException(404, 'Instagram publication or approved source was not found') from error
        except ValueError as error:
            raise HTTPException(400, str(error)) from error
        except RuntimeError as error:
            raise HTTPException(409, str(error)) from error

    @router.get('/connection')
    def connection() -> dict[str, Any]:
        return service.connection()

    @router.get('/projects/{project_id}')
    def workspace(project_id: str) -> dict[str, Any]:
        return invoke(service.workspace, project_id)

    @router.get('/projects/{project_id}/publications')
    def publications(project_id: str) -> dict[str, Any]:
        return invoke(service.publications, project_id)

    @router.post('/projects/{project_id}/publications', status_code=202)
    def publish(project_id: str, request: Mapping[str, Any], background: BackgroundTasks,
                x_ptw_actor: str = Header(default='owner-web')) -> dict[str, Any]:
        publication, created = invoke(service.reserve, project_id, request, x_ptw_actor[:200])
        if created:
            background.add_task(service.execute, publication['publication_id'])
        return {'publication': publication, 'created': created}

    @router.get('/projects/{project_id}/publications/{publication_id}')
    def detail(project_id: str, publication_id: str) -> dict[str, Any]:
        return invoke(service.detail, project_id, publication_id)

    @router.post('/projects/{project_id}/publications/{publication_id}/retry', status_code=202)
    def retry(project_id: str, publication_id: str, request: Mapping[str, Any], background: BackgroundTasks) -> dict[str, Any]:
        if request:
            raise HTTPException(400, 'Retry accepts no fields')
        publication = invoke(service.retry, project_id, publication_id)
        background.add_task(service.execute, publication_id)
        return {'publication': publication}

    @router.post('/projects/{project_id}/publications/{publication_id}/sync')
    def sync(project_id: str, publication_id: str, request: Mapping[str, Any]) -> dict[str, Any]:
        if request:
            raise HTTPException(400, 'Sync accepts no fields')
        invoke(service.detail, project_id, publication_id)
        return {'publication': invoke(service.execute, publication_id, reconcile_only=True)}

    return router


def instagram_media_router(service: Any, *, prefix: str, dependencies: Sequence[DependsParameter] = ()) -> APIRouter:
    router = APIRouter(prefix=prefix, dependencies=list(dependencies))

    @router.api_route('/{token}.jpg', methods=['GET', 'HEAD'])
    def media(token: str) -> Response:
        try:
            data = service.media(token)
        except (KeyError, ValueError):
            raise HTTPException(404, 'Media unavailable') from None
        return Response(data, media_type='image/jpeg', headers={
            'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
            'X-Robots-Tag': 'noindex, noarchive',
        })

    return router
