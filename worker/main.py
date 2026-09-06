import logging
import os
import base64
import binascii
import shutil
import signal
import subprocess
import time
import json
import tempfile
import hashlib
import re
import struct
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

from common.database import database_url
from common.events import append_event
from common.secrets import EnvironmentSecretStore

logging.basicConfig(
    level=os.getenv("PTW_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("ptw.worker")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
running = True
secrets = EnvironmentSecretStore()


def stop(_signum: int, _frame: object) -> None:
    global running
    running = False


def heartbeat(connection: psycopg.Connection) -> None:
    connection.execute(
        """
        INSERT INTO service_heartbeats (service, seen_at) VALUES ('commander-worker', now())
        ON CONFLICT (service) DO UPDATE SET seen_at = excluded.seen_at
        """
    )


def _codex_session_id(stdout: str) -> str:
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        session_id = event.get("thread_id") or event.get("session_id")
        if isinstance(session_id, str) and session_id:
            return session_id
    raise RuntimeError("structured model execution did not report a session ID")


def _codex_usage(stdout: str) -> dict[str, int]:
    usage: dict[str, int] = {}
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        candidate = event.get("usage")
        if event.get("type") == "turn.completed" and isinstance(candidate, dict):
            for key in ("input_tokens", "cached_input_tokens", "output_tokens"):
                if isinstance(candidate.get(key), int) and candidate[key] >= 0:
                    usage[key] = candidate[key]
    return usage


def _persist_non_human_graphic(
    codex_home: Path, session_id: str, *, reference_digest: str | None = None,
) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9-]{1,100}", session_id):
        raise RuntimeError("image generation returned an invalid session ID")
    generated_root = (codex_home / "generated_images").resolve()
    session_directory = (generated_root / session_id).resolve()
    if generated_root not in session_directory.parents:
        raise RuntimeError("image generation resolved outside its temporary root")
    try:
        images = sorted(path for path in session_directory.glob("*.png") if path.is_file())
        if len(images) != 1:
            raise RuntimeError("non-human graphic generation must return exactly one PNG")
        content = images[0].read_bytes()
        if len(content) < 33 or len(content) > 8 * 1024 * 1024 or not content.startswith(b"\x89PNG\r\n\x1a\n"):
            raise RuntimeError("non-human graphic generation returned an invalid PNG")
        width = struct.unpack(">I", content[16:20])[0]
        height = struct.unpack(">I", content[20:24])[0]
        if width != height or not 512 <= width <= 2048:
            raise RuntimeError("non-human graphic generation must return a bounded square image")
        digest = hashlib.sha256(content).hexdigest()
        if reference_digest is not None and digest == reference_digest:
            raise RuntimeError("non-human graphic edit returned the unchanged reference")
        asset_root = Path(
            os.environ.get("CONTENT_GRAPHIC_ASSET_DIR", "/var/lib/ptw/assets/content-graphics")
        ).resolve()
        destination_directory = asset_root / digest[:2]
        destination_directory.mkdir(mode=0o750, parents=True, exist_ok=True)
        destination = destination_directory / f"{digest}.png"
        if destination.exists():
            if hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
                raise RuntimeError("immutable content graphic digest collision")
        else:
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=destination_directory, prefix=f".{digest}.", delete=False
            ) as temporary:
                temporary.write(content)
                temporary_path = Path(temporary.name)
            temporary_path.chmod(0o640)
            os.replace(temporary_path, destination)
        return {
            "digest": digest,
            "output_digest": digest,
            "path": str(destination),
            "mime_type": "image/png",
            "width": width,
            "height": height,
            "requested_model": "gpt-image-2",
            "resolved_model": "gpt-image-2",
            "provider": "codex_chatgpt_imagegen",
            "request_id": session_id,
            "generation_policy": {
                "non_human_graphics_only": True,
                "synthetic_people": "prohibited",
                "embedded_text": "prohibited",
                "embedded_logos": "prohibited",
                "watermarks": "prohibited",
            },
        }
    finally:
        if session_directory.is_dir():
            shutil.rmtree(session_directory)


def _used_image_generation(stdout: str) -> bool:
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        item = event.get("item") if isinstance(event, dict) else None
        if not isinstance(item, dict):
            continue
        tool_marker = " ".join(
            str(item.get(key) or "") for key in ("type", "server", "tool", "name")
        ).lower()
        if "tool" not in tool_marker or "image" not in tool_marker:
            continue
        arguments = item.get("arguments") or item.get("input") or {}
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                continue
        return True
    return False


def _materialize_input_images(parameters: dict, directory: Path) -> tuple[list[Path], list[dict]]:
    images = parameters.get("input_images")
    mode = parameters.get("mode")
    if mode == "content_non_human_graphic_generation":
        if images is None:
            return [], []
        if not isinstance(images, list) or len(images) != 1:
            raise RuntimeError("non-human graphic generation accepts at most one PNG reference")
        image = images[0]
        try:
            content = base64.b64decode(image["bytes_base64"], validate=True)
        except (KeyError, TypeError, ValueError, binascii.Error) as exc:
            raise RuntimeError("non-human graphic reference base64 is invalid") from exc
        digest = hashlib.sha256(content).hexdigest()
        width = int.from_bytes(content[16:20], "big") if len(content) >= 24 else 0
        height = int.from_bytes(content[20:24], "big") if len(content) >= 24 else 0
        if (
            set(image) != {"mime_type", "digest", "width", "height", "bytes_base64"}
            or image.get("mime_type") != "image/png"
            or image.get("digest") != digest
            or not content.startswith(b"\x89PNG\r\n\x1a\n")
            or not 33 <= len(content) <= 8 * 1024 * 1024
            or image.get("width") != width
            or image.get("height") != height
            or width != height
            or not 512 <= width <= 2048
        ):
            raise RuntimeError("non-human graphic reference failed exact PNG validation")
        path = directory / f"media-reference-{digest[:12]}.png"
        path.write_bytes(content)
        path.chmod(0o600)
        return [path], [{"sha256": digest, "attachment_index": 1}]
    if images is not None:
        raise RuntimeError("only the media mode accepts input images")
    return [], []


def execute_structured_llm(parameters: dict) -> dict:
    """Run one schema-bound Codex invocation with no reusable conversation state."""
    codex_home = Path(os.environ.get("CODEX_HOME", "/tmp/ptw-codex"))
    codex_home.mkdir(mode=0o700, parents=True, exist_ok=True)
    mounted = Path("/run/ptw-codex-auth/auth.json")
    runtime = codex_home / "auth.json"
    # Refresh the runtime copy for every request so a completed owner device-login
    # takes effect without an SSH session or a worker restart.
    if mounted.is_file():
        shutil.copyfile(mounted, runtime)
        runtime.chmod(0o600)

    mode = parameters.get("mode")
    if mode not in {
        "product_brief", "product_brief_revision", "studio_creative_generation",
        "studio_edit_learning", "content_non_human_graphic_generation",
    }:
        raise RuntimeError("unsupported Result bridge mode")
    prompt = (
        parameters["system_prompt"].strip()
        + "\n\nReturn only one JSON object matching the supplied schema."
        + "\nINPUT_PAYLOAD:\n"
        + json.dumps(parameters["input_payload"], ensure_ascii=False, sort_keys=True)
    )
    with tempfile.TemporaryDirectory(prefix="ptw-llm-") as directory:
        temporary_root = Path(directory)
        output = temporary_root / "result.json"
        schema = temporary_root / "output-schema.json"
        attachments, attachment_mapping = _materialize_input_images(parameters, temporary_root)
        if attachment_mapping:
            prompt += (
                "\nREFERENCE_ATTACHMENT: Edit the one attached digest-checked PNG as the starting "
                "composition. Preserve its recognizable subject, palette, material character, and "
                "spatial arrangement unless the requested direction explicitly changes them. In "
                "the image-generation call use num_last_images_to_include=1 and do not use a path.\n"
                + json.dumps(attachment_mapping, ensure_ascii=False, sort_keys=True)
            )
        if mode == "content_non_human_graphic_generation":
            prompt += (
                "\nUse image generation or image editing exactly once to create one square PNG "
                "containing no people, faces, text, logos, UI, devices, numbers, charts, labels, "
                "or watermarks. The generated graphic remains review-gated."
            )
        schema.write_text(
            json.dumps(parameters["output_schema"], ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        command = [
            os.getenv("CODEX_EXECUTABLE", "codex"),
            "exec",
            "--ephemeral",
            "--ignore-user-config",
        ]
        requested_model = str(parameters.get("model") or "").strip()
        if requested_model and requested_model != "codex-cli-default":
            command.extend(["--model", requested_model])
        for attachment in attachments:
            command.extend(["--image", str(attachment)])
        command.extend([
            "--sandbox",
            "read-only",
            "--skip-git-repo-check",
            "--json",
            "--cd",
            directory,
            "--output-schema",
            str(schema),
            "--output-last-message",
            str(output),
            "-",
        ])
        completed = subprocess.run(
            command,
            input=prompt,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=300,
            env=os.environ.copy(),
        )
        if completed.returncode:
            raise RuntimeError("structured model execution failed")
        data = json.loads(output.read_text(encoding="utf-8"))
        session_id = _codex_session_id(completed.stdout)
        used_image_generation = _used_image_generation(completed.stdout)
        if mode != "content_non_human_graphic_generation" and used_image_generation:
            raise RuntimeError("image generation is prohibited in Result JSON modes")
        invocation = {
            "session_id": session_id,
            "session_mode": "fresh",
            "ephemeral": True,
            "conversation_reused": False,
            "model": requested_model or "codex-cli-default",
        }
        invocation.update(_codex_usage(completed.stdout))
        result = {
            "response": json.dumps(data, ensure_ascii=False),
            "invocation": invocation,
        }
        if mode == "content_non_human_graphic_generation":
            reference_digest = attachment_mapping[0]["sha256"] if attachment_mapping else None
            result["image"] = _persist_non_human_graphic(
                codex_home, session_id, reference_digest=reference_digest,
            )
            if attachment_mapping:
                result["image"]["reference"] = {
                    "sha256": attachment_mapping[0]["sha256"],
                    "used": True,
                    "transport": "codex_cli_image_attachment",
                    "evidence": "validated_cli_attachment_and_distinct_output",
                }
        return result


def process_one(connection: psycopg.Connection) -> bool:
    stopped = connection.execute(
        "SELECT emergency_stop FROM platform_control WHERE singleton=true"
    ).fetchone()
    if stopped and stopped[0]:
        heartbeat(connection)
        connection.commit()
        return False
    job = connection.execute(
        """SELECT id,session_id,parameters FROM jobs
            WHERE status='queued' AND type='llm_structured' ORDER BY created_at,id
            FOR UPDATE SKIP LOCKED LIMIT 1"""
    ).fetchone()
    if not job:
        heartbeat(connection)
        connection.commit()
        return False
    job_id, session_id, parameters = job
    connection.execute(
        "UPDATE jobs SET status = 'running', started_at = now() WHERE id = %s", (job_id,)
    )
    append_event(
        connection, "JOB_STARTED", "commander-worker", status="running",
        session_id=session_id, job_id=job_id, payload={"job_type": "llm_structured"},
    )
    connection.commit()
    try:
        result = execute_structured_llm(parameters)
        connection.execute(
            "UPDATE jobs SET status = 'completed', result = %s, finished_at = now() WHERE id = %s",
            (Jsonb(result), job_id),
        )
        append_event(
            connection, "JOB_COMPLETED", "commander-worker", status="completed",
            session_id=session_id, job_id=job_id, payload={"job_type": "llm_structured"},
        )
        connection.execute(
            "UPDATE sessions SET status = 'completed', updated_at = now() WHERE id = %s",
            (session_id,),
        )
    except Exception as exc:
        logger.warning("Result provider job %s failed: %s", job_id, type(exc).__name__)
        connection.execute(
            """UPDATE jobs SET status='failed',error_code=%s,error_message=%s,
                      finished_at=now() WHERE id=%s""",
            (type(exc).__name__, "Result provider execution failed", job_id),
        )
        append_event(
            connection, "JOB_FAILED", "commander-worker", status="failed",
            session_id=session_id, job_id=job_id,
            payload={"error_type": type(exc).__name__, "stage": "RESULT_PROVIDER"},
        )
        connection.execute(
            "UPDATE sessions SET status = 'failed', updated_at = now() WHERE id = %s",
            (session_id,),
        )
    heartbeat(connection)
    connection.commit()
    return True


def main() -> None:
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    poll_seconds = max(1, int(os.getenv("WORKER_POLL_SECONDS", "2")))
    logger.info("Commander worker started")
    while running:
        try:
            with psycopg.connect(database_url(secrets), connect_timeout=3) as connection:
                worked = process_one(connection)
        except Exception as exc:
            worked = False
            logger.warning("Worker cycle failed: %s", type(exc).__name__)
        if not worked:
            time.sleep(poll_seconds)
    logger.info("Commander worker stopped")


if __name__ == "__main__":
    main()
