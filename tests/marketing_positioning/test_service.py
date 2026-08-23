from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from marketing_positioning.service import PositioningRunner


class FakeRepository:
    def __init__(self) -> None:
        self.finished = False
        self.failed = False
        self.released = False

    def get_revision(self, _revision_id: str):
        return {"id": "revision", "project_id": "project", "status": "queued"}

    def start_attempt(self, _revision_id: str):
        return "attempt", 1

    def get_project(self, _project_id: str):
        return {"id": "project"}

    def sources(self, _revision_id: str):
        return [
            {"id": "owner", "source_type": "owner_idea"},
            {"id": "legacy", "source_type": "research_finding"},
        ]

    def finish_attempt(self, *_args):
        self.finished = True

    def fail_attempt(self, *_args):
        self.failed = True

    def release_operation(self, _revision_id: str):
        self.released = True


class FakeNotifier:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def notify(self, revision_id: str, attempt_id: str):
        self.calls.append((revision_id, attempt_id))
        return {"status": "sent"}


class PositioningRunnerTests(unittest.TestCase):
    def test_initial_generation_uses_only_owner_input_and_notifies_after_terminal_state(self) -> None:
        repository = FakeRepository()
        notifier = FakeNotifier()
        with TemporaryDirectory() as directory:
            skill = Path(directory) / "SKILL.md"
            skill.write_text("positioning contract", encoding="utf-8")
            runner = PositioningRunner(repository, SimpleNamespace(), skill_path=skill, notifier=notifier)
            captured: list[dict[str, object]] = []
            runner._synthesize = lambda _project, _revision, _attempt, _number, sources: (  # type: ignore[method-assign]
                captured.extend(sources)
                or SimpleNamespace(
                    to_dict=lambda: {"schema_version": 1}, digest="digest",
                    quality_gates={"passed": True},
                )
            )
            result = runner.generate("revision", operation_reserved=True)
        self.assertEqual("queued", result["status"])
        self.assertEqual(["owner"], [item["id"] for item in captured])
        self.assertTrue(repository.finished)
        self.assertFalse(repository.failed)
        self.assertTrue(repository.released)
        self.assertEqual([("revision", "attempt")], notifier.calls)


if __name__ == "__main__":
    unittest.main()
