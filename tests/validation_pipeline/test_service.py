from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from validation_pipeline.domain import CREATIVE_ANGLES
from validation_pipeline.images import PexelsPhoto
from validation_pipeline.service import ValidationRunner


BRIEF = {
    "schema_version": 1,
    "language": "en",
    "product": "Online psychologist consultations.",
    "target_audience": "First-time therapy seekers.",
    "main_pain": "Starting support feels risky.",
    "promise": "Take a trustworthy first step.",
    "key_benefits": ["Real profiles", "Easy booking", "Low-risk start"],
    "cta": "Get free consultation",
    "trust_strategy": "Real consultants, clear pricing, no card.",
    "offer": "First consultation free",
}


def creative_result():
    return {
        "schema_version": 1,
        "creatives": [{
            "angle": angle,
            "hook": f"{angle} support",
            "primary_text": "First consultation free. Meet a real psychologist.",
            "image_description": "Real professional conversation.",
            "cta": BRIEF["cta"],
            "desired_emotion": "confidence",
            "image_category": "professional conversation",
            "image_search_query": f"real {angle} professional conversation",
            "crop_focus": "center",
        } for angle in CREATIVE_ANGLES],
    }


class FakeRepository:
    def __init__(self) -> None:
        self.batch = {"batch_id": "018f07ea-7f20-7000-8000-000000000001", "brief_id": "018f07ea-7f20-7000-8000-000000000002", "status": "queued"}
        self.brief = {"brief_id": self.batch["brief_id"], "status": "completed", "approved": True, "document": BRIEF}
        self.finished_batch = None
        self.finished_brief = None
        self.released: list[str] = []

    def get_batch(self, _batch_id): return self.batch if self.finished_batch is None else {**self.batch, "status": "completed"}
    def get_brief(self, _brief_id):
        if self.finished_brief is not None:
            return {"brief_id": _brief_id, "status": "completed", "document": self.finished_brief, "approved": False}
        return self.brief
    def start_attempt(self, _target_id, *, stage): return ("018f07ea-7f20-7000-8000-000000000003", 1)
    def create_invocation(self, **_kwargs): return {"id": "018f07ea-7f20-7000-8000-000000000004"}
    def complete_invocation(self, *_args): return None
    def fail_invocation(self, *_args): return None
    def source(self, _brief_id): return {"id": "source", "content": "Psychologist consultations online"}
    def feedback(self, _feedback_id): raise AssertionError("initial brief has no correction")
    def finish_brief(self, _brief_id, _attempt_id, document, _digest, _quality): self.finished_brief = document
    def finish_batch(self, _batch_id, _attempt_id, **values): self.finished_batch = values
    def fail_attempt(self, *_args, **_kwargs): raise AssertionError("generation should not fail")
    def release_operation(self, target_id): self.released.append(target_id)


class FakeBridge:
    def __init__(self) -> None:
        self.calls = []
        self.last_invocation = {"bridge_request_id": 7}

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs["mode"] == "product_brief":
            return BRIEF
        return creative_result()


class FakePexels:
    def __init__(self) -> None: self.count = 0
    def select(self, _query, _category, *, used_ids):
        self.count += 1
        photo_id = str(self.count)
        if photo_id in used_ids: raise AssertionError("source photo reused")
        return PexelsPhoto(
            photo_id, 1200, 1200, f"https://images.pexels.com/{photo_id}.jpg",
            f"https://www.pexels.com/photo/{photo_id}/", "Photographer",
            "https://www.pexels.com/@photographer", "Real person",
        ), b"source"


class FakeRenderer:
    def render(self, _source, **_kwargs): return (b"jpeg", "d" * 64)


class ValidationRunnerTests(unittest.TestCase):
    def runner(self, root: Path, repository: FakeRepository, bridge: FakeBridge) -> ValidationRunner:
        first = root / "brief.md"; second = root / "creative.md"
        first.write_text("brief skill"); second.write_text("creative skill")
        return ValidationRunner(
            repository, bridge, FakePexels(), FakeRenderer(),
            product_brief_skill_path=first, ad_creative_skill_path=second,
        )

    def test_stage_one_uses_one_raw_idea_without_research_context(self) -> None:
        repository, bridge = FakeRepository(), FakeBridge()
        repository.brief = {
            "brief_id": repository.batch["brief_id"], "status": "queued",
            "base_brief_id": None, "feedback_id": None,
        }
        with TemporaryDirectory() as directory:
            self.runner(Path(directory), repository, bridge).generate_brief(
                repository.batch["brief_id"], operation_reserved=True
            )
        self.assertEqual(1, len(bridge.calls))
        call = bridge.calls[0]
        self.assertEqual("product_brief", call["mode"])
        self.assertEqual(
            {"brief_id", "raw_idea", "base_brief", "owner_correction"},
            set(call["input_payload"]),
        )
        self.assertIsNone(call["input_payload"]["base_brief"])
        self.assertNotIn("market", str(call["input_payload"]).lower())

    def test_stage_two_business_input_is_only_approved_brief_and_batch_is_atomic(self) -> None:
        repository, bridge = FakeRepository(), FakeBridge()
        with TemporaryDirectory() as directory:
            self.runner(Path(directory), repository, bridge).generate_batch(
                repository.batch["batch_id"], operation_reserved=True
            )
        self.assertEqual(1, len(bridge.calls))
        call = bridge.calls[0]
        self.assertEqual("ad_creative_batch", call["mode"])
        self.assertEqual({"brief"}, set(call["input_payload"]))
        supplied = call["input_payload"]["brief"]
        self.assertEqual({"brief_id", *BRIEF.keys()}, set(supplied))
        serialized = str(call["input_payload"]).lower()
        for forbidden in ("raw_idea", "research", "market_context", "performance", "previous_creatives"):
            self.assertNotIn(forbidden, serialized)
        self.assertEqual(5, len(repository.finished_batch["creatives"]))
        self.assertEqual(5, len({item["creative_id"] for item in repository.finished_batch["creatives"]}))
        self.assertEqual(5, len({item["photo"]["external_id"] for item in repository.finished_batch["creatives"]}))


if __name__ == "__main__":
    unittest.main()
