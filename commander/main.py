"""Result-only structured bridge and emergency Telegram poller."""

from __future__ import annotations

import asyncio
import base64
import binascii
from contextlib import asynccontextmanager
import hashlib
import hmac
import json
import logging
import os
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import Response
import httpx
import psycopg
from psycopg.types.json import Jsonb

from common.database import apply_migrations, database_url
from common.events import append_event
from common.secrets import EnvironmentSecretStore


logging.basicConfig(
    level=os.getenv("PTW_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("ptw.commander")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
secrets = EnvironmentSecretStore()

EMERGENCY_COMMANDS = frozenset({"/help", "/status", "/stop"})
JSON_MODES = frozenset({
    "product_brief", "product_brief_revision", "content_candidate_generation",
    "content_result_critic",
})
MEDIA_MODES = frozenset({"content_non_human_graphic_generation"})
STRUCTURED_LLM_MODES = frozenset(JSON_MODES | MEDIA_MODES)
MAX_STRUCTURED_LLM_REQUEST_BYTES = 12_000_000
MAX_CRITIC_IMAGE_BYTES = 1_500_000
MAX_CRITIC_TOTAL_IMAGE_BYTES = 8 * 1024 * 1024
MAX_MEDIA_REFERENCE_BYTES = 8 * 1024 * 1024


def validate_structured_llm_request(request: dict) -> None:
    if request.get("mode") not in STRUCTURED_LLM_MODES:
        raise ValueError("unsupported structured LLM mode")
    if (
        not isinstance(request.get("system_prompt"), str)
        or not request["system_prompt"].strip()
        or not isinstance(request.get("input_payload"), dict)
        or not isinstance(request.get("output_schema"), dict)
    ):
        raise ValueError("invalid structured LLM request")
    for field in ("prompt_template_version", "context_hash", "model"):
        if field in request and not isinstance(request[field], str):
            raise ValueError("invalid structured LLM request")
    idempotency_key = request.get("idempotency_key")
    if (
        not isinstance(idempotency_key, str)
        or not 1 <= len(idempotency_key) <= 240
        or any(ord(character) < 33 or ord(character) > 126 for character in idempotency_key)
    ):
        raise ValueError("invalid structured LLM request")
    images = request.get("input_images")
    if request["mode"] == "content_result_critic":
        if not isinstance(images, list) or not 1 <= len(images) <= 5:
            raise ValueError("Result critic requires one to five mapped JPEG attachments")
        total = 0
        candidates: set[str] = set()
        for image in images:
            if not isinstance(image, dict) or set(image) != {
                "candidate_id", "mime_type", "digest", "width", "height", "bytes_base64",
            }:
                raise ValueError("invalid Result critic attachment mapping")
            if image["mime_type"] != "image/jpeg" or image["width"] != 1080 or image["height"] != 1080:
                raise ValueError("Result critic attachments must be 1080x1080 JPEGs")
            candidate_id = image["candidate_id"]
            if not isinstance(candidate_id, str) or candidate_id in candidates:
                raise ValueError("Result critic candidate mappings must be unique")
            candidates.add(candidate_id)
            try:
                content = base64.b64decode(image["bytes_base64"], validate=True)
            except (TypeError, ValueError, binascii.Error) as error:
                raise ValueError("Result critic attachment base64 is invalid") from error
            digest = hashlib.sha256(content).hexdigest()
            if (
                not content.startswith(b"\xff\xd8")
                or not content.endswith(b"\xff\xd9")
                or not 1 <= len(content) <= MAX_CRITIC_IMAGE_BYTES
                or image["digest"] != digest
            ):
                raise ValueError("Result critic attachment bytes or digest are invalid")
            total += len(content)
        if total > MAX_CRITIC_TOTAL_IMAGE_BYTES:
            raise ValueError("Result critic attachments exceed the aggregate limit")
    elif request["mode"] == "content_non_human_graphic_generation":
        if images is not None:
            if not isinstance(images, list) or len(images) != 1:
                raise ValueError("non-human graphic generation accepts at most one PNG reference")
            image = images[0]
            if not isinstance(image, dict) or set(image) != {
                "mime_type", "digest", "width", "height", "bytes_base64",
            }:
                raise ValueError("invalid non-human graphic reference mapping")
            try:
                content = base64.b64decode(image["bytes_base64"], validate=True)
            except (TypeError, ValueError, binascii.Error) as error:
                raise ValueError("non-human graphic reference base64 is invalid") from error
            digest = hashlib.sha256(content).hexdigest()
            if (
                image["mime_type"] != "image/png"
                or not content.startswith(b"\x89PNG\r\n\x1a\n")
                or not 33 <= len(content) <= MAX_MEDIA_REFERENCE_BYTES
                or image["digest"] != digest
                or not isinstance(image["width"], int)
                or not isinstance(image["height"], int)
                or image["width"] != image["height"]
                or not 512 <= image["width"] <= 2048
                or int.from_bytes(content[16:20], "big") != image["width"]
                or int.from_bytes(content[20:24], "big") != image["height"]
            ):
                raise ValueError("non-human graphic reference bytes or dimensions are invalid")
    elif images is not None:
        raise ValueError("only critic and media modes accept input images")
    if len(json.dumps(request, ensure_ascii=False).encode("utf-8")) > MAX_STRUCTURED_LLM_REQUEST_BYTES:
        raise ValueError("structured LLM request is too large")


def structured_llm_capabilities() -> dict:
    return {
        "json_modes": sorted(JSON_MODES), "media_modes": sorted(MEDIA_MODES),
        "max_request_bytes": MAX_STRUCTURED_LLM_REQUEST_BYTES,
    }


def allowed_user_ids() -> set[int]:
    raw = os.getenv("TELEGRAM_ALLOWED_USER_IDS", "")
    try:
        return {int(value.strip()) for value in raw.split(",") if value.strip()}
    except ValueError as error:
        raise RuntimeError("TELEGRAM_ALLOWED_USER_IDS must contain numeric IDs") from error


def normalized_command(text: str) -> str:
    first = text.strip().split(maxsplit=1)[0].lower() if text.strip() else ""
    return first.split("@", maxsplit=1)[0]


async def telegram_loop() -> None:
    """Forward authorized updates to the app's emergency-only Telegram boundary."""
    token = secrets.get("TELEGRAM_BOT_TOKEN")
    telegram_url = f"https://api.telegram.org/bot{token}"
    application_url = os.getenv(
        "CREATIVE_SERVICE_URL", "http://ptw-commander-api:8080/internal/telegram/update",
    )
    offset = 0
    async with httpx.AsyncClient(timeout=40) as client:
        while True:
            try:
                response = await client.get(
                    f"{telegram_url}/getUpdates",
                    params={"timeout": 30, "offset": offset, "allowed_updates": '["message"]'},
                )
                response.raise_for_status()
                for update in response.json().get("result", []):
                    offset = max(offset, int(update["update_id"]) + 1)
                    message = update.get("message")
                    if not isinstance(message, dict):
                        continue
                    user_id = (message.get("from") or {}).get("id")
                    chat_id = (message.get("chat") or {}).get("id")
                    if user_id not in allowed_user_ids() or not chat_id:
                        continue
                    try:
                        forwarded = await client.post(
                            application_url, headers={"X-PTW-Bridge-Token": token},
                            json=update, timeout=15,
                        )
                        forwarded.raise_for_status()
                        text = str(forwarded.json()["result"]["response"])
                    except (httpx.HTTPError, KeyError, TypeError, ValueError):
                        logger.warning("Emergency Telegram boundary is temporarily unavailable")
                        text = "PTW emergency controls are temporarily unavailable. Use the Owner web console."
                    await client.post(
                        f"{telegram_url}/sendMessage", json={"chat_id": chat_id, "text": text},
                    )
            except asyncio.CancelledError:
                raise
            except Exception as error:
                logger.warning("Telegram polling failed: %s", type(error).__name__)
                await asyncio.sleep(5)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await asyncio.to_thread(apply_migrations)
    task = None
    if secrets.exists("TELEGRAM_BOT_TOKEN") and allowed_user_ids():
        task = asyncio.create_task(telegram_loop())
    else:
        logger.warning("Telegram integration disabled: token or allowlist is missing")
    try:
        yield
    finally:
        if task:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


app = FastAPI(
    title="PTW Result Bridge", version="1.0.0", docs_url=None, redoc_url=None, lifespan=lifespan,
)


def _authorize_bridge(token: str) -> None:
    if not hmac.compare_digest(token, secrets.get("TELEGRAM_BOT_TOKEN")):
        raise HTTPException(status_code=403, detail="invalid bridge token")


@app.post("/internal/llm/structured")
def enqueue_structured_llm(request: dict, x_ptw_bridge_token: str = Header(default="")) -> dict:
    _authorize_bridge(x_ptw_bridge_token)
    try:
        validate_structured_llm_request(request)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    owner = min(allowed_user_ids())
    with psycopg.connect(database_url(secrets)) as connection:
        connection.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (request["idempotency_key"],))
        existing = connection.execute(
            "SELECT id,status FROM jobs WHERE type='llm_structured' AND structured_idempotency_key=%s",
            (request["idempotency_key"],),
        ).fetchone()
        if existing:
            return {"request_id": existing[0], "status": existing[1], "deduplicated": True}
        user_id = connection.execute(
            """INSERT INTO users(telegram_user_id,role) VALUES(%s,'operator')
               ON CONFLICT(telegram_user_id) DO UPDATE SET role=users.role RETURNING id""", (owner,),
        ).fetchone()[0]
        session_id = connection.execute(
            "INSERT INTO sessions(user_id,status,summary) VALUES(%s,'active','Result provider request') RETURNING id",
            (user_id,),
        ).fetchone()[0]
        job_id = connection.execute(
            """INSERT INTO jobs(session_id,type,status,requested_by,parameters,structured_idempotency_key)
               VALUES(%s,'llm_structured','queued',%s,%s,%s) RETURNING id""",
            (session_id, user_id, Jsonb(request), request["idempotency_key"]),
        ).fetchone()[0]
    return {"request_id": job_id, "status": "queued"}


@app.get("/internal/llm/structured/capabilities")
def get_structured_llm_capabilities(x_ptw_bridge_token: str = Header(default="")) -> dict:
    _authorize_bridge(x_ptw_bridge_token)
    return structured_llm_capabilities()


@app.get("/internal/llm/structured/{job_id}")
def structured_llm_result(job_id: int, x_ptw_bridge_token: str = Header(default="")) -> dict:
    _authorize_bridge(x_ptw_bridge_token)
    with psycopg.connect(database_url(secrets)) as connection:
        row = connection.execute(
            "SELECT status,result,error_code FROM jobs WHERE id=%s AND type='llm_structured'", (job_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="unknown request")
    result = row[1]
    if isinstance(result, dict) and isinstance(result.get("image"), dict):
        result = dict(result)
        image = dict(result["image"])
        image.pop("path", None)
        image["asset_url"] = f"/internal/llm/structured/{job_id}/asset"
        result["image"] = image
    return {"status": row[0], "result": result, "error": row[2]}


@app.get("/internal/llm/structured/{job_id}/asset")
def structured_llm_asset(job_id: int, x_ptw_bridge_token: str = Header(default="")) -> Response:
    _authorize_bridge(x_ptw_bridge_token)
    with psycopg.connect(database_url(secrets)) as connection:
        row = connection.execute(
            "SELECT status,result FROM jobs WHERE id=%s AND type='llm_structured'", (job_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="unknown request")
    image = row[1].get("image") if row[0] == "completed" and isinstance(row[1], dict) else None
    if not isinstance(image, dict):
        raise HTTPException(status_code=404, detail="request has no generated asset")
    root = Path(os.getenv("CONTENT_GRAPHIC_ASSET_DIR", "/var/lib/ptw/assets/content-graphics")).resolve()
    path = Path(str(image.get("path") or "")).resolve()
    if root not in path.parents or path.suffix != ".png" or not path.is_file():
        raise HTTPException(status_code=404, detail="generated asset is unavailable")
    content = path.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    if digest != image.get("digest") or len(content) > 10_000_000:
        raise HTTPException(status_code=409, detail="generated asset failed integrity validation")
    return Response(
        content=content, media_type="image/png",
        headers={"ETag": f'"{digest}"', "Cache-Control": "private, immutable"},
    )


@app.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "ok", "service": "commander-api"}


@app.get("/health")
def public_health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
def ready() -> dict[str, str]:
    try:
        with psycopg.connect(database_url(secrets), connect_timeout=3) as connection:
            connection.execute("SELECT 1")
            append_event(
                connection, "HEALTH_CHECK", "commander-api", status="ready",
                payload={"check": "readiness"},
            )
    except Exception as error:
        logger.warning("Database readiness check failed: %s", type(error).__name__)
        raise HTTPException(status_code=503, detail="database unavailable") from error
    return {"status": "ready"}
