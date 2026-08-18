#!/usr/bin/env python3
"""Audit PTW's public Owner Console boundary without owner credentials."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.parse import urljoin


DEFAULT_ORIGIN = "https://provethemwrong-86123.firebaseapp.com"
DEFAULT_API = "https://commander.proove-them-wrong.com"
DEFAULT_SITE_KEY = "6LfFjYstAAAAAJaFuUPZYS9U17vROLcN7Fx6iOQL"


def fetch(url: str, *, method: str = "GET", headers: dict[str, str] | None = None):
    with tempfile.TemporaryDirectory(prefix="ptw-owner-audit-") as temp_dir:
        header_path = Path(temp_dir, "headers")
        body_path = Path(temp_dir, "body")
        command = [
            "curl", "--silent", "--show-error", "--max-time", "20",
            "--request", method, "--dump-header", str(header_path),
            "--output", str(body_path), "--write-out", "%{http_code}",
        ]
        for name, value in (headers or {}).items():
            command.extend(["--header", f"{name}: {value}"])
        command.append(url)
        completed = subprocess.run(command, check=True, capture_output=True, text=True)
        status = int(completed.stdout)
        response_headers = {}
        for line in header_path.read_text().splitlines()[1:]:
            if ":" in line:
                name, value = line.split(":", 1)
                response_headers[name.strip()] = value.strip()
        return status, response_headers, body_path.read_bytes()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--origin", default=DEFAULT_ORIGIN)
    parser.add_argument("--api", default=DEFAULT_API)
    parser.add_argument("--site-key", default=DEFAULT_SITE_KEY)
    args = parser.parse_args()

    cache_bust = f"skill-audit-{int(time.time())}"
    status, _, document_bytes = fetch(f"{args.origin}/?{cache_bust}")
    require(status == 200, f"Owner document returned HTTP {status}")
    document = document_bytes.decode()
    main_match = re.search(r'src="([^"]*?/assets/index-[^"]+\.js)"', document)
    require(main_match is not None, "Unable to resolve the live entry bundle")
    main_url = urljoin(args.origin, main_match.group(1))

    status, _, main_bytes = fetch(main_url)
    require(status == 200, f"Entry bundle returned HTTP {status}")
    app_match = re.search(r'["\'](assets/App-[^"\']+\.js)["\']', main_bytes.decode())
    require(app_match is not None, "Unable to resolve the lazy App bundle")
    app_url = urljoin(f"{args.origin}/", app_match.group(1))

    status, _, app_bytes = fetch(app_url)
    require(status == 200, f"App bundle returned HTTP {status}")
    app_bundle = app_bytes.decode()
    for label, marker in {
        "Commander API origin": args.api,
        "App Check header": "X-Firebase-AppCheck",
        "reCAPTCHA Enterprise site key": args.site_key,
    }.items():
        require(marker in app_bundle, f"Live App bundle is missing {label}")

    status, _, worker_bytes = fetch(f"{args.origin}/sw.js?{cache_bust}")
    require(status == 200, f"Service worker returned HTTP {status}")
    cache_match = re.search(r"const CACHE = '([^']+)'", worker_bytes.decode())
    require(cache_match is not None, "Unable to resolve service-worker cache")

    health_status, _, health_bytes = fetch(f"{args.api}/healthz")
    require(health_status == 200, f"Gateway health returned HTTP {health_status}")
    require(json.loads(health_bytes) == {"status": "ok"}, "Unexpected gateway health body")

    auth_status, _, auth_bytes = fetch(f"{args.api}/api/v1/overview")
    require(auth_status == 401, f"Unauthenticated Overview returned HTTP {auth_status}")
    require("Bearer token is required" in auth_bytes.decode(), "Unexpected auth failure body")

    cors_status, cors_headers, _ = fetch(
        f"{args.api}/api/v1/overview", method="OPTIONS",
        headers={
            "Origin": args.origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,x-firebase-appcheck",
        },
    )
    require(cors_status == 200, f"CORS preflight returned HTTP {cors_status}")
    allow_origin = next(
        (value for key, value in cors_headers.items() if key.lower() == "access-control-allow-origin"), ""
    )
    require(allow_origin == args.origin, f"Unexpected CORS allow origin: {allow_origin!r}")

    print(json.dumps({
        "status": "ok", "entry_bundle": main_url, "app_bundle": app_url,
        "service_worker_cache": cache_match.group(1), "gateway_health": health_status,
        "unauthenticated_overview": auth_status, "cors_preflight": cors_status,
    }, indent=2))


if __name__ == "__main__":
    main()
