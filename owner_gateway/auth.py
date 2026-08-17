from __future__ import annotations

from dataclasses import dataclass
import hmac
from typing import Any

from fastapi import Header, HTTPException

from .settings import Settings


@dataclass(frozen=True, slots=True)
class OwnerIdentity:
    uid: str
    email: str


def validate_owner_claims(
    settings: Settings, claims: dict[str, Any], app_claims: dict[str, Any]
) -> OwnerIdentity:
    email = str(claims.get("email", "")).lower()
    uid = str(claims.get("uid") or claims.get("sub") or "")
    provider = str((claims.get("firebase") or {}).get("sign_in_provider", ""))
    app_id = str(app_claims.get("app_id") or "")
    if not bool(claims.get("email_verified")):
        raise HTTPException(status_code=403, detail="owner email must be verified")
    if provider != "google.com":
        raise HTTPException(status_code=403, detail="Google Sign-In is required")
    if not hmac.compare_digest(email, settings.owner_email):
        raise HTTPException(status_code=403, detail="owner email is not allowlisted")
    if not hmac.compare_digest(uid, settings.owner_uid):
        raise HTTPException(status_code=403, detail="owner UID does not match pinned UID")
    if not app_id or not hmac.compare_digest(app_id, settings.firebase_app_id):
        raise HTTPException(status_code=401, detail="invalid App Check app identity")
    return OwnerIdentity(uid=uid, email=email)


class FirebaseVerifier:
    def __init__(self, settings: Settings) -> None:
        import firebase_admin
        from firebase_admin import credentials

        options = {"projectId": settings.firebase_project_id}
        if not firebase_admin._apps:  # initialization is process-global in Admin SDK
            credential = credentials.Certificate(str(settings.service_account_path)) if settings.service_account_path else None
            firebase_admin.initialize_app(credential, options)
        self.settings = settings

    def verify(self, id_token: str, app_check_token: str) -> OwnerIdentity:
        from firebase_admin import app_check, auth

        if not id_token or not app_check_token:
            raise HTTPException(status_code=401, detail="Firebase ID token and App Check are required")
        try:
            claims: dict[str, Any] = auth.verify_id_token(id_token, check_revoked=True)
            app_claims = app_check.verify_token(app_check_token)
        except Exception as error:
            raise HTTPException(status_code=401, detail="invalid Firebase credentials") from error
        return validate_owner_claims(self.settings, claims, app_claims)


class OwnerDependency:
    def __init__(self, verifier: FirebaseVerifier) -> None:
        self.verifier = verifier

    def __call__(
        self,
        authorization: str = Header(default=""),
        x_firebase_appcheck: str = Header(default="", alias="X-Firebase-AppCheck"),
    ) -> OwnerIdentity:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(status_code=401, detail="Bearer token is required")
        return self.verifier.verify(token, x_firebase_appcheck)
