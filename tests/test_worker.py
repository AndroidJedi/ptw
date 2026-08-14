from pathlib import Path

from worker.main import codex_available, command_available, execute_job


def test_installed_command_detection() -> None:
    assert command_available("python") is True
    assert command_available("ptw-command-that-does-not-exist") is False


def test_codex_host_metadata_detection(monkeypatch, tmp_path: Path) -> None:
    metadata = tmp_path / "codex-version"
    metadata.write_text("codex-cli 0.147.0\n", encoding="utf-8")
    monkeypatch.setenv("CODEX_METADATA_FILE", str(metadata))
    monkeypatch.setattr("worker.main.command_available", lambda command: False)
    assert codex_available() is True


def test_help_lists_research_graph_and_graph_based_creative_commands() -> None:
    help_text = execute_job(None, "help")
    assert "/research <creative|product|design|engineering> <topic>" in help_text
    assert "/task from <hypothesis-id> <request>" in help_text
    assert "/graph hypotheses" in help_text
    assert "/creative from <hypothesis-id>" in help_text
    assert "/cancel [job-id]" in help_text
    assert "/inspect TASK-<id>|ISSUE-<id>" in help_text
