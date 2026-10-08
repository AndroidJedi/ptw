"""Share the host deployment lock with runtime writers."""

from contextlib import contextmanager
import fcntl
import os

from starlette.responses import JSONResponse


def verify_maintenance_signal() -> None:
    path = os.environ.get("PTW_MAINTENANCE_LOCK_PATH", "")
    if path:
        with open(path, "rb"):
            pass


@contextmanager
def write_slot():
    """Hold a shared lock for the complete write; a deploy holds it exclusively."""
    path = os.environ.get("PTW_MAINTENANCE_LOCK_PATH", "")
    if not path:
        yield True
        return
    try:
        handle = open(path, "rb")
    except OSError:
        yield False
        return
    with handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except OSError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def analytics_cycle(analytics):
    with write_slot() as allowed:
        if allowed:
            return analytics.maintain()
    return None


class MaintenanceWriteGuard:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if (scope["type"] != "http" or scope["method"] in {"GET", "HEAD", "OPTIONS"}
                or scope["path"] == "/internal/emergency-stop"):
            return await self.app(scope, receive, send)
        with write_slot() as allowed:
            if not allowed:
                response = JSONResponse(
                    {"detail": "PTW maintenance is in progress. Retry shortly."},
                    status_code=503, headers={"Retry-After": "30"},
                )
                return await response(scope, receive, send)
            return await self.app(scope, receive, send)
