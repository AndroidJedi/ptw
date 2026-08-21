from pathlib import Path

import json
import subprocess

import pytest

from worker.main import codex_available, command_available, execute_job, execute_structured_llm


def png_header(width: int = 1254, height: int = 1254) -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n"
        + b"\x00\x00\x00\x0dIHDR"
        + width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
        + b"\x08\x06\x00\x00\x00"
        + b"test-png-payload"
    )


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


def test_structured_llm_uses_fresh_ephemeral_schema_bound_session(monkeypatch) -> None:
    observed = {}

    def fake_run(command, **kwargs):
        observed["command"] = command
        observed["input"] = kwargs["input"]
        schema_path = Path(command[command.index("--output-schema") + 1])
        observed["schema"] = json.loads(schema_path.read_text(encoding="utf-8"))
        output_path = Path(command[command.index("--output-last-message") + 1])
        output_path.write_text('{"relevant_evidence_ids":["e-1"]}', encoding="utf-8")
        return subprocess.CompletedProcess(
            command, 0, stdout='{"type":"thread.started","thread_id":"fresh-session-1"}\n', stderr=""
        )

    monkeypatch.setattr("worker.main.subprocess.run", fake_run)
    request = {
        "mode": "laval_market_signal_relevance",
        "system_prompt": "Classify only the supplied evidence IDs.",
        "input_payload": {"evidence_ids": ["e-1"]},
        "output_schema": {
            "type": "object",
            "properties": {"relevant_evidence_ids": {"type": "array", "items": {"type": "string"}}},
            "required": ["relevant_evidence_ids"],
            "additionalProperties": False,
        },
        "model": "gpt-5",
    }

    result = execute_structured_llm(request)

    assert result["invocation"] == {
        "session_id": "fresh-session-1",
        "session_mode": "fresh",
        "ephemeral": True,
        "conversation_reused": False,
        "model": "gpt-5",
    }
    assert json.loads(result["response"]) == {"relevant_evidence_ids": ["e-1"]}
    assert observed["schema"] == request["output_schema"]
    assert observed["command"][-1] == "-"
    assert "--ephemeral" in observed["command"]
    assert "--output-schema" in observed["command"]
    assert observed["command"][observed["command"].index("--model") + 1] == "gpt-5"
    assert observed["command"][observed["command"].index("--sandbox") + 1] == "read-only"
    assert "resume" not in observed["command"]
    assert "--dangerously-bypass-approvals-and-sandbox" not in observed["command"]
    assert '"evidence_ids": ["e-1"]' in observed["input"]


def test_structured_llm_requires_reported_fresh_session_id(monkeypatch) -> None:
    def fake_run(command, **_kwargs):
        output_path = Path(command[command.index("--output-last-message") + 1])
        output_path.write_text("{}", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("worker.main.subprocess.run", fake_run)
    request = {
        "mode": "laval_owner_dna",
        "system_prompt": "Return structured output.",
        "input_payload": {},
        "output_schema": {"type": "object"},
    }

    try:
        execute_structured_llm(request)
    except RuntimeError as exc:
        assert "session ID" in str(exc)
    else:
        raise AssertionError("missing session ID must fail the invocation")


def test_structured_llm_cli_default_omits_model_override(monkeypatch) -> None:
    observed = {}

    def fake_run(command, **_kwargs):
        observed["command"] = command
        output_path = Path(command[command.index("--output-last-message") + 1])
        output_path.write_text('{"classifications": []}', encoding="utf-8")
        return subprocess.CompletedProcess(
            command, 0,
            stdout='{"type":"thread.started","thread_id":"fresh-default"}\n',
            stderr="",
        )

    monkeypatch.setattr("worker.main.subprocess.run", fake_run)
    result = execute_structured_llm({
        "mode": "laval_market_signal_relevance",
        "system_prompt": "Classify supplied pairs.",
        "input_payload": {},
        "output_schema": {"type": "object"},
        "model": "codex-cli-default",
    })
    assert "--model" not in observed["command"]
    assert result["invocation"]["model"] == "codex-cli-default"


def test_branding_logo_uses_one_builtin_image_and_persists_digest_asset(
    monkeypatch, tmp_path: Path
) -> None:
    codex_home = tmp_path / "codex-home"
    asset_root = tmp_path / "assets" / "brand-provider"
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("BRAND_PROVIDER_ASSET_DIR", str(asset_root))
    observed = {}

    def fake_run(command, **kwargs):
        observed["command"] = command
        observed["input"] = kwargs["input"]
        output_path = Path(command[command.index("--output-last-message") + 1])
        output_path.write_text('{"generated":true}', encoding="utf-8")
        generated = codex_home / "generated_images" / "brand-session-1"
        generated.mkdir(parents=True)
        (generated / "symbol.png").write_bytes(png_header())
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=(
                '{"type":"thread.started","thread_id":"brand-session-1"}\n'
                '{"type":"turn.completed","usage":{"input_tokens":12,"cached_input_tokens":3,"output_tokens":4}}\n'
            ),
            stderr="",
        )

    monkeypatch.setattr("worker.main.subprocess.run", fake_run)
    result = execute_structured_llm({
        "mode": "branding_logo_generation",
        "system_prompt": "$imagegen Generate exactly one original symbol.",
        "input_payload": {"logo_prompt": "A text-free mark"},
        "output_schema": {
            "type": "object",
            "properties": {"generated": {"type": "boolean"}},
            "required": ["generated"],
            "additionalProperties": False,
        },
        "model": "codex-cli-default",
    })

    image = result["image"]
    persisted = Path(image["path"])
    assert persisted.is_file()
    assert persisted.read_bytes() == png_header()
    assert image["digest"] in persisted.name
    assert image["width"] == image["height"] == 1254
    assert image["provider"] == "codex_chatgpt_imagegen"
    assert image["resolved_model"] == "gpt-image-2"
    assert not (codex_home / "generated_images" / "brand-session-1").exists()
    assert result["invocation"]["input_tokens"] == 12
    assert result["invocation"]["output_tokens"] == 4
    assert "$imagegen" in observed["input"]
    assert observed["command"][observed["command"].index("--sandbox") + 1] == "read-only"
    assert "--model" not in observed["command"]


def test_branding_logo_rejects_multiple_generated_images(monkeypatch, tmp_path: Path) -> None:
    codex_home = tmp_path / "codex-home"
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("BRAND_PROVIDER_ASSET_DIR", str(tmp_path / "assets"))

    def fake_run(command, **_kwargs):
        output_path = Path(command[command.index("--output-last-message") + 1])
        output_path.write_text('{"generated":true}', encoding="utf-8")
        generated = codex_home / "generated_images" / "brand-session-many"
        generated.mkdir(parents=True)
        (generated / "one.png").write_bytes(png_header())
        (generated / "two.png").write_bytes(png_header())
        return subprocess.CompletedProcess(
            command, 0,
            stdout='{"type":"thread.started","thread_id":"brand-session-many"}\n',
            stderr="",
        )

    monkeypatch.setattr("worker.main.subprocess.run", fake_run)
    with pytest.raises(RuntimeError, match="exactly one PNG"):
        execute_structured_llm({
            "mode": "branding_logo_generation",
            "system_prompt": "$imagegen Generate exactly one original symbol.",
            "input_payload": {},
            "output_schema": {"type": "object"},
        })


@pytest.mark.parametrize("mode", [
    "laval_youtube_observation",
    "laval_mechanism_extraction",
    "laval_thesis_synthesis",
    "laval_thesis_falsification",
])
def test_new_laval_modes_reach_fresh_schema_bound_worker(monkeypatch, mode: str) -> None:
    observed = {}

    def fake_run(command, **kwargs):
        observed["command"] = command
        observed["input"] = kwargs["input"]
        schema_path = Path(command[command.index("--output-schema") + 1])
        observed["schema"] = json.loads(schema_path.read_text(encoding="utf-8"))
        output_path = Path(command[command.index("--output-last-message") + 1])
        output_path.write_text('{"items": []}', encoding="utf-8")
        return subprocess.CompletedProcess(
            command, 0,
            stdout=f'{{"type":"thread.started","thread_id":"fresh-{mode}"}}\n',
            stderr="",
        )

    monkeypatch.setattr("worker.main.subprocess.run", fake_run)
    schema = {
        "type": "object",
        "properties": {"items": {"type": "array", "items": {"type": "object"}}},
        "required": ["items"],
        "additionalProperties": False,
    }
    result = execute_structured_llm({
        "mode": mode,
        "system_prompt": "Return the supplied contract.",
        "input_payload": {"mode": mode},
        "output_schema": schema,
        "model": "codex-cli-default",
    })

    assert observed["schema"] == schema
    assert f'"mode": "{mode}"' in observed["input"]
    assert "--ephemeral" in observed["command"]
    assert observed["command"][observed["command"].index("--sandbox") + 1] == "read-only"
    assert result["invocation"]["session_id"] == f"fresh-{mode}"
    assert result["invocation"]["conversation_reused"] is False
