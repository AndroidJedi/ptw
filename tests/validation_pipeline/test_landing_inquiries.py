from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from validation_pipeline.landing_inquiries import LandingInquiries, LocalInquiryAudit, inquiry_router, normalize
from validation_pipeline.local_brief_store import LocalBriefStore


class Publications:
    def __init__(self):
        self.project, self.publication, self.event, self.version = (str(uuid4()) for _ in range(4))
        self.digest = 'a' * 64

    def _active(self, slug):
        if slug != 'water-quality':
            raise KeyError('Published page unavailable')
        return ({'project_id': self.project, 'publication_id': self.publication}, {'event_id': self.event, 'landing_version_id': self.version, 'landing_version_sha256': self.digest}, '', {})


class InquiryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.publications = Publications()
        self.store = LocalBriefStore(Path(self.directory.name))
        self.service = LandingInquiries(LocalInquiryAudit(self.store), self.publications)
        self.request = {'request_id': str(uuid4()), 'source': 'apple', 'question': 'Які джерела даних?', 'contact': '', 'contact_channel': 'email', 'website': '', 'landing_version_sha256': 'a' * 64}

    def test_receipt_retry_and_restart_preserve_one_inquiry_and_exact_version(self):
        first = self.service.submit('water-quality', self.request)
        self.assertTrue(first['created'])
        restarted = LandingInquiries(LocalInquiryAudit(LocalBriefStore(self.directory.name)), self.publications)
        self.assertFalse(restarted.submit('water-quality', self.request)['created'])
        inbox = restarted.inbox(self.publications.project)['items']
        self.assertEqual(1, len(inbox))
        self.assertEqual(self.publications.version, inbox[0]['landing_version_id'])
        self.assertEqual(self.request['question'], inbox[0]['question'])
        self.assertNotIn('contact', first)
        self.assertEqual([], self.store.list('human_feedback'))

    def test_changed_request_and_stale_page_do_not_create_duplicate(self):
        self.service.submit('water-quality', self.request)
        with self.assertRaises(ValueError):
            self.service.submit('water-quality', {**self.request, 'question': 'Different'})
        with self.assertRaises(ValueError):
            self.service.submit('water-quality', {**self.request, 'landing_version_sha256': 'b' * 64})
        with self.assertRaises(KeyError):
            self.service.submit('unavailable', self.request)
        self.assertEqual(1, len(self.service.inbox(self.publications.project)['items']))

    def test_contact_only_and_handles(self):
        for channel, contacts in [('email', ['you@example.com']), ('telegram', ['@natal_user', 'https://t.me/natal_user', 't.me/natal_user']), ('instagram', ['natal.user', 'https://www.instagram.com/natal.user/'])]:
            for contact in contacts:
                value = {**self.request, 'request_id': str(uuid4()), 'question': '', 'contact': contact, 'contact_channel': channel}
                self.assertTrue(self.service.submit('water-quality', value)['accepted'])

    def test_empty_oversized_unknown_and_honeypot_inputs_fail(self):
        for patch in [{'question': ''}, {'question': 'x' * 2001}, {'contact': 'invalid'}, {'contact_channel': 'sms'}, {'source': 'unknown'}, {'website': 'bot'}, {'question': 123}, {'unexpected': 'x'}, {'request_id': 'bad'}, {'contact': 'https://evil.test/user', 'contact_channel': 'telegram'}]:
            with self.subTest(patch=patch), self.assertRaises((ValueError, TypeError)):
                normalize({**self.request, **patch})

    def test_public_route_rate_bound_and_private_scope(self):
        app = FastAPI()
        app.include_router(inquiry_router(self.service, prefix='/public', public=True))
        client = TestClient(app)
        for _ in range(30):
            response = client.post('/public/water-quality/inquiries', json={**self.request, 'request_id': str(uuid4())})
            self.assertEqual(202, response.status_code)
        self.assertEqual(429, client.post('/public/water-quality/inquiries', json=self.request).status_code)
        self.assertEqual([], self.service.inbox(str(uuid4()))['items'])


if __name__ == '__main__':
    unittest.main()
