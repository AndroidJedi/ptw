from __future__ import annotations

import json
import ssl
import unittest
from unittest.mock import patch

from validation_pipeline.images import PexelsClient


class _Response:
    def __init__(self, value: dict[str, object]) -> None:
        self._body = json.dumps(value).encode("utf-8")

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

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


if __name__ == "__main__":
    unittest.main()
