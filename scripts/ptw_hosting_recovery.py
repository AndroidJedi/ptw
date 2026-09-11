#!/usr/bin/env python3
"""Snapshot/restore live Hosting versions using the existing root-owned identity."""
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def request(method, url, body=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    data = json.dumps(body).encode() if body is not None else None
    with urlopen(Request(url, data=data, headers=headers, method=method), timeout=30) as response:
        return json.load(response)


def access_token():
    credential = json.loads(Path("/opt/ptw/secrets/firebase-service-account.json").read_text())
    def encoded(value):
        return base64.urlsafe_b64encode(json.dumps(value, separators=(",", ":")).encode()).rstrip(b"=")
    stamp = int(time.time())
    message = encoded({"alg": "RS256", "typ": "JWT"}) + b"." + encoded({
        "iss": credential["client_email"], "scope": "https://www.googleapis.com/auth/firebase.hosting",
        "aud": "https://oauth2.googleapis.com/token", "iat": stamp, "exp": stamp + 600,
    })
    with tempfile.TemporaryDirectory(prefix="ptw-hosting-auth-", dir="/run") as temporary:
        path = Path(temporary) / "unsigned"
        path.write_bytes(message)
        signature = subprocess.check_output(["openssl", "dgst", "-sha256", "-sign", "/dev/stdin", str(path)],
                                            input=credential["private_key"].encode(), stderr=subprocess.DEVNULL)
    assertion = (message + b"." + base64.urlsafe_b64encode(signature).rstrip(b"=")).decode()
    data = urlencode({"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion}).encode()
    with urlopen(Request("https://oauth2.googleapis.com/token", data=data,
                         headers={"Content-Type": "application/x-www-form-urlencoded"}), timeout=30) as response:
        return json.load(response)["access_token"]


def main():
    action, filename = sys.argv[1:]
    if os.geteuid() != 0 or action not in {"snapshot", "restore"}:
        raise SystemExit(2)
    token = access_token()
    origin = "https://firebasehosting.googleapis.com/v1beta1/"
    sites = ("provethemwrong-86123", "natal-landings-86123")
    if action == "snapshot":
        versions = {}
        for site in sites:
            releases = request("GET", origin + f"sites/{site}/releases?pageSize=1", token=token).get("releases", [])
            if not releases or not releases[0].get("version", {}).get("name"):
                raise RuntimeError("Live Hosting version was not found")
            versions[site] = releases[0]["version"]["name"]
        Path(filename).write_text(json.dumps(versions))
        Path(filename).chmod(0o600)
    else:
        versions = json.loads(Path(filename).read_text())
        if set(versions) != set(sites):
            raise RuntimeError("Hosting recovery sites do not match")
        for site, version in versions.items():
            if not version.startswith(f"sites/{site}/versions/"):
                raise RuntimeError("Hosting recovery version does not match its site")
            current = request("GET", origin + f"sites/{site}/releases?pageSize=1", token=token)["releases"][0]["version"]["name"]
            if current != version:
                request("POST", origin + f"sites/{site}/releases?" + urlencode({"versionName": version}),
                        {"message": "Restore last accepted PTW release"}, token)
    print("Hosting recovery " + action + " verified")


if __name__ == "__main__":
    main()
