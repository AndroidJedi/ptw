from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from urllib.parse import urlsplit


def _ids(value: str) -> frozenset[int]:
    return frozenset(int(item.strip()) for item in value.split(",") if item.strip())


@dataclass(frozen=True, slots=True)
class Settings:
    firebase_project_id: str
    firebase_app_id: str
    owner_email: str
    owner_uid: str
    service_account_path: Path | None
    validation_database_url: str
    validation_service_url: str
    validation_service_token: str
    commander_database_url: str
    platform_database_url: str
    platform_owner_telegram_id: int
    owner_chat_id: int
    telegram_allowed_chat_ids: frozenset[int]
    control_database_path: Path
    repository_path: Path
    codex_executable: str
    root_broker_socket: Path
    public_origin: str
    owner_public_origins: tuple[str, ...] = ()
    telegram_bot_token: str = ""
    commander_service_url: str = "http://ptw-commander-api:8080"

    @classmethod
    def from_environment(cls) -> "Settings":
        required = {
            name: os.environ.get(name, "").strip()
            for name in (
                "FIREBASE_OWNER_UID", "VALIDATION_DATABASE_URL", "COMMANDER_DATABASE_URL",
                "PLATFORM_DATABASE_URL", "PLATFORM_OWNER_TELEGRAM_ID", "OWNER_GATEWAY_BRIDGE_TOKEN",
            )
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise RuntimeError(f"missing owner gateway settings: {', '.join(missing)}")
        platform_database = urlsplit(required["PLATFORM_DATABASE_URL"])
        if platform_database.scheme.startswith("postgres") and not platform_database.password:
            raise RuntimeError("PLATFORM_DATABASE_URL must include a database password")
        credential = os.environ.get("FIREBASE_SERVICE_ACCOUNT_PATH", "").strip()
        owner_chat = int(os.environ.get("TELEGRAM_OWNER_CHAT_ID", required["PLATFORM_OWNER_TELEGRAM_ID"]))
        allowed = _ids(os.environ.get("TELEGRAM_ALLOWED_CHAT_IDS", ""))
        if owner_chat not in allowed:
            raise RuntimeError("TELEGRAM_OWNER_CHAT_ID must be in the existing TELEGRAM_ALLOWED_CHAT_IDS")
        firebase_project_id = os.environ.get("FIREBASE_PROJECT_ID", "provethemwrong-86123")
        public_origin = os.environ.get(
            "OWNER_WEB_ORIGIN", f"https://{firebase_project_id}.firebaseapp.com"
        ).rstrip("/")
        configured_origins = tuple(
            value.strip().rstrip("/")
            for value in os.environ.get("OWNER_WEB_ORIGINS", "").split(",")
            if value.strip()
        )
        origins = configured_origins or (
            f"https://{firebase_project_id}.firebaseapp.com",
            f"https://{firebase_project_id}.web.app",
        )
        return cls(
            firebase_project_id=firebase_project_id,
            firebase_app_id=os.environ.get("FIREBASE_APP_ID", "1:463396258702:web:e52325c94f477ede1c9adf"),
            owner_email=os.environ.get("FIREBASE_OWNER_EMAIL", "sgolovaschuk@gmail.com").lower(),
            owner_uid=required["FIREBASE_OWNER_UID"],
            service_account_path=Path(credential) if credential else None,
            validation_database_url=required["VALIDATION_DATABASE_URL"],
            validation_service_url=os.environ.get(
                "VALIDATION_SERVICE_URL", "http://ptw-validation-api:8080"
            ).rstrip("/"),
            validation_service_token=required["OWNER_GATEWAY_BRIDGE_TOKEN"],
            commander_database_url=required["COMMANDER_DATABASE_URL"],
            platform_database_url=required["PLATFORM_DATABASE_URL"],
            platform_owner_telegram_id=int(required["PLATFORM_OWNER_TELEGRAM_ID"]),
            owner_chat_id=owner_chat,
            telegram_allowed_chat_ids=allowed,
            control_database_path=Path(os.environ.get("OWNER_CONTROL_DATABASE", "/var/lib/ptw-owner/control.sqlite3")),
            repository_path=Path(os.environ.get("PTW_REPOSITORY_PATH", "/root/ptw")),
            codex_executable=os.environ.get("CODEX_EXECUTABLE", "/opt/ptw-codex/bin/codex"),
            root_broker_socket=Path(os.environ.get("ROOT_BROKER_SOCKET", "/run/ptw-root-broker/control.sock")),
            public_origin=public_origin,
            owner_public_origins=origins,
            telegram_bot_token=os.environ.get("TELEGRAM_BOT_TOKEN", "").strip(),
            commander_service_url=os.environ.get(
                "COMMANDER_SERVICE_URL", "http://ptw-commander-api:8080"
            ).rstrip("/"),
        )
