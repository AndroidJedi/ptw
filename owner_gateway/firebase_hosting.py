"""Small, site-pinned Firebase Hosting REST publisher for generated Natal pages."""

from __future__ import annotations

import gzip
import hashlib
from pathlib import Path
import re
from typing import Any, Mapping


API_ROOT = "https://firebasehosting.googleapis.com/v1beta1"
PUBLIC_SUFFIXES = {".html", ".css", ".js", ".svg", ".png"}
PRIVATE_FILENAMES = {"brief.json", "build.json"}


class FirebaseHostingError(RuntimeError):
    pass


def public_files(root: Path) -> dict[str, bytes]:
    root = root.resolve()
    if not root.is_dir():
        raise ValueError("Firebase publish directory does not exist")
    files: dict[str, bytes] = {}
    total_bytes = 0
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("Firebase publish directory must not contain symlinks")
        if not path.is_file() or path.name in PRIVATE_FILENAMES:
            continue
        relative = path.relative_to(root)
        if any(part.startswith(".") for part in relative.parts):
            continue
        if path.suffix.lower() not in PUBLIC_SUFFIXES:
            raise ValueError(f"unsupported public landing file: {relative.as_posix()}")
        content = path.read_bytes()
        if len(content) > 10 * 1024 * 1024:
            raise ValueError(f"public landing file is too large: {relative.as_posix()}")
        total_bytes += len(content)
        if total_bytes > 50 * 1024 * 1024:
            raise ValueError("Firebase landing release exceeds 50 MiB")
        files[f"/{relative.as_posix()}"] = content
    if "/index.html" not in files:
        raise ValueError("Firebase landing release has no index.html")
    return files


class FirebaseHostingPublisher:
    def __init__(
        self,
        *,
        project_id: str,
        site_id: str,
        credential_path: Path | None = None,
        session: Any | None = None,
    ) -> None:
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,62}", site_id):
            raise ValueError("invalid Firebase landing site ID")
        self.project_id = project_id
        self.site_id = site_id
        self.credential_path = credential_path
        self._session = session

    def _authorized_session(self) -> Any:
        if self._session is not None:
            return self._session
        if self.credential_path is None or not self.credential_path.is_file():
            raise FirebaseHostingError("Firebase landing publisher credential is unavailable")
        from google.auth.transport.requests import AuthorizedSession
        from google.oauth2 import service_account

        credentials = service_account.Credentials.from_service_account_file(
            str(self.credential_path),
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        self._session = AuthorizedSession(credentials)
        return self._session

    @staticmethod
    def _body(response: Any) -> Mapping[str, Any]:
        try:
            value = response.json()
        except ValueError as error:
            raise FirebaseHostingError("Firebase Hosting returned a non-JSON response") from error
        return value if isinstance(value, Mapping) else {}

    def _request(self, method: str, url: str, **kwargs: Any) -> Mapping[str, Any]:
        response = self._authorized_session().request(method, url, timeout=60, **kwargs)
        if response.status_code >= 400:
            body = self._body(response)
            detail = body.get("error") if isinstance(body.get("error"), Mapping) else {}
            status = str(detail.get("status") or f"HTTP_{response.status_code}")
            message = str(detail.get("message") or "Firebase Hosting request failed")[:400]
            raise FirebaseHostingError(f"{status}: {message}")
        return self._body(response)

    def _current_release(self) -> Mapping[str, Any] | None:
        body = self._request(
            "GET", f"{API_ROOT}/sites/{self.site_id}/releases", params={"pageSize": 1}
        )
        releases = body.get("releases") or []
        return releases[0] if releases else None

    def publish(self, directory: Path, *, build_id: str) -> dict[str, str]:
        current = self._current_release()
        current_version = current.get("version") if isinstance(current, Mapping) else None
        labels = current_version.get("labels") if isinstance(current_version, Mapping) else None
        if isinstance(labels, Mapping) and labels.get("natal-build-id") == build_id:
            version_name = str(current_version.get("name") or "")
            return {
                "version": version_name.rsplit("/", 1)[-1],
                "public_url": f"https://{self.site_id}.web.app/builds/{build_id}/",
            }

        raw_files = public_files(directory)
        compressed: dict[str, bytes] = {}
        file_hashes: dict[str, str] = {}
        for path, content in raw_files.items():
            payload = gzip.compress(content, compresslevel=9, mtime=0)
            digest = hashlib.sha256(payload).hexdigest()
            compressed[digest] = payload
            file_hashes[path] = digest

        version = self._request(
            "POST",
            f"{API_ROOT}/sites/{self.site_id}/versions",
            json={
                "labels": {"natal-build-id": build_id, "deployment-tool": "ptw-natal"},
                "config": {
                    "headers": [
                        {
                            "glob": "**",
                            "headers": {
                                "X-Content-Type-Options": "nosniff",
                                "Referrer-Policy": "no-referrer",
                                "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
                                "Content-Security-Policy": (
                                    "default-src 'self'; img-src 'self' data:; style-src 'self'; "
                                    "script-src 'self'; object-src 'none'; base-uri 'none'; "
                                    "frame-ancestors 'none'; form-action 'self'"
                                ),
                            },
                        },
                        {"glob": "**/*.html", "headers": {"Cache-Control": "no-cache"}},
                    ]
                },
            },
        )
        version_name = str(version.get("name") or "")
        if not re.fullmatch(rf"sites/{re.escape(self.site_id)}/versions/[A-Za-z0-9_-]+", version_name):
            raise FirebaseHostingError("Firebase Hosting returned an invalid version name")

        required: set[str] = set()
        upload_url = ""
        items = list(file_hashes.items())
        for offset in range(0, len(items), 1000):
            populated = self._request(
                "POST",
                f"{API_ROOT}/{version_name}:populateFiles",
                json={"files": dict(items[offset:offset + 1000])},
            )
            required.update(str(item) for item in populated.get("uploadRequiredHashes") or [])
            upload_url = str(populated.get("uploadUrl") or upload_url)
        if required and not upload_url.startswith("https://upload-firebasehosting.googleapis.com/"):
            raise FirebaseHostingError("Firebase Hosting returned an invalid upload URL")
        for digest in sorted(required):
            payload = compressed.get(digest)
            if payload is None:
                raise FirebaseHostingError("Firebase Hosting requested an unknown file hash")
            response = self._authorized_session().post(
                f"{upload_url}/{digest}",
                data=payload,
                headers={"Content-Type": "application/octet-stream"},
                timeout=60,
            )
            if response.status_code >= 400:
                raise FirebaseHostingError(f"Firebase Hosting upload failed with HTTP {response.status_code}")

        self._request(
            "PATCH",
            f"{API_ROOT}/{version_name}",
            params={"update_mask": "status"},
            json={"status": "FINALIZED"},
        )
        self._request(
            "POST",
            f"{API_ROOT}/sites/{self.site_id}/releases",
            params={"versionName": version_name},
        )
        return {
            "version": version_name.rsplit("/", 1)[-1],
            "public_url": f"https://{self.site_id}.web.app/builds/{build_id}/",
        }
