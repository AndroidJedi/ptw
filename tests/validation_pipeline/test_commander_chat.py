from pathlib import Path
import json
import fcntl
import os
import sys
import tempfile
import time
import unittest
from uuid import uuid4
from unittest.mock import patch

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.testclient import TestClient

from validation_pipeline.commander_chat import (
    ACTIVE, ChatMessage, CommanderChatService, commander_chat_router, safe_text,
)


class CommanderChatTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        (self.repo / ".git").mkdir()
        self.skill = self.repo / "skills/commander-god-mode/SKILL.md"
        self.skill.parent.mkdir(parents=True)
        self.skill.write_text("Maintain the relevant canonical skills after verified work.")
        self.binary = self.root / "fake-codex"
        self.binary.write_text(f"#!{sys.executable}\n" + '''
import json, os, pathlib, subprocess, sys, time
prompt = sys.stdin.read()
pathlib.Path('invocation.json').write_text(json.dumps({'args': sys.argv, 'prompt': prompt, 'env': dict(os.environ)}))
latest = prompt.rsplit('Latest owner request:', 1)[-1]
if 'TEST_SLEEP' in latest:
    child = subprocess.Popen([sys.executable, '-c', "import time; time.sleep(2); open('child-survived', 'w').write('bad')"])
    pathlib.Path('child-started').write_text(str(child.pid))
    time.sleep(60)
if 'TEST_FAILURE' in latest:
    print('Bearer private-value', file=sys.stderr)
    sys.exit(1)
if 'TEST_EMPTY' in latest:
    sys.exit(0)
pathlib.Path('carousel.txt').write_text('new feature')
out = pathlib.Path(sys.argv[sys.argv.index('--output-last-message') + 1])
out.write_text('Added the local carousel feature. Tests passed.')
''')
        self.binary.chmod(0o700)
        self.service = CommanderChatService(self.repo, self.root / "state", codex_binary=str(self.binary))

    def tearDown(self):
        self.service.close()
        self.temp.cleanup()

    def wait(self, chat_id):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            chat = self.service.chat(chat_id)
            if chat["turns"] and chat["turns"][-1]["status"] not in ACTIVE:
                if self.service._thread:
                    self.service._thread.join(1)
                return chat
            time.sleep(.01)
        self.fail("Commander did not finish")

    def send(self, message, chat_id=None, request_id=None):
        chat_id = chat_id or self.service.create_chat()["id"]
        return self.service.send(chat_id, ChatMessage(request_id=request_id or uuid4(), message=message))

    def test_real_subprocess_edits_checkout_and_followup_retains_context(self):
        (self.repo / "unrelated.txt").write_text("owner draft")
        with patch.dict(os.environ, {"PTW_TEST_SECRET": "never inherit"}):
            first = self.send("Add carousel creation")
            finished = self.wait(first["id"])
        self.assertEqual("completed", finished["turns"][0]["status"])
        self.assertEqual("new feature", (self.repo / "carousel.txt").read_text())
        self.assertEqual("owner draft", (self.repo / "unrelated.txt").read_text())
        invocation = json.loads((self.repo / "invocation.json").read_text())
        self.assertNotIn("PTW_TEST_SECRET", invocation["env"])
        self.assertIn("workspace-write", invocation["args"])
        self.assertIn("sandbox_workspace_write.network_access=false", invocation["args"])
        self.assertIn("--ignore-user-config", invocation["args"])
        self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", invocation["args"])
        self.send("Now improve its layout", first["id"])
        self.wait(first["id"])
        prompt = json.loads((self.repo / "invocation.json").read_text())["prompt"]
        self.assertIn("Add carousel creation", prompt)
        self.assertIn("Added the local carousel feature", prompt)
        self.service.close()
        self.service = CommanderChatService(self.repo, self.root / "state", codex_binary=str(self.binary))
        self.assertEqual(2, len(self.service.chat(first["id"])["turns"]))

    def test_idempotency_and_cross_chat_request_conflict(self):
        request_id = uuid4()
        first = self.send("Create tab", request_id=request_id)
        self.wait(first["id"])
        duplicate = self.send("Create tab", first["id"], request_id)
        self.assertEqual(1, len(duplicate["turns"]))
        with self.assertRaises(ValueError):
            self.send("Different request", first["id"], request_id)
        with self.assertRaises(ValueError):
            self.send("Create tab", request_id=request_id)

    def test_stop_kills_process_group_and_serializes_across_conversations(self):
        started = self.send("TEST_SLEEP")
        deadline = time.monotonic() + 3
        while not (self.repo / "child-started").exists() and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertTrue((self.repo / "child-started").exists())
        with self.assertRaises(ValueError):
            self.send("another request")
        wrong_chat = self.service.create_chat()["id"]
        with self.assertRaises(KeyError):
            self.service.stop(wrong_chat, started["turns"][0]["id"])
        self.service.stop(started["id"], started["turns"][0]["id"])
        stopped = self.wait(started["id"])
        self.assertEqual("cancelled", stopped["turns"][0]["status"])
        time.sleep(2.1)
        self.assertFalse((self.repo / "child-survived").exists())
        self.send("New request after stop", started["id"])
        self.assertEqual("completed", self.wait(started["id"])["turns"][-1]["status"])

    def test_restart_marks_active_turn_interrupted_without_replay(self):
        first = self.send("first")
        self.wait(first["id"])
        self.service._update(first["turns"][0]["id"], "running")
        self.service.close()
        self.service = CommanderChatService(self.repo, self.root / "state", codex_binary=str(self.binary))
        turn = self.service.chat(first["id"])["turns"][0]
        self.assertEqual(("interrupted", "restart"), (turn["status"], turn["error_code"]))
        self.assertIsNone(self.service._thread)

    def test_worker_exits_when_the_parent_liveness_pipe_closes(self):
        started = self.send("TEST_SLEEP")
        deadline = time.monotonic() + 3
        while not (self.repo / "child-started").exists() and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertTrue((self.repo / "child-started").exists())
        self.service._liveness.close()
        self.assertEqual("failed", self.wait(started["id"])["turns"][-1]["status"])
        time.sleep(2.1)
        self.assertFalse((self.repo / "child-survived").exists())

    def test_second_service_is_rejected(self):
        with self.assertRaises(RuntimeError):
            CommanderChatService(self.repo, self.root / "state", codex_binary=str(self.binary))

    def test_release_lock_prevents_a_new_coding_turn(self):
        lease = (self.repo / ".git" / "ptw-commander-operation.lock").open("a")
        fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            with self.assertRaisesRegex(ValueError, "release is preparing"):
                self.send("must wait")
        finally:
            lease.close()

    def test_each_turn_uses_current_canonical_skill_and_records_its_digest(self):
        first = self.send("first request")
        first = self.wait(first["id"])
        old_digest = first["turns"][0]["skill_sha256"]
        self.skill.write_text("A new verified skill lesson for future turns.")
        self.send("second request", first["id"])
        finished = self.wait(first["id"])
        self.assertNotEqual(old_digest, finished["turns"][1]["skill_sha256"])
        self.assertEqual(old_digest, finished["turns"][0]["skill_sha256"])
        invocation = json.loads((self.repo / "invocation.json").read_text())
        self.assertIn(self.skill.read_text(), invocation["prompt"])
        self.skill.unlink()
        self.assertFalse(self.service.detail()["available"])
        self.assertEqual("skill_missing", self.service.detail()["unavailable_reason"])
        with self.assertRaises(RuntimeError):
            self.send("must not run", first["id"])

    def test_failure_timeout_and_missing_reply_are_bounded(self):
        for message, code in [("TEST_FAILURE", "execution_failed"), ("TEST_EMPTY", "invalid_reply")]:
            chat = self.send(message)
            value = self.wait(chat["id"])
            self.assertEqual(code, value["turns"][-1]["error_code"])
            self.assertNotIn("private-value", json.dumps(value))
        self.service.timeout_seconds = .1
        chat = self.send("TEST_SLEEP")
        self.assertEqual("timeout", self.wait(chat["id"])["turns"][-1]["error_code"])
        self.assertEqual([], list(self.service.state.glob("commander-*")))

    def test_credentials_redacted_before_persistence(self):
        message = 'token="sensitive-value" Bearer hidden-value sk-' + 'a' * 30
        chat = self.send(message)
        result = self.wait(chat["id"])
        self.assertNotIn("sensitive-value", json.dumps(result))
        self.assertNotIn("hidden-value", self.service.database.read_bytes().decode(errors="ignore"))
        self.assertNotIn('a' * 30, safe_text(message))

    def test_http_auth_origin_validation_and_no_store(self):
        def owner(authorization: str = Header(default="")):
            if authorization != "Bearer test-owner":
                raise HTTPException(401)
        app = FastAPI()
        app.include_router(commander_chat_router(self.service, dependencies=[Depends(owner)]))
        base = "/api/v1/settings/commander"
        with TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 50000)) as client:
            self.assertEqual(401, client.get(base).status_code)
            client.headers["Authorization"] = "Bearer test-owner"
            self.assertEqual(403, client.get(base, headers={"Origin": "https://evil.test"}).status_code)
            self.assertEqual(403, client.get(base, headers={"Host": "evil.test"}).status_code)
            self.assertEqual(403, client.get(base, headers={"Origin": "null"}).status_code)
            self.assertEqual("no-store", client.get(base).headers["cache-control"])
            chat = client.post(base + "/chats", json={}).json()
            url = f'{base}/chats/{chat["id"]}/messages'
            for message in ["", " ", "x" * 8001]:
                self.assertEqual(422, client.post(url, json={"message": message, "request_id": str(uuid4())}).status_code)
            self.assertEqual(422, client.post(url, json={"message": "hi", "request_id": str(uuid4()), "target": "vps"}).status_code)
            self.assertEqual(404, client.get(base + "/chats/" + str(uuid4())).status_code)
            response = client.post(url, json={"message": "Add a tab", "request_id": str(uuid4())})
            self.assertEqual(202, response.status_code)
            self.assertEqual("completed", self.wait(chat["id"])["turns"][-1]["status"])

    def test_hosted_api_uses_service_auth_and_reports_isolated_target(self):
        from validation_pipeline.commander_host_api import create_app_from_env
        credential = self.root / "auth.json"
        credential.write_text("{}")
        with patch.dict(os.environ, {
            "OWNER_GATEWAY_BRIDGE_TOKEN": "service-token",
            "PTW_COMMANDER_REPOSITORY": str(self.repo),
            "PTW_COMMANDER_STATE": str(self.root / "hosted-state"),
            "CODEX_EXECUTABLE": str(self.binary),
            "PTW_CODEX_CREDENTIAL": str(credential),
        }):
            with TestClient(create_app_from_env()) as client:
                base = "/internal/v1/settings/commander"
                self.assertEqual(200, client.get("/healthz").status_code)
                self.assertEqual(401, client.get(base).status_code)
                response = client.get(base, headers={
                    "X-PTW-Owner-Gateway-Token": "service-token",
                })
                self.assertEqual(200, response.status_code)
                self.assertEqual("hosted", response.json()["target"])
                self.assertEqual("no-store", response.headers["cache-control"])
                created = client.post(base + "/chats", headers={
                    "X-PTW-Owner-Gateway-Token": "service-token",
                }, json={})
                self.assertEqual(201, created.status_code)

    def test_hosted_turn_refreshes_credential_into_writable_runtime_home(self):
        source = self.root / "published-auth.json"
        source.write_text('{"tokens":"first"}')
        hosted = CommanderChatService(
            self.repo, self.root / "hosted-copy-state", codex_binary=str(self.binary),
            target="hosted", credential_source=source,
        )
        try:
            chat = hosted.create_chat()
            hosted.send(chat["id"], ChatMessage(request_id=uuid4(), message="check runtime"))
            deadline = time.monotonic() + 5
            while hosted.chat(chat["id"])["turns"][-1]["status"] in ACTIVE and time.monotonic() < deadline:
                time.sleep(.01)
            runtime_home = hosted.state / "codex-home"
            self.assertEqual(source.read_bytes(), (runtime_home / "auth.json").read_bytes())
            invocation = json.loads((self.repo / "invocation.json").read_text())
            self.assertEqual(str(runtime_home), invocation["env"]["CODEX_HOME"])
            self.assertIn("--dangerously-bypass-approvals-and-sandbox", invocation["args"])
            self.assertNotIn("workspace-write", invocation["args"])
            source.write_text('{"tokens":"second"}')
            hosted.send(chat["id"], ChatMessage(request_id=uuid4(), message="refresh runtime"))
            deadline = time.monotonic() + 5
            while hosted.chat(chat["id"])["turns"][-1]["status"] in ACTIVE and time.monotonic() < deadline:
                time.sleep(.01)
            self.assertEqual(source.read_bytes(), (runtime_home / "auth.json").read_bytes())
        finally:
            hosted.close()

    def test_local_app_is_opt_in_and_production_validation_has_no_routes(self):
        from validation_pipeline.studio_local_api import create_app
        with patch.dict(os.environ, {
            "PTW_COMMANDER_CHAT_MODE": "0", "STUDIO_TUNE_MODE": "0",
            "LOCAL_BRIEF_PATH": str(self.root / "briefs"),
            "STUDIO_WORKSPACE_PATH": str(self.root / "studio"),
            "STUDIO_PHONE_IMAGE_PROVIDER": "disabled",
        }):
            disabled = create_app()
            with TestClient(disabled, base_url="http://127.0.0.1") as client:
                self.assertEqual(404, client.get("/api/v1/settings/commander").status_code)
            enabled = create_app(commander_chat_service=self.service)
            with TestClient(enabled, base_url="http://127.0.0.1", client=("127.0.0.1", 50000)) as client:
                base = "/api/v1/settings/commander"
                self.assertEqual(401, client.get(base).status_code)
                self.assertEqual(200, client.get(base, headers={
                    "Authorization": "Bearer e2e-owner-token", "X-Firebase-AppCheck": "e2e-app-check",
                }).status_code)
        source = (Path(__file__).resolve().parents[2] / "validation_pipeline/api.py").read_text()
        self.assertNotIn("commander_chat", source)


if __name__ == "__main__":
    unittest.main()
