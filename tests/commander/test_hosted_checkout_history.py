"""Exercise hosted checkout preparation without touching a real workspace."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


class HostedCheckoutHistoryTests(unittest.TestCase):
    def test_preparation_retains_accepted_ancestor_and_owner_changes(self):
        script = Path(__file__).resolve().parents[2] / 'scripts/prepare_commander_god_workspace.sh'
        with tempfile.TemporaryDirectory(prefix='ptw-checkout-history-') as directory:
            root = Path(directory)
            source, hosted = root / 'source', root / 'hosted'
            def git(path, *args):
                return subprocess.check_output(['git', '-C', str(path), '-c', 'core.hooksPath=/dev/null',
                    '-c', 'user.name=Test', '-c', 'user.email=test@example.test', *args],
                    text=True, stderr=subprocess.DEVNULL).strip()
            source.mkdir()
            git(source, 'init', '-q')
            (source / 'feature').write_text('accepted')
            git(source, 'add', 'feature')
            git(source, 'commit', '-qm', 'Accepted')
            accepted = git(source, 'rev-parse', 'HEAD')
            (source / 'feature').write_text('candidate')
            git(source, 'commit', '-qam', 'Candidate')
            candidate = git(source, 'rev-parse', 'HEAD')
            subprocess.run(['git', 'clone', '-q', '--depth', '1', source.as_uri(), str(hosted)], check=True)
            self.assertEqual('true', git(hosted, 'rev-parse', '--is-shallow-repository'))
            environment = {**os.environ, 'PTW_REPOSITORY': str(source), 'PTW_COMMANDER_WORKSPACE': str(hosted)}
            subprocess.run(['bash', str(script), candidate], env=environment, check=True, capture_output=True)
            self.assertEqual('false', git(hosted, 'rev-parse', '--is-shallow-repository'))
            git(hosted, 'merge-base', '--is-ancestor', accepted, 'HEAD')
            (hosted / 'feature').write_text('owner unfinished work')
            subprocess.run(['bash', str(script), accepted], env=environment, check=True, capture_output=True)
            self.assertEqual(candidate, git(hosted, 'rev-parse', 'HEAD'))
            self.assertEqual('owner unfinished work', (hosted / 'feature').read_text())
            fresh = root / 'fresh'
            environment['PTW_COMMANDER_WORKSPACE'] = str(fresh)
            subprocess.run(['bash', str(script), candidate], env=environment, check=True, capture_output=True)
            self.assertEqual('false', git(fresh, 'rev-parse', '--is-shallow-repository'))
            git(fresh, 'merge-base', '--is-ancestor', accepted, 'HEAD')
