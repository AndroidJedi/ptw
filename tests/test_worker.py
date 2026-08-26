from pathlib import Path

import base64
import hashlib
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


def jpeg_1080() -> bytes:
    return (
        b"\xff\xd8\xff\xc0\x00\x11\x08\x04\x38\x04\x38\x03"
        b"\x01\x11\x00\x02\x11\x00\x03\x11\x00\xff\xd9"
    )


def imagegen_event(arguments: dict | None = None) -> str:
    return json.dumps({
        "type": "item.completed",
        "item": {
            "type": "mcp_tool_call",
            "server": "image_gen",
            "tool": "imagegen",
            "arguments": arguments or {"prompt": "abstract cyan route"},
        },
    })


def native_imagegen_event(call_id: str = "image-call-1") -> str:
    return json.dumps({
        "type": "item.completed",
        "item": {
            "id": call_id,
            "type": "image_generation",
            "status": "completed",
        },
    })


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


def test_studio_recipe_revision_is_json_only(monkeypatch, tmp_path: Path) -> None:
    codex_home = tmp_path / "codex-home"
    monkeypatch.setenv("CODEX_HOME", str(codex_home))

    def fake_run(command, **_kwargs):
        output_path = Path(command[command.index("--output-last-message") + 1])
        output_path.write_text('{"patch":[]}', encoding="utf-8")
        return subprocess.CompletedProcess(
            command, 0,
            stdout='{"type":"thread.started","thread_id":"studio-revision-1"}\n',
            stderr="",
        )

    monkeypatch.setattr("worker.main.subprocess.run", fake_run)
    result = execute_structured_llm({
        "mode": "ad_studio_recipe_revision",
        "system_prompt": "Propose a typed recipe patch.",
        "input_payload": {"instruction": "Move the headline left."},
        "output_schema": {"type": "object"},
    })
    assert json.loads(result["response"]) == {"patch": []}
    assert "image" not in result


def test_creative_validation_attaches_exact_jpeg_and_remains_json_only(monkeypatch, tmp_path: Path) -> None:
    observed = {}
    content = jpeg_1080()
    digest = hashlib.sha256(content).hexdigest()

    def fake_run(command, **kwargs):
        observed["command"] = command
        observed["input"] = kwargs["input"]
        image_path = Path(command[command.index("--image") + 1])
        observed["image"] = image_path.read_bytes()
        Path(command[command.index("--output-last-message") + 1]).write_text(
            '{"verdict":"approve"}', encoding="utf-8"
        )
        return subprocess.CompletedProcess(
            command, 0,
            stdout='{ "type":"thread.started", "thread_id":"creative-validator-1"}\n',
            stderr="",
        )

    monkeypatch.setattr("worker.main.subprocess.run", fake_run)
    result = execute_structured_llm({
        "mode": "ad_studio_creative_validation",
        "system_prompt": "Inspect attached pixels and return JSON only.",
        "input_payload": {"recipe_sha256": "a" * 64},
        "input_image": {
            "mime_type": "image/jpeg", "digest": digest, "width": 1080, "height": 1080,
            "bytes_base64": base64.b64encode(content).decode("ascii"),
        },
        "output_schema": {"type": "object"},
    })
    assert observed["image"] == content
    assert "bytes_base64" not in observed["input"]
    assert result["invocation"]["input_image"] == {
        "digest": digest, "mime_type": "image/jpeg", "width": 1080, "height": 1080,
        "transport": "codex_cli_image_attachment",
    }
    assert json.loads(result["response"]) == {"verdict": "approve"}


def test_studio_recipe_revision_rejects_imagegen(monkeypatch, tmp_path: Path) -> None:
    codex_home = tmp_path / "codex-home"
    monkeypatch.setenv("CODEX_HOME", str(codex_home))

    def fake_run(command, **_kwargs):
        output_path = Path(command[command.index("--output-last-message") + 1])
        output_path.write_text('{"patch":[]}', encoding="utf-8")
        generated = codex_home / "generated_images" / "studio-revision-image"
        generated.mkdir(parents=True)
        (generated / "unexpected.png").write_bytes(png_header())
        return subprocess.CompletedProcess(
            command, 0,
            stdout=(
                '{"type":"thread.started","thread_id":"studio-revision-image"}\n'
                + imagegen_event() + "\n"
            ),
            stderr="",
        )

    monkeypatch.setattr("worker.main.subprocess.run", fake_run)
    with pytest.raises(RuntimeError, match="JSON-only"):
        execute_structured_llm({
            "mode": "ad_studio_recipe_revision",
            "system_prompt": "Propose a typed recipe patch.",
            "input_payload": {},
            "output_schema": {"type": "object"},
        })
    assert not (codex_home / "generated_images" / "studio-revision-image").exists()


def test_studio_graphic_uses_exactly_one_imagegen_and_persists_provenance(
    monkeypatch, tmp_path: Path
) -> None:
    codex_home = tmp_path / "codex-home"
    asset_root = tmp_path / "assets" / "studio-provider"
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("STUDIO_PROVIDER_ASSET_DIR", str(asset_root))
    observed = {}

    def fake_run(command, **kwargs):
        observed["input"] = kwargs["input"]
        output_path = Path(command[command.index("--output-last-message") + 1])
        output_path.write_text('{"generated":true}', encoding="utf-8")
        generated = codex_home / "generated_images" / "studio-graphic-1"
        generated.mkdir(parents=True)
        (generated / "graphic.png").write_bytes(png_header(1080, 1080))
        return subprocess.CompletedProcess(
            command, 0,
            stdout=(
                '{"type":"thread.started","thread_id":"studio-graphic-1"}\n'
                + imagegen_event() + "\n"
            ),
            stderr="",
        )

    monkeypatch.setattr("worker.main.subprocess.run", fake_run)
    result = execute_structured_llm({
        "mode": "ad_studio_graphic_generation",
        "system_prompt": "Create an abstract cyan route on near-black.",
        "input_payload": {"template": "curiosity"},
        "output_schema": {"type": "object"},
    })
    image = result["image"]
    assert image["output_digest"] == image["digest"]
    assert Path(image["path"]).read_bytes() == png_header(1080, 1080)
    assert image["provider"] == "codex_chatgpt_imagegen"
    assert image["requested_model"] == "gpt-image-2"
    assert image["resolved_model"] == "gpt-image-2"
    assert image["request_id"] == "studio-graphic-1"
    assert len(image["prompt_digest"]) == 64
    assert len(image["tool_trace_digest"]) == 64
    assert image["generation_policy"]["synthetic_people"] == "prohibited"
    assert image["generation_policy"]["non_human_graphics_only"] is True
    assert "Call the built-in $imagegen tool exactly once" in observed["input"]
    assert "must not contain people" in observed["input"]
    assert not (codex_home / "generated_images" / "studio-graphic-1").exists()


def test_studio_graphic_accepts_native_image_generation_completion(
    monkeypatch, tmp_path: Path
) -> None:
    codex_home = tmp_path / "codex-home"
    asset_root = tmp_path / "assets" / "studio-provider"
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("STUDIO_PROVIDER_ASSET_DIR", str(asset_root))

    def fake_run(command, **_kwargs):
        Path(command[command.index("--output-last-message") + 1]).write_text(
            '{"generated":true}', encoding="utf-8"
        )
        generated = codex_home / "generated_images" / "studio-native-trace"
        generated.mkdir(parents=True)
        (generated / "graphic.png").write_bytes(png_header(1080, 1080))
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=(
                '{"type":"thread.started","thread_id":"studio-native-trace"}\n'
                + native_imagegen_event()
                + "\n"
            ),
            stderr="",
        )

    monkeypatch.setattr("worker.main.subprocess.run", fake_run)
    result = execute_structured_llm({
        "mode": "ad_studio_graphic_generation",
        "system_prompt": "Generate one abstract graphic.",
        "input_payload": {},
        "output_schema": {"type": "object"},
    })

    assert result["image"]["request_id"] == "studio-native-trace"
    assert len(result["image"]["tool_trace_digest"]) == 64


def test_studio_graphic_accepts_one_session_scoped_imagegen_receipt_without_trace(
    monkeypatch, tmp_path: Path
) -> None:
    codex_home = tmp_path / "codex-home"
    asset_root = tmp_path / "assets" / "studio-provider"
    request_id = "8788cf54-8fe8-4fe1-93cf-86e83c000f5b"
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("STUDIO_PROVIDER_ASSET_DIR", str(asset_root))

    def fake_run(command, **_kwargs):
        Path(command[command.index("--output-last-message") + 1]).write_text(
            '{"generated":true}', encoding="utf-8"
        )
        generated = codex_home / "generated_images" / "studio-receipt"
        generated.mkdir(parents=True)
        (generated / f"exec-{request_id}.png").write_bytes(png_header(1080, 1080))
        return subprocess.CompletedProcess(
            command,
            0,
            stdout='{"type":"thread.started","thread_id":"studio-receipt"}\n',
            stderr="",
        )

    monkeypatch.setattr("worker.main.subprocess.run", fake_run)
    result = execute_structured_llm({
        "mode": "ad_studio_graphic_generation",
        "system_prompt": "Generate one abstract graphic.",
        "input_payload": {},
        "output_schema": {"type": "object"},
    })

    assert result["image"]["request_id"] == request_id
    assert result["image"]["tool_proof_kind"] == "session_scoped_exec_receipt"
    assert len(result["image"]["tool_trace_digest"]) == 64


@pytest.mark.parametrize("trace_count", [0, 2])
def test_studio_graphic_rejects_missing_or_multiple_imagegen_calls(
    monkeypatch, tmp_path: Path, trace_count: int
) -> None:
    codex_home = tmp_path / f"codex-home-{trace_count}"
    monkeypatch.setenv("CODEX_HOME", str(codex_home))

    def fake_run(command, **_kwargs):
        output_path = Path(command[command.index("--output-last-message") + 1])
        output_path.write_text('{"generated":true}', encoding="utf-8")
        generated = codex_home / "generated_images" / f"studio-traces-{trace_count}"
        generated.mkdir(parents=True)
        (generated / "graphic.png").write_bytes(png_header())
        traces = "".join(imagegen_event() + "\n" for _ in range(trace_count))
        return subprocess.CompletedProcess(
            command, 0,
            stdout=(
                f'{{"type":"thread.started","thread_id":"studio-traces-{trace_count}"}}\n'
                + traces
            ),
            stderr="",
        )

    monkeypatch.setattr("worker.main.subprocess.run", fake_run)
    with pytest.raises(RuntimeError, match="call imagegen exactly once"):
        execute_structured_llm({
            "mode": "ad_studio_graphic_generation",
            "system_prompt": "Generate one abstract graphic.",
            "input_payload": {},
            "output_schema": {"type": "object"},
        })


def test_studio_graphic_rejects_multiple_pngs_from_one_call(monkeypatch, tmp_path: Path) -> None:
    codex_home = tmp_path / "codex-home"
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("STUDIO_PROVIDER_ASSET_DIR", str(tmp_path / "assets"))

    def fake_run(command, **_kwargs):
        Path(command[command.index("--output-last-message") + 1]).write_text(
            '{"generated":true}', encoding="utf-8"
        )
        generated = codex_home / "generated_images" / "studio-many-pngs"
        generated.mkdir(parents=True)
        (generated / "one.png").write_bytes(png_header())
        (generated / "two.png").write_bytes(png_header())
        return subprocess.CompletedProcess(
            command, 0,
            stdout=(
                '{"type":"thread.started","thread_id":"studio-many-pngs"}\n'
                + imagegen_event() + "\n"
            ),
            stderr="",
        )

    monkeypatch.setattr("worker.main.subprocess.run", fake_run)
    with pytest.raises(RuntimeError, match="exactly one PNG"):
        execute_structured_llm({
            "mode": "ad_studio_graphic_generation",
            "system_prompt": "Generate one abstract graphic.",
            "input_payload": {},
            "output_schema": {"type": "object"},
        })


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


def test_branding_reference_edit_proves_exact_attached_source(monkeypatch, tmp_path: Path) -> None:
    codex_home = tmp_path / "codex-home"
    shared_root = tmp_path / "assets"
    provider_root = shared_root / "brand-provider"
    source_path = shared_root / "approved.png"
    shared_root.mkdir()
    source_path.write_bytes(png_header())
    source_digest = __import__("hashlib").sha256(source_path.read_bytes()).hexdigest()
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("BRAND_SHARED_ASSET_ROOT", str(shared_root))
    monkeypatch.setenv("BRAND_PROVIDER_ASSET_DIR", str(provider_root))
    observed = {}

    def fake_run(command, **kwargs):
        observed["command"] = command
        observed["input"] = kwargs["input"]
        output_path = Path(command[command.index("--output-last-message") + 1])
        output_path.write_text('{"generated":true}', encoding="utf-8")
        generated = codex_home / "generated_images" / "brand-edit-session"
        generated.mkdir(parents=True)
        (generated / "edited.png").write_bytes(png_header())
        tool_event = {
            "type": "item.completed",
            "item": {
                "type": "mcp_tool_call", "server": "image_gen", "tool": "imagegen",
                "arguments": {"num_last_images_to_include": 1},
            },
        }
        return subprocess.CompletedProcess(
            command, 0,
            stdout=(
                '{"type":"thread.started","thread_id":"brand-edit-session"}\n'
                + json.dumps(tool_event) + "\n"
            ),
            stderr="",
        )

    monkeypatch.setattr("worker.main.subprocess.run", fake_run)
    result = execute_structured_llm({
        "mode": "branding_logo_reference_edit",
        "system_prompt": (
            f"$imagegen Edit the attached image from {source_path.resolve()}."
        ),
        "input_payload": {
            "source_path": str(source_path.resolve()),
            "source_digest": source_digest,
        },
        "output_schema": {"type": "object"},
    })
    assert result["image"]["reference"]["used"] is True
    assert result["image"]["reference"]["source_digest"] == source_digest
    assert result["image"]["reference"]["source_path"] == str(source_path.resolve())
    assert result["image"]["reference"]["transport"] == "codex_cli_image_attachment"
    assert observed["command"][observed["command"].index("--image") + 1] == str(source_path.resolve())
    assert "num_last_images_to_include=1" in observed["input"]


def test_branding_reference_edit_rejects_a_missing_tool_trace(monkeypatch, tmp_path: Path) -> None:
    codex_home = tmp_path / "codex-home"
    shared_root = tmp_path / "assets"
    source_path = shared_root / "approved.png"
    shared_root.mkdir()
    source_path.write_bytes(png_header())
    source_digest = __import__("hashlib").sha256(source_path.read_bytes()).hexdigest()
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("BRAND_SHARED_ASSET_ROOT", str(shared_root))
    monkeypatch.setenv("BRAND_PROVIDER_ASSET_DIR", str(shared_root / "provider"))

    def fake_run(command, **_kwargs):
        Path(command[command.index("--output-last-message") + 1]).write_text(
            '{"generated":true}', encoding="utf-8"
        )
        generated = codex_home / "generated_images" / "brand-edit-unproved"
        generated.mkdir(parents=True)
        (generated / "edited.png").write_bytes(png_header())
        return subprocess.CompletedProcess(
            command, 0,
            stdout='{"type":"thread.started","thread_id":"brand-edit-unproved"}\n',
            stderr="",
        )

    monkeypatch.setattr("worker.main.subprocess.run", fake_run)
    with pytest.raises(RuntimeError, match="exact reference path"):
        execute_structured_llm({
            "mode": "branding_logo_reference_edit",
            "system_prompt": (
                f"$imagegen Use referenced_image_paths with {source_path.resolve()}."
            ),
            "input_payload": {
                "source_path": str(source_path.resolve()),
                "source_digest": source_digest,
            },
            "output_schema": {"type": "object"},
        })


def test_branding_reference_edit_rejects_path_text_without_attached_image_use(
    monkeypatch, tmp_path: Path
) -> None:
    codex_home = tmp_path / "codex-home"
    shared_root = tmp_path / "assets"
    source_path = shared_root / "approved.png"
    shared_root.mkdir()
    source_path.write_bytes(png_header())
    source_digest = __import__("hashlib").sha256(source_path.read_bytes()).hexdigest()
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("BRAND_SHARED_ASSET_ROOT", str(shared_root))
    monkeypatch.setenv("BRAND_PROVIDER_ASSET_DIR", str(shared_root / "provider"))

    def fake_run(command, **_kwargs):
        Path(command[command.index("--output-last-message") + 1]).write_text(
            '{"generated":true}', encoding="utf-8"
        )
        generated = codex_home / "generated_images" / "brand-edit-path-only"
        generated.mkdir(parents=True)
        (generated / "edited.png").write_bytes(png_header())
        event = {
            "type": "item.completed",
            "item": {
                "type": "mcp_tool_call", "server": "image_gen", "tool": "imagegen",
                "arguments": {"referenced_image_paths": [str(source_path.resolve())]},
            },
        }
        return subprocess.CompletedProcess(
            command, 0,
            stdout=(
                '{"type":"thread.started","thread_id":"brand-edit-path-only"}\n'
                + json.dumps(event) + "\n"
            ),
            stderr="",
        )

    monkeypatch.setattr("worker.main.subprocess.run", fake_run)
    with pytest.raises(RuntimeError, match="exact reference path"):
        execute_structured_llm({
            "mode": "branding_logo_reference_edit",
            "system_prompt": f"$imagegen Edit {source_path.resolve()}.",
            "input_payload": {
                "source_path": str(source_path.resolve()),
                "source_digest": source_digest,
            },
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
