"""Deterministic 1080x1350 composition over a generated ad visual."""

from __future__ import annotations

import hashlib
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps

from .ad_provider import AdCreativeSpec


class InstagramAdRenderer:
    source_size = (1536, 1920)
    width = 1080
    height = 1350

    def __init__(self, output_directory: Path) -> None:
        self.output_directory = output_directory
        self.output_directory.mkdir(parents=True, exist_ok=True)

    def render(
        self, *, slot_key: str, source_path: Path, spec: AdCreativeSpec
    ) -> tuple[Path, str]:
        with Image.open(source_path) as source:
            if source.size != self.source_size:
                raise ValueError(
                    f"generated ad visual must be {self.source_size[0]}x{self.source_size[1]}"
                )
            canvas = ImageOps.fit(source.convert("RGB"), (self.width, self.height)).convert("RGBA")
        canvas = ImageEnhance.Brightness(canvas).enhance(0.72)
        overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        draw.rectangle((0, 0, self.width, self.height), fill=(8, 6, 18, 42))
        draw.rounded_rectangle((52, 54, 1028, 650), radius=38, fill=(0, 0, 0, 174))
        draw.rounded_rectangle((70, 950, 1010, 1248), radius=34, fill=(0, 0, 0, 205))
        canvas = Image.alpha_composite(canvas, overlay)
        draw = ImageDraw.Draw(canvas)

        accent = (244, 6, 110)
        self._fitted(
            draw, spec.concept_name.upper(), (70, 78, 990, 140),
            maximum_size=34, minimum_size=18, bold=True, fill=accent,
        )
        self._fitted(
            draw, spec.hook, (70, 150, 990, 605),
            maximum_size=82, minimum_size=38, bold=True,
        )
        self._fitted(
            draw,
            spec.supporting_copy,
            (92, 974, 988, 1135),
            maximum_size=39,
            minimum_size=22,
        )
        cta_font = self._single_line_font(draw, spec.cta.upper(), 760, 38, 22)
        cta_box = draw.textbbox((0, 0), spec.cta.upper(), font=cta_font)
        cta_width = cta_box[2] - cta_box[0]
        x1 = max(90, (self.width - cta_width) // 2 - 42)
        x2 = min(990, (self.width + cta_width) // 2 + 42)
        draw.rounded_rectangle((x1, 1155, x2, 1228), radius=32, fill=accent)
        draw.text(
            ((self.width - cta_width) / 2, 1168),
            spec.cta.upper(),
            font=cta_font,
            fill="white",
        )
        draw.text(
            (70, 1284),
            "CONCEPT AD · ESTIMATION",
            font=self._font(24, bold=True),
            fill=(235, 235, 240),
        )

        path = self.output_directory / f"{slot_key}.png"
        canvas.convert("RGB").save(path, "PNG", optimize=True)
        return path, hashlib.sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        candidates = (
            Path("assets/fonts/Roboto-Bold.ttf" if bold else "assets/fonts/Roboto-Regular.ttf"),
            Path(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
                if bold
                else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
            ),
        )
        for path in candidates:
            if path.is_file():
                return ImageFont.truetype(str(path), size)
        return ImageFont.load_default()

    def _fitted(
        self,
        draw: ImageDraw.ImageDraw,
        value: str,
        box: tuple[int, int, int, int],
        *,
        maximum_size: int,
        minimum_size: int,
        bold: bool = False,
        fill: str | tuple[int, int, int] = "white",
    ) -> None:
        left, top, right, bottom = box
        width, height = right - left, bottom - top
        selected: tuple[ImageFont.ImageFont, list[str], int, int] | None = None
        for size in range(maximum_size, minimum_size - 1, -2):
            font = self._font(size, bold=bold)
            lines = self._pixel_wrap(draw, value.strip(), font, width)
            spacing = max(5, size // 7)
            bounds = draw.multiline_textbbox(
                (0, 0), "\n".join(lines), font=font, spacing=spacing
            )
            text_height = bounds[3] - bounds[1]
            selected = (font, lines, spacing, text_height)
            if text_height <= height:
                break
        assert selected is not None
        font, lines, spacing, text_height = selected
        y = top + max(0, (height - text_height) // 2)
        draw.multiline_text(
            (left, y), "\n".join(lines), font=font, fill=fill, spacing=spacing
        )

    def _single_line_font(
        self,
        draw: ImageDraw.ImageDraw,
        value: str,
        width: int,
        maximum_size: int,
        minimum_size: int,
    ) -> ImageFont.ImageFont:
        for size in range(maximum_size, minimum_size - 1, -2):
            font = self._font(size, bold=True)
            if draw.textlength(value, font=font) <= width:
                return font
        return self._font(minimum_size, bold=True)

    @staticmethod
    def _pixel_wrap(
        draw: ImageDraw.ImageDraw,
        value: str,
        font: ImageFont.ImageFont,
        width: int,
    ) -> list[str]:
        words = value.split() or [""]
        lines: list[str] = []
        current = ""
        for word in words:
            candidate = word if not current else f"{current} {word}"
            if current and draw.textlength(candidate, font=font) > width:
                lines.append(current)
                current = word
            else:
                current = candidate
        lines.append(current)
        return lines
