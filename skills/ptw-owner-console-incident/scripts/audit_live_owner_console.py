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


def resolve_app_bundle_url(origin: str, entry_url: str, entry_bundle: str) -> str:
    match = re.search(r'["\']([^"\']*?App-[^"\']+\.js)["\']', entry_bundle)
    require(match is not None, "Unable to resolve the lazy App bundle")
    path = match.group(1)
    if path.startswith("assets/"):
        return urljoin(f"{origin}/", path)
    return urljoin(entry_url, path)


def load_live_app_bundle(origin: str) -> tuple[str, str, str, dict[str, str]]:
    last_error: RuntimeError | None = None
    for attempt in range(5):
        try:
            cache_bust = f"skill-audit-{time.time_ns()}"
            status, document_headers, document_bytes = fetch(f"{origin}/?{cache_bust}")
            require(status == 200, f"Owner document returned HTTP {status}")
            document = document_bytes.decode()
            main_match = re.search(r'src="([^"]*?/assets/index-[^"]+\.js)"', document)
            require(main_match is not None, "Unable to resolve the live entry bundle")
            main_url = urljoin(origin, main_match.group(1))

            status, _, main_bytes = fetch(main_url)
            require(status == 200, f"Entry bundle returned HTTP {status}")
            app_url = resolve_app_bundle_url(origin, main_url, main_bytes.decode())

            status, _, app_bytes = fetch(app_url)
            require(status == 200, f"App bundle returned HTTP {status}")
            return main_url, app_url, app_bytes.decode(), document_headers
        except RuntimeError as error:
            last_error = error
            if attempt < 4:
                time.sleep(2)
    raise last_error or RuntimeError("Unable to load the live App bundle")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--origin", default=DEFAULT_ORIGIN)
    parser.add_argument("--api", default=DEFAULT_API)
    parser.add_argument("--site-key", default=DEFAULT_SITE_KEY)
    args = parser.parse_args()

    main_url, app_url, app_bundle, document_headers = load_live_app_bundle(args.origin)
    lower_headers = {name.lower(): value for name, value in document_headers.items()}
    csp = lower_headers.get("content-security-policy", "")
    require("frame-ancestors 'none'" in csp, "Owner document does not enforce frame-ancestors 'none'")
    require("content-security-policy-report-only" not in lower_headers, "Owner document unexpectedly uses report-only CSP")
    require(lower_headers.get("x-frame-options", "").casefold() == "deny", "Owner document X-Frame-Options is not DENY")
    for label, marker in {
        "Commander API origin": args.api,
        "App Check header": "X-Firebase-AppCheck",
        "reCAPTCHA Enterprise site key": args.site_key,
        "Safari-safe Auth persistence": "ptw-auth-local-storage-v1",
        "Product Brief workspace": "Product Brief",
        "Post destination": "Post",
        "Landing destination": "Landing",
        "Landing save timeout reconciliation": "Landing was already saved.",
        "ChatGPT authorization settings": "ChatGPT Authorization",
        "actionable API error guidance": "Що робити",
        "bounded API technical context": "Технічні дані",
        "approved Brief existing-Creative resolution": "approved-brief-existing-creative-v1",
        "draft-bound phone preview state": "Updating preview…",
        "recent-image credential coalescing": "firebase-token-coalescing-v1",
        "optional Landing Instagram contact": "Instagram profile link",
    }.items():
        require(marker in app_bundle, f"Live App bundle is missing {label}")
    for retired_label in (
        "Stage 3 pending", "Generate new Ads", "Ad Studio", "Review steps",
        "Docs / System / Terminal", "PROJECT BRAND KIT", "Result type",
        "Describe the one result you need",
        "Improving the strongest direction", "WHY THIS DIRECTION",
        "Five verified creative directions", "Tune selected", "Regenerate all",
        "Retry notification", "Social posts",
    ):
        require(retired_label not in app_bundle, f"Live App bundle still exposes {retired_label!r}")

    status, _, worker_bytes = fetch(f"{args.origin}/sw.js?skill-audit-{time.time_ns()}")
    require(status == 200, f"Service worker returned HTTP {status}")
    cache_match = re.search(r"const CACHE = '([^']+)'", worker_bytes.decode())
    require(cache_match is not None, "Unable to resolve service-worker cache")
    require(
        "url.pathname.startsWith('/__/auth/')" in worker_bytes.decode(),
        "Live service worker does not bypass Firebase Auth helper traffic",
    )

    health_status, _, health_bytes = fetch(f"{args.api}/healthz")
    require(health_status == 200, f"Gateway health returned HTTP {health_status}")
    require(json.loads(health_bytes) == {"status": "ok"}, "Unexpected gateway health body")

    auth_status, _, auth_bytes = fetch(f"{args.api}/api/v1/overview")
    require(auth_status == 401, f"Unauthenticated Overview returned HTTP {auth_status}")
    require("Bearer token is required" in auth_bytes.decode(), "Unexpected auth failure body")

    private_route_status, _, private_route_bytes = fetch(
        f"{args.api}/api/v1/studio/projects/00000000-0000-0000-0000-000000000001/"
        "creatives/00000000-0000-0000-0000-000000000002/creative-direction",
        method="POST",
    )
    require(
        private_route_status == 401,
        f"Creative-direction route registration returned HTTP {private_route_status}",
    )
    require(
        "Bearer token is required" in private_route_bytes.decode(),
        "Unexpected creative-direction auth failure body",
    )

    for retired_path in (
        "/api/v1/ideas", "/api/v1/branding", "/api/v1/posts",
        "/api/v1/content-runs", "/api/v1/project-assets",
        "/api/v1/project-brand-kits",
        "/api/v1/positionings", "/api/v1/ads", "/api/v1/ad-batches",
        "/api/v1/ad-studio", "/api/v1/landings", "/api/v1/jobs",
        "/api/v1/public/landings/00000000-0000-0000-0000-000000000000/leads",
    ):
        retired_status, _, _ = fetch(f"{args.api}{retired_path}")
        require(retired_status == 404, f"Retired route {retired_path} returned HTTP {retired_status}")

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
        "unauthenticated_overview": auth_status,
        "creative_direction_route": private_route_status,
        "cors_preflight": cors_status,
    }, indent=2))


if __name__ == "__main__":
    main()
