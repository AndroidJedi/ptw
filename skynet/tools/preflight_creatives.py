#!/usr/bin/env python3
"""Audit frozen SKYNET creatives with one deterministic, pixel-level gate.

The manifest and queue checks use only the standard library. Pixel checks use
Pillow from the repository virtual environment so the actual master PNG, not a
browser preview or a hash alone, remains the visual authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import tempfile
from typing import Any, Iterable, Mapping, Sequence


SCHEMA = "ptw.skynet.frozen-creative-preflight.v1"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def require_regular_below(root: Path, path: Path) -> Path:
    root = root.resolve()
    absolute = path if path.is_absolute() else root / path
    lexical = absolute.parent.resolve() / absolute.name
    if lexical != root and root not in lexical.parents:
        raise ValueError(f"path leaves SKYNET root: {path}")
    cursor = root
    for part in lexical.relative_to(root).parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"symlink is not accepted as durable evidence: {path}")
    if not lexical.is_file():
        raise FileNotFoundError(lexical)
    return lexical


def recorded_entries(value: object) -> list[Mapping[str, Any]]:
    if isinstance(value, list):
        return [entry for entry in value if isinstance(entry, Mapping)]
    if isinstance(value, Mapping):
        return [entry for entry in value.values() if isinstance(entry, Mapping)]
    return []


def resolve_recorded_path(root: Path, manifest_path: Path, recorded: str) -> Path:
    local = manifest_path.parent / recorded
    if local.is_file():
        return require_regular_below(root, local)
    return require_regular_below(root, root / recorded)


def hex_rgb(value: str) -> tuple[int, int, int]:
    normalized = value.removeprefix("#")
    if len(normalized) != 6:
        raise ValueError(f"expected six-digit RGB color, received {value!r}")
    return tuple(bytes.fromhex(normalized))  # type: ignore[return-value]


def relative_luminance(color: Sequence[int]) -> float:
    channels = []
    for byte in color[:3]:
        normalized = byte / 255
        channels.append(
            normalized / 12.92
            if normalized <= 0.04045
            else ((normalized + 0.055) / 1.055) ** 2.4
        )
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def contrast_ratio(first: Sequence[int], second: Sequence[int]) -> float:
    first_luminance = relative_luminance(first)
    second_luminance = relative_luminance(second)
    return (max(first_luminance, second_luminance) + 0.05) / (
        min(first_luminance, second_luminance) + 0.05
    )


def color_distance(first: Sequence[int], second: Sequence[int]) -> float:
    return math.sqrt(sum((first[index] - second[index]) ** 2 for index in range(3)))


def ltrb(box: Mapping[str, int]) -> tuple[int, int, int, int]:
    return (
        box["x"],
        box["y"],
        box["x"] + box["width"],
        box["y"] + box["height"],
    )


def box_inside_canvas(box: Mapping[str, int], width: int, height: int) -> bool:
    left, top, right, bottom = ltrb(box)
    return left >= 0 and top >= 0 and right <= width and bottom <= height


def edge_clearances(
    assigned: Mapping[str, int], visible: Sequence[int]
) -> dict[str, int]:
    left, top, right, bottom = ltrb(assigned)
    return {
        "left": visible[0] - left,
        "top": visible[1] - top,
        "right": right - visible[2],
        "bottom": bottom - visible[3],
    }


def pixels_in_box(image: Any, box: Mapping[str, int]) -> Iterable[tuple[int, int, tuple[int, int, int]]]:
    left, top, right, bottom = ltrb(box)
    for y_position in range(top, bottom):
        for x_position in range(left, right):
            value = image.getpixel((x_position, y_position))
            yield x_position, y_position, tuple(value[:3])


def visible_color_bounds(
    image: Any,
    box: Mapping[str, int],
    targets: Sequence[Sequence[int]],
    tolerance: float,
) -> tuple[int, tuple[int, int, int, int] | None, list[tuple[int, int, int]]]:
    visible: list[tuple[int, int, tuple[int, int, int]]] = []
    background: list[tuple[int, int, int]] = []
    background_threshold = tolerance * 1.5
    for x_position, y_position, pixel in pixels_in_box(image, box):
        distance = min(color_distance(pixel, target) for target in targets)
        if distance <= tolerance:
            visible.append((x_position, y_position, pixel))
        elif distance > background_threshold:
            background.append(pixel)
    if not visible:
        return 0, None, background
    bounds = (
        min(pixel[0] for pixel in visible),
        min(pixel[1] for pixel in visible),
        max(pixel[0] for pixel in visible) + 1,
        max(pixel[1] for pixel in visible) + 1,
    )
    return len(visible), bounds, background


def median_rgb(pixels: Sequence[Sequence[int]]) -> tuple[int, int, int]:
    if not pixels:
        raise ValueError("background sample is empty")
    return tuple(
        round(statistics.median(pixel[channel] for pixel in pixels))
        for channel in range(3)
    )  # type: ignore[return-value]


def audit_manifest(root: Path, manifest_path: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    results = []
    for group in ("inputs", "outputs"):
        for entry in recorded_entries(manifest.get(group)):
            if not isinstance(entry.get("path"), str) or not isinstance(entry.get("sha256"), str):
                continue
            resolved = resolve_recorded_path(root, manifest_path, entry["path"])
            actual = sha256_file(resolved)
            results.append({
                "group": group,
                "path": resolved.relative_to(root).as_posix(),
                "expected_sha256": entry["sha256"],
                "actual_sha256": actual,
                "passed": actual == entry["sha256"],
            })
    failures = [result for result in results if not result["passed"]]
    return {
        "status": "passed" if not failures else "failed",
        "digests_checked": len(results),
        "failures": failures,
    }


def audit_text_role(image: Any, role: Mapping[str, Any]) -> dict[str, Any]:
    assigned = role["box"]
    foreground = hex_rgb(role["foreground"])
    tolerance = float(role.get("color_tolerance", 42))
    count, visible, background_pixels = visible_color_bounds(
        image, assigned, [foreground], tolerance
    )
    failures = []
    if count < int(role.get("minimum_ink_pixels", 250)):
        failures.append("required text ink is absent or unexpectedly sparse")
    clearance = None
    if visible is None:
        failures.append("required text has no visible bounds")
    else:
        clearance = edge_clearances(assigned, visible)
        minimum = role.get("minimum_edge_clearance", {})
        for edge in ("left", "right", "bottom"):
            required = int(minimum.get(edge, 1))
            if clearance[edge] < required:
                failures.append(
                    f"visible ink touches {edge} edge "
                    f"({clearance[edge]}px < {required}px)"
                )
    background = median_rgb(background_pixels) if background_pixels else None
    measured_contrast = contrast_ratio(foreground, background) if background else 0.0
    required_contrast = float(role.get("minimum_contrast", 4.5))
    if measured_contrast < required_contrast:
        failures.append(
            f"median local contrast is {measured_contrast:.2f}:1, below {required_contrast:.2f}:1"
        )
    return {
        "role": role["role"],
        "assigned_box": assigned,
        "visible_ink_pixels": count,
        "visible_bounds": list(visible) if visible else None,
        "edge_clearance_pixels": clearance,
        "foreground_rgb": list(foreground),
        "median_background_rgb": list(background) if background else None,
        "contrast_ratio": round(measured_contrast, 2),
        "status": "passed" if not failures else "failed",
        "failures": failures,
    }


def audit_logo(image: Any, logo: Mapping[str, Any], canvas_area: int) -> dict[str, Any]:
    assigned = logo["box"]
    targets = [hex_rgb(color) for color in logo["target_colors"]]
    tolerance = float(logo.get("color_tolerance", 25))
    count, visible, background_pixels = visible_color_bounds(
        image, assigned, targets, tolerance
    )
    failures = []
    if visible is None:
        width = height = 0
        failures.append("Natal mark has no visible brand-color bounds")
    else:
        width = visible[2] - visible[0]
        height = visible[3] - visible[1]
    area_ratio = width * height / canvas_area
    if count < int(logo.get("minimum_ink_pixels", 1000)):
        failures.append("Natal mark is unexpectedly sparse")
    if width < int(logo.get("minimum_visible_width", 145)):
        failures.append("Natal mark is narrower than the prominence floor")
    if height < int(logo.get("minimum_visible_height", 35)):
        failures.append("Natal mark is shorter than the prominence floor")
    minimum_area_ratio = float(logo.get("minimum_bbox_area_ratio", 0.0045))
    if area_ratio < minimum_area_ratio:
        failures.append("Natal mark falls below the canvas prominence floor")
    background = median_rgb(background_pixels) if background_pixels else None
    wordmark_contrast = contrast_ratio(targets[0], background) if background else 0.0
    required_contrast = float(logo.get("minimum_wordmark_contrast", 4.5))
    if wordmark_contrast < required_contrast:
        failures.append("Natal wordmark contrast is below the required floor")
    return {
        "assigned_box": assigned,
        "visible_brand_pixels": count,
        "visible_bounds": list(visible) if visible else None,
        "visible_width": width,
        "visible_height": height,
        "bbox_canvas_area_ratio": round(area_ratio, 5),
        "normalized_center": [
            round(((visible[0] + visible[2]) / 2) / image.width, 4),
            round(((visible[1] + visible[3]) / 2) / image.height, 4),
        ] if visible else None,
        "median_background_rgb": list(background) if background else None,
        "wordmark_contrast_ratio": round(wordmark_contrast, 2),
        "status": "passed" if not failures else "failed",
        "failures": failures,
    }


def audit_queue(root: Path, artifact: Mapping[str, Any], delivery_sha256: str) -> dict[str, Any]:
    event_id = artifact["queue_event_id"]
    queue_path = require_regular_below(
        root, root / "runtime" / "telegram" / "queue" / f"{event_id}.json"
    )
    event = json.loads(queue_path.read_text(encoding="utf-8"))
    queued_artifact = event.get("artifact") or {}
    artifact_path = require_regular_below(root, root / queued_artifact["path"])
    actual = sha256_file(artifact_path)
    failures = []
    if event.get("event_id") != event_id:
        failures.append("queue event ID differs from the configured stable ID")
    if "skynet" not in str(event.get("text", "")).casefold():
        failures.append("queue text does not identify SKYNET")
    if queued_artifact.get("sha256") != actual:
        failures.append("queued artifact differs from its queue digest")
    if actual != delivery_sha256:
        failures.append("queued artifact differs from the frozen delivery")
    return {
        "event_id": event_id,
        "queue_path": queue_path.relative_to(root).as_posix(),
        "artifact_path": artifact_path.relative_to(root).as_posix(),
        "artifact_sha256": actual,
        "status": "passed" if not failures else "failed",
        "failures": failures,
    }


def audit_artifact(root: Path, artifact: Mapping[str, Any], image_module: Any) -> dict[str, Any]:
    manifest_path = require_regular_below(root, root / artifact["manifest_path"])
    master_path = require_regular_below(root, root / artifact["master_path"])
    delivery_path = require_regular_below(root, root / artifact["delivery_path"])
    candidate_path = require_regular_below(root, root / artifact["candidate_path"])
    manifest = audit_manifest(root, manifest_path)
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    copy_failures = []
    for key, expected in artifact["protected_copy"].items():
        if candidate.get(key) != expected:
            copy_failures.append(f"candidate {key} is not byte-exact")

    image = image_module.open(master_path).convert("RGB")
    expected_size = tuple(artifact.get("canvas", [1080, 1080]))
    geometry_failures = []
    if image.size != expected_size:
        geometry_failures.append(f"master is {image.size}, expected {expected_size}")
    for role in artifact["text_roles"]:
        if not box_inside_canvas(role["box"], *expected_size):
            geometry_failures.append(f"{role['role']} assigned box leaves the canvas")
    if not box_inside_canvas(artifact["logo"]["box"], *expected_size):
        geometry_failures.append("logo assigned box leaves the canvas")

    text = [audit_text_role(image, role) for role in artifact["text_roles"]]
    logo = audit_logo(image, artifact["logo"], expected_size[0] * expected_size[1])
    delivery_sha256 = sha256_file(delivery_path)
    queue = audit_queue(root, artifact, delivery_sha256)
    failed_sections = []
    if manifest["status"] != "passed":
        failed_sections.append("manifest")
    if copy_failures:
        failed_sections.append("protected_copy")
    if geometry_failures:
        failed_sections.append("geometry")
    if any(role["status"] != "passed" for role in text):
        failed_sections.append("visible_text")
    if logo["status"] != "passed":
        failed_sections.append("brand_prominence")
    if queue["status"] != "passed":
        failed_sections.append("queue")
    return {
        "experiment_id": artifact["experiment_id"],
        "candidate_id": artifact["candidate_id"],
        "master_path": master_path.relative_to(root).as_posix(),
        "master_sha256": sha256_file(master_path),
        "delivery_path": delivery_path.relative_to(root).as_posix(),
        "delivery_sha256": delivery_sha256,
        "canvas": list(image.size),
        "manifest": manifest,
        "protected_copy": {
            "status": "passed" if not copy_failures else "failed",
            "failures": copy_failures,
        },
        "geometry": {
            "status": "passed" if not geometry_failures else "failed",
            "failures": geometry_failures,
        },
        "visible_text": text,
        "brand_prominence": logo,
        "queue": queue,
        "status": "passed" if not failed_sections else "failed",
        "failed_sections": failed_sections,
    }


def run(root: Path, config_path: Path) -> dict[str, Any]:
    try:
        from PIL import Image
    except ModuleNotFoundError as error:
        raise RuntimeError(
            "Pillow is required; run with ../.venv/bin/python from the SKYNET root"
        ) from error

    root = root.resolve()
    config_path = require_regular_below(root, config_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("schema") != "ptw.skynet.frozen-creative-preflight-config.v1":
        raise ValueError("unsupported preflight configuration schema")
    artifacts = [audit_artifact(root, artifact, Image) for artifact in config["artifacts"]]
    passed = [artifact["candidate_id"] for artifact in artifacts if artifact["status"] == "passed"]
    failed = [artifact["candidate_id"] for artifact in artifacts if artifact["status"] != "passed"]
    return {
        "schema": SCHEMA,
        "config_path": config_path.relative_to(root).as_posix(),
        "config_sha256": sha256_file(config_path),
        "status": "passed" if not failed else "failed",
        "summary": {
            "artifacts_checked": len(artifacts),
            "artifacts_passed": len(passed),
            "artifacts_failed": len(failed),
            "passed_candidate_ids": passed,
            "failed_candidate_ids": failed,
            "manifest_digests_checked": sum(
                artifact["manifest"]["digests_checked"] for artifact in artifacts
            ),
        },
        "artifacts": artifacts,
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    result.add_argument(
        "--config",
        type=Path,
        default=Path("preflight/frozen-creatives-v1.json"),
    )
    result.add_argument("--output", type=Path)
    return result


def main() -> None:
    arguments = parser().parse_args()
    root = arguments.root.resolve()
    config = arguments.config
    if not config.is_absolute():
        config = root / config
    report = run(root, config)
    if arguments.output:
        output = arguments.output
        if not output.is_absolute():
            output = root / output
        output = output.parent.resolve() / output.name
        if output != root and root not in output.parents:
            raise SystemExit("output path must stay below the SKYNET root")
        atomic_json(output, report)
        displayed: Mapping[str, Any] = {
            "schema": report["schema"],
            "status": report["status"],
            "output": output.relative_to(root).as_posix(),
            "summary": report["summary"],
        }
    else:
        displayed = report
    print(json.dumps(displayed, ensure_ascii=False, sort_keys=True, indent=2))
    raise SystemExit(0 if report["status"] == "passed" else 1)


if __name__ == "__main__":
    main()
