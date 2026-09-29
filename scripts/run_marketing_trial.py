#!/usr/bin/env python3
"""Private paired copy trial using real inference and a fixed Natal template pair.

No approvals, publishing, analytics or production data. The initial previews use
fixed neutral artwork. --artwork-only adds real image-provider previews without
repeating completed Brief/copy calls or replacing the fixed-art comparison.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from html import escape
import json
from pathlib import Path
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from validation_pipeline.domain import _text, require_language
from validation_pipeline.local_brief_store import LocalBriefStore
from validation_pipeline.local_briefs import LocalBriefService
from validation_pipeline.local_codex import LocalCodexStructuredProvider
from validation_pipeline.openai_images import LocalCodexPhoneScreenImageProvider
from validation_pipeline.template_agent import obj, text_schema
from validation_pipeline.template_components import seed, render, sha, bounded_text
from validation_pipeline.template_previews import geometry

IDEAS = {
    "water": "A Natal app that compares bottled-water labels side by side and explains mineral content in plain language. It helps shoppers compare labels; it does not test water safety, diagnose health needs, or make medical recommendations. Free early access.",
    "mentor": "A Natal service connecting independent professionals to a human mentor for a first conversation about organizing a career change. Real consultant profiles and simple booking. A free first 15-minute call. No guaranteed jobs or earnings.",
    "maintenance": "A Natal tool for a small property maintenance team to record repair requests, assign an owner and see their status in one list. It does not predict faults or guarantee response times. Free early access.",
}


def trial_artwork(destination, model):
    """Generate artwork for completed pairs without repeating Brief/copy calls."""
    def create(saved):
        entry = json.loads(saved.read_text())
        if entry["model"] != model:
            raise ValueError("Keep the same model for the paired trial")
        path = saved.parent
        prompt = ("Create artwork for this Natal concept. No logos, advertising text, metrics or testimonials. "
                  + entry["image_direction"] + "\nBrief positioning (hypothesis, not evidence): "
                  + json.dumps(entry["brief"]["positioning"], ensure_ascii=False))
        receipt = path / "artwork-source.json"
        if receipt.exists():
            source = json.loads(receipt.read_text())
            if source["prompt"] != prompt:
                raise ValueError("Saved artwork belongs to different trial input")
            data = (path / "artwork.png").read_bytes()
        else:
            image = LocalCodexPhoneScreenImageProvider(model=model).generate(prompt)
            data = image["bytes"]
            (path / "artwork.png").write_bytes(data)
            receipt.write_text(json.dumps({"prompt": prompt, **image["source"]}, ensure_ascii=False, indent=2))
        findings = {}
        for surface in ("post", "landing"):
            document = seed(surface)
            assets = {c["id"]: {"bytes": data, "mime_type": "image/png"}
                      for c in document["components"] if c["type"] in {"image", "phone", "cutout_image"}
                      and c["role"] in {"hero", "secondary_media"}}
            for mobile in ([False, True] if surface == "landing" else [False]):
                name = f"{surface}-{'mobile' if mobile else 'desktop'}-artwork"
                preview = render(document, surface=surface, mobile=mobile,
                                 content=entry["bindings"][surface], assets=assets)
                (path / f"{name}.png").write_bytes(preview["bytes"])
                findings[name] = geometry(preview)[1]
        (path / "artwork-review.json").write_text(json.dumps(findings, indent=2))
        print(f"Completed artwork: {entry['case']}/{entry['approach']}", flush=True)
    with ThreadPoolExecutor(max_workers=2) as workers:
        list(workers.map(create, sorted(destination.glob("*/example.json"))))
    trial_gallery(destination)


def trial_gallery(destination):
    rows = []
    for case in IDEAS:
        cards = []
        for selected in ("benefit_led", "identity_led"):
            folder = f"{case}-{selected}"
            saved = destination / folder / "example.json"
            if not saved.exists():
                continue
            entry = json.loads(saved.read_text())
            position = entry["brief"]["positioning"]
            title = "Benefit-led" if selected == "benefit_led" else "Identity-led"
            cards.append(f'<article><h2>{title}</h2><p>{escape(entry["brief"]["promise"])}</p>'
                         f'<p><b>Functional value:</b> {escape(position["functional_value"])}</p>'
                         f'<img data-folder="{folder}" src="{folder}/post-desktop-artwork.png" alt="{title} private {case} draft">'
                         f'<p><a href="{folder}/brief.json">Brief JSON</a> · <a href="{folder}/example.json">Copy and provenance</a> · '
                         f'<a href="{folder}/artwork-source.json">Artwork provenance</a></p></article>')
        rows.append(f'<section data-case="{case}"><h2>{case.title()}</h2><div class="pair">{"".join(cards)}</div></section>')
    (destination / "index.html").write_text('''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Private marketing approach trial</title><style>
body{font:16px/1.5 system-ui,sans-serif;background:#f5f6f8;color:#182333;max-width:1300px;margin:auto;padding:24px}h1{font-size:28px}.pair{display:grid;grid-template-columns:1fr 1fr;gap:24px}article{background:white;padding:20px;border-radius:16px}img{width:100%;height:auto}select{font:inherit;padding:10px;min-height:44px;margin:8px}a{color:#254aa5}section[hidden]{display:none}@media(max-width:650px){.pair{grid-template-columns:1fr}body{padding:12px}}
</style><h1>Private marketing approach trial</h1><p>Real Brief, copy and artwork generation. Within each pair: same idea, language, selected model and template. Private drafts; no conversion evidence or performance winner.</p>
<p><a href="README.md">Full copy comparison</a> · <a href="../../docs/architecture/marketing-approaches-trial.md">Review and limitations</a></p>
<label>Idea <select id="idea"><option value="water">Consumer utility: water labels</option><option value="mentor">Personal service: mentoring</option><option value="maintenance">Business tool: repair tracker</option></select></label>
<label>Preview <select id="surface"><option value="post-desktop-artwork">Post with artwork</option><option value="landing-desktop-artwork">Landing desktop</option><option value="landing-mobile-artwork">Landing mobile</option><option value="post-desktop">Post with fixed neutral artwork</option></select></label>
''' + "".join(rows) + '''<script>
const idea=document.getElementById('idea'),surface=document.getElementById('surface');
function update(){document.querySelectorAll('section[data-case]').forEach(s=>s.hidden=s.dataset.case!==idea.value);document.querySelectorAll('img[data-folder]').forEach(i=>i.src=i.dataset.folder+'/'+surface.value+'.png')}
idea.addEventListener('change',update);surface.addEventListener('change',update);update();
</script></html>''')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / ".local/marketing-approaches-trial")
    parser.add_argument("--model", default="gpt-6-astra")
    parser.add_argument("--artwork-only", action="store_true", help="Generate private artwork for completed examples; keep fixed-art previews")
    args = parser.parse_args()
    destination = args.output_dir.resolve()
    if not destination.is_relative_to(ROOT / ".local"):
        raise ValueError("Trial output must stay in the private .local directory")
    destination.mkdir(parents=True, exist_ok=True)
    if args.artwork_only:
        trial_artwork(destination, args.model)
        return
    provider = LocalCodexStructuredProvider(model=args.model, reasoning_effort="xhigh")
    briefs = LocalBriefService(store=LocalBriefStore(destination / "briefs"), provider=provider, repository_root=ROOT)
    definitions = {surface: seed(surface) for surface in ("post", "landing")}
    constraints = {s: {"canvas": doc["canvas"], "background": doc["background"], "components": [
        {k: c[k] for k in ("id", "type", "role", "box", "mobile_box", "font_size", "font_weight", "color")}
        for c in doc["components"] if c["type"] in {"text", "button"}]} for s, doc in definitions.items()}
    fields = {s: {c["id"]: text_schema(500) for c in doc["components"] if c["type"] in {"text", "button"}} for s, doc in definitions.items()}
    schema = obj({"bindings": obj({s: obj(v) for s, v in fields.items()}), "image_direction": text_schema(1800), "replace_image": {"type": "boolean"}})
    skill = (ROOT / "skills/natal-creation-studio/SKILL.md").read_text()
    entries = []
    for case, idea in IDEAS.items():
        for selected in ("benefit_led", "identity_led"):
            path = destination / f"{case}-{selected}"
            path.mkdir(exist_ok=True)
            saved = path / "example.json"
            if saved.exists():
                entry = json.loads(saved.read_text())
                if (entry["raw_idea"], entry["model"], entry["language"], entry["template_pair_sha256"]) != (idea, args.model, "en", sha(definitions)):
                    raise ValueError("Saved trial inputs changed; use another private output directory")
                entries.append(entry)
                continue
            name = f"Private trial: {case} / {selected}"
            existing = next((p for p in briefs.list_projects() if p["name"] == name), None)
            if existing:
                brief = briefs.get_brief(existing["latest_brief_id"])
            else:
                project, _ = briefs.create_project(request_id=str(uuid4()), name=name, requested_by="private-marketing-trial")
                _, brief, _ = briefs.create_brief(project_id=project["project_id"], request_id=str(uuid4()), raw_idea=idea,
                    required_language="en", requested_by="private-marketing-trial", marketing_approach=selected)
            if brief["status"] == "queued":
                brief = briefs.generate_brief(brief["brief_id"])
            if brief["status"] != "completed":
                raise RuntimeError(f"{case}/{selected}: Brief failed ({brief.get('error_code')}); saved diagnostics remain private")
            (path / "brief.json").write_text(json.dumps(brief["document"], ensure_ascii=False, indent=2))
            def validate(value):
                if set(value) != {"bindings", "image_direction", "replace_image"} or set(value["bindings"]) != set(fields) or type(value["replace_image"]) is not bool:
                    raise ValueError("Invalid content bindings")
                for surface, expected in fields.items():
                    if set(value["bindings"][surface]) != set(expected):
                        raise ValueError("Bind every enabled text component exactly once")
                    for identifier, copy in value["bindings"][surface].items():
                        if not isinstance(copy, str):
                            raise ValueError("Copy must be text")
                        bounded_text(copy, 500, identifier)
                        _text(copy, identifier, 500)
                    require_language("en", list(value["bindings"][surface].values()), "Trial copy")
                if not isinstance(value["image_direction"], str) or not 24 <= len(value["image_direction"]) <= 1800:
                    raise ValueError("Image direction must be concrete and bounded")
                return value
            binding_path = path / "binding-result.json"
            if binding_path.exists():
                result = json.loads(binding_path.read_text())
            else:
                result = provider.call(mode="template_creation", system_prompt=skill,
                    input_payload={"phase": "bind", "brief": brief["document"], "language": "en", "definitions": constraints,
                                   "owner_edit": None, "previous_bindings": {}, "fit_failures": {}, "has_images": False},
                    output_schema=schema, idempotency_key=f"private-marketing-trial:{uuid4()}", prompt_version="natal-creation-v1",
                    response_validator=validate)
                binding_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
            value = result["response"]
            entry = {"case": case, "approach": selected, "raw_idea": idea, "model": args.model, "reasoning_effort": "xhigh",
                "language": "en", "template_pair_sha256": sha(definitions), "brief_id": brief["brief_id"],
                "brief_sha256": brief["document_sha256"], "policy_sha256": brief["generation_settings"]["policy_sha256"],
                "brief": brief["document"], **value, "geometry": {}, "copy_invocation": result["invocation"],
                "artwork": "Fixed neutral renderer fixture; not generated marketing artwork or performance evidence"}
            for surface, doc in definitions.items():
                for mobile in ([False, True] if surface == "landing" else [False]):
                    name = f"{surface}-{'mobile' if mobile else 'desktop'}"
                    preview = render(doc, surface=surface, mobile=mobile, content=value["bindings"][surface])
                    (path / f"{name}.png").write_bytes(preview["bytes"])
                    entry["geometry"][name] = geometry(preview)[1]
            saved.write_text(json.dumps(entry, ensure_ascii=False, indent=2))
            entries.append(entry)
            print(f"Completed {case}/{selected}: real Brief and copy; private fixture previews", flush=True)
    (destination / "examples.json").write_text(json.dumps(entries, ensure_ascii=False, indent=2))
    report = ["# Private marketing approach trial", "", "Real Brief and Natal content-binding inference; identical model, language, raw idea and template within each pair. Neutral fixture artwork is held constant and is not an image-generation result. No approvals, publication or performance learning occurred.", "", "Optional `--artwork-only` creates `artwork.png`, `artwork-source.json` and `*-artwork.png` previews beside each example using the real local image provider. Those preserve the fixed-art comparison. The provider records the chosen agent model but does not expose the underlying image-model version.", ""]
    for entry in entries:
        report.extend([f"## {entry['case']} / {entry['approach']}", "", f"Promise: {entry['brief']['promise']}",
            f"Positioning: {json.dumps(entry['brief']['positioning'], ensure_ascii=False)}", "",
            f"Post: {json.dumps(entry['bindings']['post'], ensure_ascii=False)}", "",
            f"Landing: {json.dumps(entry['bindings']['landing'], ensure_ascii=False)}", "", f"Image direction: {entry['image_direction']}", ""])
    (destination / "README.md").write_text("\n".join(report))


if __name__ == "__main__":
    main()
