import pytest

from engineering.issues import _safe_text, parse_reference


@pytest.mark.parametrize(
    ("value", "expected"),
    (("42", ("task", 42)), ("TASK-42", ("task", 42)), ("issue-7", ("issue", 7))),
)
def test_stable_task_and_issue_references(value, expected) -> None:
    assert parse_reference(value) == expected


def test_invalid_reference_fails_closed() -> None:
    with pytest.raises(ValueError):
        parse_reference("job-latest")


def test_issue_diagnostics_are_bounded_and_secret_scrubbed() -> None:
    value = _safe_text("before token=super-secret password: hunter2 after", limit=100)
    assert "super-secret" not in value
    assert "hunter2" not in value
    assert value == "before token=[REDACTED] password: [REDACTED] after"
