"""Canonical Natal identity available across PTW Studio surfaces."""

from __future__ import annotations

import hashlib
from functools import lru_cache
from io import BytesIO
from pathlib import Path
import re


NATAL_LOGO_PATH = Path(__file__).resolve().parents[1] / "natal/assets/logo-natal.png"
NATAL_FONT_PATH = Path(__file__).resolve().parents[1] / "natal/assets/inter.ttf"
NATAL_LOGO_SHA256 = "f465a0e11be3c1ff1943bcc1bcd19246a9a54957fd5c1c6162081aec9a59c8ba"
NATAL_FONT_SHA256 = "29160a80ff49ddcab2c97711247e08b1fab27a484a329ce8b813d820dc559031"
NATAL_SYMBOL_COLOR = "#87D0DD"
NATAL_NAME_COLOR = "#383840"
_NATAL_SYMBOL_RIGHT = 102
_COLOR = re.compile(r"#[0-9A-F]{6}")


def _verified_bytes(path: Path, expected_digest: str, label: str) -> bytes:
    try:
        data = path.read_bytes()
    except OSError as error:
        raise RuntimeError(f"canonical Natal {label} is unavailable") from error
    if hashlib.sha256(data).hexdigest() != expected_digest:
        raise RuntimeError(f"canonical Natal {label} digest does not match the approved asset")
    return data


@lru_cache(maxsize=1)
def natal_logo_bytes() -> bytes:
    _verified_bytes(NATAL_FONT_PATH, NATAL_FONT_SHA256, "font")
    return _verified_bytes(NATAL_LOGO_PATH, NATAL_LOGO_SHA256, "logo")


def normalize_natal_logo_colors(value: object) -> dict[str, str]:
    """Validate the two owner-tunable colors without changing brand geometry."""

    if not isinstance(value, dict) or set(value) != {"symbol_color", "name_color"}:
        raise ValueError("Natal logo colors must contain symbol_color and name_color")
    result = {
        "symbol_color": str(value["symbol_color"]).upper(),
        "name_color": str(value["name_color"]).upper(),
    }
    if not _COLOR.fullmatch(result["symbol_color"]):
        raise ValueError("Natal symbol color must be a six-digit hex color")
    if not _COLOR.fullmatch(result["name_color"]):
        raise ValueError("Natal name color must be a six-digit hex color")
    return result


@lru_cache(maxsize=64)
def natal_logo_colored_bytes(
    symbol_color: str = NATAL_SYMBOL_COLOR,
    name_color: str = NATAL_NAME_COLOR,
) -> bytes:
    """Return a deterministic two-color lock-up with the original alpha mask.

    The symbol occupies the first connected artwork segment. Recoloring by
    segment, rather than by source RGB, makes its former dark inner stroke use
    the selected symbol color while the NATAL word remains independent.
    """

    colors = normalize_natal_logo_colors({
        "symbol_color": symbol_color, "name_color": name_color,
    })
    if colors == {
        "symbol_color": NATAL_SYMBOL_COLOR, "name_color": NATAL_NAME_COLOR,
    }:
        return natal_logo_bytes()

    from PIL import Image

    def rgb(value: str) -> tuple[int, int, int]:
        return tuple(int(value[index:index + 2], 16) for index in (1, 3, 5))

    with Image.open(BytesIO(natal_logo_bytes())) as source:
        image = source.convert("RGBA")
    symbol_rgb = rgb(colors["symbol_color"])
    name_rgb = rgb(colors["name_color"])
    pixels = image.load()
    for y in range(image.height):
        for x in range(image.width):
            alpha = pixels[x, y][3]
            if alpha:
                pixels[x, y] = (*(
                    symbol_rgb if x <= _NATAL_SYMBOL_RIGHT else name_rgb
                ), alpha)
    output = BytesIO()
    image.save(output, format="PNG", optimize=False)
    return output.getvalue()


@lru_cache(maxsize=32)
def natal_symbol_bytes(symbol_color: str = NATAL_SYMBOL_COLOR) -> bytes:
    """Return only the digest-verified Natal symbol for decorative reuse."""

    from PIL import Image
    normalize_natal_logo_colors({
        "symbol_color": symbol_color,
        "name_color": NATAL_NAME_COLOR,
    })
    with Image.open(BytesIO(natal_logo_colored_bytes(symbol_color, NATAL_NAME_COLOR))) as source:
        symbol = source.convert("RGBA").crop((0, 0, _NATAL_SYMBOL_RIGHT + 1, source.height))
    output = BytesIO()
    symbol.save(output, format="PNG", optimize=False)
    return output.getvalue()
