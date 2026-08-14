from commander.main import (SUPPORTED_COMMANDS, TRACKED_BRIDGE_COMMANDS,
                            engineering_task, normalized_command, public_health,
                            safe_bridge_error)


def test_command_routing_is_deterministic() -> None:
    assert normalized_command("/PING") == "/ping"
    assert normalized_command("/status@ptw_commander_bot extra") == "/status"
    assert normalized_command("hello") == "hello"


def test_public_health() -> None:
    assert public_health() == {"status": "ok"}


def test_task_text_is_free_form_and_engineer_repo_prefix_is_optional() -> None:
    assert engineering_task("/task Fix login, add tests, and deploy it") == "Fix login, add tests, and deploy it"
    assert engineering_task("/engineer repo=ptw Improve the queue") == "Improve the queue"
    assert engineering_task("/task") == ""


def test_tasks_can_be_cancelled() -> None:
    assert "/cancel" in SUPPORTED_COMMANDS
    assert engineering_task("/cancel 42") == "42"


def test_issue_and_task_inspection_is_routed() -> None:
    assert "/inspect" in SUPPORTED_COMMANDS
    assert engineering_task("/inspect ISSUE-7") == "ISSUE-7"


def test_long_running_creative_commands_require_task_lifecycle() -> None:
    assert TRACKED_BRIDGE_COMMANDS == frozenset({"/creative", "/research"})
    assert "/feedback" not in TRACKED_BRIDGE_COMMANDS


def test_bridge_errors_are_secret_scrubbed() -> None:
    assert safe_bridge_error(RuntimeError("token=hidden")) == "RuntimeError: token=[REDACTED]"
