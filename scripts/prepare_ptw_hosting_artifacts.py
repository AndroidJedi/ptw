#!/usr/bin/env python3
"""Build only planned Hosting bundles for the trusted CI release workflow."""
import json
import hashlib
from pathlib import Path
import subprocess
import sys

directory = Path(sys.argv[1])
plan = json.loads((directory / "release-plan.json").read_text())
for target, app in (("owner-console", "commander-web"), ("public-landings", "landing-web")):
    if not plan["hosting"][target]:
        continue
    if target == "public-landings":
        subprocess.run(["npm", "--prefix", f"apps/{app}", "ci"], check=True)
        subprocess.run(["npm", "--prefix", f"apps/{app}", "run", "check"], check=True)
    subprocess.run(["tar", "-C", f"apps/{app}/dist", "-czf", str(directory.resolve() / f"{target}.tar.gz"), "."], check=True)

digests = {}
for name in ("release-plan.json", "commander.tar", "validation.tar", "owner-gateway.tar", "commander-god.tar", "owner-console.tar.gz", "public-landings.tar.gz"):
    path = directory / name
    if path.is_file():
        with path.open("rb") as source:
            digests[name] = hashlib.file_digest(source, "sha256").hexdigest()
(directory / "artifact-digests.json").write_text(json.dumps({"revision": plan["target_revision"], "sha256": digests}, sort_keys=True))
