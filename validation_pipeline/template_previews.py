"""Authoritative template previews with fixed, explicitly non-domain fixtures."""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import subprocess
import os
import signal

from .post_templates import POST_TEMPLATE_REGISTRY
from .landing_templates import LANDING_TEMPLATE_REGISTRY
from .template_components import normalize_document, placeholder_image, render, render_contract_sha256, sha

ROOT = Path(__file__).resolve().parents[1]


def builtin_record(definition) -> dict:
    return {**definition.identity.to_reference(), "name": definition.name, "description": definition.description,
            "builtin": True, "status": "registered", "renderer_key": definition.renderer_key,
            "canvas": None if definition.canvas is None else dict(definition.canvas),
            "capabilities": definition.capabilities.to_dict(),
            "component_roles": [{"type": item["component_id"], "role": item["role"]} for item in definition.catalog()["components"]]}


def builtins(*, all_versions=False) -> list[dict]:
    return [builtin_record(definition)
            for registry in (POST_TEMPLATE_REGISTRY, LANDING_TEMPLATE_REGISTRY)
            for definition in (registry.registered_versions() if all_versions else registry.all())]


def landing_fixture(template_id="project_landing", *, reference=None) -> dict:
    definition = (LANDING_TEMPLATE_REGISTRY.resolve_reference(reference) if reference
                  else LANDING_TEMPLATE_REGISTRY.get(template_id))
    template_id = definition.identity.template_id
    content = definition.default_content()
    content["hero"].update(title="Template title", supporting_text="Supporting text placeholder", cta_label="Action")
    content["features"] = [{"title": "Section title", "description": "Body text placeholder"} for _ in range(3)]
    content["contacts"].update(heading="Contact section", supporting_text="Owner contact details appear here")
    content["faq"] = [{"question": "Question placeholder", "answer": "Answer placeholder"} for _ in range(3)]
    content["app_feature"] = {"title": "Feature title", "description": "Feature description", "action_label": "Action", "items": [{"label": "Label", "value": "Value"} for _ in range(3)]}
    if template_id == "app_showcase":
        content.pop("app_feature", None)
        content["app_screens"] = [{"title": f"Step {i + 1}", "description": "Project-specific app screen", "visual_direction": "Neutral interface preview"} for i in range(3)]
    if "marketing" in content:
        m = content["marketing"]
        m.update(introduction="Your app, everyday possibilities.", comparison_heading="A simpler way with Natal", walkthrough_heading="How it works", benefits_heading="Made for everyday tasks", benefits_supporting="A clear, connected experience", benefit_highlight_title="Your next step", benefit_highlight_text="Project-specific benefit", cta_heading="Explore the app", cta_text="Start with one simple step")
        m["comparison_rows"] = [{"text": f"Project benefit {i+1}", "enabled": True} for i in range(6)]
        m["walkthrough_steps"] = [{"title": f"Step {i+1}", "description": "Project-specific instructions", "enabled": True} for i in range(4)]
        m["values"] = [{"title": f"Benefit {i+1}", "description": "Brief-grounded description", "enabled": True} for i in range(4)]
    configuration = definition.default_configuration()
    configuration["presentation"] = {"language": "en", "cta_target": "contacts", "heading_scale": 1, "spacing": "comfortable", "hero_focus": {"x": 50, "y": 50}, "visual_break_focus": {"x": 50, "y": 50}}
    # Native phone demo defaults are labels, not claims; no contact or proof is invented.
    image = "data:image/png;base64," + base64.b64encode(placeholder_image()).decode()
    images = {slot: image for slot in definition.capabilities.image_slots}
    from .landing_showcase import reference_photo
    images["visual_break_visual"] = "data:image/png;base64," + base64.b64encode(reference_photo()["bytes"]).decode()
    if template_id == "app_showcase":
        from .template_demo_assets import app_screen, walkthrough
        for index in range(3):
            images[f"app_screen_{index + 1}"] = "data:image/png;base64," + base64.b64encode(app_screen(index)).decode()
        if "walkthrough_visual" in images:
            images["walkthrough_visual"] = "data:image/png;base64," + base64.b64encode(walkthrough()).decode()
    return {"configuration": configuration, "content": content, "imageUrls": images}


def builtin_preview_contract(record: dict) -> str:
    """Version preview caches separately from immutable templates/approved PNGs."""
    paths = [Path(__file__), ROOT / "validation_pipeline/template_demo_assets.py"]
    reference = {key: record[key] for key in ("template_id", "template_version", "template_sha256")}
    if record["surface"] == "landing":
        paths.append(ROOT / "apps/commander-web/scripts/render-template-landing.mjs")
        bundle = Path(os.environ.get("PTW_TEMPLATE_PREVIEW_BUNDLE", str(ROOT / ".local/template-preview")))
        paths.extend(sorted(path for path in bundle.rglob("*") if path.is_file()))
        fixture = sha(landing_fixture(reference=reference))
    else:
        paths.extend(ROOT / "validation_pipeline" / name for name in
                     ("studio_phone_metrics.py", "studio.py", "studio_primitives.py", "studio_workspace.py", "natal_brand.py"))
        definition = POST_TEMPLATE_REGISTRY.resolve_reference(reference)
        fixture = sha({"configuration": definition.default_configuration(), "content": definition.default_content()})
    return sha({"reference": {key: record[key] for key in ("surface", "template_id", "template_version", "template_sha256")},
                "fixture_sha256": fixture,
                "renderer_files": [hashlib.sha256(path.read_bytes()).hexdigest() for path in paths]})


def render_builtin(record: dict, *, mobile=False) -> dict:
    reference = {key: record[key] for key in ("template_id", "template_version", "template_sha256")}
    if record["surface"] == "post":
        definition = POST_TEMPLATE_REGISTRY.resolve_reference(reference)
        configuration, content = definition.default_configuration(), definition.default_content()
        content.update(hero_title="Your next idea starts here", supporting_text="Describe the task your app helps people complete.",
                       offer="TEMPLATE PREVIEW", cta="Explore the details", phone_hero_title="Your workspace",
                       phone_buttons=["Explore options", "View requests", "Profile"])
        for item in content.get("stats", []):
            item.update(value="01", label="Label")
        import tempfile
        from .studio_workspace import PostStudioWorkspace
        with tempfile.TemporaryDirectory(prefix="ptw-template-fixture-") as temporary:
            workspace = PostStudioWorkspace(Path(temporary))
            detail = workspace.apply_template(base_sha256=workspace.detail()["state_sha256"],
                template_id=record["template_id"], template_reference={"surface": "post", **reference})
            result = workspace.render_preview(state_sha256=detail["state_sha256"], configuration=configuration, content=content)
    else:
        process = subprocess.Popen(["node", str(ROOT / "apps/commander-web/scripts/render-template-landing.mjs")],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
        try:
            stdout, _stderr = process.communicate(json.dumps({"fixture": landing_fixture(reference=reference), "width": 360 if mobile else 1280}), timeout=45)
        except subprocess.TimeoutExpired as error:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
            raise TimeoutError("Landing template preview timed out") from error
        if process.returncode:
            raise RuntimeError("Landing template preview renderer unavailable; build the template preview bundle and install Chromium")
        value = json.loads(stdout)
        result = {"bytes": base64.b64decode(value["png"], validate=True), "geometry": value["geometry"]}
    return result


def geometry(result: dict) -> tuple[list[dict], list[dict]]:
    if "geometry" in result:
        return [{**item, "box": [round(v * 1000, 2) for v in item["box"]]} for item in result["geometry"]], []
    resolved = result["resolved"]
    observations, failures = [], []
    roles = {identifier: role for role, identifiers in resolved["semantic_roles"].items() for identifier in identifiers}
    for identifier, node in resolved["nodes"].items():
        if identifier not in roles:
            continue
        bounds = node["box"]
        observation = {"role": roles[identifier], "id": identifier,
                       "box": [round(bounds[k] * 1000, 2) for k in ("x", "y", "width", "height")]}
        observations.append(observation)
        text = node.get("text_layout") or {}
        if text.get("overflow") or text.get("truncated"):
            failures.append({"role": roles[identifier], "issue": "Text overflows its assigned box", "solvable": True})
        if bounds["x"] < -.001 or bounds["y"] < -.001 or bounds["x"] + bounds["width"] > 1.001 or bounds["y"] + bounds["height"] > 1.001:
            failures.append({"role": roles[identifier], "issue": "Component exceeds canvas bounds", "solvable": True})
    text_nodes = [(identifier, node["visible_bounds"]) for identifier, node in resolved["nodes"].items()
                  if identifier in roles and node["type"] in ("text", "rich_text", "button") and node.get("visible_bounds")]
    for index, (left_id, left) in enumerate(text_nodes):
        for right_id, right in text_nodes[index + 1:]:
            overlap_x = min(left["x"] + left["width"], right["x"] + right["width"]) - max(left["x"], right["x"])
            overlap_y = min(left["y"] + left["height"], right["y"] + right["height"]) - max(left["y"], right["y"])
            if overlap_x > .002 and overlap_y > .002:
                failures.append({"role": roles[left_id], "issue": f"Visible text overlaps {roles[right_id]}", "solvable": True})
    return observations[:32], failures[:16]


def render_designs(documents: dict) -> dict:
    results = {}
    for surface, document in documents.items():
        document = normalize_document(document)
        for viewport in (["desktop", "mobile"] if surface == "landing" else ["desktop"]):
            result = render(document, surface=surface, mobile=viewport == "mobile")
            observations, failures = geometry(result)
            results[f"{surface}:{viewport}"] = {"bytes": result["bytes"], "geometry": observations, "failures": failures,
                "definition_sha256": sha(document), "render_contract_sha256": render_contract_sha256(document),
                "sha256": hashlib.sha256(result["bytes"]).hexdigest()}
    return results
