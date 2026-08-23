"""Exact-snapshot Natal build and dedicated-site Firebase publication."""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
import shutil
import tempfile
from typing import Any, Callable, Mapping

from natal.builder import build_landing

from .firebase_hosting import FirebaseHostingPublisher, public_files
from .landing_repository import LandingBuildRepository


class LandingBuildCoordinator:
    def __init__(
        self,
        *,
        repository: LandingBuildRepository,
        publisher: FirebaseHostingPublisher,
        output_root: Path,
        stopped: Callable[[], bool],
        lead_api_base_url: str,
    ) -> None:
        self.repository = repository
        self.publisher = publisher
        self.output_root = output_root.resolve()
        self.stopped = stopped
        self.lead_api_base_url = lead_api_base_url.rstrip("/")

    def recover_interrupted(self) -> int:
        return self.repository.recover_interrupted()

    def verify_ready(self) -> None:
        if not self.lead_api_base_url.startswith("https://"):
            raise RuntimeError("published Landing lead API must be HTTPS")

    def active(self) -> dict[str, Any] | None:
        return self.repository.active()

    def get(self, build_id: str) -> dict[str, Any]:
        return self.repository.get(build_id)

    def by_request(self, request_id: str) -> dict[str, Any] | None:
        return self.repository.by_request(request_id)

    def list(self, limit: int = 30, *, positioning_revision_id: str | None = None) -> list[dict[str, Any]]:
        return self.repository.list(limit, positioning_revision_id=positioning_revision_id)

    def skill_memory(self, positioning_revision_id: str) -> list[dict[str, Any]]:
        return self.repository.skill_memory(positioning_revision_id)

    def record_feedback(self, build_id: str, *, comment: str, requested_by: str) -> dict[str, Any]:
        return self.repository.record_feedback(build_id, comment=comment, requested_by=requested_by)

    def create(self, prepared: Mapping[str, Any], *, request_id: str, requested_by: str) -> tuple[dict[str, Any], bool]:
        output = self.output_root / "builds" / str(prepared["build_id"])
        return self.repository.create(
            prepared, request_id=request_id, requested_by=requested_by,
            output_path=str(output), firebase_site_id=self.publisher.site_id,
        )

    def retry(self, build_id: str) -> dict[str, Any]:
        return self.repository.retry(build_id)

    async def run(self, build_id: str) -> None:
        await asyncio.to_thread(self.run_sync, build_id)

    def run_sync(self, build_id: str) -> None:
        staging: Path | None = None
        try:
            build = self.repository.mark_building(build_id)
            output = Path(str(build["output_path"])).resolve()
            expected_output = self.output_root / "builds" / build_id
            if output != expected_output:
                raise ValueError("Landing output does not match the server-owned build path")
            if output.exists():
                shutil.rmtree(output)
            manifest = build_landing(
                str(build["template_id"]), dict(build["brief"]), output,
                page_content=dict(build["page_content"]), build_id=build_id,
                lead_api_url=self.lead_api_base_url,
            )
            artifact_sha256 = self._artifact_digest(output)
            self.repository.mark_publishing(build_id, manifest=manifest, artifact_sha256=artifact_sha256)
            if self.stopped():
                raise RuntimeError("PTW emergency stop became active before Firebase publication")
            staging_root = self.output_root / "staging"
            staging_root.mkdir(parents=True, exist_ok=True)
            staging = Path(tempfile.mkdtemp(prefix=f"{build_id}-", dir=staging_root))
            self._assemble_release(staging, build_id, output)
            result = self.publisher.publish(staging, build_id=build_id)
            self.repository.mark_published(build_id, version=result["version"], public_url=result["public_url"])
        except Exception as error:
            try:
                self.repository.mark_failed(build_id, code=type(error).__name__, message=str(error) or type(error).__name__)
            except (KeyError, ValueError):
                pass
        finally:
            if staging is not None:
                shutil.rmtree(staging, ignore_errors=True)

    @staticmethod
    def _artifact_digest(output: Path) -> str:
        digest = hashlib.sha256()
        for path, content in sorted(public_files(output).items()):
            digest.update(path.encode()); digest.update(b"\0"); digest.update(content)
        return digest.hexdigest()

    def _assemble_release(self, target: Path, build_id: str, current_output: Path) -> None:
        for prior in reversed(self.repository.published()):
            prior_output = Path(str(prior["output_path"])).resolve()
            expected = self.output_root / "builds" / str(prior["id"])
            if prior_output != expected or not prior_output.is_dir():
                continue
            self._write_public(prior_output, target / "builds" / str(prior["id"]))
        self._write_public(current_output, target)
        self._write_public(current_output, target / "builds" / build_id)

    @staticmethod
    def _write_public(source: Path, target: Path) -> None:
        for relative, content in public_files(source).items():
            destination = target / relative.removeprefix("/")
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
