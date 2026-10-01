from io import BytesIO
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock
from urllib.error import HTTPError

from PIL import Image
from validation_pipeline.verify_pexels import verify


class PexelsCanaryTests(TestCase):
    def photo(self):
        output = BytesIO()
        Image.new('RGB', (1200, 1200), '#BBAACC').save(output, format='JPEG')
        return SimpleNamespace(photo_id='fixture'), output.getvalue()

    def failure(self, status):
        error = RuntimeError('Pexels search failed')
        error.__cause__ = HTTPError('https://api.pexels.com/v1/search', status, 'test', {}, None)
        return error

    def test_transient_server_error_requires_a_real_successful_photo(self):
        client, pause = Mock(), Mock()
        client.select.side_effect = [self.failure(500), self.photo()]
        photo, inspected = verify(client, pause=pause)
        self.assertEqual('fixture', photo.photo_id)
        self.assertEqual(1200, inspected['width'])
        self.assertEqual(2, client.select.call_count)
        pause.assert_called_once_with(1)

    def test_server_errors_stop_after_three_attempts(self):
        client, pause = Mock(), Mock()
        client.select.side_effect = self.failure(503)
        with self.assertRaises(RuntimeError): verify(client, pause=pause)
        self.assertEqual(3, client.select.call_count)
        self.assertEqual([1,2], [call.args[0] for call in pause.call_args_list])

    def test_credentials_rate_limits_and_bad_pixels_are_not_retried(self):
        for status in (401,403,429):
            client, pause = Mock(), Mock()
            client.select.side_effect = self.failure(status)
            with self.assertRaises(RuntimeError): verify(client, pause=pause)
            self.assertEqual(1, client.select.call_count)
            pause.assert_not_called()
        client = Mock()
        client.select.return_value = (SimpleNamespace(photo_id='bad'), b'incomplete image')
        with self.assertRaises(ValueError): verify(client, pause=Mock())
        self.assertEqual(1, client.select.call_count)
