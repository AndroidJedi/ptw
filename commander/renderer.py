"""Deterministic server-side Instagram Story rendering adapter."""

from __future__ import annotations

import hashlib
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps


class InstagramStoryRenderer:
    width = 1080
    height = 1920

    def __init__(self, output_directory: Path) -> None:
        self.output_directory = output_directory
        output_directory.mkdir(parents=True, exist_ok=True)

    def render(
        self,
        *,
        creative_id: str,
        hook: str,
        caption: str,
        cta: str,
        hero_image: Path | None = None,
    ) -> tuple[Path, str]:
        canvas = self._background(hero_image)
        draw = ImageDraw.Draw(canvas)
        headline_font = self._font(88, bold=True)
        body_font = self._font(44)
        cta_font = self._font(46, bold=True)

        draw.rounded_rectangle((62, 110, 1018, 760), radius=42, fill=(0, 0, 0, 190))
        self._centered(draw, hook, headline_font, 110, 760, 16, fill="white")
        self._centered(draw, caption, body_font, 1190, 1510, 32, fill="white")
        draw.rounded_rectangle((145, 1605, 935, 1775), radius=85, fill=(0, 0, 0, 255), outline="white", width=3)
        self._centered(draw, cta, cta_font, 1605, 1775, 24, fill=(244, 6, 110))
        draw.text((62, 1820), "PROVE THEM WRONG", font=self._font(30, bold=True), fill="white")

        path = self.output_directory / f"{creative_id}.png"
        canvas.convert("RGB").save(path, "PNG", optimize=True)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        return path, digest

    def _background(self, hero_image: Path | None) -> Image.Image:
        if hero_image is not None:
            with Image.open(hero_image) as source:
                image = ImageOps.fit(source.convert("RGB"), (self.width, self.height))
                return ImageEnhance.Brightness(image).enhance(0.62).convert("RGBA")
        gradient = Image.linear_gradient("L").resize((self.width, self.height))
        return ImageOps.colorize(
            gradient, black=(244, 6, 110), white=(75, 24, 180)
        ).convert("RGBA")

    @staticmethod
    def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        candidates = [
            Path("assets/fonts/Roboto-Bold.ttf" if bold else "assets/fonts/Roboto-Regular.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        ]
        for path in candidates:
            if path.is_file():
                return ImageFont.truetype(str(path), size)
        return ImageFont.load_default()

    @staticmethod
    def _centered(
        draw: ImageDraw.ImageDraw,
        value: str,
        font: ImageFont.ImageFont,
        top: int,
        bottom: int,
        wrap: int,
        *,
        fill: str | tuple[int, int, int],
    ) -> None:
        lines = textwrap.wrap(value.strip(), width=wrap) or [""]
        spacing = 16
        boxes = [draw.textbbox((0, 0), line, font=font) for line in lines]
        heights = [box[3] - box[1] for box in boxes]
        total = sum(heights) + spacing * (len(lines) - 1)
        y = top + max(0, (bottom - top - total) // 2)
        for line, box, height in zip(lines, boxes, heights, strict=True):
            width = box[2] - box[0]
            draw.text(((1080 - width) / 2, y), line, font=font, fill=fill)
            y += height + spacing
