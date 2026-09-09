from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.testclient import TestClient

from validation_pipeline.local_authorization import LocalAuthorization, local_authorization_router


class LocalAuthorizationTests(unittest.TestCase):
    def test_status_does_not_expose_cli_output_or_claim_a_working_test(self):
        service = LocalAuthorization(sys.executable)
        with patch('validation_pipeline.local_authorization.subprocess.run') as run:
            run.return_value.returncode = 0
            self.assertEqual({'status': 'authorized', 'test_status': None}, service.detail())
            self.assertEqual('status', run.call_args.args[0][-1])
            run.return_value.returncode = 1
            self.assertEqual('authorization_required', service.detail()['status'])

    def test_device_login_uses_pty_and_exposes_only_url_code_and_status(self):
        with tempfile.TemporaryDirectory() as folder:
            binary = Path(folder) / 'codex'
            binary.write_text(f'#!{sys.executable}\n' + '''
import os, sys, time
if sys.argv[-1] == 'status': sys.exit(0)
assert os.isatty(1)
print('private CLI output must not leak', flush=True)
print('https://auth.openai.com/codex/device', flush=True)
print('\\x1b[1mABCD-12345\\x1b[0m', flush=True)
time.sleep(1)
''')
            binary.chmod(0o700)
            service = LocalAuthorization(str(binary))
            try:
                self.assertEqual('authorizing', service.refresh()['status'])
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline and not service.detail().get('device_code'):
                    time.sleep(.01)
                self.assertEqual({'status': 'authorizing', 'test_status': None,
                                  'authorization_url': 'https://auth.openai.com/codex/device',
                                  'device_code': 'ABCD-12345'}, service.detail())
                thread = service.thread
                service.refresh()
                self.assertIs(thread, service.thread)
                thread.join(3)
                self.assertEqual({'status': 'authorized', 'test_status': None}, service.detail())
            finally:
                service.close()

    def test_routes_require_auth_and_loopback_origin(self):
        def owner(authorization: str = Header(default='')):
            if authorization != 'Bearer owner': raise HTTPException(401)
        service = LocalAuthorization('missing-codex-binary')
        app = FastAPI()
        app.include_router(local_authorization_router(service, [Depends(owner)]))
        with TestClient(app, base_url='http://127.0.0.1', client=('127.0.0.1', 50000)) as client:
            path = '/api/v1/settings/chatgpt-authorization'
            self.assertEqual(401, client.get(path).status_code)
            client.headers['Authorization'] = 'Bearer owner'
            self.assertEqual('no-store', client.get(path).headers['cache-control'])
            self.assertEqual(403, client.post(path+'/refresh', headers={'Origin': 'https://evil.test'}).status_code)
            self.assertEqual('failed', client.post(path+'/refresh').json()['status'])
