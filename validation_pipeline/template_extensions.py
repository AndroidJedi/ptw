"""Source-only capability review boundary. No browser API can install code."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_FILES = frozenset({
    "validation_pipeline/template_components.py", "validation_pipeline/template_agent.py", "validation_pipeline/studio_primitives.py",
    "validation_pipeline/template_registry.py", "validation_pipeline/post_templates.py",
    "validation_pipeline/landing_templates.py", "docs/architecture/templates-mode.md",
    "docs/architecture/post-studio.md", "docs/architecture/landing-studio.md",
})
ALLOWED_PREFIXES = ("validation_pipeline/studio_components/", "tests/validation_pipeline/test_template_",
                    "apps/commander-web/src/components/templates/", "skills/template-creation-agent/")


def allowed_path(path: str) -> bool:
    p = Path(path)
    return not p.is_absolute() and ".." not in p.parts and (path in ALLOWED_FILES or any(path.startswith(prefix) for prefix in ALLOWED_PREFIXES))


def handoff(run: dict) -> dict:
    gap = run.get("capability_gap")
    if run.get("status") != "capability_gap" or not gap:
        raise ValueError("This run has no capability gap")
    return {"schema": "ptw.template-capability-handoff.v1", "run_id": run["run_id"], "state_sha256": run["state_sha256"],
        "capability_gap": gap, "allowed_files": sorted(ALLOWED_FILES), "allowed_prefixes": list(ALLOWED_PREFIXES),
        "workflow": "Owner-reviewed isolated development snapshot. Prepare with scripts/review_template_extension.py, implement using Commander GOD mode, verify, inspect rendered previews, then apply the exact reviewed digest. Restart and resume this run.",
        "requirements": ["Reuse existing settings/composition first", "No runtime code, HTML/CSS or screenshot-specific component",
                         "No deletions, symlinks or concurrent source replacement", "Focused tests and Studio visual audit must pass", "Owner inspects the exact rendered preview before apply"]}


def validated_capability(capability: str, root: Path = ROOT) -> bool:
    if not re.fullmatch(r"[a-z][a-z0-9_]{2,59}", capability):
        return False
    path = root / "validation_pipeline/studio_components/capability_reviews" / f"{capability}.json"
    try:
        if path.is_symlink() or path.stat().st_size > 20_000:
            return False
        record = json.loads(path.read_text())
        if record["capability"] != capability or record["verification"] != "passed" or not record["visual_review_sha256"]:
            return False
        sources = record["sources"]
        if not isinstance(sources, dict) or not sources:
            return False
        for name, digest in sources.items():
            source = root / name
            if not allowed_path(name) or source.is_symlink() or not source.resolve().is_relative_to(root.resolve()) or hashlib.sha256(source.read_bytes()).hexdigest() != digest:
                return False
        # A review receipt alone cannot enable a capability. The live catalog must expose it.
        from .template_components import catalog
        return capability in catalog("post").get("extensions", []) or capability in catalog("landing").get("extensions", [])
    except (OSError, KeyError, ValueError, TypeError):
        return False
