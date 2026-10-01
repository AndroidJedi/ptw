"""Real Daddy pipeline canary using the deployed bridge and a disposable authority."""
from pathlib import Path
import hashlib
import tempfile
from uuid import uuid4

from .local_brief_store import LocalBriefStore, sha256_json, utc_now
from .studio_creatives import LocalStudioAuthority, StudioCreativeService
from .studio_workspace import PostStudioWorkspace
from .studio_daddy import required_slots
from .png_integrity import validate_png


def verify(settings, provider, media, brief_document, accept):
    class CheckedProvider:
        def call(self, *, response_validator, **request):
            value = provider.call(response_validator=response_validator, **request)
            accept(value, "daddy_" + request["mode"])
            return value

    with tempfile.TemporaryDirectory(prefix="ptw-daddy-bridge-") as temporary:
        root = Path(temporary)
        store = LocalBriefStore(root / "authority")
        project, brief = str(uuid4()), str(uuid4())
        now = utc_now()
        store.append("projects", project, {"project_id":project,"name":"Disposable Daddy bridge canary","created_at":now})
        store.append("briefs", brief, {"brief_id":brief,"project_id":project,"approved":True,"status":"completed",
            "document":brief_document,"document_sha256":sha256_json(brief_document),"created_at":now})
        service = StudioCreativeService(root=root/"studio", authority=LocalStudioAuthority(store),
            workspace_factory=lambda path: PostStudioWorkspace(path,image_provider=media), structured_provider=CheckedProvider(),
            composer_skill_path=settings.studio_composer_skill_path,phone_skill_path=settings.studio_phone_skill_path,
            manual_agent_skill_path=settings.studio_manual_agent_skill_path)
        creative,_ = service.reserve_from_brief(brief_id=brief,template_id="daddy",requested_by="disposable-canary",
            creative_direction={"schema":"ptw.studio.phone-hero-direction.v1","style":"ultra_realistic_lifestyle","background":"scene"})
        identifier = creative["creative_id"]
        service.authority.update_creative(identifier,generation={**creative["generation"],
            "daddy_owner_instruction":"Use the lifestyle composition with one required scene image. No hands. Preserve supported Brief claims."})
        service.generate(identifier)
        detail = service.detail(project,identifier)
        workspace = service._workspace(identifier)
        slots = required_slots(detail["configuration"])
        if detail["status"] != "draft" or "scene" not in slots or detail["versions"]:
            raise RuntimeError("Daddy bridge canary did not deliver an unapproved image-backed draft")
        assets = []
        for slot in slots:
            asset = workspace._asset_record(slot)
            validate_png(asset["bytes"])
            if asset["source"].get("transport") != "authenticated_result_bridge":
                raise RuntimeError("Daddy canary did not use the production media transport")
            assets.append({"slot":slot,"sha256":asset["sha256"],"request_id":asset["source"].get("bridge_request_id")})
        rendered = workspace.render_preview(state_sha256=detail["state_sha256"])
        digest = hashlib.sha256(rendered["bytes"]).hexdigest()
        if detail["generation"]["daddy"]["review"]["render_sha256"] != digest:
            raise RuntimeError("Daddy canary did not review its actual final PNG")
        return {"mode":"daddy_pipeline","assets":assets,"render_sha256":digest,
            "findings":detail["generation"]["daddy"].get("issues",[])}
