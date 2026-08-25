import pytest
import hashlib
from pathlib import Path

from commander.main import (IDEA_COMMANDS, STUDIO_MODES, VALIDATION_MODES, MAX_STRUCTURED_LLM_REQUEST_BYTES, STRUCTURED_LLM_MODES, SUPPORTED_COMMANDS, TRACKED_BRIDGE_COMMANDS,
                            _validated_studio_graphic,
                            bridge_target, engineering_task, normalized_command,
                            get_structured_llm_capabilities, public_health, safe_bridge_error, structured_llm_asset, structured_llm_capabilities, structured_llm_result, task_research_reference,
                            validate_structured_llm_request)

SOURCE_ROOT = Path(__file__).resolve().parents[1]


def png_header(width: int = 1080, height: int = 1080) -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n"
        + b"\x00\x00\x00\x0dIHDR"
        + width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
        + b"\x08\x06\x00\x00\x00"
        + b"studio-test-png"
    )


class FakeConnection:
    def __init__(self, row):
        self.row = row

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, *_args, **_kwargs):
        return self

    def fetchone(self):
        return self.row


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


def test_structured_bridge_accepts_validation_modes_and_full_contract() -> None:
    validation_modes = {
        "product_brief",
        "product_brief_revision",
        "ad_creative_batch",
    }
    assert VALIDATION_MODES == validation_modes
    assert structured_llm_capabilities() == {
        "validation_modes": sorted(validation_modes),
        "studio_modes": sorted(STUDIO_MODES),
        "max_request_bytes": MAX_STRUCTURED_LLM_REQUEST_BYTES,
    }
    for mode in validation_modes:
        validate_structured_llm_request({
            "mode": mode,
            "system_prompt": "Return the requested validation artifact.",
            "input_payload": {"brief_id": "01900000-0000-7000-8000-000000000001"},
            "output_schema": {"type": "object"},
            "prompt_template_version": "contract-v1",
            "context_hash": "sha256:abc",
        })


def test_structured_bridge_advertises_additive_studio_modes() -> None:
    assert VALIDATION_MODES == {
        "product_brief", "product_brief_revision", "ad_creative_batch",
    }
    assert STUDIO_MODES == {
        "ad_studio_recipe_revision", "ad_studio_graphic_generation",
    }
    assert STUDIO_MODES <= STRUCTURED_LLM_MODES
    for mode in STUDIO_MODES:
        validate_structured_llm_request({
            "mode": mode,
            "system_prompt": "Return the requested Studio artifact.",
            "input_payload": {"project_id": "01900000-0000-7000-8000-000000000001"},
            "output_schema": {"type": "object"},
        })


@pytest.mark.parametrize("mode", [
    "marketing_positioning_research_plan",
    "marketing_positioning_document",
    "marketing_positioning_revision",
    "natal_landing_revision",
    "laval_owner_dna",
    "branding_direction_synthesis",
])
def test_structured_bridge_rejects_retired_ptw_modes(mode: str) -> None:
    with pytest.raises(ValueError, match="unsupported structured LLM mode"):
        validate_structured_llm_request({
            "mode": mode,
            "system_prompt": "Return structured evidence.",
            "input_payload": {},
            "output_schema": {"type": "object"},
        })


def test_structured_bridge_rejects_unknown_and_oversized_requests() -> None:
    request = {
        "mode": "validation_not_registered",
        "system_prompt": "Return structured output.",
        "input_payload": {},
        "output_schema": {"type": "object"},
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
    worker = compose.split("  commander-worker:", 1)[1].split("  git-watcher:", 1)[0]
    assert "image: ptw-agent-platform-commander-worker:${PTW_PLATFORM_IMAGE_TAG:-latest}" in worker
    assert "pull_policy: never" in worker
    assert "commander-assets:/var/lib/ptw/assets" in worker


def test_completed_studio_graphic_asset_is_authenticated_digest_checked_and_private(
    monkeypatch, tmp_path: Path
) -> None:
    content = png_header()
    digest = hashlib.sha256(content).hexdigest()
    asset_root = tmp_path / "studio-provider"
    path = asset_root / digest[:2] / f"{digest}.png"
    path.parent.mkdir(parents=True)
    path.write_bytes(content)
    result = {
        "image": {
            "digest": digest,
            "output_digest": digest,
            "path": str(path),
            "mime_type": "image/png",
        }
    }
    parameters = {"mode": "ad_studio_graphic_generation"}
    monkeypatch.setenv("STUDIO_PROVIDER_ASSET_DIR", str(asset_root))
    monkeypatch.setattr("commander.main.secrets.get", lambda _name: "bridge-token")
    monkeypatch.setattr(
        "commander.main.psycopg.connect",
        lambda *_args, **_kwargs: FakeConnection(("completed", result, parameters)),
    )

    with pytest.raises(Exception) as rejected:
        structured_llm_asset(71, "wrong-token", "")
    assert rejected.value.status_code == 403

    response = structured_llm_asset(71, "bridge-token", "")
    assert response.body == content
    assert response.media_type == "image/png"
    assert response.headers["etag"] == f'"{digest}"'
    assert response.headers["cache-control"] == "private, immutable, max-age=31536000"

    not_modified = structured_llm_asset(71, "bridge-token", f'W/"{digest}"')
    assert not_modified.status_code == 304
    assert not_modified.body == b""


def test_studio_graphic_asset_rejects_path_escape_and_digest_mismatch(
    monkeypatch, tmp_path: Path
) -> None:
    content = png_header()
    digest = hashlib.sha256(content).hexdigest()
    asset_root = tmp_path / "studio-provider"
    outside = tmp_path / f"{digest}.png"
    outside.write_bytes(content)
    monkeypatch.setenv("STUDIO_PROVIDER_ASSET_DIR", str(asset_root))
    base = {
        "digest": digest,
        "output_digest": digest,
        "path": str(outside),
        "mime_type": "image/png",
    }
    with pytest.raises(ValueError, match="outside its asset root"):
        _validated_studio_graphic({"image": base})

    canonical = asset_root / digest[:2] / f"{digest}.png"
    canonical.parent.mkdir(parents=True)
    canonical.write_bytes(content + b"tampered")
    base["path"] = str(canonical)
    with pytest.raises(ValueError, match="digest validation"):
        _validated_studio_graphic({"image": base})


def test_studio_graphic_result_uses_asset_endpoint_instead_of_shared_path(monkeypatch) -> None:
    stored = {"image": {"digest": "a" * 64, "path": "/private/asset.png"}}
    parameters = {"mode": "ad_studio_graphic_generation"}
    monkeypatch.setattr("commander.main.secrets.get", lambda _name: "bridge-token")
    monkeypatch.setattr(
        "commander.main.psycopg.connect",
        lambda *_args, **_kwargs: FakeConnection(("completed", stored, None, parameters)),
    )
    response = structured_llm_result(83, "bridge-token")
    assert "path" not in response["result"]["image"]
    assert response["result"]["image"]["asset_url"] == (
        "/internal/llm/structured/83/asset"
    )


@pytest.mark.parametrize("missing", ["system_prompt", "input_payload", "output_schema"])
def test_structured_bridge_rejects_incomplete_contract(missing: str) -> None:
    request = {
        "mode": "product_brief",
        "system_prompt": "Return a Product Brief.",
        "input_payload": {},
        "output_schema": {"type": "object"},
    }
    request.pop(missing)
    with pytest.raises(ValueError, match="invalid structured LLM request"):
        validate_structured_llm_request(request)
