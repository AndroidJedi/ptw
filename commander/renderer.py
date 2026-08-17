"""Deterministic server-side Instagram feed-post rendering adapter."""

from __future__ import annotations

import hashlib
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps


class InstagramPostRenderer:
    width = 1080
    height = 1350

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

        draw.rounded_rectangle((58, 72, 1022, 608), radius=42, fill=(0, 0, 0, 190))
        self._centered(draw, hook, headline_font, 72, 608, 16, fill="white")
        self._centered(draw, caption, body_font, 790, 1010, 32, fill="white")
        draw.rounded_rectangle((145, 1070, 935, 1228), radius=79, fill=(0, 0, 0, 255), outline="white", width=3)
        self._centered(draw, cta, cta_font, 1070, 1228, 24, fill=(244, 6, 110))
        draw.text((58, 1280), "PROVE THEM WRONG", font=self._font(30, bold=True), fill="white")

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
        canvas = ImageOps.colorize(
            gradient, black=(244, 6, 110), white=(75, 24, 180)
        ).convert("RGBA")
        draw = ImageDraw.Draw(canvas, "RGBA")
        # Layered shapes make the fallback a complete branded composition,
        # rather than exposing a placeholder gradient when no photo is supplied.
        draw.ellipse((570, 430, 1180, 1040), fill=(255, 171, 64, 135))
        draw.polygon(
            ((0, 840), (760, 520), (1080, 710), (1080, 1350), (0, 1350)),
            fill=(22, 9, 56, 150),
        )
        draw.line((0, 900, 1080, 590), fill=(255, 255, 255, 90), width=10)
        return canvas

    @staticmethod
    def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        candidates = [
            Path("commander/assets/fonts/Roboto-Bold.ttf" if bold else "commander/assets/fonts/Roboto-Regular.ttf"),
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
            draw.text(
                ((InstagramPostRenderer.width - width) / 2, y),
                line,
                font=font,
                fill=fill,
            )
            y += height + spacing


# Preserve imports from integrations that predate feed-post generation.
InstagramStoryRenderer = InstagramPostRenderer
