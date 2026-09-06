from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    firebase_project_id: str
    firebase_app_id: str
    owner_email: str
    owner_uid: str
    service_account_path: Path | None
    validation_service_url: str
    validation_service_token: str
    public_origin: str
    owner_public_origins: tuple[str, ...] = ()
    codex_authorization_service_url: str = ""
    codex_authorization_bridge_token: str = ""

    @classmethod
    def from_environment(cls) -> "Settings":
        owner_uid = os.environ.get("FIREBASE_OWNER_UID", "").strip()
        token = os.environ.get("OWNER_GATEWAY_BRIDGE_TOKEN", "").strip()
        codex_authorization_token = os.environ.get("PTW_CODEX_AUTH_BRIDGE_TOKEN", "").strip()
        missing = [
            name for name, value in (
                ("FIREBASE_OWNER_UID", owner_uid),
                ("OWNER_GATEWAY_BRIDGE_TOKEN", token),
                ("PTW_CODEX_AUTH_BRIDGE_TOKEN", codex_authorization_token),
            ) if not value
        ]
        if missing:
            raise RuntimeError(f"missing owner gateway settings: {', '.join(missing)}")
        credential = os.environ.get("FIREBASE_SERVICE_ACCOUNT_PATH", "").strip()
        firebase_project_id = os.environ.get("FIREBASE_PROJECT_ID", "provethemwrong-86123")
        public_origin = os.environ.get(
            "OWNER_WEB_ORIGIN", f"https://{firebase_project_id}.firebaseapp.com"
        ).rstrip("/")
        configured = tuple(
            value.strip().rstrip("/")
            for value in os.environ.get("OWNER_WEB_ORIGINS", "").split(",")
            if value.strip()
        )
        origins = configured or (
            f"https://{firebase_project_id}.firebaseapp.com",
            f"https://{firebase_project_id}.web.app",
        )
        return cls(
            firebase_project_id=firebase_project_id,
            firebase_app_id=os.environ.get(
                "FIREBASE_APP_ID", "1:463396258702:web:e52325c94f477ede1c9adf"
            ),
            owner_email=os.environ.get(
                "FIREBASE_OWNER_EMAIL", "sgolovaschuk@gmail.com"
            ).lower(),
            owner_uid=owner_uid,
            service_account_path=Path(credential) if credential else None,
            validation_service_url=os.environ.get(
                "VALIDATION_SERVICE_URL", "http://ptw-validation-api:8080"
            ).rstrip("/"),
            validation_service_token=token,
            public_origin=public_origin,
            owner_public_origins=origins,
            codex_authorization_service_url=os.environ.get(
                "PTW_CODEX_AUTH_SERVICE_URL", "http://codex-auth:8094"
            ).rstrip("/"),
            codex_authorization_bridge_token=codex_authorization_token,
        )
