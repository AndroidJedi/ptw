import pytest

from commander.main import (IDEA_COMMANDS, STRUCTURED_LLM_MODES, SUPPORTED_COMMANDS, TRACKED_BRIDGE_COMMANDS,
                            bridge_target, engineering_task, normalized_command,
                            public_health, safe_bridge_error, task_research_reference,
                            validate_structured_llm_request)


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


def test_idea_draft_commands_are_forwarded_to_the_idea_service() -> None:
    assert {"/idea_add", "/idea_done", "/idea_abort", "/idea_queue"} <= IDEA_COMMANDS


def test_ad_commands_route_to_their_owning_service() -> None:
    assert bridge_target("/ads", "/ads from 42") == "idea"
    assert bridge_target("/ads", "/ads status") == "commander"
    assert bridge_target("/estimate", "/estimate 1.8 4 Strong proof") == "commander"
    assert bridge_target("/ad_context", "/ad_context A01") == "commander"
    assert bridge_target("/idea", "/idea 42") == "idea"


def test_bridge_errors_are_secret_scrubbed() -> None:
    assert safe_bridge_error(RuntimeError("token=hidden")) == "RuntimeError: token=[REDACTED]"


def test_task_can_consume_an_explicit_research_hypothesis() -> None:
    assert task_research_reference("from abc-123 implement onboarding") == (
        "abc-123", "implement onboarding"
    )
    assert task_research_reference("implement onboarding") == (None, "implement onboarding")


def test_structured_bridge_accepts_laval_modes_and_full_contract() -> None:
    assert {
        "laval_owner_dna",
        "laval_query_plan",
        "laval_competitor_dossier",
        "laval_opportunity_matrix",
        "laval_market_signal_relevance",
        "laval_idea_expansion",
        "laval_idea_evaluation",
    } <= STRUCTURED_LLM_MODES
    validate_structured_llm_request({
        "mode": "laval_market_signal_relevance",
        "system_prompt": "Classify evidence.",
        "input_payload": {"evidence_ids": ["e-1"]},
        "output_schema": {"type": "object"},
        "prompt_template_version": "market-signal-v1",
        "context_hash": "sha256:abc",
    })


@pytest.mark.parametrize("missing", ["system_prompt", "input_payload", "output_schema"])
def test_structured_bridge_rejects_incomplete_contract(missing: str) -> None:
    request = {
        "mode": "laval_owner_dna",
        "system_prompt": "Return DNA.",
        "input_payload": {},
        "output_schema": {"type": "object"},
    }
    request.pop(missing)
    with pytest.raises(ValueError, match="invalid structured LLM request"):
        validate_structured_llm_request(request)
