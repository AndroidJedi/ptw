import pytest
from pathlib import Path

from commander.main import (BRANDING_IMAGE_MODEL, IDEA_COMMANDS, MAX_STRUCTURED_LLM_REQUEST_BYTES, STRUCTURED_LLM_MODES, SUPPORTED_COMMANDS, TRACKED_BRIDGE_COMMANDS,
                            bridge_target, engineering_task, normalized_command,
                            get_structured_llm_capabilities, public_health, safe_bridge_error, structured_llm_capabilities, task_research_reference,
                            validate_structured_llm_request)

SOURCE_ROOT = Path(__file__).resolve().parents[1]


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
    laval_modes = {
        "laval_owner_dna",
        "laval_query_plan",
        "laval_competitor_dossier",
        "laval_opportunity_matrix",
        "laval_market_signal_relevance",
        "laval_idea_expansion",
        "laval_idea_evaluation",
        "laval_youtube_observation",
        "laval_mechanism_extraction",
        "laval_thesis_synthesis",
        "laval_thesis_falsification",
    }
    assert {mode for mode in STRUCTURED_LLM_MODES if mode.startswith("laval_")} == laval_modes
    branding_modes = {
        "branding_reference_plan",
        "branding_design_principles",
        "branding_brand_brief",
        "branding_direction_synthesis",
        "branding_logo_generation",
    }
    assert {mode for mode in STRUCTURED_LLM_MODES if mode.startswith("branding_")} == branding_modes
    assert structured_llm_capabilities() == {
        "laval_modes": sorted(laval_modes),
        "branding_modes": sorted(branding_modes),
        "branding_image": {
            "ready": True,
            "model": BRANDING_IMAGE_MODEL,
            "provider": "codex_chatgpt_imagegen",
            "max_images_per_request": 1,
            "asset_transport": "commander_asset_volume",
        },
        "max_request_bytes": MAX_STRUCTURED_LLM_REQUEST_BYTES,
    }
    for mode in laval_modes | branding_modes:
        validate_structured_llm_request({
            "mode": mode,
            "system_prompt": (
                "$imagegen Return structured evidence."
                if mode == "branding_logo_generation"
                else "Return structured evidence."
            ),
            "input_payload": {"evidence_ids": ["e-1"]},
            "output_schema": {"type": "object"},
            "prompt_template_version": "contract-v1",
            "context_hash": "sha256:abc",
        })


def test_structured_bridge_rejects_unknown_and_oversized_requests() -> None:
    request = {
        "mode": "laval_not_registered",
        "system_prompt": "Return structured output.",
        "input_payload": {},
        "output_schema": {"type": "object"},
    }
    with pytest.raises(ValueError, match="unsupported structured LLM mode"):
        validate_structured_llm_request(request)
    request["mode"] = "laval_owner_dna"
    request["input_payload"] = {"content": "x" * MAX_STRUCTURED_LLM_REQUEST_BYTES}
    with pytest.raises(ValueError, match="too large"):
        validate_structured_llm_request(request)


def test_branding_logo_contract_requires_explicit_builtin_image_generation() -> None:
    request = {
        "mode": "branding_logo_generation",
        "system_prompt": "Create one logo.",
        "input_payload": {},
        "output_schema": {"type": "object"},
    }
    with pytest.raises(ValueError, match=r"\$imagegen"):
        validate_structured_llm_request(request)
    request["system_prompt"] = "$imagegen Create exactly one original symbol."
    validate_structured_llm_request(request)


def test_structured_capabilities_require_the_bridge_token(monkeypatch) -> None:
    monkeypatch.setattr("commander.main.secrets.get", lambda name: "bridge-token")
    with pytest.raises(Exception) as rejected:
        get_structured_llm_capabilities("wrong-token")
    assert rejected.value.status_code == 403
    assert get_structured_llm_capabilities("bridge-token") == structured_llm_capabilities()


def test_platform_api_release_is_explicitly_tagged_and_never_built_on_production() -> None:
    compose = (SOURCE_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    api = compose.split("  commander-api:", 1)[1].split("  commander-worker:", 1)[0]
    assert "image: ptw-agent-platform-commander-api:${PTW_PLATFORM_IMAGE_TAG:-latest}" in api
    assert "pull_policy: never" in api
    worker = compose.split("  commander-worker:", 1)[1].split("  git-watcher:", 1)[0]
    assert "image: ptw-agent-platform-commander-worker:${PTW_PLATFORM_IMAGE_TAG:-latest}" in worker
    assert "pull_policy: never" in worker
    assert "commander-assets:/var/lib/ptw/assets" in worker


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
