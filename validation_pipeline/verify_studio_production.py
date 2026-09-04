"""Safe production canary for the authenticated, restart-safe Studio authority."""

from __future__ import annotations

import json
import os
import urllib.request
from uuid import UUID


def main() -> None:
    token = os.environ.get("OWNER_GATEWAY_BRIDGE_TOKEN", "").strip()
    if not token:
        raise SystemExit("owner gateway bridge token is unavailable")
    request = urllib.request.Request(
        "http://127.0.0.1:8080/internal/v1/studio",
        headers={"X-PTW-Owner-Gateway-Token": token},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        value = json.loads(response.read())
    workspace_id = str(UUID(str(value["workspace_id"])))
    state_sha256 = str(value["state_sha256"])
    if (
        value.get("schema") != "ptw.studio.workspace.v8"
        or value.get("template_id") not in {"universal_ad", "phone_metrics"}
        or len(state_sha256) != 64
        or value.get("phone_screen_generation_available") is not True
    ):
        raise SystemExit("production Studio contract is unavailable")
    print(json.dumps({
        "status": "ok",
        "workspace_id": workspace_id,
        "state_sha256": state_sha256,
        "template_id": value["template_id"],
        "phone_screen_history_count": len(value.get("phone_screen_history", [])),
        "version_count": len(value.get("versions", [])),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
