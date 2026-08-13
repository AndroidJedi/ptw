from commander.main import engineering_task, normalized_command, public_health


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
