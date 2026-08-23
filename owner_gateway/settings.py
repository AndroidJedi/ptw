from __future__ import annotations

from dataclasses import dataclass
import ipaddress
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
    positioning_database_url: str
    positioning_service_url: str
    positioning_service_token: str
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
    firebase_landing_site_id: str = ""
    firebase_landing_service_account_path: Path | None = None
    landing_output_root: Path = Path("/var/lib/ptw-owner/landings")
    landing_llm_bridge_url: str = ""
    landing_llm_model: str = "codex-cli-default"
    landing_lead_api_base_url: str = "https://commander.proove-them-wrong.com/api/v1/public/landings"
    landing_public_origins: tuple[str, ...] = ()
    landing_lead_hmac_secret: str = ""
    landing_trusted_proxy_networks: tuple[str, ...] = ()

    @classmethod
    def from_environment(cls) -> "Settings":
        required = {
            name: os.environ.get(name, "").strip()
            for name in (
                "FIREBASE_OWNER_UID", "POSITIONING_DATABASE_URL", "COMMANDER_DATABASE_URL",
                "PLATFORM_DATABASE_URL", "PLATFORM_OWNER_TELEGRAM_ID", "OWNER_GATEWAY_BRIDGE_TOKEN",
                "LANDING_LEAD_HMAC_SECRET",
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
        site_id = os.environ.get("FIREBASE_LANDING_SITE_ID", "natal-landings-86123").strip()
        configured_origins = tuple(
            value.strip().rstrip("/")
            for value in os.environ.get("LANDING_PUBLIC_ORIGINS", "").split(",")
            if value.strip()
        )
        landing_origins = configured_origins or (
            f"https://{site_id}.web.app", f"https://{site_id}.firebaseapp.com",
        )
        lead_base = os.environ.get(
            "LANDING_LEAD_API_BASE_URL",
            "https://commander.proove-them-wrong.com/api/v1/public/landings",
        ).strip().rstrip("/")
        if not lead_base.startswith("https://"):
            raise RuntimeError("LANDING_LEAD_API_BASE_URL must be HTTPS")
        proxy_networks = tuple(
            value.strip() for value in os.environ.get(
                "LANDING_TRUSTED_PROXY_NETWORKS", "127.0.0.0/8,::1/128"
            ).split(",") if value.strip()
        )
        try:
            for network in proxy_networks:
                ipaddress.ip_network(network, strict=False)
        except ValueError as error:
            raise RuntimeError("LANDING_TRUSTED_PROXY_NETWORKS contains an invalid CIDR") from error
        firebase_project_id = os.environ.get("FIREBASE_PROJECT_ID", "provethemwrong-86123")
        public_origin = os.environ.get(
            "OWNER_WEB_ORIGIN", f"https://{firebase_project_id}.firebaseapp.com"
        ).rstrip("/")
        configured_owner_origins = tuple(
            value.strip().rstrip("/")
            for value in os.environ.get("OWNER_WEB_ORIGINS", "").split(",")
            if value.strip()
        )
        owner_origins = configured_owner_origins or (
            f"https://{firebase_project_id}.firebaseapp.com",
            f"https://{firebase_project_id}.web.app",
        )
        return cls(
            firebase_project_id=firebase_project_id,
            firebase_app_id=os.environ.get("FIREBASE_APP_ID", "1:463396258702:web:e52325c94f477ede1c9adf"),
            owner_email=os.environ.get("FIREBASE_OWNER_EMAIL", "sgolovaschuk@gmail.com").lower(),
            owner_uid=required["FIREBASE_OWNER_UID"],
            service_account_path=Path(credential) if credential else None,
            positioning_database_url=required["POSITIONING_DATABASE_URL"],
            positioning_service_url=os.environ.get("POSITIONING_SERVICE_URL", "http://ptw-positioning-api:8080").rstrip("/"),
            positioning_service_token=required["OWNER_GATEWAY_BRIDGE_TOKEN"],
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
            owner_public_origins=owner_origins,
            telegram_bot_token=os.environ.get("TELEGRAM_BOT_TOKEN", "").strip(),
            commander_service_url=os.environ.get("COMMANDER_SERVICE_URL", "http://ptw-commander-api:8080").rstrip("/"),
            firebase_landing_site_id=site_id,
            firebase_landing_service_account_path=(
                Path(os.environ["FIREBASE_LANDING_SERVICE_ACCOUNT_PATH"])
                if os.environ.get("FIREBASE_LANDING_SERVICE_ACCOUNT_PATH", "").strip() else None
            ),
            landing_output_root=Path(os.environ.get("NATAL_LANDING_OUTPUT_ROOT", "/var/lib/ptw-owner/landings")),
            landing_llm_bridge_url=os.environ.get(
                "LANDING_LLM_BRIDGE_URL",
                "http://ptw-agent-platform-commander-api-1:8000/internal/llm/structured",
            ).strip().rstrip("/"),
            landing_llm_model=os.environ.get("LANDING_LLM_MODEL", "codex-cli-default").strip(),
            landing_lead_api_base_url=lead_base,
            landing_public_origins=landing_origins,
            landing_lead_hmac_secret=required["LANDING_LEAD_HMAC_SECRET"],
            landing_trusted_proxy_networks=proxy_networks,
        )
