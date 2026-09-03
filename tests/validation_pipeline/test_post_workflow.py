from __future__ import annotations

from copy import deepcopy
from io import BytesIO
import importlib.util
from pathlib import Path
import tempfile
import unittest

from validation_pipeline.images import PexelsPhoto
from validation_pipeline.post_workflow import LEGACY_POST_SCHEMA, POST_SCHEMA, SimplePostService


HAS_PILLOW = importlib.util.find_spec("PIL") is not None


def _photo_bytes(color: str) -> bytes:
    from PIL import Image

    image = Image.new("RGB", (1080, 1080), color)
    output = BytesIO()
    image.save(output, format="JPEG", quality=92)
    return output.getvalue()


def _sticker_photo_bytes() -> bytes:
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (1080, 1080), "#F4EEE5")
    draw = ImageDraw.Draw(image)
    draw.ellipse((300, 210, 780, 690), fill="#D83B35", outline="#8D1715", width=18)
    draw.polygon(((510, 650), (570, 650), (540, 930)), fill="#A42320")
    output = BytesIO()
    image.save(output, format="JPEG", quality=94)
    return output.getvalue()


class FakePexels:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.rejected_sticker_queries: set[str] = set()

    def select(
        self, query: str, category: str, *, used_ids: set[str],
        required_alt_terms: tuple[str, ...] = (),
    ):
        self.calls.append(query)
        photo_id = str(7000 + len(self.calls))
        sticker = "physical object" in category
        subject = required_alt_terms[0] if required_alt_terms else "physical object"
        return PexelsPhoto(
            photo_id=photo_id, width=1080, height=1080,
            image_url=f"https://images.pexels.com/photos/{photo_id}/image.jpeg",
            page_url=f"https://www.pexels.com/photo/{photo_id}/",
            photographer="Post Test", photographer_url="https://www.pexels.com/@post-test/",
            alt=(
                f"Close-up photograph of a real {subject} on a plain background"
                if sticker else "Close portrait of a thoughtful person with a visible human face"
            ),
        ), (
            _photo_bytes("#F4EEE5")
            if sticker and query in self.rejected_sticker_queries
            else _sticker_photo_bytes()
            if sticker else _photo_bytes("#6F8294" if len(self.calls) == 1 else "#967E70")
        )


class FakeProvider:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.tune_response: dict | None = None

    def call(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs["mode"] == "simple_post_generate":
            response = {
                "content": {
                    "schema": "ptw.studio.universal-ad-content.v2",
                    "hero_title": "A CALMER FIRST STEP",
                    "supporting_text": "Meet a suitable psychologist without a high-commitment start.",
                    "offer": "First consultation free",
                    "bullets": ["Real profiles", "Simple booking"],
                    "cta": "BOOK A CONVERSATION",
                },
                "commands": [
                    {"setting_id": "configuration.typography.hero_size", "value": 104},
                    {"setting_id": "configuration.background.overlay_opacity", "value": 0.45},
                ],
                "image_query": "calm person considering therapy portrait",
            }
        elif kwargs["mode"] == "simple_post_phone_screen_prompt":
            response = {
                "image_prompt": "Abstract editorial composition of soft graphite spheres and lime light on a clean warm-white field, generous quiet negative space.",
            }
        else:
            response = deepcopy(self.tune_response) if self.tune_response is not None else {
                "commands": [
                    {"setting_id": "configuration.typography.hero_size", "value": 88},
                    {"setting_id": "content.hero_title", "value": "START WITH ONE CONVERSATION"},
                ],
                "image_request": {
                    "slot": "background_image",
                    "query": "thoughtful person close up portrait visible face",
                },
            }
        validator = kwargs.get("response_validator")
        if validator is not None:
            response = dict(validator(response))
        return {
            "response": response,
            "invocation": {"provider": "fake", "mode": kwargs["mode"]},
        }


class FakePhoneScreenImageProvider:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> dict:
        from PIL import Image, ImageDraw

        self.prompts.append(prompt)
        image = Image.new("RGBA", (832, 1792), "#F7F8F5")
        draw = ImageDraw.Draw(image)
        draw.ellipse((90, 250, 560, 720), fill="#1D2638")
        draw.ellipse((350, 880, 810, 1340), fill="#D6E644")
        output = BytesIO(); image.save(output, format="PNG")
        data = output.getvalue()
        return {
            "bytes": data, "mime_type": "image/png", "width": 832, "height": 1792,
            "source": {
                "origin": "openai_image_api", "provider": "openai", "model": "fake-image",
                "size": "832x1792", "quality": "medium", "text_in_screen": "prohibited_by_prompt",
            },
        }


@unittest.skipUnless(HAS_PILLOW, "Pillow is required")
class SimplePostServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.provider = FakeProvider()
        self.pexels = FakePexels()
        self.phone_images = FakePhoneScreenImageProvider()
        self.brief = {
            "brief_id": "01900000-0000-7000-8000-000000000001",
            "project_id": "01900000-0000-7000-8000-000000000002",
            "status": "completed", "approved": True,
            "document_sha256": "b" * 64,
            "document": {
                "schema_version": 1, "language": "en",
                "product": "Guided first therapy session",
                "target_audience": "People seeking a low-risk first step into therapy.",
                "main_pain": "Finding trustworthy support feels difficult and high commitment.",
                "promise": "Meet a suitable psychologist with a calmer first step.",
                "key_benefits": ["Real consultant profiles", "Simple booking"],
                "cta": "Book the first conversation",
                "trust_strategy": "Transparent process and real profiles.",
                "offer": "First consultation free",
            },
        }
        self.service = SimplePostService(
            Path(self.temporary.name), provider=self.provider,
            brief_resolver=lambda _brief_id: self.brief, pexels=self.pexels,
            image_provider=self.phone_images,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _draft(self) -> dict:
        post, created = self.service.create_post(
            request_id="01900000-0000-7000-8000-000000000003",
            brief_id=self.brief["brief_id"], requested_by="owner",
        )
        self.assertTrue(created)
        self.assertEqual("queued", post["status"])
        return self.service.generate_post(post["post_id"])

    def test_one_approved_brief_generates_one_studio_rendered_draft(self) -> None:
        post = self._draft()

        self.assertEqual("draft", post["status"])
        self.assertEqual("A CALMER FIRST STEP", post["studio"]["content"]["hero_title"])
        self.assertEqual(104, post["studio"]["configuration"]["typography"]["hero_size"])
        self.assertEqual("image", post["studio"]["configuration"]["background"]["mode"])
        self.assertTrue(post["studio"]["configuration"]["logo"]["enabled"])
        self.assertFalse(post["studio"]["configuration"]["sticker"]["enabled"])
        self.assertEqual(["calm person considering therapy portrait"], self.pexels.calls)
        self.assertEqual((1080, 1080), (post["preview"]["width"], post["preview"]["height"]))
        background = next(
            asset for asset in post["studio"]["assets"] if asset["slot"] == "background_image"
        )
        self.assertEqual("pexels", background["source"]["provider"])
        self.assertEqual(
            "calm person considering therapy portrait", background["source"]["query"],
        )

        duplicate, created = self.service.create_post(
            request_id="01900000-0000-7000-8000-000000000099",
            brief_id=self.brief["brief_id"], requested_by="owner",
        )
        self.assertFalse(created)
        self.assertEqual(post["post_id"], duplicate["post_id"])

    def test_legacy_universal_draft_with_a_stale_state_digest_is_reconciled_once(self) -> None:
        post = self._draft()
        legacy = dict(self.service.store.get("posts", post["post_id"]))
        legacy.update({
            "schema": LEGACY_POST_SCHEMA,
            "state_sha256": "0" * 64,
            "template_sha256": "1" * 64,
            "preview_sha256": "2" * 64,
        })
        legacy.pop("template_id")
        legacy.pop("template_input")
        self.service.store.append("posts", post["post_id"], legacy)

        reconciled = self.service.get_post(post["post_id"])

        self.assertEqual(POST_SCHEMA, reconciled["schema"])
        self.assertEqual("universal_ad", reconciled["template_id"])
        self.assertIsNone(reconciled["template_input"])
        self.assertEqual(reconciled["state_sha256"], reconciled["studio"]["state_sha256"])
        self.assertEqual(reconciled["template_sha256"], reconciled["studio"]["template_sha256"])
        self.assertEqual(reconciled["preview"]["sha256"], reconciled["preview_sha256"])
        history = self.service.store.history("posts", post["post_id"])
        self.assertEqual(POST_SCHEMA, history[-1]["payload"]["schema"])

    def test_phone_metrics_locks_template_copy_and_uses_text_free_server_art(self) -> None:
        content = {
            "schema": "ptw.studio.phone-metrics-content.v1",
            "offer": "NATAL", "hero_title": "START WITH CLARITY",
            "supporting_text": "A concise explanation for a confident next step.",
            "cta": "LEARN MORE",
            "stats": [
                {"value": "$5K", "label": "minimum"},
                {"value": "7,000+", "label": "members"},
                {"value": "95", "label": "ventures"},
            ],
            "phone_hero_title": "",
        }
        legacy_input = self.service._template_input(  # pylint: disable=protected-access
            "phone_metrics", {"content": content},
        )
        self.assertEqual(
            {
                "background": "concrete", "copy_background": "none",
                "phone_screen": "grain",
            },
            legacy_input["textures"],
        )
        with self.assertRaisesRegex(ValueError, "not an approved option"):
            self.service._template_input(  # pylint: disable=protected-access
                "phone_metrics", {
                    "content": content,
                    "textures": {"background": "fabric", "phone_screen": "grain"},
                },
            )
        post, created = self.service.create_post(
            request_id="01900000-0000-7000-8000-000000000091",
            brief_id=self.brief["brief_id"], requested_by="owner",
            template_id="phone_metrics", template_input={
                "content": content,
                "textures": {
                    "background": "travertine", "copy_background": "concrete",
                    "phone_screen": "frosted",
                },
            },
        )
        self.assertTrue(created)
        self.assertEqual("phone_metrics", post["template_id"])
        completed = self.service.generate_post(post["post_id"])
        self.assertEqual("draft", completed["status"])
        self.assertEqual("phone_metrics", completed["studio"]["template_id"])
        self.assertEqual(
            "travertine", completed["studio"]["configuration"]["background"]["texture"],
        )
        self.assertEqual(
            "concrete",
            completed["studio"]["configuration"]["copy_background"]["texture"],
        )
        self.assertEqual(
            "frosted", completed["studio"]["configuration"]["phone_screen"]["texture"],
        )
        self.assertEqual((1080, 1350), (
            completed["preview"]["width"], completed["preview"]["height"],
        ))
        self.assertEqual([], self.pexels.calls)
        self.assertEqual(1, len(self.phone_images.prompts))
        self.assertIn("abstract", self.phone_images.prompts[0].casefold())
        screen = next(item for item in completed["studio"]["assets"] if item["slot"] == "phone_screen")
        self.assertEqual("openai_image_api", screen["source"]["origin"])
        self.assertEqual("prohibited_by_prompt", screen["source"]["text_in_screen"])
        with self.assertRaisesRegex(ValueError, "fixed when its draft starts"):
            self.service.create_tune(
                completed["post_id"], request_id="01900000-0000-7000-8000-000000000092",
                comment="Make the headline smaller", requested_by="owner",
            )
        approved, created_asset = self.service.approve_post(
            completed["post_id"], state_sha256=completed["state_sha256"], approved_by="owner",
        )
        self.assertTrue(created_asset)
        self.assertEqual("approved", approved["status"])

    def test_semantic_comment_becomes_exact_settings_and_a_face_photo_query(self) -> None:
        post = self._draft()
        tuned, created = self.service.create_tune(
            post["post_id"], request_id="01900000-0000-7000-8000-000000000004",
            comment="Pick image with thinking human face and make the title smaller.",
            requested_by="owner",
        )
        self.assertTrue(created)
        tuned = self.service.apply_tune(tuned["active_tune_id"])

        self.assertEqual("draft", tuned["status"])
        self.assertEqual(88, tuned["studio"]["configuration"]["typography"]["hero_size"])
        self.assertEqual(
            "START WITH ONE CONVERSATION", tuned["studio"]["content"]["hero_title"],
        )
        self.assertEqual(
            "thoughtful person close up portrait visible face", self.pexels.calls[-1],
        )
        self.assertEqual(
            {"setting_id": "configuration.typography.hero_size", "value": 88},
            tuned["last_commands"][0],
        )
        tune_call = self.provider.calls[-1]
        self.assertEqual("simple_post_tune", tune_call["mode"])
        self.assertEqual(
            "Pick image with thinking human face and make the title smaller.",
            tune_call["input_payload"]["owner_comment"],
        )

    def test_add_sticker_comment_sources_real_object_and_enables_studio_component(self) -> None:
        self.provider.tune_response = {
            "commands": [],
            "image_request": {
                "slot": "sticker_object",
                "query": "red push pin physical object close up plain background",
                "required_subject_terms": ["push pin"],
                "fallbacks": [],
            },
        }
        post = self._draft()
        original_title = post["studio"]["content"]["hero_title"]
        tuned, created = self.service.create_tune(
            post["post_id"], request_id="01900000-0000-7000-8000-000000000007",
            comment="add sticker", requested_by="owner",
        )
        self.assertTrue(created)
        tuned = self.service.apply_tune(tuned["active_tune_id"])

        self.assertEqual("draft", tuned["status"])
        self.assertIsNone(tuned["last_error"])
        self.assertEqual(original_title, tuned["studio"]["content"]["hero_title"])
        self.assertNotIn("📌", tuned["studio"]["content"]["hero_title"])
        self.assertTrue(tuned["studio"]["configuration"]["sticker"]["enabled"])
        self.assertIn(
            {"setting_id": "configuration.sticker.enabled", "value": True},
            tuned["last_commands"],
        )
        self.assertEqual("sticker_object", tuned["last_image_request"]["slot"])
        self.assertEqual(
            ["push pin"], tuned["last_image_request"]["required_subject_terms"],
        )
        sticker = next(
            asset for asset in tuned["studio"]["assets"]
            if asset["slot"] == "sticker_object"
        )
        self.assertTrue(sticker["available"])
        self.assertEqual("pexels", sticker["source"]["provider"])
        self.assertEqual("photograph", sticker["source"]["media_type"])
        self.assertEqual("edge_color_soft_alpha_v1", sticker["source"]["transformation"])
        self.assertEqual(
            "passed",
            sticker["source"]["photographic_object_evidence"]["provider_subject_screen"],
        )
        self.assertEqual(
            ["push pin"],
            sticker["source"]["photographic_object_evidence"]["required_subject_terms"],
        )
        self.assertEqual(
            "red push pin physical object close up plain background", self.pexels.calls[-1],
        )
        sticker_schema = self.provider.calls[-1]["output_schema"]["properties"][
            "image_request"
        ]
        self.assertEqual("sticker_object", sticker_schema["properties"]["slot"]["const"])
        self.assertNotIn("anyOf", sticker_schema)
        rendered = self.service._workspace(post["post_id"]).render_preview(
            state_sha256=tuned["state_sha256"],
        )
        sticker_node = rendered["resolved"]["nodes"]["sticker_object"]
        self.assertIsNotNone(sticker_node["visible_bounds"])

    def test_generic_add_sticker_uses_a_clean_agent_fallback_and_renders_it(self) -> None:
        rejected_query = "single smartphone on a plain background"
        accepted_query = "single light bulb on a plain dark background"
        self.pexels.rejected_sticker_queries.add(rejected_query)
        self.provider.tune_response = {
            "commands": [{
                "setting_id": "configuration.sticker.enabled", "value": True,
            }],
            "image_request": {
                "slot": "sticker_object",
                "query": rejected_query,
                "required_subject_terms": ["smartphone"],
                "fallbacks": [
                    {
                        "query": accepted_query,
                        "required_subject_terms": ["light bulb"],
                    },
                    {
                        "query": "single key on a plain background",
                        "required_subject_terms": ["key"],
                    },
                ],
            },
        }
        post = self._draft()
        tuned, _created = self.service.create_tune(
            post["post_id"], request_id="01900000-0000-7000-8000-000000000017",
            comment="add sticker", requested_by="owner",
        )
        tuned = self.service.apply_tune(tuned["active_tune_id"])

        self.assertEqual("draft", tuned["status"])
        self.assertIsNone(tuned["last_error"])
        self.assertTrue(tuned["studio"]["configuration"]["sticker"]["enabled"])
        self.assertEqual(accepted_query, tuned["last_image_request"]["query"])
        self.assertEqual(["light bulb"], tuned["last_image_request"]["required_subject_terms"])
        self.assertEqual(6, self.pexels.calls.count(rejected_query))
        rendered = self.service._workspace(post["post_id"]).render_preview(
            state_sha256=tuned["state_sha256"],
        )
        self.assertIn("sticker_object", rendered["resolved"]["nodes"])
        self.assertIsNotNone(
            rendered["resolved"]["nodes"]["sticker_object"]["visible_bounds"]
        )

    def test_sticker_comment_cannot_fall_back_to_an_emoji_content_command(self) -> None:
        with self.assertRaisesRegex(ValueError, "Studio sticker component, not copy"):
            self.service._validate_tune_plan({
                "commands": [{
                    "setting_id": "content.hero_title",
                    "value": "📌 A CALMER FIRST STEP",
                }],
                "image_request": None,
            }, owner_comment="add sticker")

    def test_add_sticker_cannot_enable_a_stale_asset_and_source_a_background(self) -> None:
        with self.assertRaisesRegex(ValueError, "must source sticker_object"):
            self.service._validate_tune_plan({
                "commands": [{
                    "setting_id": "configuration.sticker.enabled", "value": True,
                }],
                "image_request": {
                    "slot": "background_image",
                    "query": "single gold trophy on a plain white background",
                },
            }, owner_comment="add sticker")

    def test_only_approval_creates_an_immutable_asset(self) -> None:
        post = self._draft()
        self.assertEqual([], self.service.store.list("post_assets"))

        approved, created = self.service.approve_post(
            post["post_id"], state_sha256=post["state_sha256"], approved_by="owner",
        )
        self.assertTrue(created)
        self.assertEqual("approved", approved["status"])
        asset = approved["approved_asset"]
        rendered = self.service.asset_render(asset["asset_id"])
        self.assertEqual(asset["sha256"], rendered["sha256"])
        self.assertTrue((Path(self.temporary.name) / "assets" / f"{asset['asset_id']}.json").is_file())
        with self.assertRaisesRegex(ValueError, "draft simple post"):
            self.service.create_tune(
                post["post_id"], request_id="01900000-0000-7000-8000-000000000005",
                comment="Change it again", requested_by="owner",
            )

    def test_unapproved_brief_cannot_create_a_post(self) -> None:
        self.brief["approved"] = False
        with self.assertRaisesRegex(ValueError, "approved Product Brief"):
            self.service.create_post(
                request_id="01900000-0000-7000-8000-000000000006",
                brief_id=self.brief["brief_id"], requested_by="owner",
            )


if __name__ == "__main__":
    unittest.main()
