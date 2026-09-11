#!/usr/bin/env python3
"""Real, non-production Plan/question/Build canary in an isolated checkout."""
import argparse
from pathlib import Path
import subprocess
import tempfile
import time
from uuid import uuid4

from validation_pipeline.commander_chat import ChatMessage, QuestionAnswer
from validation_pipeline.commander_workspace import CommanderWorkspaceService


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--codex", default="codex")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="ptw-workspace-canary-") as directory:
        root = Path(directory)
        repo = root / "repository"
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        skill = repo / "skills/commander-god-mode/SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text("This is an isolated diagnostic checkout. Never change files or call external systems. Follow the diagnostic owner conversation.\n")
        service = CommanderWorkspaceService(repo, root / "state", codex_binary=args.codex)
        try:
            capabilities = service.capabilities()
            model = next((m for m in capabilities["models"] if m["default"]), capabilities["models"][0])
            effort = "low" if "low" in model["efforts"] else model["default_effort"]
            chat = service.create_chat()
            service.send(chat["id"], ChatMessage(request_id=uuid4(), mode="plan", model=model["id"], effort=effort,
                message="This is a harmless dialogue test. Do not inspect or change files. Use request_user_input to ask which label I prefer, Blue or Green. After I answer, reply exactly 'Plan label: <my answer>'."))
            deadline = time.monotonic() + 180
            answered = False
            while service._thread and time.monotonic() < deadline:
                current = service.chat(chat["id"])
                for question in current["questions"]:
                    if question["status"] == "pending":
                        service.answer(chat["id"], question["id"], QuestionAnswer(request_id=uuid4(),
                            answers={q["id"]: ["Green"] for q in question["payload"]["questions"]}))
                        answered = True
                time.sleep(.1)
            current = service.chat(chat["id"])
            assert answered, "Runtime did not exercise interactive questions"
            assert current["turns"][0]["status"] == "completed", "Plan did not complete"
            assert "Green" in current["turns"][0]["reply"], "Plan lost clarification"
            service.send(chat["id"], ChatMessage(request_id=uuid4(), mode="build", model=model["id"], effort=effort,
                reply_to_message_id=current["turns"][0]["id"], message="Continue the conversation. Do not inspect or change files. Reply exactly with the label I selected earlier."))
            deadline = time.monotonic() + 180
            while service._thread and time.monotonic() < deadline:
                time.sleep(.1)
            current = service.chat(chat["id"])
            assert current["turns"][-1]["status"] == "completed", "Build dialogue did not complete"
            assert "Green" in current["turns"][-1]["reply"], "Build lost the selected plan or answer"
            print("Real runtime model discovery, Plan question/answer, Build continuation and targeted reply passed")
        finally:
            service.close()


if __name__ == "__main__":
    main()
