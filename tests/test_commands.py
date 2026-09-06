import base64
import hashlib
import pytest
from pathlib import Path

from commander.main import (
    EMERGENCY_COMMANDS, JSON_MODES, MEDIA_MODES, MAX_STRUCTURED_LLM_REQUEST_BYTES,
    get_structured_llm_capabilities, normalized_command, public_health,
    structured_llm_capabilities, validate_structured_llm_request,
)

SOURCE_ROOT = Path(__file__).resolve().parents[1]


def test_command_routing_is_deterministic() -> None:
    assert normalized_command("/PING") == "/ping"
    assert normalized_command("/status@ptw_commander_bot extra") == "/status"
    assert normalized_command("hello") == "hello"


def test_public_health() -> None:
    assert public_health() == {"status": "ok"}


def test_telegram_surface_is_emergency_only() -> None:
    assert EMERGENCY_COMMANDS == frozenset({"/help", "/status", "/stop"})
    source = (SOURCE_ROOT / "commander/main.py").read_text(encoding="utf-8")
    for retired in ("/task", "/engineer", "/creative", "/research", "/inspect", "/cancel"):
        assert retired not in source


def test_structured_bridge_accepts_exact_result_modes_and_full_contract() -> None:
    json_modes = {
        "product_brief", "product_brief_revision", "studio_creative_generation",
        "studio_edit_learning",
    }
    assert JSON_MODES == json_modes
    assert MEDIA_MODES == {"content_non_human_graphic_generation"}
    assert structured_llm_capabilities() == {
        "json_modes": sorted(json_modes),
        "media_modes": ["content_non_human_graphic_generation"],
        "max_request_bytes": MAX_STRUCTURED_LLM_REQUEST_BYTES,
    }
    for mode in json_modes | MEDIA_MODES:
        validate_structured_llm_request({
            "mode": mode,
            "system_prompt": "Return structured evidence.",
            "input_payload": {"evidence_ids": ["e-1"]},
            "output_schema": {"type": "object"},
            "prompt_template_version": "contract-v1",
            "context_hash": "sha256:abc",
            "idempotency_key": f"test:{mode}:attempt:1",
        })
    content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8 + (1024).to_bytes(4, "big") * 2
    validate_structured_llm_request({
        "mode": "content_non_human_graphic_generation",
        "system_prompt": "Enhance the exact reference.",
        "input_payload": {},
        "output_schema": {"type": "object"},
        "idempotency_key": "test:enhance:attempt:1",
        "input_images": [{
            "mime_type": "image/png",
            "digest": hashlib.sha256(content).hexdigest(),
            "width": 1024,
            "height": 1024,
            "bytes_base64": base64.b64encode(content).decode(),
        }],
    })


@pytest.mark.parametrize("mode", [
    "marketing_positioning_document", "natal_landing_revision", "branding_logo_generation",
    "content_candidate_generation", "content_result_critic",
])
def test_structured_bridge_rejects_retired_ptw_modes(mode: str) -> None:
    with pytest.raises(ValueError, match="unsupported structured LLM mode"):
        validate_structured_llm_request({
            "mode": mode,
            "system_prompt": "Return structured evidence.",
            "input_payload": {},
            "output_schema": {"type": "object"},
            "idempotency_key": "test:retired:attempt:1",
        })


def test_structured_bridge_rejects_unknown_and_oversized_requests() -> None:
    request = {
        "mode": "content_not_registered",
        "system_prompt": "Return structured output.",
        "input_payload": {},
        "output_schema": {"type": "object"},
        "idempotency_key": "test:unknown:attempt:1",
    }
    with pytest.raises(ValueError, match="unsupported structured LLM mode"):
        validate_structured_llm_request(request)
    request["mode"] = "product_brief"
    request["input_payload"] = {"content": "x" * MAX_STRUCTURED_LLM_REQUEST_BYTES}
    with pytest.raises(ValueError, match="too large"):
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
    assert "commander-assets:/var/lib/ptw/assets:ro" in api
    worker = compose.split("  commander-worker:", 1)[1].split("  caddy:", 1)[0]
    assert "image: ptw-agent-platform-commander-worker:${PTW_PLATFORM_IMAGE_TAG:-latest}" in worker
    assert "pull_policy: never" in worker
    assert "commander-assets:/var/lib/ptw/assets" in worker


def test_tmpfs_mount_options_remain_one_quoted_compose_item() -> None:
    compose = (SOURCE_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert '      - "/tmp:size=16m,mode=1777"' in compose
    assert '      - "/tmp:size=64m,mode=1777"' in compose
    assert "tmpfs: [" not in compose


@pytest.mark.parametrize("missing", ["system_prompt", "input_payload", "output_schema", "idempotency_key"])
def test_structured_bridge_rejects_incomplete_contract(missing: str) -> None:
    request = {
        "mode": "product_brief",
        "system_prompt": "Return DNA.",
        "input_payload": {},
        "output_schema": {"type": "object"},
        "idempotency_key": "test:incomplete:attempt:1",
    }
    request.pop(missing)
    with pytest.raises(ValueError, match="invalid structured LLM request"):
        validate_structured_llm_request(request)
