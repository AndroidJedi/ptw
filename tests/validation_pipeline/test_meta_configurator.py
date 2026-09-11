"""Exercise the hidden-prompt setup without real credentials or network calls."""
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[2]


class MetaConfiguratorTests(unittest.TestCase):
    def test_organic_setup_does_not_require_advertising_access(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            binary = root / 'bin'
            binary.mkdir()
            fake_git = binary / 'git'
            fake_git.write_text('#!/bin/sh\nprintf "%s\\n" "$PTW_TEST_ROOT"\n')
            fake_curl = binary / 'curl'
            fake_curl.write_text(f'''#!{sys.executable}
import json, os, pathlib, sys
args = sys.argv[1:]
assert '--config' in args and sys.stdin.read().startswith('oauth2-bearer = "')
assert '--globoff' in args
assert args[-1].endswith('/me/accounts?fields=id,name,instagram_business_account{{id,username}}&limit=100')
pathlib.Path(args[args.index('--output')+1]).write_text(json.dumps({{'data':[{{'id':'456','name':'Example','instagram_business_account': {{'id':'789','username':'example'}}}}]}}))
''')
            fake_git.chmod(0o700)
            fake_curl.chmod(0o700)
            result = subprocess.run(['bash',str(ROOT/'scripts/configure_meta_ads.sh'),'local','-','456','example'],
                env={**os.environ,'PATH':str(binary)+os.pathsep+os.environ['PATH'],
                     'PYTHON_BIN':sys.executable,'PTW_TEST_ROOT':str(root),'META_INSTAGRAM_MEDIA_ORIGIN':'https://test.example'},
                input='test-only-hidden-token-123456\n', text=True, capture_output=True, check=True)
            self.assertNotIn('test-only-hidden-token-123456', result.stdout + result.stderr)
            config = root/'.local/local-studio.env'
            self.assertEqual(config.stat().st_mode & 0o777,0o600)
            fields = dict(line.split('=',1) for line in config.read_text().splitlines())
            self.assertEqual(fields['META_AD_ACCOUNT_ID'],'')
            self.assertEqual(fields['META_INSTAGRAM_ACTOR_ID'],'789')
            self.assertEqual(fields['META_INSTAGRAM_MEDIA_ORIGIN'],'https://test.example')

    def test_organic_setup_rejects_an_unassigned_page(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            binary = root / 'bin'
            binary.mkdir()
            fake_git = binary / 'git'
            fake_git.write_text('#!/bin/sh\nprintf "%s\\n" "$PTW_TEST_ROOT"\n')
            fake_curl = binary / 'curl'
            fake_curl.write_text(f'''#!{sys.executable}
import json, pathlib, sys
args = sys.argv[1:]
sys.stdin.read()
pathlib.Path(args[args.index('--output')+1]).write_text(json.dumps({{'data':[{{'id':'other','instagram_business_account':{{'id':'789','username':'example'}}}}]}}))
''')
            fake_git.chmod(0o700)
            fake_curl.chmod(0o700)
            result = subprocess.run(['bash', str(ROOT/'scripts/configure_meta_ads.sh'), 'local', '-', '456', 'example'],
                env={**os.environ, 'PATH': str(binary)+os.pathsep+os.environ['PATH'],
                     'PYTHON_BIN': sys.executable, 'PTW_TEST_ROOT': str(root)},
                input='test-only-hidden-token-123456\n', text=True, capture_output=True)
            self.assertNotEqual(0, result.returncode)
            self.assertIn('The requested Facebook Page is not assigned', result.stderr)
            self.assertFalse((root/'.local/local-studio.env').exists())
