"""Build a dependency-free Natal landing site from a validated brief."""

from __future__ import annotations

import argparse
import hashlib
from html import escape
import json
from pathlib import Path
import shutil
from string import Template
from typing import Any, Iterable, Mapping

from .brief import LandingBrief
from .catalog import ROOT, landing_templates, recommend_template, template_manifest


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
    overwrite: bool = False,
) -> dict[str, Any]:
    manifest = template_manifest(template_id)
    brief = brief_value if isinstance(brief_value, LandingBrief) else LandingBrief.from_dict(brief_value)
    output = output_directory.resolve()
    if output.exists() and any(output.iterdir()) and not overwrite:
        raise FileExistsError(f"output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    verify_brand_assets()

    labels = _labels(brief.language)
    values = {
        "lang": brief.language,
        "page_title": escape(f"Natal — {brief.business_idea}"),
        "description": escape(brief.promise),
        "business_idea": escape(brief.business_idea),
        "target_audience": escape(brief.target_audience),
        "pain": escape(brief.pain),
        "promise": escape(brief.promise),
        "cta_label": escape(brief.cta["label"]),
        "cta_url": escape(brief.cta["url"], quote=True),
        "feature_cards": _feature_cards(brief.key_features),
        "steps": _steps(brief.steps),
        "proof_points": _proof_points(brief.proof_points, labels),
        "faq_items": _faq_items(brief.faq, labels),
        **labels,
    }
    source_template = ROOT / "templates" / template_id / "index.html.tmpl"
    document = Template(source_template.read_text()).substitute(values)
    (output / "index.html").write_text(document)
    shutil.copyfile(SHARED_ROOT / "styles.css", output / "styles.css")
    shutil.copyfile(SHARED_ROOT / "app.js", output / "app.js")
    assets = output / "assets"
    assets.mkdir(exist_ok=True)
    for item in _asset_manifest()["assets"]:
        shutil.copyfile(ASSET_ROOT / item["file"], assets / item["file"])
    (output / "brief.json").write_text(json.dumps(brief.to_dict(), ensure_ascii=False, indent=2) + "\n")
    normalized_brief = json.dumps(brief.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    build = {
        "schema_version": 1,
        "brand": "Natal",
        "template_id": template_id,
        "template_version": manifest["version"],
        "source": dict(brief.source or {}),
        "brief_sha256": hashlib.sha256(normalized_brief.encode()).hexdigest(),
        "template_sha256": hashlib.sha256(source_template.read_bytes()).hexdigest(),
        "files": ["index.html", "styles.css", "app.js", "brief.json", *[f"assets/{item['file']}" for item in _asset_manifest()["assets"]]],
    }
    (output / "build.json").write_text(json.dumps(build, ensure_ascii=False, indent=2) + "\n")
    return build


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


def _proof_points(points: Iterable[str], labels: Mapping[str, str]) -> str:
    values = list(points)
    if not values:
        return f'<li class="honest-empty">{escape(labels["proof_empty"])}</li>'
    return "\n".join(f'<li><span>✓</span>{escape(item)}</li>' for item in values)


def _faq_items(items: Iterable[Mapping[str, str]], labels: Mapping[str, str]) -> str:
    values = list(items)
    if not values:
        values = [
            {"question": labels["faq_question"], "answer": labels["faq_answer"]},
            {"question": labels["faq_name_question"], "answer": labels["faq_name_answer"]},
        ]
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
