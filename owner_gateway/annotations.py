from __future__ import annotations

import math
from typing import Any, Mapping


def coordinate(value: Mapping[str, Any], name: str) -> float:
    number = float(value.get(name))
    if not math.isfinite(number) or not 0 <= number <= 1:
        raise ValueError(f"annotation point {name} must be within [0,1]")
    return number


def region(value: Mapping[str, Any]) -> dict[str, Any]:
    kind = value.get("kind")
    result = {"id": str(value.get("id", ""))[:80], "kind": kind, "comment": str(value.get("comment", ""))[:1000]}
    if not result["id"] or not result["comment"]:
        raise ValueError("annotation id and comment are required")
    if kind == "pin":
        result.update(x=coordinate(value, "x"), y=coordinate(value, "y"))
    elif kind == "rectangle":
        result.update(x=coordinate(value, "x"), y=coordinate(value, "y"), width=coordinate(value, "width"), height=coordinate(value, "height"))
        if result["x"] + result["width"] > 1 or result["y"] + result["height"] > 1:
            raise ValueError("annotation rectangle must remain within [0,1]")
    elif kind == "freehand":
        points = value.get("points")
        if not isinstance(points, list) or not 2 <= len(points) <= 500:
            raise ValueError("freehand annotation requires 2-500 points")
        result["points"] = [{"x": coordinate(point, "x"), "y": coordinate(point, "y")} for point in points]
    else:
        raise ValueError("annotation kind must be pin, rectangle, or freehand")
    return result
