import logging
import os
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

import httpx
import psycopg
from psycopg.types.json import Jsonb

from common.database import database_url
from common.events import append_event
from common.secrets import EnvironmentSecretStore
from common.telegram import send_telegram as send_telegram_message
from engineering.service import execute_engineering_job
from engineering.issues import create_issue, render_reference, transition_issue
from engineering.runner import JobCancelled, StageFailure

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


def command_available(command: str) -> bool:
    executable = shutil.which(command)
    if not executable:
        return False
    try:
        subprocess.run(
            [executable, "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=3, check=False,
        )
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def codex_available() -> bool:
    """Detect Codex directly or via host-generated, read-only metadata."""
    if command_available("codex"):
        return True
    metadata = Path(os.getenv("CODEX_METADATA_FILE", "/run/ptw-host/codex-version"))
    try:
        return metadata.is_file() and metadata.read_text(encoding="utf-8").startswith("codex-cli ")
    except OSError:
        return False


def status_response(connection: psycopg.Connection) -> str:
    checks: dict[str, bool] = {}
    try:
        response = httpx.get("http://commander-api:8000/health/ready", timeout=3)
        checks["Commander"] = response.status_code == 200
    except httpx.HTTPError:
        checks["Commander"] = False
    checks["Worker"] = True
    try:
        connection.execute("SELECT 1")
        checks["PostgreSQL"] = True
    except psycopg.Error:
        checks["PostgreSQL"] = False
    checks["Git"] = command_available("git")
    checks["Codex"] = codex_available()
    usage = shutil.disk_usage(Path("/"))
    checks["Disk"] = usage.free >= 512 * 1024 * 1024
    queued = connection.execute("SELECT count(*) FROM jobs WHERE status = 'queued'").fetchone()[0]
    failed = connection.execute("SELECT count(*) FROM jobs WHERE status = 'failed'").fetchone()[0]
    blocked = connection.execute("SELECT count(*) FROM jobs WHERE status = 'blocked'").fetchone()[0]
    issues = connection.execute(
        "SELECT count(*) FROM engineering_issues WHERE status IN ('open','resolving','unresolved')"
    ).fetchone()[0]
    lines = ["PTW Commander v0.1"]
    lines.extend(f"{name:<14}{'✅' if ok else '❌'}" for name, ok in checks.items())
    lines.extend((f"Queued jobs: {queued}", f"Blocked jobs: {blocked}",
                  f"Failed jobs: {failed}", f"Open/unresolved issues: {issues}"))
    return "\n".join(lines)


def execute_job(connection: psycopg.Connection, job_type: str, job_id: int | None = None,
                parameters: dict | None = None, reporter=None) -> str | dict:
    if job_type == "ping":
        return "pong"
    if job_type == "version":
        return "PTW Commander v0.1"
    if job_type == "help":
        return "PTW Commander v0.7\n/task <request> - freely describe a fix, implementation, or change\n/task from <hypothesis-id> <request> - execute with sourced product/design/engineering research\n/inspect TASK-<id>|ISSUE-<id> - inspect task state, issue details, and logs\n/cancel [job-id] - interrupt your latest queued, running, or blocked task\n/research <creative|product|design|engineering> <topic> - run an owned research agent\n/graph hypotheses - inspect hypotheses and source IDs\n/graph weights - inspect learned component weights\n/creative from <hypothesis-id> - generate from creative research\n/creative <hook> | <caption> | <CTA> - generate an Instagram Story directly\n/feedback <creative-id> <1-5> [comment] - rate a creative (or reply to its image)\n/engineer repo=ptw <task> - compatibility alias for engineering tasks\n/ping - test job execution\n/status - dependency status\n/version - show version\n/help - show commands"
    if job_type == "status":
        return status_response(connection)
    if job_type == "inspect" and parameters is not None:
        if not parameters.get("task"):
            raise ValueError("usage: /inspect TASK-<id> or /inspect ISSUE-<id>")
        return render_reference(connection, parameters["task"])
    if job_type == "engineer" and job_id is not None and parameters is not None:
        return execute_engineering_job(connection, job_id, parameters, reporter=reporter)
    if job_type == "llm_structured" and parameters is not None:
        return execute_structured_llm(parameters)
    raise ValueError(f"Unsupported job type: {job_type}")

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


def _persist_brand_image(codex_home: Path, session_id: str) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9-]{1,100}", session_id):
        raise RuntimeError("image generation returned an invalid session ID")
    generated_root = (codex_home / "generated_images").resolve()
    session_directory = (generated_root / session_id).resolve()
    if generated_root not in session_directory.parents:
        raise RuntimeError("image generation resolved outside its temporary root")
    try:
        images = sorted(path for path in session_directory.glob("*.png") if path.is_file())
        if len(images) != 1:
            raise RuntimeError("Branding image generation must return exactly one PNG")
        content = images[0].read_bytes()
        if len(content) < 33 or len(content) > 10_000_000 or not content.startswith(b"\x89PNG\r\n\x1a\n"):
            raise RuntimeError("Branding image generation returned an invalid PNG")
        width = struct.unpack(">I", content[16:20])[0]
        height = struct.unpack(">I", content[20:24])[0]
        if width != height or not 512 <= width <= 2048:
            raise RuntimeError("Branding image generation must return a bounded square image")
        digest = hashlib.sha256(content).hexdigest()
        asset_root = Path(
            os.environ.get("BRAND_PROVIDER_ASSET_DIR", "/var/lib/ptw/assets/brand-provider")
        ).resolve()
        destination_directory = asset_root / digest[:2]
        destination_directory.mkdir(mode=0o750, parents=True, exist_ok=True)
        destination = destination_directory / f"{digest}.png"
        if destination.exists():
            if hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
                raise RuntimeError("immutable Branding provider asset digest collision")
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
            "path": str(destination),
            "mime_type": "image/png",
            "width": width,
            "height": height,
            "requested_model": "gpt-image-2",
            "resolved_model": "gpt-image-2",
            "provider": "codex_chatgpt_imagegen",
            "request_id": session_id,
        }
    finally:
        if session_directory.is_dir():
            shutil.rmtree(session_directory)


def _validate_brand_reference(parameters: dict) -> dict | None:
    if parameters.get("mode") != "branding_logo_reference_edit":
        return None
    payload = parameters.get("input_payload") or {}
    path = Path(str(payload.get("source_path") or "")).resolve()
    root = Path(os.environ.get("BRAND_SHARED_ASSET_ROOT", "/var/lib/ptw/assets")).resolve()
    if path == root or root not in path.parents or path.suffix.lower() != ".png":
        raise RuntimeError("Branding reference image is outside the shared asset volume")
    content = path.read_bytes() if path.is_file() else b""
    digest = hashlib.sha256(content).hexdigest() if content else ""
    if (
        not content.startswith(b"\x89PNG\r\n\x1a\n")
        or digest != payload.get("source_digest")
        or len(content) > 10_000_000
    ):
        raise RuntimeError("Branding reference image failed PNG or digest validation")
    width = struct.unpack(">I", content[16:20])[0]
    height = struct.unpack(">I", content[20:24])[0]
    if width != height or not 512 <= width <= 2048:
        raise RuntimeError("Branding reference image must be a bounded square PNG")
    return {"source_path": str(path), "source_digest": digest}


def _prove_brand_reference(stdout: str, reference: dict | None) -> dict | None:
    if reference is None:
        return None
    path = reference["source_path"]
    matching = []
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
        referenced = (
            arguments.get("referenced_image_paths")
            if isinstance(arguments, dict) else None
        )
        if isinstance(referenced, list) and referenced == [path]:
            matching.append(json.dumps(event, sort_keys=True, separators=(",", ":")))
    if not matching:
        raise RuntimeError("Branding image trace did not supply the exact reference path")
    return {
        **reference,
        "used": True,
        "trace_digest": hashlib.sha256("\n".join(matching).encode()).hexdigest(),
    }


def execute_structured_llm(parameters: dict) -> dict:
    """Run one schema-bound Codex invocation with no reusable conversation state."""
    codex_home = Path(os.environ.get("CODEX_HOME", "/tmp/ptw-codex"))
    codex_home.mkdir(mode=0o700, parents=True, exist_ok=True)
    mounted = Path("/run/ptw-codex-auth/auth.json")
    runtime = codex_home / "auth.json"
    if mounted.is_file() and not runtime.exists():
        shutil.copyfile(mounted, runtime)
        runtime.chmod(0o600)

    reference = _validate_brand_reference(parameters)
    prompt = (
        parameters["system_prompt"].strip()
        + "\n\nReturn only one JSON object matching the supplied schema."
        + "\nINPUT_PAYLOAD:\n"
        + json.dumps(parameters["input_payload"], ensure_ascii=False, sort_keys=True)
    )
    with tempfile.TemporaryDirectory(prefix="ptw-llm-") as directory:
        output = Path(directory) / "result.json"
        schema = Path(directory) / "output-schema.json"
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
        if parameters.get("mode") in {"branding_logo_generation", "branding_logo_reference_edit"}:
            result["image"] = _persist_brand_image(codex_home, session_id)
            reference_trace = _prove_brand_reference(completed.stdout, reference)
            if reference_trace is not None:
                result["image"]["reference"] = reference_trace
        return result


def send_telegram(parameters: dict, text: str) -> None:
    send_telegram_message(parameters["chat_id"], text,
                          reply_to_message_id=parameters.get("reply_to_message_id"))


def process_one(connection: psycopg.Connection) -> bool:
    awaiting = connection.execute(
        """SELECT id,session_id,parameters FROM jobs
           WHERE status='awaiting_ack' ORDER BY created_at,id
           FOR UPDATE SKIP LOCKED LIMIT 1"""
    ).fetchone()
    if awaiting:
        job_id, session_id, parameters = awaiting
        scope = str(parameters.get("task", ""))
        send_telegram(
            parameters,
            f"Accepted job #{job_id}. I understood the task as:\n{scope}\n\n"
            f"Work is queued and will start automatically. Cancel with /cancel {job_id}.",
        )
        connection.execute("UPDATE jobs SET status='queued' WHERE id=%s", (job_id,))
        append_event(
            connection, "ACKNOWLEDGEMENT_SENT", "commander-worker", status="sent",
            session_id=session_id, job_id=job_id,
            payload={"channel": "telegram", "source": "codex_workspace"},
        )
        connection.commit()
        return True
    job = connection.execute(
        """
        SELECT id, session_id, type, parameters FROM jobs
        WHERE status = 'queued' ORDER BY created_at, id
        FOR UPDATE SKIP LOCKED LIMIT 1
        """
    ).fetchone()
    if not job:
        heartbeat(connection)
        connection.commit()
        return False
    job_id, session_id, job_type, parameters = job
    connection.execute(
        "UPDATE jobs SET status = 'running', started_at = now() WHERE id = %s", (job_id,)
    )
    append_event(
        connection, "JOB_STARTED", "commander-worker", status="running",
        session_id=session_id, job_id=job_id, payload={"job_type": job_type},
    )
    connection.commit()
    try:
        if job_type == "engineer":
            send_telegram(parameters, f"TASK-{job_id} started. Stage and issue updates will be reported automatically. Use /inspect TASK-{job_id} at any time.")
        result = execute_job(
            connection, job_type, job_id, parameters,
            reporter=lambda update: send_telegram(parameters, update),
        )
        if job_type != 'llm_structured':
            send_telegram(parameters, result)
            stored_result = {"response": result}
        else:
            stored_result = result
        connection.execute(
            "UPDATE jobs SET status = 'completed', result = %s, finished_at = now() WHERE id = %s",
            (Jsonb(stored_result), job_id),
        )
        if job_type != 'llm_structured': append_event(
            connection, "JOB_COMPLETED", "commander-worker", status="completed",
            session_id=session_id, job_id=job_id, payload={"job_type": job_type},
        )
        append_event(
            connection, "RESPONSE_SENT", "commander-worker", status="sent",
            session_id=session_id, job_id=job_id, payload={"channel": "telegram"},
        )
        connection.execute(
            "UPDATE sessions SET status = 'completed', updated_at = now() WHERE id = %s",
            (session_id,),
        )
    except JobCancelled:
        connection.execute("UPDATE jobs SET status='cancelled', finished_at=now() WHERE id=%s", (job_id,))
        append_event(connection, "JOB_CANCELLED", "commander-worker", status="cancelled",
                     session_id=session_id, job_id=job_id)
        connection.execute("UPDATE sessions SET status='cancelled', updated_at=now() WHERE id=%s", (session_id,))
        send_telegram(parameters, f"Engineering job #{job_id} cancelled.")
    except Exception as exc:
        logger.warning("Job %s failed: %s", job_id, type(exc).__name__)
        stage = exc.stage if isinstance(exc, StageFailure) else "EXECUTION"
        existing_issue = connection.execute(
            """SELECT id FROM engineering_issues WHERE job_id=%s
               AND status IN ('open','resolving','unresolved') ORDER BY id DESC LIMIT 1""",
            (job_id,),
        ).fetchone()
        issue_id = existing_issue[0] if existing_issue else create_issue(
            connection, job_id=job_id, stage=stage, error=exc
        )
        if not existing_issue:
            transition_issue(
                connection, issue_id, "unresolved",
                summary="Failure occurred outside a safely resumable stage; manual interference is required",
            )
        connection.execute(
            """
            UPDATE jobs SET status = 'failed', error_code = %s, error_message = %s,
                            finished_at = now() WHERE id = %s
            """,
            (type(exc).__name__, f"ISSUE-{issue_id}: inspect the retained sanitized issue log", job_id),
        )
        append_event(
            connection, "JOB_FAILED", "commander-worker", status="failed",
            session_id=session_id, job_id=job_id,
            payload={"error_type": type(exc).__name__, "issue_id": issue_id, "stage": stage},
        )
        if isinstance(exc, StageFailure):
            connection.execute(
                "UPDATE engineering_runs SET status='failed',failure_stage=%s,updated_at=now() WHERE job_id=%s",
                (exc.stage, job_id),
            )
        connection.execute(
            "UPDATE sessions SET status = 'failed', updated_at = now() WHERE id = %s",
            (session_id,),
        )
        try:
            if job_type != 'llm_structured': send_telegram(
                parameters,
                f"TASK-{job_id} failed during {stage}; ISSUE-{issue_id} is retained as unresolved. "
                f"No changes were deployed. Inspect with /inspect ISSUE-{issue_id}.",
            )
        except Exception as notification_error:
            logger.warning(
                "Job %s failure notification failed: %s",
                job_id,
                type(notification_error).__name__,
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
