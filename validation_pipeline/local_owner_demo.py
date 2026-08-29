"""Deterministic read-only Product Brief and Result data for the loopback app."""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from io import BytesIO
from typing import Any, Mapping, Sequence

from fastapi import APIRouter, HTTPException, Query
from fastapi.params import Depends as DependsParameter
from fastapi.responses import Response
from PIL import Image, ImageDraw


PROJECT_ID = "018f07ea-7f20-7000-8000-000000000001"
SOURCE_ID = "018f07ea-7f20-7000-8000-000000000002"
BRIEF_ID = "018f07ea-7f20-7000-8000-000000000003"
RUN_ID = "018f07ea-7f20-7000-8000-000000000005"
CREATIVE_ID = "018f07ea-7f20-7000-8000-000000000006"
CANDIDATE_IDS = tuple(
    f"018f07ea-7f20-7000-8000-{index:012d}" for index in range(10, 15)
)


def _jpeg_bytes(index: int, title: str) -> bytes:
    palettes = (
        ("#F0E653", "#111111"),
        ("#111111", "#F0E653"),
        ("#E66B42", "#111111"),
        ("#BDD9D2", "#111111"),
        ("#EFE9DD", "#191919"),
        ("#F0E653", "#111111"),
    )
    background, foreground = palettes[index % len(palettes)]
    image = Image.new("RGB", (1080, 1080), background)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((70, 70, 1010, 1010), radius=44, outline=foreground, width=8)
    draw.rectangle((70, 760, 1010, 1010), fill=foreground)
    draw.ellipse((720 - index * 8, 120 + index * 8, 980, 380 + index * 8), outline=foreground, width=18)
    draw.text((110, 140), "NATAL / LOCAL DEMO", fill=foreground, stroke_width=1)
    draw.multiline_text((110, 440), title, fill=foreground, spacing=18, stroke_width=1)
    draw.text((110, 850), "BOOK THE FIRST CONVERSATION", fill=background, stroke_width=1)
    output = BytesIO()
    image.save(output, format="JPEG", quality=90, optimize=False, progressive=False)
    return output.getvalue()


class LocalOwnerDemo:
    """One immutable representative journey; only its display name is mutable."""

    def __init__(self) -> None:
        document = {
            "schema_version": 1,
            "language": "en",
            "product": "Guided first therapy session",
            "target_audience": "People seeking a low-risk first step into therapy.",
            "main_pain": "Finding trustworthy support feels difficult and high commitment.",
            "promise": "Meet a suitable psychologist with a calmer first step.",
            "key_benefits": ["Real consultant profiles", "Simple booking", "No-card first step"],
            "cta": "Book the first conversation",
            "trust_strategy": "Transparent process and real profiles.",
            "offer": "First consultation free",
        }
        self.project = {
            "project_id": PROJECT_ID,
            "request_id": PROJECT_ID,
            "owner_idea_source_id": SOURCE_ID,
            "name": document["product"],
            "name_source": "product_brief",
            "requested_by": "loopback:local-demo",
            "result_creation_enabled": False,
            "latest_brief_id": BRIEF_ID,
            "latest_brief_status": "completed",
            "brief_count": 1,
            "result_run_count": 1,
            "created_at": "2026-08-26T08:00:00Z",
            "updated_at": "2026-08-26T08:14:00Z",
        }
        self.brief = {
            "brief_id": BRIEF_ID,
            "project_id": PROJECT_ID,
            "project_name": self.project["name"],
            "request_id": BRIEF_ID,
            "owner_idea_source_id": SOURCE_ID,
            "raw_idea": "A calmer way to start therapy.",
            "base_brief_id": None,
            "feedback_id": None,
            "status": "completed",
            "document": document,
            "document_sha256": sha256(repr(sorted(document.items())).encode()).hexdigest(),
            "failure_count": 0,
            "approved": True,
            "created_at": "2026-08-26T08:00:00Z",
            **document,
        }
        self.run = {
            "run_id": RUN_ID,
            "request_id": RUN_ID,
            "parent_run_id": None,
            "project_id": PROJECT_ID,
            "brief_id": BRIEF_ID,
            "output_profile": "instagram_static_ad_v1",
            "task": "Create one ready-to-publish Instagram feed post using Natal.",
            "status": "completed",
            "current_stage": "completed",
            "progress_percent": 100,
            "maximum_minutes": 45,
            "final_result_id": CREATIVE_ID,
            "created_at": "2026-08-26T08:10:00Z",
            "updated_at": "2026-08-26T08:14:00Z",
        }
        self.result_image = _jpeg_bytes(5, "A CALMER\nFIRST STEP")
        self.result = {
            "creative_id": CREATIVE_ID,
            "run_id": RUN_ID,
            "selected_candidate_id": CANDIDATE_IDS[0],
            "recipe_id": None,
            "render_id": None,
            "decision_summary": [
                "The hook starts with a concrete moment of hesitation.",
                "The offer and next step remain immediately clear.",
            ],
            "result_sha256": "c" * 64,
            "content_sha256": "d" * 64,
            "asset_sha256": sha256(self.result_image).hexdigest(),
            "asset_url": f"/api/v1/content-runs/{RUN_ID}/result/asset",
            "created_at": "2026-08-26T08:14:00Z",
            "content": {
                "hook": "You do not need to commit to therapy to start one honest conversation.",
                "headline": "A calmer first step",
                "primary_text": "Meet a real psychologist and see whether it feels right.",
                "supporting_text": "Transparent profiles. Simple booking. No card required.",
                "offer": document["offer"],
                "cta": document["cta"],
                "caption": "One conversation can make the next step clearer.",
                "alt_text": "A local demo Natal card offering a calmer first therapy conversation.",
                "desired_emotion": "calm confidence",
                "visual_concept": "A simple high-contrast editorial card.",
            },
        }
        template_ids = (
            "moment_tension", "contrast_reframe", "mechanism_proof",
            "human_story", "direct_offer",
        )
        self.candidate_images: dict[str, bytes] = {}
        candidates = []
        for index, (candidate_id, template_id) in enumerate(zip(CANDIDATE_IDS, template_ids)):
            image = _jpeg_bytes(index, f"DIRECTION {index + 1}\nA CALMER START")
            self.candidate_images[candidate_id] = image
            candidates.append({
                "candidate_id": candidate_id,
                "alias": f"C{index + 1}",
                "round": 0,
                "generation_kind": "initial",
                "parent_candidate_id": None,
                "template_id": template_id,
                "template_version": 3,
                "parameters": {
                    "hook_pressure": 50 + index,
                    "emotional_intensity": 40 + index,
                    "conceptual_novelty": 60 + index,
                    "information_density": 30 + index,
                    "visual_complexity": 20 + index,
                },
                "document": {
                    "hook": f"Candidate hook {index + 1}",
                    "headline": f"Candidate headline {index + 1}",
                    "primary_text": "One clear message.",
                    "supporting_text": "One supporting point.",
                    "offer": document["offer"],
                    "cta": document["cta"],
                    "caption": "One representative local caption.",
                    "alt_text": f"Local demo candidate {index + 1}",
                    "desired_emotion": "calm confidence",
                    "visual_concept": "One coherent layout.",
                },
                "preview": {
                    "asset_url": f"/api/v1/content-runs/{RUN_ID}/candidates/{candidate_id}/asset",
                    "sha256": sha256(image).hexdigest(),
                    "mime_type": "image/jpeg",
                    "width": 1080,
                    "height": 1080,
                },
            })
        self.debug = {
            "candidates": candidates,
            "critic_passes": [
                self._critic_pass(1, CANDIDATE_IDS),
                self._critic_pass(2, CANDIDATE_IDS[:3]),
                self._critic_pass(3, CANDIDATE_IDS[:2]),
            ],
            "result": self.result,
        }

    def _critic_pass(self, pass_number: int, ranking: Sequence[str]) -> dict[str, Any]:
        return {
            "pass_id": f"local-demo-pass-{pass_number}",
            "pass_number": pass_number,
            "active_candidate_ids": list(ranking),
            "hard_gates": {candidate_id: {
                "exact_offer_cta": True,
                "honest_claims": True,
                "safe_crop_layout": True,
            } for candidate_id in ranking},
            "candidate_scores": {candidate_id: {
                "scores": {"message_clarity": 10 - index},
                "complexity": "none",
                "weighted_total": 92 - index,
                "eligible": True,
                "reason_codes": ["clear_message"],
            } for index, candidate_id in enumerate(ranking)},
            "ranking": list(ranking),
            "pairwise_results": [{
                "left": ranking[0],
                "right": ranking[1],
                "winner": ranking[0],
                "reason_codes": ["clearer"],
            }],
            "observations": [f"Pass {pass_number} retained the clearest direction."],
            "actions": [] if pass_number == 3 else [{
                "action_type": "regenerate_elements",
                "base_candidate_id": ranking[0],
                "status": "completed",
            }],
            "final_selection": None if pass_number != 3 else {
                "candidate_id": ranking[0],
                "decision_summary": self.result["decision_summary"],
            },
        }

    @staticmethod
    def _require(identifier: str, expected: str, kind: str) -> None:
        if identifier != expected:
            raise HTTPException(status_code=404, detail=f"local demo {kind} was not found")

    def rename_project(self, project_id: str, request: Mapping[str, Any]) -> dict[str, Any]:
        self._require(project_id, PROJECT_ID, "Project")
        if set(request) != {"name"} or not isinstance(request.get("name"), str):
            raise HTTPException(status_code=400, detail="Project rename requires one name")
        name = request["name"].strip()
        if not 1 <= len(name) <= 160:
            raise HTTPException(status_code=400, detail="Project name must contain 1 to 160 characters")
        self.project["name"] = name
        self.project["name_source"] = "owner"
        self.brief["project_name"] = name
        return deepcopy(self.project)

    @staticmethod
    def image_response(content: bytes) -> Response:
        digest = sha256(content).hexdigest()
        return Response(
            content=content,
            media_type="image/jpeg",
            headers={
                "Cache-Control": "private, no-store",
                "ETag": f'"{digest}"',
                "X-PTW-Content-SHA256": digest,
                "X-Content-Type-Options": "nosniff",
            },
        )


def local_owner_demo_router(
    demo: LocalOwnerDemo,
    *,
    dependencies: Sequence[DependsParameter] = (),
) -> APIRouter:
    router = APIRouter(prefix="/api/v1", dependencies=list(dependencies))

    @router.get("/projects")
    def projects(limit: int = Query(default=100, ge=1, le=100)) -> dict[str, Any]:
        return {"items": [deepcopy(demo.project)][:limit], "next_cursor": None}

    @router.post("/projects/{project_id}/rename")
    def rename_project(project_id: str, request: Mapping[str, Any]) -> dict[str, Any]:
        return demo.rename_project(project_id, request)

    @router.get("/briefs")
    def briefs(
        project_id: str | None = None,
        limit: int = Query(default=100, ge=1, le=100),
    ) -> dict[str, Any]:
        items = [] if project_id and project_id != PROJECT_ID else [deepcopy(demo.brief)]
        return {"items": items[:limit], "next_cursor": None}

    @router.get("/briefs/{brief_id}")
    def brief(brief_id: str) -> dict[str, Any]:
        demo._require(brief_id, BRIEF_ID, "Product Brief")
        return deepcopy(demo.brief)

    @router.post("/briefs")
    def create_brief() -> None:
        raise HTTPException(
            status_code=409,
            detail="provider-backed Product Brief generation is disabled in the local demo",
        )

    @router.post("/briefs/{brief_id}/correct")
    @router.post("/briefs/{brief_id}/retry")
    @router.post("/briefs/{brief_id}/approve")
    def mutate_brief(brief_id: str) -> None:
        demo._require(brief_id, BRIEF_ID, "Product Brief")
        raise HTTPException(
            status_code=409,
            detail="Product Brief mutation is disabled in the local demo",
        )

    @router.get("/content-runs")
    def content_runs(
        project_id: str,
        limit: int = Query(default=50, ge=1, le=100),
    ) -> dict[str, Any]:
        items = [] if project_id != PROJECT_ID else [deepcopy(demo.run)]
        return {"items": items[:limit], "next_cursor": None}

    @router.get("/content-runs/{run_id}")
    def content_run(run_id: str) -> dict[str, Any]:
        demo._require(run_id, RUN_ID, "Result run")
        return deepcopy(demo.run)

    @router.post("/content-runs")
    def create_content_run() -> None:
        raise HTTPException(
            status_code=409,
            detail="provider-backed Result generation is disabled in the local demo",
        )

    @router.get("/content-runs/{run_id}/result")
    def result(run_id: str) -> dict[str, Any]:
        demo._require(run_id, RUN_ID, "Result run")
        return deepcopy(demo.result)

    @router.get("/content-runs/{run_id}/result/asset")
    def result_asset(run_id: str) -> Response:
        demo._require(run_id, RUN_ID, "Result run")
        return demo.image_response(demo.result_image)

    @router.get("/content-runs/{run_id}/candidates/{candidate_id}/asset")
    def candidate_asset(run_id: str, candidate_id: str) -> Response:
        demo._require(run_id, RUN_ID, "Result run")
        content = demo.candidate_images.get(candidate_id)
        if content is None:
            raise HTTPException(status_code=404, detail="local demo candidate was not found")
        return demo.image_response(content)

    @router.get("/content-runs/{run_id}/debug")
    def debug(run_id: str) -> dict[str, Any]:
        demo._require(run_id, RUN_ID, "Result run")
        return deepcopy(demo.debug)

    @router.post("/content-runs/{run_id}/feedback")
    @router.post("/content-runs/{run_id}/outcomes")
    @router.post("/content-runs/{run_id}/retry")
    def unavailable_result_mutation(run_id: str) -> None:
        demo._require(run_id, RUN_ID, "Result run")
        raise HTTPException(
            status_code=409,
            detail="Result mutation and feedback persistence are disabled in the local demo",
        )

    return router
