from __future__ import annotations

from io import BytesIO
import json
import ssl
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from PIL import Image

from validation_pipeline.images import (
    PexelsClient, PexelsPhoto, validate_pexels_photographic_object,
)


class _Response:
    def __init__(self, value: dict[str, object]) -> None:
        self._body = json.dumps(value).encode("utf-8")

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, _maximum: int) -> bytes:
        return self._body


class _ImageResponse:
    def __init__(
        self, body: bytes, *, content_type: str = "image/jpeg",
        final_url: str = "https://images.pexels.com/photos/123/example.jpeg?fm=jpg",
    ) -> None:
        self._body = body
        self._final_url = final_url
        self.headers = {"Content-Type": content_type}

    def __enter__(self) -> "_ImageResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def geturl(self) -> str:
        return self._final_url

    def read(self, _maximum: int) -> bytes:
        return self._body


class PexelsClientTlsTests(unittest.TestCase):
    def test_search_uses_certifi_context(self) -> None:
        client = PexelsClient("test-key")
        payload = {
            "photos": [{
                "id": 123,
                "width": 1080,
                "height": 1080,
                "url": "https://www.pexels.com/photo/example-123/",
                "photographer": "Example",
                "photographer_url": "https://www.pexels.com/@example/",
                "alt": "Example photograph",
                "src": {"large2x": "https://images.pexels.com/photos/123/example.jpeg"},
            }],
        }

        with patch(
            "validation_pipeline.images.urllib.request.urlopen",
            return_value=_Response(payload),
        ) as urlopen:
            photos = client.search("investment")

        self.assertEqual([photo.photo_id for photo in photos], ["123"])
        self.assertIs(urlopen.call_args.kwargs["context"], client.ssl_context)
        self.assertEqual(client.ssl_context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(client.ssl_context.check_hostname)


class PexelsClientDownloadTests(unittest.TestCase):
    @staticmethod
    def _photo() -> PexelsPhoto:
        return PexelsPhoto(
            photo_id="123", width=1200, height=1200,
            image_url=(
                "https://images.pexels.com/photos/123/example.jpeg"
                "?auto=compress&fm=png&w=940"
            ),
            page_url="https://www.pexels.com/photo/example-123/",
            photographer="Example",
            photographer_url="https://www.pexels.com/@example/",
            alt="Example photograph",
        )

    @staticmethod
    def _image(format_name: str) -> bytes:
        output = BytesIO()
        Image.new("RGB", (1200, 1200), "#B99B73").save(output, format=format_name)
        return output.getvalue()

    def test_download_requests_and_verifies_an_explicit_jpeg(self) -> None:
        client = PexelsClient("test-key")
        expected = self._image("JPEG")
        with patch(
            "validation_pipeline.images.urllib.request.urlopen",
            return_value=_ImageResponse(expected),
        ) as urlopen:
            actual = client.download(self._photo())

        self.assertEqual(expected, actual)
        request = urlopen.call_args.args[0]
        query = parse_qs(urlparse(request.full_url).query)
        self.assertEqual(["jpg"], query["fm"])
        self.assertEqual(["compress"], query["auto"])
        self.assertEqual(["940"], query["w"])
        self.assertEqual("image/jpeg", request.get_header("Accept"))
        self.assertIs(urlopen.call_args.kwargs["context"], client.ssl_context)

    def test_download_rejects_a_non_jpeg_http_response(self) -> None:
        client = PexelsClient("test-key")
        with patch(
            "validation_pipeline.images.urllib.request.urlopen",
            return_value=_ImageResponse(self._image("PNG"), content_type="image/png"),
        ):
            with self.assertRaisesRegex(ValueError, "requested JPEG"):
                client.download(self._photo())

    def test_download_rejects_jpeg_mime_with_png_bytes(self) -> None:
        client = PexelsClient("test-key")
        with patch(
            "validation_pipeline.images.urllib.request.urlopen",
            return_value=_ImageResponse(self._image("PNG")),
        ):
            with self.assertRaisesRegex(ValueError, "decoded JPEG format"):
                client.download(self._photo())


class PexelsPhotographicObjectTests(unittest.TestCase):
    @staticmethod
    def _photo(*, alt: str) -> PexelsPhoto:
        return PexelsPhoto(
            photo_id="123", width=1200, height=1200,
            image_url="https://images.pexels.com/photos/123/example.jpeg",
            page_url="https://www.pexels.com/photo/example-123/",
            photographer="Example",
            photographer_url="https://www.pexels.com/@example/",
            alt=alt,
        )

    @staticmethod
    def _image(format_name: str = "JPEG") -> bytes:
        output = BytesIO()
        Image.new("RGB", (1200, 1200), "#B99B73").save(output, format=format_name)
        return output.getvalue()

    def test_accepts_full_size_opaque_pexels_jpeg_photo(self) -> None:
        evidence = validate_pexels_photographic_object(
            self._photo(alt="Close-up photograph of a brass compass on a wooden table"),
            self._image(),
            query="real brass compass on wood close-up photograph",
        )
        self.assertEqual("photograph", evidence["provider_media_type"])
        self.assertEqual("image/jpeg", evidence["source_mime_type"])
        self.assertFalse(evidence["synthetic_visuals_allowed"])

    def test_rejects_explicit_render_or_non_jpeg_source(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-photographic"):
            validate_pexels_photographic_object(
                self._photo(alt="3D rendered compass icon"), self._image(),
                query="brass compass",
            )
        with self.assertRaisesRegex(ValueError, "opaque JPEG photograph"):
            validate_pexels_photographic_object(
                self._photo(alt="Photograph of a real brass compass"),
                self._image("PNG"), query="brass compass photograph",
            )


if __name__ == "__main__":
    unittest.main()
