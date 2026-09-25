"""Explicitly reapply one approved Landing as a replacement draft, without inference.

This is an owner-directed operation, never a migration or a publication read path.
"""
from copy import deepcopy
from hashlib import sha256

from .landing_delivery import prepare
from .landing_pages import _snapshot
from .landing_workspace import sha256_json


def reapply_approved(service, *, project_id, landing_id, version, request_id, requested_by):
    with service.operations.lock:
        service.operations.assert_idle(landing_id)
        source = service.approved_version_detail(project_id, landing_id, version)
        page = service.authority.get_page(landing_id)
        reference = source["template_reference"]
        provenance = {"landing_id": landing_id, "version": version, "version_sha256": source["version_sha256"]}
        target, created = service.reserve_from_post(project_id=project_id,
            source_creative_id=page["source_creative_id"], source_version=page["source_version"],
            requested_by=requested_by, additional=True, template_reference=reference, request_id=request_id)
        target_id = target["landing_id"]
        if not created:
            if target.get("generation", {}).get("reapplied_from") != provenance:
                raise RuntimeError("Reapplication request belongs to a different approved source")
            if target["status"] == "draft":
                return service.detail(project_id, target_id)
        # A restart must never reinterpret or generate the approved source.
        service.authority.update_page(target_id, status="failed", generation={"stage": "reapplying", "reapplied_from": provenance})
        original, workspace = service._workspace(landing_id), service._workspace(target_id)
        detail = workspace.save_configuration(base_sha256=workspace.state_sha256(),
            configuration=deepcopy(source["configuration"]), content=deepcopy(source["content"]))
        for asset in source["assets"]:
            if not asset.get("sha256"):
                continue
            slot, digest = asset["slot"], asset["sha256"]
            entry = next(item for item in asset["history"] if item["sha256"] == digest)
            data = (original.assets / f"{digest}.png").read_bytes()
            if sha256(data).hexdigest() != digest:
                raise RuntimeError("Approved source image digest mismatch")
            image = {"bytes": data, "mime_type": "image/png"}
            generated = {**image, "delivery": prepare(image["bytes"], slot), "source": deepcopy(entry.get("source", {}))}
            raw_digest = generated["source"].get("preparation", {}).get("raw_sha256")
            if raw_digest:
                raw = (original.assets / "raw" / f"{raw_digest}.png").read_bytes()
                if sha256(raw).hexdigest() != raw_digest:
                    raise RuntimeError("Approved source raw image digest mismatch")
                generated["raw_bytes"] = raw
            detail = workspace.commit_prepared_visual(base_sha256=detail["state_sha256"], slot=slot,
                visual_direction=entry.get("visual_direction", "Approved source artwork"), generated=generated, image_context=None)
        service._synchronize_workspace(target_id, workspace)
        baseline = _snapshot(detail)
        service.authority.update_page(target_id, status="draft", state_sha256=detail["state_sha256"],
            generation={"stage": "draft", "reapplied_from": provenance},
            learning_baseline=baseline, learning_baseline_sha256=sha256_json(baseline))
        return service.detail(project_id, target_id)
