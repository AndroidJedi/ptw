"""Deterministic Brand Kit assets and React/TypeScript package assembly."""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import re
import zipfile
from typing import Any, Mapping

from .brand_domain import FONT_ASSET_ROOT, FONT_CATALOG


def _slug(value: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return result or "brand-kit"


def _css(manifest: Mapping[str, Any]) -> str:
    palette = manifest["palette"]
    typography = manifest["typography"]
    selected_fonts = list(dict.fromkeys(str(value) for value in typography.values()))
    lines = []
    for name in selected_fonts:
        font = FONT_CATALOG[name]
        lines.extend((
            "@font-face {",
            f"  font-family: '{name}';",
            f"  src: url('../fonts/{font['font_file']}') format('truetype');",
            "  font-style: normal;",
            f"  font-weight: {'100 900' if font['variable'] else '400'};",
            "  font-display: swap;",
            "}",
        ))
    lines.append(":root,")
    lines.append('[data-brand-theme="light"] {')
    for key, value in palette["light"].items():
        lines.append(f"  --brand-{key}: {value};")
    lines.extend((
        f"  --brand-font-display: '{typography['display']}', system-ui, sans-serif;",
        f"  --brand-font-body: '{typography['body']}', system-ui, sans-serif;",
        f"  --brand-font-mono: '{typography['mono']}', ui-monospace, monospace;",
        "  --brand-radius-sm: 8px;",
        "  --brand-radius-md: 14px;",
        "  --brand-radius-lg: 22px;",
        "  --brand-motion: 180ms;",
        "}",
        '[data-brand-theme="dark"] {',
    ))
    for key, value in palette["dark"].items():
        lines.append(f"  --brand-{key}: {value};")
    lines.extend((
        "}",
        ".brand-root { color: var(--brand-text); background: var(--brand-background); font-family: var(--brand-font-body); }",
        ".brand-control { min-height: 44px; border: 1px solid color-mix(in srgb, var(--brand-text) 20%, transparent); border-radius: var(--brand-radius-md); color: var(--brand-text); background: var(--brand-surface); font: inherit; }",
        ".brand-button { padding: 0 16px; font-weight: 750; cursor: pointer; transition: transform var(--brand-motion), background var(--brand-motion); }",
        '.brand-button[data-variant="primary"] { border-color: transparent; color: var(--brand-background); background: var(--brand-primary); }',
        ".brand-button:focus-visible, .brand-input:focus-visible { outline: 3px solid var(--brand-accent); outline-offset: 2px; }",
        ".brand-card { padding: 20px; border: 1px solid color-mix(in srgb, var(--brand-text) 16%, transparent); border-radius: var(--brand-radius-lg); background: var(--brand-surface); }",
        ".brand-input { width: 100%; padding: 0 12px; }",
        ".brand-badge { display: inline-flex; padding: 5px 9px; border-radius: 999px; color: var(--brand-text); background: color-mix(in srgb, var(--brand-primary) 18%, var(--brand-surface)); font-size: 12px; font-weight: 700; }",
        ".brand-alert { padding: 12px 14px; border-left: 4px solid var(--brand-accent); border-radius: var(--brand-radius-sm); background: var(--brand-surface); }",
        ".brand-tabs { display: flex; gap: 6px; }",
        '.brand-tabs button[aria-selected="true"] { border-color: var(--brand-primary); color: var(--brand-primary); }',
        "@media (prefers-reduced-motion: reduce) { .brand-root * { transition-duration: 0.001ms !important; } }",
    ))
    return "\n".join(lines) + "\n"


COMPONENTS_TSX = r'''import type { ButtonHTMLAttributes, HTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from 'react'

export function Button(props: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' }) {
  const { variant = 'primary', className = '', ...rest } = props
  return <button className={`brand-control brand-button ${className}`} data-variant={variant} {...rest} />
}
export function IconButton({ label, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { label: string }) {
  return <button className="brand-control brand-button" aria-label={label} {...props} />
}
export function TextField({ label, ...props }: InputHTMLAttributes<HTMLInputElement> & { label: string }) {
  return <label>{label}<input className="brand-control brand-input" {...props} /></label>
}
export function Select({ label, children, ...props }: SelectHTMLAttributes<HTMLSelectElement> & { label: string; children: ReactNode }) {
  return <label>{label}<select className="brand-control brand-input" {...props}>{children}</select></label>
}
export function Checkbox({ label, ...props }: InputHTMLAttributes<HTMLInputElement> & { label: string }) {
  return <label><input type="checkbox" {...props} />{label}</label>
}
export function Switch({ label, ...props }: InputHTMLAttributes<HTMLInputElement> & { label: string }) {
  return <label><input type="checkbox" role="switch" {...props} />{label}</label>
}
export function Card(props: HTMLAttributes<HTMLElement>) { return <article {...props} className={`brand-card ${props.className || ''}`} /> }
export function Badge(props: HTMLAttributes<HTMLSpanElement>) { return <span {...props} className={`brand-badge ${props.className || ''}`} /> }
export function Alert(props: HTMLAttributes<HTMLDivElement>) { return <div role="status" {...props} className={`brand-alert ${props.className || ''}`} /> }
export function Tabs({ labels, selected, onSelect }: { labels: string[]; selected: number; onSelect: (index: number) => void }) {
  return <div className="brand-tabs" role="tablist">{labels.map((label, index) => <button className="brand-control brand-button" role="tab" aria-selected={selected === index} key={label} onClick={() => onSelect(index)}>{label}</button>)}</div>
}
'''


def _theme_ts(manifest: Mapping[str, Any]) -> str:
    return "export const brandTheme = " + json.dumps({
        "name": manifest["name"],
        "palette": manifest["palette"],
        "typography": manifest["typography"],
        "radius": manifest.get("ui_system", {}).get("radius", [8, 14, 22]),
        "spacing": manifest.get("ui_system", {}).get("spacing", [4, 8, 12, 16, 24, 32, 48]),
    }, ensure_ascii=False, indent=2) + " as const\n"


def render_wordmarks(logo_path: Path, manifest: Mapping[str, Any], output_directory: Path) -> dict[str, Path]:
    from PIL import Image, ImageDraw, ImageFont

    symbol = Image.open(logo_path).convert("RGBA")
    name = str(manifest["name"])
    font_path = _verified_font_path(str(manifest["typography"]["display"]))
    font = ImageFont.truetype(str(font_path), 116)
    output: dict[str, Path] = {}
    for theme in ("light", "dark"):
        palette = manifest["palette"][theme]
        canvas = Image.new("RGBA", (1800, 480), palette["background"])
        resized = symbol.copy()
        resized.thumbnail((330, 330))
        canvas.alpha_composite(resized, (70, (480 - resized.height) // 2))
        draw = ImageDraw.Draw(canvas)
        draw.text((450, 240), name, font=font, fill=palette["text"], anchor="lm")
        path = output_directory / f"wordmark-{theme}.png"
        canvas.save(path, "PNG")
        output[theme] = path
    icon = symbol.resize((256, 256), Image.Resampling.LANCZOS)
    icon_path = output_directory / "app-icon.png"
    icon.save(icon_path, "PNG")
    output["icon"] = icon_path
    favicon = symbol.resize((64, 64), Image.Resampling.LANCZOS)
    favicon_path = output_directory / "favicon.png"
    favicon.save(favicon_path, "PNG")
    output["favicon"] = favicon_path
    return output


def _verified_font_path(name: str) -> Path:
    details = FONT_CATALOG[name]
    path = FONT_ASSET_ROOT / str(details["font_file"])
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != details["font_sha256"]:
        raise RuntimeError(f"bundled font checksum mismatch: {name}")
    return path


def _font_files(selected_fonts: list[str]) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    for name in selected_fonts:
        details = FONT_CATALOG[name]
        font_path = _verified_font_path(name)
        license_path = FONT_ASSET_ROOT / str(details["license_file"])
        if hashlib.sha256(license_path.read_bytes()).hexdigest() != details["license_sha256"]:
            raise RuntimeError(f"bundled font license checksum mismatch: {name}")
        files[f"fonts/{font_path.name}"] = font_path.read_bytes()
        files[f"fonts/{license_path.name}"] = license_path.read_bytes()
    return files


def assemble_brand_kit(manifest: Mapping[str, Any], logo_path: Path, output_directory: Path) -> tuple[Path, str, dict[str, Any]]:
    output_directory.mkdir(parents=True, exist_ok=True)
    wordmarks = render_wordmarks(logo_path, manifest, output_directory)
    package_name = f"@ptw/{_slug(str(manifest['name']))}-brand-kit"
    selected_fonts = list(dict.fromkeys(str(value) for value in manifest["typography"].values()))
    package = {
        "name": package_name,
        "version": "1.0.0",
        "private": True,
        "type": "module",
        "peerDependencies": {"react": ">=18", "react-dom": ">=18"},
        "exports": {".": "./src/index.ts", "./tokens.css": "./src/tokens.css"},
    }
    kit_manifest = {
        **dict(manifest),
        "pipeline_version": "branding_v1",
        "naming_clearance": "competitor_collision_screen_only; trademark and domain clearance required",
        "font_catalog": {name: FONT_CATALOG[name] for name in selected_fonts},
        "assets": {"logo": "assets/logo-symbol.png", "wordmark_light": "assets/wordmark-light.png", "wordmark_dark": "assets/wordmark-dark.png", "app_icon": "assets/app-icon.png", "favicon": "assets/favicon.png"},
    }
    files: dict[str, bytes] = {
        "package.json": (json.dumps(package, ensure_ascii=False, indent=2) + "\n").encode(),
        "brand-kit.json": (json.dumps(kit_manifest, ensure_ascii=False, indent=2) + "\n").encode(),
        "src/tokens.css": _css(manifest).encode(),
        "src/theme.ts": _theme_ts(manifest).encode(),
        "src/components.tsx": COMPONENTS_TSX.encode(),
        "src/index.ts": b"export * from './theme'\nexport * from './components'\nimport './tokens.css'\n",
        "README.md": (f"# {manifest['name']} Brand Kit\n\nGenerated from an approved PTW Branding run. Set `data-brand-theme=\"light\"` or `dark` on the root element.\n\nThe name passed a bounded competitor collision screen only. Complete trademark and domain clearance before launch.\n").encode(),
        "fonts/catalog.json": (json.dumps({name: FONT_CATALOG[name] for name in selected_fonts}, indent=2) + "\n").encode(),
        "assets/logo-symbol.png": logo_path.read_bytes(),
        "assets/wordmark-light.png": wordmarks["light"].read_bytes(),
        "assets/wordmark-dark.png": wordmarks["dark"].read_bytes(),
        "assets/app-icon.png": wordmarks["icon"].read_bytes(),
        "assets/favicon.png": wordmarks["favicon"].read_bytes(),
    }
    files.update(_font_files(selected_fonts))
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(files):
            archive.writestr(name, files[name])
    content = stream.getvalue()
    digest = hashlib.sha256(content).hexdigest()
    path = output_directory / f"brand-kit-{digest[:16]}.zip"
    path.write_bytes(content)
    return path, digest, kit_manifest
