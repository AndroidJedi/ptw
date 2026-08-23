"""Build a dependency-free Natal landing site from a validated brief."""

from __future__ import annotations

import argparse
import base64
import hashlib
from html import escape
import json
import mimetypes
from pathlib import Path
import shutil
from string import Template
from typing import Any, Iterable, Mapping

from .brief import LandingBrief
from .catalog import ROOT, landing_templates, recommend_template, template_manifest
from .page import LandingPageContent, page_content_from_brief


ASSET_ROOT = ROOT / "assets"
SHARED_ROOT = ROOT / "templates" / "shared"


def _asset_manifest() -> Mapping[str, Any]:
    return json.loads((ROOT / "brand" / "brand.json").read_text())


def verify_brand_assets() -> None:
    for item in _asset_manifest()["assets"]:
        path = ASSET_ROOT / item["file"]
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != item["sha256"]:
            raise ValueError(f"Natal brand asset digest mismatch: {item['file']}")


def build_landing(
    template_id: str,
    brief_value: Mapping[str, Any] | LandingBrief,
    output_directory: Path,
    *,
    page_content: Mapping[str, Any] | LandingPageContent | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    manifest = template_manifest(template_id)
    brief = brief_value if isinstance(brief_value, LandingBrief) else LandingBrief.from_dict(brief_value)
    output = output_directory.resolve()
    if output.exists() and any(output.iterdir()) and not overwrite:
        raise FileExistsError(f"output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    verify_brand_assets()
    content = _page_content(template_id, brief, page_content)
    source_template = ROOT / "templates" / template_id / "index.html.tmpl"
    document = _render_document(template_id, brief, content)
    (output / "index.html").write_text(document)
    shutil.copyfile(SHARED_ROOT / "styles.css", output / "styles.css")
    shutil.copyfile(SHARED_ROOT / "app.js", output / "app.js")
    assets = output / "assets"
    assets.mkdir(exist_ok=True)
    for item in _asset_manifest()["assets"]:
        shutil.copyfile(ASSET_ROOT / item["file"], assets / item["file"])
    (output / "brief.json").write_text(json.dumps(brief.to_dict(), ensure_ascii=False, indent=2) + "\n")
    (output / "page_content.json").write_text(
        json.dumps(content.to_dict(), ensure_ascii=False, indent=2) + "\n"
    )
    normalized_brief = json.dumps(brief.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    normalized_content = json.dumps(content.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    build = {
        "schema_version": 1,
        "brand": "Natal",
        "template_id": template_id,
        "template_version": manifest["version"],
        "source": dict(brief.source or {}),
        "brief_sha256": hashlib.sha256(normalized_brief.encode()).hexdigest(),
        "page_content_sha256": hashlib.sha256(normalized_content.encode()).hexdigest(),
        "template_sha256": hashlib.sha256(source_template.read_bytes()).hexdigest(),
        "files": ["index.html", "styles.css", "app.js", "brief.json", "page_content.json", *[f"assets/{item['file']}" for item in _asset_manifest()["assets"]]],
    }
    (output / "build.json").write_text(json.dumps(build, ensure_ascii=False, indent=2) + "\n")
    return build


def preview_document(
    template_id: str,
    brief_value: Mapping[str, Any] | LandingBrief,
    page_content: Mapping[str, Any] | LandingPageContent | None = None,
) -> str:
    """Return a private, self-contained editor preview with inert actions."""

    brief = brief_value if isinstance(brief_value, LandingBrief) else LandingBrief.from_dict(brief_value)
    content = _page_content(template_id, brief, page_content)
    document = _render_document(template_id, brief, content, preview=True)
    stylesheet = (SHARED_ROOT / "styles.css").read_text()
    preview_styles = """
[data-landing-block] { position: relative; cursor: pointer; }
[data-landing-block]:focus, [data-landing-block].landing-block-selected {
  outline: 3px solid #43bdd3; outline-offset: -3px;
}
[data-landing-block].landing-block-selected::after {
  content: attr(data-landing-block); position: absolute; z-index: 90; top: 8px; right: 8px;
  padding: 6px 8px; border-radius: 8px; color: #06161a; background: #87d0dd;
  font: 800 11px/1 Inter, sans-serif; text-transform: uppercase;
}
""".strip()
    script = (SHARED_ROOT / "app.js").read_text() + "\n" + _preview_script(template_id)
    document = document.replace(
        '<link rel="stylesheet" href="styles.css">',
        f"<style>{stylesheet}\n{preview_styles}</style>",
    ).replace('<script src="app.js"></script>', f"<script>{script}</script>")
    for item in _asset_manifest()["assets"]:
        path = ASSET_ROOT / item["file"]
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        data = base64.b64encode(path.read_bytes()).decode()
        document = document.replace(f"assets/{item['file']}", f"data:{mime};base64,{data}")
    return document


def _page_content(
    template_id: str,
    brief: LandingBrief,
    value: Mapping[str, Any] | LandingPageContent | None,
) -> LandingPageContent:
    if value is None:
        return page_content_from_brief(template_id, brief)
    if isinstance(value, LandingPageContent):
        if value.template_id != template_id:
            raise ValueError("page content template does not match the build template")
        return value
    return LandingPageContent.from_dict(value, expected_template_id=template_id)


def _render_document(
    template_id: str,
    brief: LandingBrief,
    content: LandingPageContent,
    *,
    preview: bool = False,
) -> str:
    labels = _labels(brief.language)
    hero = content.blocks["hero"]
    problem = content.blocks["problem"]
    features = content.blocks["features"]
    steps = content.blocks["steps"]
    proof = content.blocks["proof"]
    faq = content.blocks["faq"]
    final_cta = content.blocks["final_cta"]
    values = {
        "lang": brief.language,
        "page_title": escape(f"Natal — {hero['title']}"),
        "description": escape(str(hero["body"])),
        "hero_eyebrow": escape(str(hero["eyebrow"])),
        "hero_title": escape(str(hero["title"])),
        "hero_body": escape(str(hero["body"])),
        "hero_cta_label": escape(str(hero["cta_label"])),
        "cta_label": escape(str(hero["cta_label"])),
        "problem_eyebrow": escape(str(problem["eyebrow"])),
        "problem_title": escape(str(problem["title"])),
        "problem_body": escape(str(problem["body"])),
        "features_eyebrow": escape(str(features["eyebrow"])),
        "features_title": escape(str(features["title"])),
        "feature_cards": _feature_cards(features["items"]),
        "steps_eyebrow": escape(str(steps["eyebrow"])),
        "steps_title": escape(str(steps["title"])),
        "steps": _steps(steps["items"]),
        "proof_eyebrow": escape(str(proof["eyebrow"])),
        "proof_title": escape(str(proof["title"])),
        "proof_points": _proof_points(proof["items"], str(proof["empty_text"])),
        "faq_eyebrow": escape(str(faq["eyebrow"])),
        "faq_title": escape(str(faq["title"])),
        "faq_items": _faq_items(faq["items"]),
        "final_title": escape(str(final_cta["title"])),
        "final_body": escape(str(final_cta["body"])),
        "final_cta_label": escape(str(final_cta["cta_label"])),
        "cta_url": "#preview-action" if preview else escape(brief.cta["url"], quote=True),
        **labels,
    }
    source_template = ROOT / "templates" / template_id / "index.html.tmpl"
    return Template(source_template.read_text()).substitute(values)


def _preview_script(template_id: str) -> str:
    encoded_template = json.dumps(template_id)
    return f"""
(() => {{
  const templateId = {encoded_template};
  const select = (node) => {{
    document.querySelectorAll('[data-landing-block]').forEach((item) => item.classList.remove('landing-block-selected'));
    node.classList.add('landing-block-selected');
    window.parent.postMessage({{ type: 'natal.select-block', templateId, blockId: node.dataset.landingBlock }}, '*');
  }};
  document.querySelectorAll('[data-landing-block]').forEach((node) => {{
    node.tabIndex = 0;
    node.setAttribute('role', 'button');
    node.setAttribute('aria-label', `Edit ${{node.dataset.landingBlock}} block`);
    node.addEventListener('click', (event) => {{ event.preventDefault(); event.stopPropagation(); select(node); }});
    node.addEventListener('keydown', (event) => {{
      if (event.key === 'Enter' || event.key === ' ') {{ event.preventDefault(); event.stopPropagation(); select(node); }}
    }});
  }});
  document.querySelectorAll('a').forEach((link) => link.addEventListener('click', (event) => event.preventDefault()));
}})();
""".strip()


def _feature_cards(features: Iterable[Mapping[str, str]]) -> str:
    icons = ("convenient.svg", "flex.svg", "prof.svg", "quality.svg", "safety.svg")
    return "\n".join(
        f'''<article class="feature-card"><img src="assets/{icons[index % len(icons)]}" alt="" aria-hidden="true"><div><span>{index + 1:02d}</span><h3>{escape(item["title"])}</h3><p>{escape(item["description"])}</p></div></article>'''
        for index, item in enumerate(features)
    )


def _steps(steps: Iterable[Mapping[str, str]]) -> str:
    return "\n".join(
        f'''<li><strong>{escape(item["title"])}</strong><p>{escape(item["description"])}</p></li>'''
        for item in steps
    )


def _proof_points(points: Iterable[str], empty_text: str) -> str:
    values = list(points)
    if not values:
        return f'<li class="honest-empty">{escape(empty_text)}</li>'
    return "\n".join(f'<li><span>✓</span>{escape(item)}</li>' for item in values)


def _faq_items(items: Iterable[Mapping[str, str]]) -> str:
    values = list(items)
    return "\n".join(
        f'''<details><summary>{escape(item["question"])}</summary><p>{escape(item["answer"])}</p></details>'''
        for item in values
    )


def _labels(language: str) -> dict[str, str]:
    if language == "en":
        return {
            "nav_features": "Benefits", "nav_how": "How it works", "nav_faq": "FAQ",
            "skip_link": "Skip to content",
            "eyebrow": "A focused way forward", "audience_label": "Built for",
            "pain_label": "The problem", "features_label": "What Natal changes",
            "features_title": "Less friction. A clearer next step.", "how_label": "How it works",
            "how_title": "From first intent to useful progress", "proof_label": "Evidence",
            "proof_title": "What supports this promise", "proof_empty": "No customer result is claimed yet. Add verified proof after the experiment.",
            "faq_label": "Questions", "faq_title": "Before you start", "final_title": "Ready for a simpler next step?",
            "faq_question": "What exactly is available?", "faq_answer": "This page presents the evaluated concept. Confirm delivery details before launch.",
            "faq_name_question": "Is the product called Natal?", "faq_name_answer": "Yes. Every landing in this kit uses the Natal name and canonical logo.",
        }
    return {
        "nav_features": "Переваги", "nav_how": "Як працює", "nav_faq": "Питання",
        "skip_link": "Перейти до основного контенту",
        "eyebrow": "Чіткий шлях уперед", "audience_label": "Для кого",
        "pain_label": "Проблема", "features_label": "Що змінює Natal",
        "features_title": "Менше тертя. Зрозуміліший наступний крок.", "how_label": "Як це працює",
        "how_title": "Від першого наміру до корисного прогресу", "proof_label": "Докази",
        "proof_title": "Що підтверджує цю обіцянку", "proof_empty": "Ми ще не заявляємо про результати клієнтів. Додайте лише перевірені докази після експерименту.",
        "faq_label": "Питання", "faq_title": "Перед початком", "final_title": "Готові до простішого наступного кроку?",
        "faq_question": "Що саме вже доступно?", "faq_answer": "Ця сторінка представляє оцінену концепцію. Перед запуском підтвердьте деталі надання послуги.",
        "faq_name_question": "Продукт називається Natal?", "faq_name_answer": "Так. Кожен лендинг у цьому наборі використовує назву Natal і канонічний логотип.",
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a Natal landing page from a JSON brief")
    parser.add_argument("--list-templates", action="store_true")
    parser.add_argument("--recommend", type=Path, help="Print a template recommendation for a candidate JSON file")
    parser.add_argument("--template", choices=[item["id"] for item in landing_templates()])
    parser.add_argument("--brief", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.list_templates:
        print(json.dumps({"items": landing_templates()}, ensure_ascii=False, indent=2))
        return
    if args.recommend:
        print(recommend_template(json.loads(args.recommend.read_text())))
        return
    if not args.template or not args.brief or not args.output:
        raise SystemExit("--template, --brief, and --output are required")
    result = build_landing(
        args.template,
        json.loads(args.brief.read_text()),
        args.output,
        overwrite=args.overwrite,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
