from pathlib import Path
import json
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from validation_pipeline.commander_release import (
    CONFIRMATION, CommanderReleaseService, DeploymentRequest, create_app_from_env,
)


class Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def __iter__(self):
        return iter(json.dumps(self.payload).splitlines(keepends=True))

    def read(self):
        return json.dumps(self.payload).encode()


class CommanderReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "-C", self.repo, "init", "-q"], check=True)
        (self.repo / "README.md").write_text("baseline\n")
        subprocess.run(["git", "-C", self.repo, "add", "."], check=True)
        subprocess.run([
            "git", "-C", self.repo, "-c", "user.name=Test", "-c", "user.email=test@example.test",
            "commit", "-qm", "baseline",
        ], check=True)
        self.base = subprocess.check_output(["git", "-C", self.repo, "rev-parse", "HEAD"], text=True).strip()
        self.deployed = self.root / "deployed-revision"
        self.deployed.write_text(self.base + "\n")
        self.key = self.root / "id_ed25519"
        self.key.write_text("test-key")
        self.hosts = self.root / "known_hosts"
        self.hosts.write_text("github.com test-key\n")
        self.service = CommanderReleaseService(
            self.repo, self.root / "state", deployed_revision_file=self.deployed,
            deploy_key=self.key, known_hosts=self.hosts,
        )

    def tearDown(self):
        self.temp.cleanup()

    def create_without_network(self, request_id=None):
        original = self.service._git

        def git(*args, environment=None):
            if args and args[0] == "push":
                return ""
            return original(*args, environment=environment)

        with patch.object(self.service, "_git", side_effect=git):
            return self.service.create(DeploymentRequest(
                request_id=request_id or uuid4(), confirmation=CONFIRMATION,
            ))

    def test_commits_exact_candidate_and_idempotently_queues_workflow(self):
        path = self.repo / "apps/commander-web/src/change.ts"
        path.parent.mkdir(parents=True)
        path.write_text("export const changed = true\n")
        request_id = uuid4()
        result = self.create_without_network(request_id)
        deployment = result["deployment"]
        self.assertEqual("queued", deployment["status"])
        self.assertRegex(deployment["revision"], r"^[0-9a-f]{40}$")
        self.assertEqual([], result["candidate"]["protected_files"])
        self.assertIn("PTW-Base-Revision: " + self.base, subprocess.check_output(
            ["git", "-C", self.repo, "log", "-1", "--format=%B"], text=True,
        ))
        duplicate = self.service.create(DeploymentRequest(
            request_id=request_id, confirmation=CONFIRMATION,
        ))
        self.assertEqual(deployment["id"], duplicate["deployment"]["id"])

    def test_rejects_protected_infrastructure_and_exact_confirmation(self):
        workflow = self.repo / ".github/workflows/release.yml"
        workflow.parent.mkdir(parents=True)
        workflow.write_text("unsafe\n")
        detail = self.service.detail()
        self.assertEqual([".github/workflows/release.yml"], detail["candidate"]["protected_files"])
        with self.assertRaisesRegex(ValueError, "Type DEPLOY NEW CHANGES"):
            self.service.create(DeploymentRequest(request_id=uuid4(), confirmation="x" * len(CONFIRMATION)))
        with self.assertRaisesRegex(ValueError, "protected release infrastructure"):
            self.service.create(DeploymentRequest(request_id=uuid4(), confirmation=CONFIRMATION))

    def test_refresh_maps_public_workflow_result_without_exposing_logs(self):
        path = self.repo / "owner_gateway/change.py"
        path.parent.mkdir()
        path.write_text("value = 1\n")
        queued = self.create_without_network()["deployment"]
        payload = {"workflow_runs": [{
            "head_sha": queued["revision"], "status": "completed", "conclusion": "failure",
            "html_url": "https://github.com/AndroidJedi/ptw/actions/runs/1",
        }]}
        self.service._last_workflow_poll = float("-inf")
        with patch("validation_pipeline.commander_release.urlopen", return_value=Response(payload)):
            result = self.service.detail()["deployment"]
        self.assertEqual(("failed", "release_workflow_failed"), (result["status"], result["error_code"]))
        self.assertEqual(payload["workflow_runs"][0]["html_url"], result["workflow_url"])

    def test_private_api_requires_gateway_token(self):
        with patch.dict("os.environ", {
            "OWNER_GATEWAY_BRIDGE_TOKEN": "bridge",
            "PTW_COMMANDER_REPOSITORY": str(self.repo),
            "PTW_RELEASE_STATE": str(self.root / "api-state"),
            "PTW_DEPLOYED_REVISION": str(self.deployed),
            "PTW_GITHUB_DEPLOY_KEY": str(self.key),
            "PTW_GITHUB_KNOWN_HOSTS": str(self.hosts),
        }):
            with TestClient(create_app_from_env()) as client:
                path = "/internal/v1/settings/commander/deployments"
                self.assertEqual(401, client.get(path).status_code)
                response = client.get(path, headers={"X-PTW-Owner-Gateway-Token": "bridge"})
                self.assertEqual(200, response.status_code)
                self.assertEqual("no-store", response.headers["cache-control"])


if __name__ == "__main__":
    unittest.main()
