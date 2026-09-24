"""Server-owned image geometry, independent of creative prompt instructions."""
from copy import deepcopy
from typing import Any, Mapping

IMAGE_OUTPUT_VERSION = "ptw.image-output.v1"


def output_specification(destination: Mapping[str, Any]) -> dict:
    mode = destination.get("mode")
    width, height = (864, 1872) if mode == "app_screen" else (1536, 1152) if mode == "app_mockup" else (1024, 1024)
    return {
        "schema": IMAGE_OUTPUT_VERSION, "width": width, "height": height,
        "background": "transparent" if mode == "app_mockup" else "opaque",
        "safe_area": {"top": .065 if mode == "app_screen" else .04,
                      "right": .04, "bottom": .04, "left": .04},
    }


def normalize_output_specification(value: Mapping[str, Any]) -> dict:
    import math
    if not isinstance(value, Mapping) or set(value) != {"schema", "width", "height", "background", "safe_area"}:
        raise ValueError("Invalid image output specification")
    if value["schema"] != IMAGE_OUTPUT_VERSION or value["background"] not in {"opaque", "transparent"}:
        raise ValueError("Unsupported image output specification")
    width, height = value["width"], value["height"]
    if any(type(n) is not int or not 512 <= n <= 2048 or n % 16 for n in (width, height)) or not 1/3 <= width/height <= 3:
        raise ValueError("Invalid image output dimensions")
    safe = value["safe_area"]
    if not isinstance(safe, Mapping) or set(safe) != {"top", "right", "bottom", "left"} or any(
        type(n) not in (int, float) or not math.isfinite(n) or not 0 <= n <= .2 for n in safe.values()
    ):
        raise ValueError("Invalid image safe area")
    return deepcopy(dict(value))


def output_prompt(value: Mapping[str, Any]) -> str:
    spec = normalize_output_specification(value)
    return (f"Output contract: one PNG, {spec['width']}x{spec['height']} pixels; preserve this aspect ratio. "
            f"Background: {spec['background']}. Safe areas are fractions of the full canvas: {spec['safe_area']}. "
            "Keep essential labels and controls inside these margins. For app screens, the top margin is "
            "the camera/status safe area; extend the screen background to every edge. "
            + ("Use actual transparent alpha outside the complete devices, including gaps between them; "
               "keep white screen interiors opaque. Do not draw a white card or checkerboard background."
               if spec["background"] == "transparent" else ""))


def validate_output_dimensions(width: int, height: int, spec: Mapping[str, Any]) -> None:
    expected = normalize_output_specification(spec)
    if not (512 <= width <= 2048 and 512 <= height <= 2048) or abs((width / height) / (expected["width"] / expected["height"]) - 1) > .03:
        raise ValueError("Generated image does not match the requested aspect ratio or dimension bounds")
