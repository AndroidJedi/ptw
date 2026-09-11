from pathlib import Path
import json
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from validation_pipeline.commander_chat import ChatMessage, commander_chat_router
from validation_pipeline.commander_workspace import CommanderWorkspaceService, Preferences, QuestionAnswer, authorizes_deployment


CAPABILITIES = {"models": [
    {"id": "available", "name": "Available", "default": True, "default_effort": "medium", "efforts": ["low", "medium", "high"]},
    {"id": "fast", "name": "Fast", "default": False, "default_effort": "low", "efforts": ["low"]},
], "modes": ["build", "plan"]}


class FakeRPC:
    instances = []

    def __init__(self, binary, repository, environment, callback):
        self.callback, self.calls, self.responses = callback, [], []
        self.instances.append(self)

    def request(self, method, params, timeout=25):
        self.calls.append((method, params))
        if method == "thread/start":
            return {"thread": {"id": "native-thread"}}
        if method == "turn/start":
            return {"turn": {"id": "native-turn"}}
        return {}

    def respond(self, identifier, result):
        self.responses.append((identifier, result))

    def close(self):
        pass

    def emit(self, method, params, identifier=None):
        self.callback({"method": method, "params": params, **({"id": identifier} if identifier is not None else {})})

    def finish(self, text="Completed response"):
        self.emit("item/agentMessage/delta", {"delta": text})
        self.emit("turn/completed", {"turn": {"status": "completed"}})


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        (self.repo / ".git").mkdir(parents=True)
        skill = self.repo / "skills/commander-god-mode/SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text("Test skill")
        self.rpc_patch = patch("validation_pipeline.commander_workspace.CodexRPC", FakeRPC)
        self.rpc_patch.start()
        self.service = CommanderWorkspaceService(self.repo, self.root / "state", codex_binary="/bin/true", release_url="http://release")
        self.service._handoff_stop.set()
        self.service.capabilities = lambda: CAPABILITIES
        self.chat_id = self.service.create_chat()["id"]

    def tearDown(self):
        self.service.close()
        self.rpc_patch.stop()
        self.temp.cleanup()

    def until(self, predicate):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(.005)
        self.fail("Timed out")

    def send(self, message="Build feature", **kwargs):
        body = ChatMessage(message=message, request_id=kwargs.pop("request_id", uuid4()), **kwargs)
        result = self.service.send(self.chat_id, body)
        self.until(lambda: self.service.native_turn)
        return result, body

    def finish(self, text="Completed response"):
        self.service.rpc.finish(text)
        self.until(lambda: self.service._thread is None)

    def test_native_mode_settings_and_ephemeral_history(self):
        self.send(mode="plan", model="available", effort="high")
        rpc = self.service.rpc
        thread, turn = rpc.calls[:2]
        self.assertTrue(thread[1]["ephemeral"])
        self.assertEqual("read-only", thread[1]["sandbox"])
        self.assertEqual(["conversation_history"], [t["name"] for t in thread[1]["dynamicTools"]])
        self.assertEqual({"mode": "plan", "settings": {"model": "available", "reasoning_effort": "high", "developer_instructions": None}}, turn[1]["collaborationMode"])
        self.finish("The plan")
        self.send("Implement this plan", mode="build", reply_to_message_id=self.service.chat(self.chat_id)["turns"][0]["id"])
        self.assertIn("The plan", self.service.rpc.calls[1][1]["input"][0]["text"])
        self.finish()

    def test_live_steering_uuid_reconciliation_and_effective_settings(self):
        first, _ = self.send()
        second, body = self.send("Also improve layout", mode="plan", model="fast", effort="low")
        self.service.send(self.chat_id, body)
        self.until(lambda: any(c[0] == "turn/steer" for c in self.service.rpc.calls))
        self.assertEqual(2, len(second["turns"]))
        self.assertEqual("steered", second["turns"][1]["status"])
        self.assertEqual("build", second["turns"][1]["mode"])
        self.assertEqual("plan", second["preferences"]["mode"])
        self.assertEqual(1, sum(c[0] == "turn/steer" for c in self.service.rpc.calls))
        self.finish()

    def test_questions_persist_answers_and_idempotency_in_context(self):
        self.send()
        rpc = self.service.rpc
        rpc.emit("item/tool/requestUserInput", {"questions": [{"id": "colour", "question": "Which colour?", "isSecret": False, "isOther": True, "options": []}]}, "q-native")
        question = self.service.chat(self.chat_id)["questions"][0]
        body = QuestionAnswer(request_id=uuid4(), answers={"colour": ["blue"]})
        self.service.answer(self.chat_id, question["id"], body)
        self.service.answer(self.chat_id, question["id"], body)
        self.assertEqual(1, len(rpc.responses))
        self.finish()
        self.send("Continue")
        self.assertIn("blue", self.service.rpc.calls[1][1]["input"][0]["text"])
        self.finish()

    def test_deployment_requires_explicit_build_owner_and_successful_handoff(self):
        self.send("Implement and deploy")
        self.service.rpc.emit("item/tool/call", {"tool": "request_deployment", "arguments": {}}, "tool")
        self.finish()
        chat = self.service.chat(self.chat_id)
        self.assertEqual("pending", chat["releases"][0]["status"])
        self.assertEqual(chat["turns"][0]["id"], chat["releases"][0]["owner_message_id"])
        with self.assertRaisesRegex(ValueError, "handed to deployment"):
            self.service.send(self.chat_id, ChatMessage(request_id=uuid4(), message="Edit again"))

    def test_plan_deployment_tool_cannot_authorize(self):
        self.send("Deploy it", mode="plan")
        rpc = self.service.rpc
        rpc.emit("item/tool/call", {"tool": "request_deployment", "arguments": {}}, "tool")
        self.assertFalse(rpc.responses[-1][1]["success"])
        self.finish()
        self.assertEqual([], self.service.chat(self.chat_id)["releases"])

    def test_one_click_uses_same_durable_handoff_and_owner_message(self):
        request = str(uuid4())
        first = self.service.deploy_chat(self.chat_id, request)
        duplicate = self.service.deploy_chat(self.chat_id, request)
        self.assertEqual(1, len(duplicate["turns"]))
        self.assertEqual(request, first["releases"][0]["request_id"])
        self.assertEqual(first["turns"][0]["id"], first["releases"][0]["owner_message_id"])

    def test_cancellation_retains_edits_without_release(self):
        first, _ = self.send("Implement and deploy")
        self.service.rpc.emit("item/tool/call", {"tool": "request_deployment", "arguments": {}}, "tool")
        self.service.stop(self.chat_id, first["turns"][0]["id"])
        self.until(lambda: self.service._thread is None)
        self.assertEqual("cancelled", self.service.chat(self.chat_id)["turns"][0]["status"])
        self.assertFalse(self.service.chat(self.chat_id)["releases"])

    def test_invalid_selections_and_scoped_reply(self):
        for preference in [Preferences(model="missing"), Preferences(model="fast", effort="high"), Preferences(mode="invalid")]:
            with self.assertRaises(ValueError):
                self.service.preferences(self.chat_id, preference)
        with self.assertRaisesRegex(ValueError, "Reply target"):
            self.send(reply_to_message_id=uuid4())

    def test_no_thirty_turn_limit_and_cursor_events(self):
        for i in range(35):
            self.send(f"Discuss item {i}")
            self.finish()
        latest = self.service.chat(self.chat_id, limit=10)
        earlier = self.service.chat(self.chat_id, before=latest["before"], limit=10)
        self.assertTrue(latest["has_more"])
        self.assertFalse(set(t["id"] for t in latest["turns"]) & set(t["id"] for t in earlier["turns"]))
        event = self.service.events(self.chat_id)
        self.assertTrue(event["events"])
        self.assertEqual([], self.service.events(self.chat_id, event["cursor"])["events"])

    def test_actual_preferences_and_answer_request_validation(self):
        app = FastAPI()
        app.include_router(commander_chat_router(self.service, dependencies=[], local_only=False))
        with TestClient(app) as client:
            prefix = f"/api/v1/settings/commander/chats/{self.chat_id}"
            result = client.post(prefix + "/preferences", json={"mode": "plan", "model": "available", "effort": "high"})
            self.assertEqual(200, result.status_code, result.text)
            result = client.post(prefix + f"/questions/{uuid4()}/answers", json={"request_id": str(uuid4()), "answers": {"q": ["A"]}})
            self.assertEqual(404, result.status_code, result.text)

    def test_deploy_intent_classification(self):
        for message in ["Deploy", "Implement and deploy", "Розгорни зміни", "Implement and deploy, don't reset data"]:
            self.assertTrue(authorizes_deployment(message), message)
        for message in ['Explain "deploy"', "Why didn't you deploy?", "Do not deploy", "> deploy\nDiscuss this", "`deploy`", "How do I deploy?"]:
            self.assertFalse(authorizes_deployment(message), message)
