from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from urllib.parse import urlsplit


@dataclass(frozen=True, slots=True)
class Settings:
    firebase_project_id: str
    firebase_app_id: str
    owner_email: str
    owner_uid: str
    service_account_path: Path | None
    idea_database_url: str
    idea_service_url: str
    idea_service_token: str
    commander_database_url: str
    platform_database_url: str
    platform_owner_telegram_id: int
    owner_chat_id: int
    control_database_path: Path
    repository_path: Path
    codex_executable: str
    root_broker_socket: Path
    commander_asset_root: Path
    commander_policy_path: Path
    public_origin: str
    telegram_bot_token: str = ""
    commander_service_url: str = "http://ptw-commander-api:8080"

    @classmethod
    def from_environment(cls) -> "Settings":
        required = {
            name: os.environ.get(name, "").strip()
            for name in (
                "FIREBASE_OWNER_UID",
                "IDEA_DATABASE_URL",
                "COMMANDER_DATABASE_URL",
                "PLATFORM_DATABASE_URL",
                "PLATFORM_OWNER_TELEGRAM_ID",
            )
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise RuntimeError(f"missing owner gateway settings: {', '.join(missing)}")
        platform_database = urlsplit(required["PLATFORM_DATABASE_URL"])
        if platform_database.scheme.startswith("postgres") and not platform_database.password:
            raise RuntimeError("PLATFORM_DATABASE_URL must include a database password")
        credential = os.environ.get("FIREBASE_SERVICE_ACCOUNT_PATH", "").strip()
        return cls(
            firebase_project_id=os.environ.get("FIREBASE_PROJECT_ID", "provethemwrong-86123"),
            firebase_app_id=os.environ.get("FIREBASE_APP_ID", "1:463396258702:web:e52325c94f477ede1c9adf"),
            owner_email=os.environ.get("FIREBASE_OWNER_EMAIL", "sgolovaschuk@gmail.com").lower(),
            owner_uid=required["FIREBASE_OWNER_UID"],
            service_account_path=Path(credential) if credential else None,
            idea_database_url=required["IDEA_DATABASE_URL"],
            idea_service_url=os.environ.get("IDEA_SERVICE_URL", "http://ptw-idea-api:8080").rstrip("/"),
            idea_service_token=os.environ.get("OWNER_GATEWAY_BRIDGE_TOKEN", ""),
            commander_database_url=required["COMMANDER_DATABASE_URL"],
            platform_database_url=required["PLATFORM_DATABASE_URL"],
            platform_owner_telegram_id=int(required["PLATFORM_OWNER_TELEGRAM_ID"]),
            owner_chat_id=int(os.environ.get("TELEGRAM_OWNER_CHAT_ID", required["PLATFORM_OWNER_TELEGRAM_ID"])),
            control_database_path=Path(os.environ.get("OWNER_CONTROL_DATABASE", "/var/lib/ptw-owner/control.sqlite3")),
            repository_path=Path(os.environ.get("PTW_REPOSITORY_PATH", "/root/ptw")),
            codex_executable=os.environ.get("CODEX_EXECUTABLE", "/opt/ptw-codex/bin/codex"),
            root_broker_socket=Path(os.environ.get("ROOT_BROKER_SOCKET", "/run/ptw-root-broker/control.sock")),
            commander_asset_root=Path(os.environ.get("COMMANDER_ASSET_DIR", "/var/lib/ptw/assets")),
            commander_policy_path=Path(os.environ.get("COMMANDER_POLICY_PATH", "config/commander/policies.json")),
            public_origin=os.environ.get("OWNER_WEB_ORIGIN", "https://provethemwrong-86123.firebaseapp.com"),
            telegram_bot_token=os.environ.get("TELEGRAM_BOT_TOKEN", "").strip(),
            commander_service_url=os.environ.get(
                "COMMANDER_SERVICE_URL", "http://ptw-commander-api:8080"
            ).rstrip("/"),
        )
