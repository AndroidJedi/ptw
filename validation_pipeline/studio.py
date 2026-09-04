"""Shared media validation and primitive renderer entrypoint for Universal Studio."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any, Mapping

from .natal_brand import NATAL_FONT_PATH


MAX_IMAGE_BYTES = 12 * 1024 * 1024
SUPPORTED_FONTS = {
    "Inter": NATAL_FONT_PATH,
    "DejaVu Sans": Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    "DejaVu Serif": Path("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"),
    "DejaVu Mono": Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"),
}
STUDIO_PREVIEW_FONTS = {
    "Roboto Condensed": Path(__file__).with_name("studio_assets") / "fonts" / "Roboto-Variable.ttf",
    "Manrope": Path(__file__).with_name("studio_assets") / "fonts" / "Manrope-Variable.ttf",
    "Montserrat": Path(__file__).with_name("studio_assets") / "fonts" / "Montserrat-Variable.ttf",
    "Source Sans 3": Path(__file__).with_name("studio_assets") / "fonts" / "SourceSans3-Variable.ttf",
    "Oswald": Path(__file__).with_name("studio_assets") / "fonts" / "Oswald-Variable.ttf",
    "Cormorant Garamond": (
        Path(__file__).with_name("studio_assets") / "fonts" / "CormorantGaramond-Variable.ttf"
    ),
    "Cormorant Garamond Italic": (
        Path(__file__).with_name("studio_assets") / "fonts" / "CormorantGaramond-Italic-Variable.ttf"
    ),
    "Lora": Path(__file__).with_name("studio_assets") / "fonts" / "Lora-Variable.ttf",
    "Lora Italic": Path(__file__).with_name("studio_assets") / "fonts" / "Lora-Italic-Variable.ttf",
}
STUDIO_FONT_FAMILIES = (
    "Inter", "Roboto Condensed", "Manrope", "Montserrat", "Source Sans 3",
    "Oswald", "Cormorant Garamond", "Cormorant Garamond Italic", "Lora",
    "Lora Italic",
)


def inspect_media(data: bytes, declared_mime: str) -> dict[str, Any]:
    if declared_mime not in {"image/jpeg", "image/png", "image/webp"}:
        raise ValueError("Studio assets must be JPEG, PNG, or WebP images")
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise ValueError("Studio image exceeds the bounded size")
    from PIL import Image

    try:
        image = Image.open(BytesIO(data))
        image.load()
    except Exception as error:
        raise ValueError("Studio image cannot be decoded") from error
    actual = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}.get(image.format)
    if actual != declared_mime:
        raise ValueError("Studio image MIME does not match its decoded format")
    if image.width < 64 or image.height < 64 or image.width > 12000 or image.height > 12000:
        raise ValueError("Studio image dimensions are outside the bounded range")
    return {
        "mime_type": actual, "width": image.width, "height": image.height,
        "duration_seconds": None,
    }


class StudioRenderer:
    """Render Universal Studio primitive trees deterministically."""

    def __init__(self, font_path: Path = SUPPORTED_FONTS["Inter"]) -> None:
        self.font_path = font_path

    def _font(self, size: int, font_name: str = "Inter", weight: int | None = None):
        from PIL import ImageFont

        path = STUDIO_PREVIEW_FONTS.get(
            font_name, SUPPORTED_FONTS.get(font_name, self.font_path),
        )
        try:
            font = ImageFont.truetype(str(path), max(12, size))
            if weight is not None:
                try:
                    values = []
                    for axis in font.get_variation_axes():
                        name = bytes(axis["name"]).decode("ascii", "ignore").lower()
                        if "width" in name and font_name == "Roboto Condensed":
                            values.append(75)
                        elif "weight" in name:
                            values.append(max(axis["minimum"], min(axis["maximum"], int(weight))))
                        else:
                            values.append(axis["default"])
                    font.set_variation_by_axes(values)
                    return font
                except (AttributeError, KeyError, OSError, TypeError, ValueError):
                    pass
                variation = {
                    100: "Thin", 200: "ExtraLight", 300: "Light", 400: "Regular",
                    500: "Medium", 600: "SemiBold", 700: "Bold",
                    800: "ExtraBold", 900: "Black",
                }.get(int(weight), "Medium")
                try:
                    font.set_variation_by_name(variation)
                except (AttributeError, OSError, ValueError):
                    pass
            return font
        except OSError:
            return ImageFont.load_default()

    def render_preview(
        self, template: Any, *, semantic_data: Mapping[str, Any],
        assets: Mapping[str, Mapping[str, Any]], width: int | None = None,
        height: int | None = None,
    ) -> dict[str, Any]:
        from .studio_primitives import PrimitivePreviewRenderer

        return PrimitivePreviewRenderer(self._font).render(
            template, semantic_data=semantic_data, assets=assets,
            width=width, height=height,
        )
