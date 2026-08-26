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


def thread_output(session_id: str, *, image_call: bool = False) -> str:
    lines = [{"type": "thread.started", "thread_id": session_id}]
    if image_call:
        lines.append({
            "type": "item.completed",
            "item": {"type": "mcp_tool_call", "server": "image_gen", "tool": "imagegen"},
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
    value = execute_structured_llm(request("content_candidate_generation", model="gpt-5"))

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


def test_result_critic_receives_digest_mapped_private_jpeg_attachments(monkeypatch) -> None:
    content = b"\xff\xd8exact-render-bytes\xff\xd9"
    digest = hashlib.sha256(content).hexdigest()
    observed = {}

    def fake_run(command, **kwargs):
        paths = [Path(command[index + 1]) for index, value in enumerate(command) if value == "--image"]
        observed["paths"] = paths
        observed["bytes"] = [path.read_bytes() for path in paths]
        observed["input"] = kwargs["input"]
        Path(command[command.index("--output-last-message") + 1]).write_text(
            '{"selected":true}', encoding="utf-8"
        )
        return subprocess.CompletedProcess(
            command, 0, stdout=thread_output("fresh-critic-1"), stderr=""
        )

    monkeypatch.setattr("worker.main.subprocess.run", fake_run)
    value = execute_structured_llm(request(
        "content_result_critic",
        input_images=[{
            "candidate_id": "0190aa00-0000-7000-8000-000000000101",
            "mime_type": "image/jpeg",
            "digest": digest,
            "width": 1080,
            "height": 1080,
            "bytes_base64": base64.b64encode(content).decode(),
        }],
    ))

    assert json.loads(value["response"]) == {"selected": True}
    assert observed["bytes"] == [content]
    assert digest in observed["input"]
    assert base64.b64encode(content).decode() not in observed["input"]
    assert all(not path.exists() for path in observed["paths"])


def test_result_critic_rejects_image_generation(monkeypatch) -> None:
    content = b"\xff\xd8render\xff\xd9"
    digest = hashlib.sha256(content).hexdigest()

    def fake_run(command, **_kwargs):
        Path(command[command.index("--output-last-message") + 1]).write_text(
            '{"selected":true}', encoding="utf-8"
        )
        return subprocess.CompletedProcess(
            command, 0, stdout=thread_output("critic-image-call", image_call=True), stderr=""
        )

    monkeypatch.setattr("worker.main.subprocess.run", fake_run)
    with pytest.raises(RuntimeError, match="prohibited"):
        execute_structured_llm(request(
            "content_result_critic",
            input_images=[{
                "candidate_id": "0190aa00-0000-7000-8000-000000000101",
                "mime_type": "image/jpeg",
                "digest": digest,
                "width": 1080,
                "height": 1080,
                "bytes_base64": base64.b64encode(content).decode(),
            }],
        ))


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
