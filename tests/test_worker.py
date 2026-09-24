import base64
import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from worker.main import execute_structured_llm


def png_header(width: int = 1254, height: int = 1254) -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n"
        + b"\x00\x00\x00\x0dIHDR"
        + width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
        + b"\x08\x06\x00\x00\x00"
        + b"result-v1-test-payload"
    )


def request(mode: str, **extra) -> dict:
    return {
        "mode": mode,
        "system_prompt": "Return the exact structured contract.",
        "input_payload": {"task": "test"},
        "output_schema": {"type": "object"},
        "idempotency_key": f"test:{mode}:attempt:1",
        **extra,
    }


def thread_output(
    session_id: str, *, image_call: bool = False, attached_image: bool = False,
) -> str:
    lines = [{"type": "thread.started", "thread_id": session_id}]
    if image_call:
        lines.append({
            "type": "item.completed",
            "item": {
                "type": "mcp_tool_call", "server": "image_gen", "tool": "imagegen",
                **({"arguments": {"num_last_images_to_include": 1}}
                   if attached_image else {}),
            },
        })
    lines.append({
        "type": "turn.completed",
        "usage": {"input_tokens": 12, "cached_input_tokens": 3, "output_tokens": 4},
    })
    return "\n".join(json.dumps(line) for line in lines) + "\n"


def test_result_json_uses_fresh_ephemeral_schema_bound_session(monkeypatch) -> None:
    observed = {}

    def fake_run(command, **kwargs):
        observed["command"] = command
        observed["input"] = kwargs["input"]
        schema_path = Path(command[command.index("--output-schema") + 1])
        observed["schema"] = json.loads(schema_path.read_text(encoding="utf-8"))
        Path(command[command.index("--output-last-message") + 1]).write_text(
            '{"candidate":"ok"}', encoding="utf-8"
        )
        return subprocess.CompletedProcess(
            command, 0, stdout=thread_output("fresh-result-1"), stderr=""
        )

    monkeypatch.setattr("worker.main.subprocess.run", fake_run)
    value = execute_structured_llm(request("studio_creative_generation", model="gpt-5"))

    assert json.loads(value["response"]) == {"candidate": "ok"}
    assert value["invocation"]["session_id"] == "fresh-result-1"
    assert value["invocation"]["session_mode"] == "fresh"
    assert value["invocation"]["conversation_reused"] is False
    assert value["invocation"]["input_tokens"] == 12
    assert "--ephemeral" in observed["command"]
    assert "resume" not in observed["command"]
    assert observed["command"][observed["command"].index("--sandbox") + 1] == "read-only"
    assert observed["command"][observed["command"].index("--model") + 1] == "gpt-5"
    assert observed["schema"] == {"type": "object"}


def test_visual_analysis_receives_digest_checked_approved_png(monkeypatch) -> None:
    approved = png_header(1024, 768)
    digest = hashlib.sha256(approved).hexdigest()
    observed = {}
    monkeypatch.setattr("worker.main.secrets.get", lambda _name: "test-token")
    reference_id = "1" * 32

    def consume(url, **kwargs):
        assert url.endswith(f"/{reference_id}/consume")
        assert kwargs["headers"] == {"X-PTW-Bridge-Token": "test-token"}
        return __import__("unittest").mock.Mock(status_code=200, content=approved)

    def fake_run(command, **kwargs):
        attachments = [
            Path(command[index + 1])
            for index, value in enumerate(command) if value == "--image"
        ]
        observed["bytes"] = [path.read_bytes() for path in attachments]
        observed["prompt"] = kwargs["input"]
        Path(command[command.index("--output-last-message") + 1]).write_text(
            '{"palette":["neutral"]}', encoding="utf-8",
        )
        return subprocess.CompletedProcess(
            command, 0, stdout=thread_output("visual-analysis-1"), stderr="",
        )

    monkeypatch.setattr("worker.main.httpx.post", consume)
    monkeypatch.setattr("worker.main.subprocess.run", fake_run)
    value = execute_structured_llm(request(
        "creative_visual_analysis",
        input_reference={
            "id": reference_id, "name": "approved_png",
            "mime_type": "image/png", "sha256": digest,
        },
    ))

    assert json.loads(value["response"]) == {"palette": ["neutral"]}
    assert observed["bytes"] == [approved]
    assert digest in observed["prompt"]
    assert base64.b64encode(approved).decode() not in observed["prompt"]
    assert "Do not perform OCR" in observed["prompt"]


def test_structured_execution_timeout_is_bounded_and_passed_to_codex(monkeypatch) -> None:
    observed = {}
    monkeypatch.setenv("RESULT_BRIDGE_EXECUTION_TIMEOUT_SECONDS", "360")
    monkeypatch.setenv("RESULT_BRIDGE_REASONING_EFFORT", "low")

    def fake_run(command, **kwargs):
        observed["command"] = command
        observed["timeout"] = kwargs["timeout"]
        Path(command[command.index("--output-last-message") + 1]).write_text(
            '{"candidate":"ok"}', encoding="utf-8",
        )
        return subprocess.CompletedProcess(
            command, 0, stdout=thread_output("bounded-timeout"), stderr="",
        )

    monkeypatch.setattr("worker.main.subprocess.run", fake_run)
    execute_structured_llm(request("studio_creative_generation"))
    assert observed["timeout"] == 360
    config_index = observed["command"].index("--config")
    assert observed["command"][config_index + 1] == 'model_reasoning_effort="low"'

    for value in ("59", "391", "not-a-number"):
        monkeypatch.setenv("RESULT_BRIDGE_EXECUTION_TIMEOUT_SECONDS", value)
        with pytest.raises(RuntimeError, match="execution timeout"):
            execute_structured_llm(request("studio_creative_generation"))

    monkeypatch.setenv("RESULT_BRIDGE_EXECUTION_TIMEOUT_SECONDS", "360")
    monkeypatch.setenv("RESULT_BRIDGE_REASONING_EFFORT", "unsupported")
    with pytest.raises(RuntimeError, match="reasoning effort"):
        execute_structured_llm(request("studio_creative_generation"))


def test_template_creation_pins_xhigh_reasoning(monkeypatch) -> None:
    observed = {}
    monkeypatch.setenv("RESULT_BRIDGE_REASONING_EFFORT", "low")
    def fake_run(command, **kwargs):
        observed["command"] = command
        Path(command[command.index("--output-last-message") + 1]).write_text(
            '{"candidate":"ok"}', encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, stdout=thread_output("template-1"), stderr="")
    monkeypatch.setattr("worker.main.subprocess.run", fake_run)
    execute_structured_llm(request("template_creation", reasoning_effort="xhigh"))
    config_index = observed["command"].index("--config")
    assert observed["command"][config_index + 1] == 'model_reasoning_effort="xhigh"'
    with pytest.raises(RuntimeError, match="xhigh"):
        execute_structured_llm(request("template_creation"))


def test_non_human_graphic_enhancement_receives_private_png_reference(monkeypatch, tmp_path: Path) -> None:
    codex_home = tmp_path / "codex-home"
    asset_root = tmp_path / "assets" / "content-graphics"
    reference = png_header(1024, 1024)
    digest = hashlib.sha256(reference).hexdigest()
    observed = {}
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("CONTENT_GRAPHIC_ASSET_DIR", str(asset_root))

    def fake_run(command, **kwargs):
        paths = [Path(command[index + 1]) for index, value in enumerate(command) if value == "--image"]
        observed["paths"] = paths
        observed["bytes"] = [path.read_bytes() for path in paths]
        observed["input"] = kwargs["input"]
        Path(command[command.index("--output-last-message") + 1]).write_text(
            '{"generated":true}', encoding="utf-8"
        )
        generated = codex_home / "generated_images" / "graphic-edit-1"
        generated.mkdir(parents=True)
        (generated / "graphic.png").write_bytes(png_header())
        return subprocess.CompletedProcess(
            command, 0,
            stdout=thread_output("graphic-edit-1", image_call=True, attached_image=True),
            stderr="",
        )

    monkeypatch.setattr("worker.main.subprocess.run", fake_run)
    value = execute_structured_llm(request(
        "content_non_human_graphic_generation",
        input_images=[{
            "mime_type": "image/png", "digest": digest,
            "width": 1024, "height": 1024,
            "bytes_base64": base64.b64encode(reference).decode(),
        }],
    ))

    assert value["image"]["digest"]
    assert observed["bytes"] == [reference]
    assert digest in observed["input"]
    assert base64.b64encode(reference).decode() not in observed["input"]
    assert all(not path.exists() for path in observed["paths"])


def test_non_human_graphic_is_single_square_png_with_review_policy(monkeypatch, tmp_path: Path) -> None:
    codex_home = tmp_path / "codex-home"
    asset_root = tmp_path / "assets" / "content-graphics"
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("CONTENT_GRAPHIC_ASSET_DIR", str(asset_root))

    def fake_run(command, **_kwargs):
        Path(command[command.index("--output-last-message") + 1]).write_text(
            '{"generated":true}', encoding="utf-8"
        )
        generated = codex_home / "generated_images" / "graphic-session-1"
        generated.mkdir(parents=True)
        (generated / "graphic.png").write_bytes(png_header())
        return subprocess.CompletedProcess(
            command, 0, stdout=thread_output("graphic-session-1", image_call=True), stderr=""
        )

    monkeypatch.setattr("worker.main.subprocess.run", fake_run)
    value = execute_structured_llm(request("content_non_human_graphic_generation"))
    image = value["image"]

    assert Path(image["path"]).read_bytes() == png_header()
    assert image["digest"] == image["output_digest"]
    assert image["generation_policy"]["non_human_graphics_only"] is True
    assert image["generation_policy"]["synthetic_people"] == "prohibited"
    assert not (codex_home / "generated_images" / "graphic-session-1").exists()


def test_non_human_graphic_reference_is_digest_checked_attached_and_provenanced(
    monkeypatch, tmp_path: Path,
) -> None:
    codex_home = tmp_path / "codex-home"
    asset_root = tmp_path / "assets" / "content-graphics"
    reference = png_header(1024, 1024)
    digest = hashlib.sha256(reference).hexdigest()
    observed = {}
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("CONTENT_GRAPHIC_ASSET_DIR", str(asset_root))

    def fake_run(command, **kwargs):
        attachments = [
            Path(command[index + 1])
            for index, value in enumerate(command) if value == "--image"
        ]
        observed["bytes"] = [path.read_bytes() for path in attachments]
        observed["paths"] = attachments
        observed["prompt"] = kwargs["input"]
        Path(command[command.index("--output-last-message") + 1]).write_text(
            '{"generated":true}', encoding="utf-8"
        )
        generated = codex_home / "generated_images" / "graphic-edit-session"
        generated.mkdir(parents=True)
        (generated / "graphic.png").write_bytes(png_header())
        return subprocess.CompletedProcess(
            command, 0,
            stdout=thread_output(
                "graphic-edit-session", image_call=True, attached_image=True,
            ), stderr="",
        )

    monkeypatch.setattr("worker.main.subprocess.run", fake_run)
    value = execute_structured_llm(request(
        "content_non_human_graphic_generation",
        input_images=[{
            "mime_type": "image/png", "digest": digest,
            "width": 1024, "height": 1024,
            "bytes_base64": base64.b64encode(reference).decode(),
        }],
    ))

    assert observed["bytes"] == [reference]
    assert digest in observed["prompt"]
    assert base64.b64encode(reference).decode() not in observed["prompt"]
    assert all(not path.exists() for path in observed["paths"])
    assert value["image"]["reference"] == {
        "sha256": digest, "used": True,
        "transport": "codex_cli_image_attachment",
        "evidence": "validated_cli_attachment_and_distinct_output",
    }


def test_non_human_graphic_reference_rejects_unchanged_output(
    monkeypatch, tmp_path: Path,
) -> None:
    codex_home = tmp_path / "codex-home"
    reference = png_header(1024, 1024)
    digest = hashlib.sha256(reference).hexdigest()
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("CONTENT_GRAPHIC_ASSET_DIR", str(tmp_path / "assets"))

    def fake_run(command, **_kwargs):
        Path(command[command.index("--output-last-message") + 1]).write_text(
            '{"generated":true}', encoding="utf-8"
        )
        generated = codex_home / "generated_images" / "unchanged-edit-session"
        generated.mkdir(parents=True)
        (generated / "graphic.png").write_bytes(reference)
        return subprocess.CompletedProcess(
            command, 0,
            # Current Codex CLI JSON does not expose nested imagegen arguments.
            stdout=thread_output("unchanged-edit-session"), stderr="",
        )

    monkeypatch.setattr("worker.main.subprocess.run", fake_run)
    with pytest.raises(RuntimeError, match="unchanged reference"):
        execute_structured_llm(request(
            "content_non_human_graphic_generation",
            input_images=[{
                "mime_type": "image/png", "digest": digest,
                "width": 1024, "height": 1024,
                "bytes_base64": base64.b64encode(reference).decode(),
            }],
        ))
    assert not (codex_home / "generated_images" / "unchanged-edit-session").exists()


def test_non_human_graphic_rejects_multiple_generated_images(monkeypatch, tmp_path: Path) -> None:
    codex_home = tmp_path / "codex-home"
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("CONTENT_GRAPHIC_ASSET_DIR", str(tmp_path / "assets"))

    def fake_run(command, **_kwargs):
        Path(command[command.index("--output-last-message") + 1]).write_text(
            '{"generated":true}', encoding="utf-8"
        )
        generated = codex_home / "generated_images" / "graphic-session-many"
        generated.mkdir(parents=True)
        (generated / "one.png").write_bytes(png_header())
        (generated / "two.png").write_bytes(png_header())
        return subprocess.CompletedProcess(
            command, 0, stdout=thread_output("graphic-session-many", image_call=True), stderr=""
        )

    monkeypatch.setattr("worker.main.subprocess.run", fake_run)
    with pytest.raises(RuntimeError, match="exactly one PNG"):
        execute_structured_llm(request("content_non_human_graphic_generation"))


def test_worker_rejects_retired_structured_mode() -> None:
    with pytest.raises(RuntimeError, match="unsupported Result bridge mode"):
        execute_structured_llm(request("natal_landing_revision"))


def test_domain_image_policy_preserves_request_and_accepts_unchanged_edit(monkeypatch, tmp_path):
    codex_home = tmp_path / "codex-home"
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("CONTENT_GRAPHIC_ASSET_DIR", str(tmp_path / "assets"))
    reference = png_header(1024, 1024)
    digest = hashlib.sha256(reference).hexdigest()
    observed = []
    def fake_run(command, **kwargs):
        observed.append(kwargs["input"])
        Path(command[command.index("--output-last-message") + 1]).write_text('{"generated":true}')
        generated = codex_home / "generated_images" / "domain-scene"
        generated.mkdir(parents=True)
        (generated / "scene.png").write_bytes(reference)
        return subprocess.CompletedProcess(command, 0, stdout=thread_output("domain-scene", image_call=True), stderr="")
    monkeypatch.setattr("worker.main.subprocess.run", fake_run)
    value = execute_structured_llm(request("content_non_human_graphic_generation",
        input_payload={"generation_policy_version": "ptw.domain-image.v1", "visual_direction": "A guest scanning a hotel QR card with a phone; label SPA"},
        input_images=[{"mime_type": "image/png", "digest": digest, "width": 1024, "height": 1024, "bytes_base64": base64.b64encode(reference).decode()}]))
    assert len(observed) == 1
    assert "guest scanning a hotel QR card" in observed[0]
    assert "containing no people" not in observed[0]
    assert "review-gated" not in observed[0]
    assert value["image"]["digest"] == digest
    assert value["image"]["generation_policy"]["version"] == "ptw.domain-image.v1"
    assert value["image"]["generation_policy"]["visual_quality_gate"] is False
    assert value["image"]["reference"]["evidence"] == "validated_cli_attachment"


@pytest.mark.parametrize("mode,size", [("app_screen", (864,1872)), ("app_mockup", (1536,1152))])
def test_image_output_spec_reaches_worker_without_square_override(monkeypatch, tmp_path, mode, size):
    from common.image_output import output_specification
    home=tmp_path/'codex'; observed=[]
    monkeypatch.setenv('CODEX_HOME',str(home))
    monkeypatch.setenv('CONTENT_GRAPHIC_ASSET_DIR',str(tmp_path/'assets'))
    spec=output_specification({'mode':mode})
    def run(command, **kwargs):
        observed.append((command,kwargs['input']))
        Path(command[command.index('--output-last-message')+1]).write_text('{"generated":true}')
        output=home/'generated_images'/'portrait';output.mkdir(parents=True)
        (output/'image.png').write_bytes(png_header(*size))
        return subprocess.CompletedProcess(command,0,stdout=thread_output('portrait',image_call=True),stderr='')
    monkeypatch.setattr('worker.main.subprocess.run',run)
    result=execute_structured_llm(request('content_non_human_graphic_generation',model='gpt-6-astra',input_payload={
        'generation_policy_version':'ptw.domain-image.v1','output_spec':spec,'visual_direction':'Realistic hotel app screens'}))
    assert len(observed)==1
    assert 'square PNG' not in observed[0][1]
    assert f'{size[0]}x{size[1]}' in observed[0][1]
    assert result['image']['output_spec']==spec
    assert result['invocation']['model']=='gpt-6-astra'
    assert result['image']['resolved_model'] is None


def test_portrait_output_rejects_square_pixels_and_cleans_temporary_files(tmp_path,monkeypatch):
    from common.image_output import output_specification
    from worker.main import _persist_non_human_graphic
    output=tmp_path/'generated_images'/'square';output.mkdir(parents=True)
    (output/'image.png').write_bytes(png_header(1024,1024))
    with pytest.raises(ValueError,match='aspect ratio'):
        _persist_non_human_graphic(tmp_path,'square',policy_version='ptw.domain-image.v1',output_spec=output_specification({'mode':'app_screen'}))
    assert not output.exists()
