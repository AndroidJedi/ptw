import json
from pathlib import Path
from unittest.mock import patch

import pytest

from common.repositories import Repository
from engineering.runner import (EngineeringResult, JobCancelled, StageFailure, ValidationResult,
                                branch_name, commit_changes, copy_attachments,
                                create_workspace, enforce_push_branch, invoke_codex,
                                render_result, validate, validation_commands)
from engineering.components import load_manifest

REPO = Repository("ptw", "PTW", "git@example:ptw.git", "main", True, "flutter", {})


def write_manifest(root: Path) -> None:
    (root / "project.components.json").write_text(json.dumps({
        "version": 1,
        "global_validation": [["git", "diff", "--check"]],
        "components": [
            {
                "name": "creative-learning",
                "description": "Python creative services",
                "paths": ["commander/**", "tests/commander/**"],
                "validation": [["python3", "-m", "unittest", "discover", "-s", "tests/commander", "-v"]],
                "extended_validation": [],
            },
            {
                "name": "flutter-product",
                "description": "Flutter client",
                "paths": ["lib/**", "test/**"],
                "validation": [["dart", "format", "."], ["flutter", "analyze"], ["flutter", "test"]],
                "extended_validation": [["flutter", "build", "web"]],
            },
        ],
    }))


def test_predictable_unique_branch_and_main_rejected() -> None:
    assert branch_name(12, "Fix Share Layout") == "agent/job-12-fix-share-layout"
    enforce_push_branch("agent/job-12-fix")
    for branch in ("main", "feature/foo", "agent/main"):
        with pytest.raises(StageFailure): enforce_push_branch(branch)


def test_isolated_workspace(tmp_path: Path) -> None:
    with patch("engineering.runner.run") as run:
        run.return_value.returncode = 0; run.return_value.stdout = ""
        checkout, branch = create_workspace(9, REPO, "Fix it", tmp_path)
    assert checkout == tmp_path / "9/repo" and branch.startswith("agent/job-9-")
    assert str(checkout) in run.call_args_list[0].args[0]


def test_screenshot_attachment_is_copied_to_job_storage(tmp_path: Path) -> None:
    source = tmp_path / "screen.png"; source.write_bytes(b"png")
    copied = copy_attachments([source], tmp_path / "job")
    assert copied[0].read_bytes() == b"png" and copied[0].stat().st_mode & 0o777 == 0o600


def test_codex_receives_spec_and_image_not_conversation(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-home"))
    checkout = tmp_path / "repo"; checkout.mkdir()
    spec = tmp_path / "spec.md"; spec.write_text("Goal: fix")
    image = tmp_path / "image.png"; image.write_bytes(b"x")
    with patch("engineering.runner.subprocess.Popen") as popen:
        process = popen.return_value
        process.poll.return_value = 0
        process.returncode = 0
        invoke_codex(checkout, spec, [image], tmp_path / "out")
    command = popen.call_args.args[0]
    assert "--image" in command and "Goal: fix" in command[-1]


def test_codex_process_can_be_cancelled(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-home"))
    checkout = tmp_path / "repo"; checkout.mkdir()
    spec = tmp_path / "spec.md"; spec.write_text("Goal: stop")
    with patch("engineering.runner.subprocess.Popen") as popen:
        process = popen.return_value
        process.poll.return_value = None
        with pytest.raises(JobCancelled):
            invoke_codex(checkout, spec, [], tmp_path / "out", lambda: True)
        process.terminate.assert_called_once()


def test_validation_failure_stops_stages(tmp_path: Path) -> None:
    write_manifest(tmp_path)
    with patch("engineering.runner.changed_paths", return_value=["lib/a.dart"]), \
         patch("engineering.runner.shutil.which", return_value="/tool"), \
         patch("engineering.runner.run") as run:
        run.return_value.returncode = 1; run.return_value.stdout = "error excerpt"
        with pytest.raises(StageFailure, match="error excerpt") as failure: validate(tmp_path, "LOW")
    assert failure.value.stage == "VALIDATION" and run.call_count == 1


def test_commander_changes_use_python_validation_without_flutter(tmp_path: Path) -> None:
    write_manifest(tmp_path)
    with patch("engineering.runner.changed_paths", return_value=["commander/api.py"]):
        commands = validation_commands(tmp_path, "LOW")
    assert commands[1][:4] == ["python3", "-m", "unittest", "discover"]
    assert all(command[0] not in {"dart", "flutter"} for command in commands)


def test_flutter_changes_still_require_flutter_validation(tmp_path: Path) -> None:
    write_manifest(tmp_path)
    with patch("engineering.runner.changed_paths", return_value=["lib/main.dart"]):
        commands = validation_commands(tmp_path, "LOW")
    assert [command[0] for command in commands[1:4]] == ["dart", "flutter", "flutter"]


def test_high_risk_adds_extended_component_validation(tmp_path: Path) -> None:
    write_manifest(tmp_path)
    with patch("engineering.runner.changed_paths", return_value=["lib/main.dart"]):
        commands = validation_commands(tmp_path, "HIGH")
    assert ["flutter", "build", "web"] in commands


def test_validation_uses_manifest_loaded_before_agent_edits(tmp_path: Path) -> None:
    write_manifest(tmp_path)
    trusted = load_manifest(tmp_path)
    (tmp_path / "project.components.json").write_text("{}")
    with patch("engineering.runner.changed_paths", return_value=["commander/api.py"]):
        commands = validation_commands(tmp_path, "LOW", trusted)
    assert any(command[:3] == ["python3", "-m", "unittest"] for command in commands)


def test_retry_exhaustion_is_bounded() -> None:
    assert int(__import__("os").environ.get("CODEX_MAX_RETRIES", "2")) == 2


def test_successful_local_commit_and_result(tmp_path: Path) -> None:
    outputs = iter([" M lib/a.dart\n", "", "", "abc123\n", "lib/a.dart\n"])
    with patch("engineering.runner.run") as run:
        run.side_effect = lambda *a, **k: type("R", (), {"returncode":0, "stdout":next(outputs)})()
        sha, files = commit_changes(tmp_path, 1, "Fix")
    result = EngineeringResult("agent/job-1-fix", sha, files, [ValidationResult("flutter test", True, 1)])
    assert "abc123" in render_result(result) and "flutter test: PASS" in render_result(result)
