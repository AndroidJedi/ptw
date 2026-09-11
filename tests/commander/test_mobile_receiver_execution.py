"""Execute the real receiver in a disposable container with simulated services."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from uuid import uuid4


@unittest.skipUnless(os.environ.get("PTW_RECEIVER_DISPOSABLE") == "1" and Path('/.dockerenv').exists(), "requires the isolated receiver test container")
class ReceiverExecutionTests(unittest.TestCase):
    def setUp(self):
        self.source = Path(__file__).resolve().parents[2]
        self.repo = Path("/root/ptw")
        self.assertFalse(self.repo.exists(), "Refuse to overwrite an existing checkout")
        self.temp = tempfile.TemporaryDirectory(prefix="receiver-fixture-")
        self.origin = Path(self.temp.name) / "origin.git"
        subprocess.run(["git", "init", "--bare", "-q", str(self.origin)], check=True)
        subprocess.run(["git", "clone", "-q", str(self.origin), str(self.repo)], check=True, stderr=subprocess.DEVNULL)
        self.addCleanup(shutil.rmtree, self.repo)
        (self.repo / "scripts").mkdir()
        for name in ("verify_ptw_release_request.py", "receive_ptw_mobile_release.sh"):
            shutil.copyfile(self.source / "scripts" / name, self.repo / "scripts" / name)
        helpers = {
            "ptw_release_recovery.sh": '''#!/bin/bash
set -eu
if [[ $1 == snapshot ]]; then mkdir "$2"; git -C /root/ptw rev-parse HEAD > "$2/revision"; exit; fi
if [[ ${PTW_TEST_FAILURE:-} == recovery ]]; then exit 1; fi
git -C /root/ptw switch --detach "$(<"$2/revision")"
printf '%s\\n' restored > /root/ptw/.local/recovery-result
''',
            "receive_ptw_preserving_release.sh": '''#!/bin/bash
set -eu
IFS= read -r header
[[ $header == 'PTW-PRESERVING-STREAM 1' ]]
IFS= read -r payload
[[ $payload == 'artifact-stream-sentinel' ]]
printf '%s\\n' cutover > /root/ptw/.local/cutover
[[ ${PTW_TEST_FAILURE:-} != application && ${PTW_TEST_FAILURE:-} != recovery ]]
''',
            "apply_ptw_release_configuration.sh": '''#!/bin/bash
[[ ${PTW_TEST_FAILURE:-} != infrastructure ]]
''',
            "verify_ptw_migration_inventory.py": "import sys\nassert sys.stdin.read() == '', 'Inventory helper consumed the artifact stream'\nprint('Simulated migration inventory accepted')\n",
        }
        for name, content in helpers.items():
            path = self.repo / "scripts" / name
            path.write_text(content)
            path.chmod(0o755)
        audit = self.repo / "skills/ptw-owner-console-incident/scripts/audit_live_owner_console.py"
        audit.parent.mkdir(parents=True)
        audit.write_text("print('Simulated Hosting audit passed')\n")
        self.git("add", ".")
        self.git("commit", "-qm", "Accepted fixture")
        self.base = self.git("rev-parse", "HEAD")
        self.git("push", "-q", "origin", "HEAD:main")
        (self.repo / ".local").mkdir()
        (self.repo / ".local/deployed-revision").write_text(self.base)
        (self.repo / "feature.txt").write_text("candidate")
        self.git("add", "feature.txt")
        self.git("commit", "-qm", "Candidate")
        self.candidate = self.git("rev-parse", "HEAD")
        self.identifier = str(uuid4())
        self.git("push", "-q", "origin", f"HEAD:refs/heads/god-candidate/{self.identifier}")
        self.git("switch", "--detach", self.base)
        manifest = {"version": 2, "id": self.identifier, "base_revision": self.base, "revision": self.candidate, "candidate_branch": "god-candidate/" + self.identifier}
        (self.repo / ".ptw-release-request.json").write_text(json.dumps(manifest))
        self.git("add", ".ptw-release-request.json")
        self.git("commit", "-qm", "Request")
        self.git("push", "-q", "origin", f"HEAD:refs/heads/god-deploy/{self.identifier}")
        self.git("switch", "--detach", self.base)
        Path("/opt/ptw/commander-workspace/.git").mkdir(parents=True, exist_ok=True)
        Path("/opt/ptw/platform").mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init", "-q", "/opt/ptw/platform"], check=True)
        subprocess.run(["git", "-C", "/opt/ptw/platform", "-c", "user.name=Test", "-c", "user.email=test@example.test", "commit", "--allow-empty", "-qm", "Platform fixture"], check=True)

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.repo), "-c", "user.name=Test", "-c", "user.email=test@example.test", *args], text=True, stderr=subprocess.DEVNULL).strip()

    def tearDown(self):
        # Exact disposable fixture roots, never invoked on a production host.
        self.temp.cleanup()

    def run_release(self, failure=""):
        revision = "a" * 40 if failure == "before" else self.candidate
        payload = f"PTW-MOBILE-RELEASE 2 god-mobile-20260911-{revision[:12]} {revision} god-deploy/{self.identifier}\nREUSE owner-console\nREUSE public-landings\nPTW-PRESERVING-STREAM 1\nartifact-stream-sentinel\n"
        return subprocess.run(["bash", str(self.source / "scripts/receive_ptw_mobile_release.sh")], input=payload, text=True,
            env={**os.environ, "PTW_TEST_FAILURE": failure}, capture_output=True, timeout=30)

    def receipt(self):
        return json.loads((self.repo / ".local/commander-releases" / (self.identifier + ".json")).read_text())

    def test_failure_before_cutover_never_changes_source(self):
        result = self.run_release("before")
        self.assertNotEqual(0, result.returncode)
        self.assertEqual(self.base, self.git("rev-parse", "HEAD"))
        self.assertFalse((self.repo / ".local/cutover").exists())

    def test_failure_after_cutover_records_restored_release(self):
        result = self.run_release("application")
        self.assertNotEqual(0, result.returncode, result.stdout)
        self.assertEqual("rolled_back", self.receipt()["phase"], result.stderr)
        self.assertEqual(self.base, self.git("rev-parse", "HEAD"))

    def test_infrastructure_failure_still_uses_accepted_recovery(self):
        result = self.run_release("infrastructure")
        self.assertNotEqual(0, result.returncode)
        self.assertEqual("rolled_back", self.receipt()["phase"], result.stderr)

    def test_failed_recovery_is_explicit_and_retains_artifacts(self):
        result = self.run_release("recovery")
        self.assertNotEqual(0, result.returncode)
        self.assertEqual("recovery_failed", self.receipt()["phase"], result.stderr)
        self.assertIn("protected recovery files retained", result.stderr)

    def test_acceptance_advances_marker_only_after_all_checks(self):
        result = self.run_release()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("accepted", self.receipt()["phase"])
        self.assertEqual(self.candidate, (self.repo / ".local/deployed-revision").read_text().strip())


if __name__ == "__main__":
    unittest.main()
