import json
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path

from engineering.runner import StageFailure


MANIFEST_NAME = "project.components.json"


@dataclass(frozen=True)
class Component:
    name: str
    description: str
    paths: tuple[str, ...]
    validation: tuple[tuple[str, ...], ...]
    extended_validation: tuple[tuple[str, ...], ...]


@dataclass(frozen=True)
class ComponentManifest:
    components: tuple[Component, ...]
    global_validation: tuple[tuple[str, ...], ...]

    def matching(self, changed_paths: list[str]) -> tuple[Component, ...]:
        return tuple(
            component
            for component in self.components
            if any(
                fnmatch(path, pattern) or path == pattern.rstrip("/**")
                for path in changed_paths
                for pattern in component.paths
            )
        )


def _commands(value: object, field: str) -> tuple[tuple[str, ...], ...]:
    if not isinstance(value, list):
        raise StageFailure("VALIDATION_CONFIG", f"{field} must be a list")
    commands: list[tuple[str, ...]] = []
    for command in value:
        if not isinstance(command, list) or not command or not all(isinstance(item, str) and item for item in command):
            raise StageFailure("VALIDATION_CONFIG", f"{field} commands must be non-empty string arrays")
        commands.append(tuple(command))
    return tuple(commands)


def load_manifest(checkout: Path) -> ComponentManifest:
    path = checkout / MANIFEST_NAME
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise StageFailure("VALIDATION_CONFIG", f"Cannot load {MANIFEST_NAME}: {type(error).__name__}") from error
    if raw.get("version") != 1 or not isinstance(raw.get("components"), list):
        raise StageFailure("VALIDATION_CONFIG", f"Unsupported {MANIFEST_NAME} schema")
    components: list[Component] = []
    names: set[str] = set()
    for item in raw["components"]:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str) or item["name"] in names:
            raise StageFailure("VALIDATION_CONFIG", "Component names must be unique strings")
        paths = item.get("paths")
        if not isinstance(paths, list) or not paths or not all(isinstance(value, str) and value for value in paths):
            raise StageFailure("VALIDATION_CONFIG", f"Component {item['name']} requires paths")
        names.add(item["name"])
        components.append(
            Component(
                item["name"],
                str(item.get("description") or ""),
                tuple(paths),
                _commands(item.get("validation", []), f"{item['name']}.validation"),
                _commands(item.get("extended_validation", []), f"{item['name']}.extended_validation"),
            )
        )
    return ComponentManifest(
        tuple(components),
        _commands(raw.get("global_validation", []), "global_validation"),
    )


def describe_manifest(manifest: ComponentManifest) -> str:
    lines = []
    for component in manifest.components:
        commands = [" ".join(command) for command in component.validation]
        lines.append(
            f"- {component.name}: {component.description}; paths={', '.join(component.paths)}; "
            f"validation={'; '.join(commands) or 'global checks only'}"
        )
    return "\n".join(lines)
