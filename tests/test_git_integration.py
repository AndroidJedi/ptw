import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from common.repositories import Repository, RepositoryRegistry
from watcher.main import Commit, deliver_one, format_notification, observe

REPOSITORY = Repository("ptw", "Proof Them Wrong", "git@github.com:AndroidJedi/ptw.git",
                        "main", True, "flutter", {"dart_sdk": "^3.7.0", "fvm": False})
OLD = "1" * 40
NEW = "2" * 40
SOURCE_ROOT = Path(os.getenv("PTW_SOURCE_ROOT", "."))


class Result:
    def __init__(self, row=None): self.row = row
    def fetchone(self): return self.row


def test_repository_registry_entry_and_allowlist() -> None:
    connection = MagicMock()
    connection.execute.return_value = Result((REPOSITORY.id, REPOSITORY.name, REPOSITORY.clone_url,
                                               REPOSITORY.default_branch, True, "flutter", REPOSITORY.metadata))
    assert RepositoryRegistry(connection).get("ptw") == REPOSITORY
    assert "WHERE id = %s AND enabled" in connection.execute.call_args.args[0]
    connection.execute.return_value = Result()
    with pytest.raises(KeyError): RepositoryRegistry(connection).get("arbitrary-url")


def test_registry_seed_is_ptw() -> None:
    migration = (SOURCE_ROOT / "migrations/003_git_integration.sql").read_text()
    assert "('ptw', 'Proof Them Wrong', 'git@github.com:AndroidJedi/ptw.git', 'main', true" in migration


def test_credential_boundary_exposes_agent_not_private_key() -> None:
    compose = (SOURCE_ROOT / "docker-compose.yml").read_text()
    watcher = compose.split("  git-watcher:", 1)[1].split("  caddy:", 1)[0]
    assert "/root/.ssh" not in watcher
    assert "git-agent-socket:/run/ptw-git-agent" in watcher
    config = (SOURCE_ROOT / "infrastructure/git-client/ssh_config").read_text()
    assert "Host github.com" in config and "Host *\n    IdentityAgent none" in config
    entrypoint = (SOURCE_ROOT / "infrastructure/git-agent/entrypoint.sh").read_text()
    assert "ssh-add -h github.com" in entrypoint


@patch("watcher.main.remote_sha", return_value=NEW)
def test_initial_branch_sha_has_no_notification(_remote) -> None:
    connection = MagicMock()
    connection.execute.side_effect = [Result((*REPOSITORY.__dict__.values(),)), Result(), Result()]
    assert observe(connection) == "initialized"
    assert not any("git_notifications" in call.args[0] for call in connection.execute.call_args_list)


@patch("watcher.main.remote_sha", return_value=OLD)
def test_unchanged_and_restart_do_not_notify(_remote) -> None:
    for _ in range(2):
        connection = MagicMock()
        connection.execute.side_effect = [Result((*REPOSITORY.__dict__.values(),)), Result((OLD,))]
        assert observe(connection) == "unchanged"
        assert len(connection.execute.call_args_list) == 2


@patch("watcher.main.commit_metadata", return_value=([Commit(NEW, "Fix layout", "Serhii", "2026-08-12T07:42:00Z")], 4))
@patch("watcher.main.remote_sha", return_value=NEW)
def test_changed_sha_produces_one_authorized_notification(_remote, _metadata, monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "123")
    connection = MagicMock()
    connection.execute.side_effect = [Result((*REPOSITORY.__dict__.values(),)), Result((OLD,)), Result(), Result(), Result()]
    assert observe(connection) == "updated"
    inserts = [call for call in connection.execute.call_args_list if "INSERT INTO git_notifications" in call.args[0]]
    assert len(inserts) == 1 and inserts[0].args[1][4] == 123


def test_multiple_commit_summary_is_bounded() -> None:
    commits = [Commit(str(index) * 40, f"Subject {index}", "Author", "time") for index in range(1, 9)]
    message = format_notification(REPOSITORY, "main", OLD, NEW, commits, 10, maximum=5)
    assert message.count("• ") == 5
    assert "+ 3 more commits" in message


def test_single_commit_summary_format() -> None:
    message = format_notification(REPOSITORY, "main", OLD, NEW,
                                  [Commit(NEW, "Fix layout", "Serhii", "time")], 4)
    assert "2222222 — Fix layout" in message
    assert "Author: Serhii" in message and "Files changed: 4" in message


@patch("watcher.main.send_telegram", side_effect=RuntimeError("no delivery"))
def test_telegram_failure_is_persisted_with_bounded_retry(sender) -> None:
    connection = MagicMock()
    connection.execute.side_effect = [Result((7, 123, "message", "ptw", "main", NEW, 0)), Result(), Result()]
    assert deliver_one(connection) is True
    sender.assert_called_once_with(123, "message")
    update = connection.execute.call_args_list[1]
    assert update.args[1][0] == "pending" and update.args[1][1] == 1


def test_watcher_contains_no_model_or_codex_call() -> None:
    source = (SOURCE_ROOT / "watcher/main.py").read_text().lower()
    assert "openai" not in source and "codex" not in source and "llm" not in source
