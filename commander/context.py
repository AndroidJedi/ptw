"""Deterministic bootstrap context broker backed by a curated registry."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ContextBundle:
    task_class: str
    canonical_paths: tuple[Path, ...]
    optional_paths: tuple[Path, ...]


class ContextBroker:
    def __init__(self, repository_root: Path, registry_path: Path) -> None:
        self.repository_root = repository_root.resolve()
        self.registry = json.loads(registry_path.read_text(encoding="utf-8"))

    def retrieve(self, task_class: str) -> ContextBundle:
        try:
            route = self.registry["routes"][task_class]
        except KeyError as error:
            raise KeyError(f"unknown context route: {task_class}") from error
        canonical = tuple(self._safe_path(value) for value in route["canonical"])
        optional = tuple(self._safe_path(value) for value in route.get("optional", []))
        missing = [path for path in canonical if not path.is_file()]
        if missing:
            raise FileNotFoundError(f"canonical context is missing: {missing}")
        return ContextBundle(task_class, canonical, optional)

    def _safe_path(self, relative: str) -> Path:
        path = (self.repository_root / relative).resolve()
        if path != self.repository_root and self.repository_root not in path.parents:
            raise ValueError(f"context path escapes repository: {relative}")
        return path
