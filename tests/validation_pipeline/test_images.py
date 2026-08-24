from __future__ import annotations

from io import BytesIO
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import urllib.error

HAS_PILLOW = importlib.util.find_spec("PIL") is not None
if HAS_PILLOW:
    from PIL import Image

from validation_pipeline.images import PexelsClient, PexelsPhoto, SquareCreativeRenderer


def jpeg(width: int = 1400, height: int = 1200) -> bytes:
    output = BytesIO()
    Image.new("RGB", (width, height), "#68758a").save(output, format="JPEG")
    return output.getvalue()


def photo(photo_id: str, *, width: int = 1400, height: int = 1200) -> PexelsPhoto:
    return PexelsPhoto(
        photo_id=photo_id, width=width, height=height,
        image_url=f"https://images.pexels.com/photos/{photo_id}/image.jpeg",
        page_url=f"https://www.pexels.com/photo/{photo_id}/",
        photographer="Real Photographer", photographer_url="https://www.pexels.com/@real",
        alt="Real people in conversation",
    )


@unittest.skipUnless(HAS_PILLOW, "Pillow is verified in the Validation image")
class PexelsAndRenderTests(unittest.TestCase):
    def test_search_is_bounded_square_and_preserves_official_attribution_urls(self) -> None:
        payload = b'{"photos":[{"id":42,"width":1400,"height":1200,"url":"https://www.pexels.com/photo/42/","photographer":"Real Photographer","photographer_url":"https://www.pexels.com/@real","alt":"A real person","src":{"large2x":"https://images.pexels.com/photos/42/image.jpeg"}}]}'

        class Response:
            def __enter__(self): return self
            def __exit__(self, *_args): return None
            def read(self, _limit): return payload

        with patch("validation_pipeline.images.urllib.request.urlopen", return_value=Response()) as opened:
            result = PexelsClient("secret").search("professional conversation", per_page=80)
        request = opened.call_args.args[0]
        self.assertIn("orientation=square", request.full_url)
        self.assertIn("per_page=10", request.full_url)
        self.assertEqual("42", result[0].photo_id)
        self.assertEqual("https://www.pexels.com/@real", result[0].photographer_url)

    def test_search_reports_rate_limit_without_fallback_evasion(self) -> None:
        error = urllib.error.HTTPError("https://api.pexels.com/v1/search", 429, "limited", {}, None)
        with patch("validation_pipeline.images.urllib.request.urlopen", side_effect=error):
            with self.assertRaisesRegex(RuntimeError, "rate limit"):
                PexelsClient("secret").search("people")

    def test_selection_skips_duplicates_and_small_results_then_uses_fallback(self) -> None:
        client = PexelsClient("key")
        calls: list[str] = []
        client.search = lambda query: calls.append(query) or (  # type: ignore[method-assign]
            [photo("used"), photo("small", width=900)] if query == "specific" else [photo("fresh")]
        )
        client.download = lambda _photo: jpeg()  # type: ignore[method-assign]
        selected, data = client.select("specific", "people", used_ids={"used"})
        self.assertEqual("fresh", selected.photo_id)
        self.assertEqual(["specific", "people"], calls)
        self.assertTrue(data.startswith(b"\xff\xd8"))

    def test_selection_is_bounded_to_one_query_and_one_fallback(self) -> None:
        client = PexelsClient("key")
        calls: list[str] = []
        client.search = lambda query: calls.append(query) or []  # type: ignore[method-assign]
        with self.assertRaisesRegex(RuntimeError, "distinct usable"):
            client.select("specific", "category", used_ids=set())
        self.assertEqual(["specific", "category"], calls)

    def test_download_rejects_non_pexels_cdn_before_network(self) -> None:
        client = PexelsClient("key")
        unsafe = PexelsPhoto("1", 1200, 1200, "https://evil.example/a.jpg", "", "", "", "")
        with self.assertRaisesRegex(ValueError, "allowed CDN"):
            client.download(unsafe)

    def test_download_rejects_invalid_mime_oversize_and_unsafe_redirect(self) -> None:
        class Response:
            def __init__(self, *, content_type="image/jpeg", data=b"ok", url="https://images.pexels.com/a.jpg"):
                self.headers = {"Content-Type": content_type}; self.data = data; self.url = url
            def __enter__(self): return self
            def __exit__(self, *_args): return None
            def read(self, _limit): return self.data
            def geturl(self): return self.url

        client = PexelsClient("key")
        candidate = photo("1")
        with patch("validation_pipeline.images.urllib.request.urlopen", return_value=Response(content_type="text/html")):
            with self.assertRaisesRegex(ValueError, "supported image"):
                client.download(candidate)
        with patch("validation_pipeline.images.urllib.request.urlopen", return_value=Response(data=b"x" * (12 * 1024 * 1024 + 1))):
            with self.assertRaisesRegex(ValueError, "bounded size"):
                client.download(candidate)
        with patch("validation_pipeline.images.urllib.request.urlopen", return_value=Response(url="https://evil.example/a.jpg")):
            with self.assertRaisesRegex(ValueError, "redirected outside"):
                client.download(candidate)

    def test_render_is_valid_square_jpeg_with_matching_deterministic_digest(self) -> None:
        with TemporaryDirectory() as directory:
            font = Path(directory) / "font.ttf"
            system_font = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
            if not system_font.exists():
                self.skipTest("DejaVu font is unavailable")
            font.write_bytes(system_font.read_bytes())
            renderer = SquareCreativeRenderer(font)
            first, first_digest = renderer.render(
                jpeg(), hook="Перший спокійний крок", offer="Перша консультація безкоштовно",
                cta="Записатися", crop_focus="left",
            )
            second, second_digest = renderer.render(
                jpeg(), hook="Перший спокійний крок", offer="Перша консультація безкоштовно",
                cta="Записатися", crop_focus="left",
            )
        image = Image.open(BytesIO(first))
        self.assertEqual((1080, 1080), image.size)
        self.assertEqual("JPEG", image.format)
        self.assertEqual(first, second)
        self.assertEqual(first_digest, second_digest)
        self.assertEqual(64, len(first_digest))

    def test_attribution_is_complete(self) -> None:
        metadata = photo("42").source_metadata()
        self.assertEqual("pexels", metadata["provider"])
        self.assertEqual("Real Photographer", metadata["photographer"])
        self.assertIn("Pexels", metadata["attribution"])
        self.assertTrue(metadata["license_url"].startswith("https://www.pexels.com/"))


if __name__ == "__main__":
    unittest.main()
