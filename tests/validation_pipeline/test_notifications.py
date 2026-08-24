from __future__ import annotations

import unittest
from unittest.mock import patch

from validation_pipeline.notifications import FailureNotificationClient


class Response:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return b'{"status":"sent","attempt_id":"attempt"}'


class FailureNotificationClientTests(unittest.TestCase):
    @patch("validation_pipeline.notifications.urllib.request.urlopen", return_value=Response())
    def test_callback_is_one_authenticated_bounded_request(self, urlopen) -> None:
        client = FailureNotificationClient("http://owner/internal/v1/validation-failures", "shared-token")
        result = client.notify(target_id="target", attempt_id="attempt", stage="ad_creative_batch")

        self.assertEqual("sent", result["status"])
        urlopen.assert_called_once()
        request, = urlopen.call_args.args
        self.assertEqual("http://owner/internal/v1/validation-failures", request.full_url)
        self.assertEqual("shared-token", request.headers["X-ptw-owner-gateway-token"])
        self.assertEqual(
            b'{"target_id": "target", "attempt_id": "attempt", "stage": "ad_creative_batch"}',
            request.data,
        )
        self.assertEqual(30, urlopen.call_args.kwargs["timeout"])


if __name__ == "__main__":
    unittest.main()
