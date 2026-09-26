"""Offline draft exports: no remote scripts, tracking, forms or implied publication."""
from __future__ import annotations

import base64
from html import escape
from io import BytesIO
import json
from pathlib import Path
import zipfile

from .natal_brand import NATAL_FONT_PATH
from .studio import STUDIO_PREVIEW_FONTS
from .template_components import primitive, resolved_assets


def landing_html(document, content, assets, *, language="en"):
    media = resolved_assets(document, assets)
    styles, nodes = [], []
    roles = {c["id"]: c["role"] for c in document["components"]}
    for mobile in (False, True):
        tree = primitive(document, surface="landing", mobile=mobile, content=content).document["root"]
        width, height = tree["props"]["width"], tree["props"]["height"]
        css = [f".canvas{{height:{height / width * 100:.6f}cqw;background:{document['background']}}}"]
        for node in tree["children"]:
            p, kind, identifier = node["props"], node["type"], node["id"]
            unit = lambda v: f"{v / width * 100:.6f}cqw"
            declarations = ["position:absolute", f"left:{unit(p['x'])}", f"top:{unit(p['y'])}", f"width:{unit(p['width'])}", f"height:{unit(p['height'])}",
                f"opacity:{p['opacity']}", f"border-radius:{unit(p['radius'])}", f"border:{unit(p['border_width'])} solid {p['border_color']}",
                f"transform:rotate({p['rotation']}deg)", "box-sizing:border-box", f"display:{'block' if p['visible'] else 'none'}"]
            background = p.get("background_color") or "transparent"
            if p.get("background_gradient"):
                background = "linear-gradient(135deg," + ",".join(p["background_gradient"]) + ")"
            declarations.append(f"background:{background}")
            if kind in {"text", "button"}:
                declarations += [f"font-size:{unit(p['font_size'])}", f"font-weight:{p['font_weight']}", "font-family:Inter,sans-serif", "line-height:1.15",
                    f"font-family:'{p['font_family']}',sans-serif", f"text-align:{p['text_align']}", f"color:{p.get('color') or p.get('label_color')}", "white-space:pre-wrap", "margin:0", "padding:0"]
                if kind == "button":
                    declarations += ["display:flex", "align-items:center", "justify-content:center"]
            elif kind == "image":
                declarations += [f"object-fit:{p['fit']}", f"object-position:{p['focal_x'] * 100}% {p['focal_y'] * 100}%"]
            css.append(f"#{identifier}" + "{" + ";".join(declarations) + "}")
            if mobile:
                continue
            if kind == "image":
                image = media[p["asset"]]
                src = "data:" + image["mime_type"] + ";base64," + base64.b64encode(image["bytes"]).decode()
                alt = "Natal" if roles.get(identifier) == "brand" else ""
                nodes.append(f'<img id="{identifier}" src="{src}" alt="{alt}">')
            elif kind == "button":
                nodes.append(f'<button id="{identifier}" type="button" disabled>{escape(p["label"])}</button>')
            elif kind == "text":
                tag = "h1" if roles.get(identifier) == "headline" and not any(n.startswith('<h1 ') for n in nodes) else "p"
                nodes.append(f'<{tag} id="{identifier}">{escape(p["text"])}</{tag}>')
            else:
                nodes.append(f'<div id="{identifier}" aria-hidden="true"></div>')
        styles.append(("@media(max-width:600px){" + "".join(css) + "}") if mobile else "".join(css))
    families = {"Inter", *(c["font_family"] for c in document["components"] if c["type"] in {"text", "button"})}
    fonts = "".join(f"@font-face{{font-family:'{family}';src:url(data:font/ttf;base64,{base64.b64encode(STUDIO_PREVIEW_FONTS.get(family, NATAL_FONT_PATH).read_bytes()).decode()}) format('truetype');font-weight:100 900}}" for family in sorted(families))
    note = "Чернетка · кнопки не підключено до публікації чи збору заявок." if language == "uk" else "Draft preview · actions are not connected to publication or lead collection."
    return '<!doctype html><html lang="' + language + '"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' + escape(document["name"]) + '</title><style>' + fonts + 'body{margin:0;background:#edf1f2}aside{font:13px/1.5 Inter,sans-serif;padding:10px 16px;text-align:center}main{container-type:inline-size;max-width:1280px;margin:auto}.canvas{position:relative}button:disabled{opacity:1;cursor:default}' + ''.join(styles) + '</style><aside>' + note + '</aside><main><div class="canvas">' + ''.join(nodes) + '</div></main></html>'


def export_bundle(service, run):
    if run["status"] != "ready":
        raise ValueError("Finish the creation before exporting")
    stream = BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as bundle:
        payload = {k: run[k] for k in ("run_id", "mode", "language", "brief", "documents", "bindings", "source", "image_assets", "template_versions")}
        payload["surface_images"] = run.get("surface_images", {})
        bundle.writestr("natal-draft.json", json.dumps(payload, ensure_ascii=False, indent=2))
        if run["brief"]:
            bundle.writestr("brief.json", json.dumps(run["brief"]["document"], ensure_ascii=False, indent=2))
        for name, preview in run["previews"].items():
            bundle.writestr(name.replace(":", "-") + ".png", service.read_media(preview["sha256"]))
        images = {item["sha256"]: item for records in [run["image_assets"], *run.get("surface_images", {}).values()] for item in records}
        for index, item in enumerate(images.values()):
            bundle.writestr(f"assets/artwork-{index + 1}.png", service.read_media(item["sha256"]))
        if "landing" in run["documents"]:
            bundle.writestr("landing.html", landing_html(run["documents"]["landing"], run["bindings"].get("landing", {}), service.bound_assets(run, "landing"), language=run["language"]))
        bundle.writestr("README.txt", "Natal Studio draft export.\nThe HTML is an offline preview. Buttons are intentionally inactive until a publication/contact destination is configured.\nSource images retain their original provenance; owner-directed reuse is not a public license.\n")
        licenses = Path(__file__).with_name("studio_assets") / "fonts"
        for license_file in sorted(licenses.glob("OFL-*.txt")):
            bundle.writestr("font-licenses/" + license_file.name, license_file.read_bytes())
        inter_license = NATAL_FONT_PATH.with_name("OFL-Inter.txt")
        bundle.writestr("font-licenses/OFL-Inter.txt", inter_license.read_bytes())
    return stream.getvalue()
