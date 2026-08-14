import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from common.repositories import Repository
from engineering.github import (create_or_get_pr, merge_pull_request,
                                pull_request_body, push_agent_branch)
from engineering.runner import StageFailure, ValidationResult

REPO = Repository("ptw", "PTW", "git@github.com:AndroidJedi/ptw.git", "main", True, "flutter", {})


def test_direct_main_push_rejected(tmp_path: Path) -> None:
    with pytest.raises(StageFailure): push_agent_branch(tmp_path, "main")


def test_only_current_agent_branch_pushes(tmp_path: Path) -> None:
    with patch("engineering.github.run") as run:
        run.side_effect = [MagicMock(stdout="agent/job-1-fix\n"), MagicMock(returncode=0, stdout="")]
        push_agent_branch(tmp_path, "agent/job-1-fix")
    assert "refs/heads/agent/job-1-fix" in run.call_args_list[1].args[0][-1]


def test_duplicate_pr_is_reused() -> None:
    with patch("engineering.github.subprocess.run") as run:
        run.return_value.stdout = json.dumps([{"number":42,"url":"https://github.com/AndroidJedi/ptw/pull/42"}])
        assert create_or_get_pr(REPO, "agent/job-1-fix", "title", "body") == (42, "https://github.com/AndroidJedi/ptw/pull/42", False)
        assert run.call_count == 1


def test_pr_creation_and_deterministic_body() -> None:
    body = pull_request_body(1, "Fix", ["Works"], ["lib/a.dart"], [ValidationResult("flutter test", True, 1)])
    assert "PTW engineering job: #1" in body and "✅ `flutter test`" in body
    with patch("engineering.github.subprocess.run") as run:
        run.side_effect = [MagicMock(stdout="[]"), MagicMock(stdout="https://github.com/AndroidJedi/ptw/pull/43\n")]
        assert create_or_get_pr(REPO, "agent/job-1-fix", "title", body)[0] == 43


def test_merge_records_rollback_and_resulting_main_sha() -> None:
    with patch("engineering.github.subprocess.run") as run:
        run.side_effect = [
            MagicMock(stdout="a" * 40 + "\n"),
            MagicMock(stdout=""),
            MagicMock(stdout="b" * 40 + "\n"),
        ]
        assert merge_pull_request(REPO, 43) == ("a" * 40, "b" * 40)
    assert run.call_args_list[1].args[0][0:3] == ["gh", "pr", "merge"]
