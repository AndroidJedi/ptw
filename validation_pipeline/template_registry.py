"""Small, surface-neutral contracts for registered PTW templates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Generic, Mapping, TypeVar


T = TypeVar("T", bound="TemplateDefinition")


@dataclass(frozen=True)
class TemplateIdentity:
    surface: str
    template_id: str
    template_version: int
    template_sha256: str

    def to_reference(self) -> dict[str, Any]:
        return {
            "surface": self.surface,
            "template_id": self.template_id,
            "template_version": self.template_version,
            "template_sha256": self.template_sha256,
        }


@dataclass(frozen=True)
class TemplateCapabilities:
    image_slots: tuple[str, ...] = ()
    supports_manual_agent: bool = True
    supports_generation: bool = True
    supports_preview: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "image_slots": list(self.image_slots),
            "supports_manual_agent": self.supports_manual_agent,
            "supports_generation": self.supports_generation,
            "supports_preview": self.supports_preview,
        }


@dataclass(frozen=True)
class TemplateDefinition:
    identity: TemplateIdentity
    name: str
    description: str
    canvas: Mapping[str, int] | None
    catalog: Callable[[], dict[str, Any]]
    agent_catalog: Callable[[], dict[str, Any]]
    default_configuration: Callable[[], dict[str, Any]]
    default_content: Callable[[], dict[str, Any]]
    normalize_configuration: Callable[[Mapping[str, Any]], dict[str, Any]]
    normalize_content: Callable[[Mapping[str, Any]], dict[str, Any]]
    component_settings: Callable[[Mapping[str, Any], Mapping[str, Any]], dict[str, Any]]
    capabilities: TemplateCapabilities
    renderer_key: str
    editor_key: str

    def summary(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "template_id": self.identity.template_id,
            "name": self.name,
            "description": self.description,
            "template_version": self.identity.template_version,
            "template_sha256": self.identity.template_sha256,
            "capabilities": self.capabilities.to_dict(),
        }
        if self.canvas is not None:
            result["canvas"] = dict(self.canvas)
        return result


class TemplateRegistry(Generic[T]):
    """Immutable lookup boundary for one independent template surface."""

    def __init__(self, surface: str, definitions: tuple[T, ...], *, version_loader: Callable[[Mapping[str, Any]], T] | None = None) -> None:
        if not surface or not definitions:
            raise ValueError("Template registry requires a surface and definitions")
        indexed: dict[str, T] = {}
        versions: dict[tuple[str, int], T] = {}
        for definition in definitions:
            identity = definition.identity
            if identity.surface != surface:
                raise ValueError("Template definition belongs to another surface")
            key = (identity.template_id, identity.template_version)
            if key in versions:
                raise ValueError("Template versions must be unique within one surface")
            if identity.template_version < 1 or len(identity.template_sha256) != 64:
                raise ValueError("Template identity is invalid")
            versions[key] = definition
            if identity.template_id not in indexed or indexed[identity.template_id].identity.template_version < identity.template_version:
                indexed[identity.template_id] = definition
        self.surface = surface
        self._definitions = indexed
        self._versions = versions
        self._version_loader = version_loader

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(self._definitions)

    def get(self, template_id: str) -> T:
        try:
            return self._definitions[str(template_id)]
        except KeyError as error:
            raise ValueError(
                f"{self.surface.title()} template is not registered"
            ) from error

    def all(self) -> tuple[T, ...]:
        return tuple(self._definitions.values())

    def registered_versions(self) -> tuple[T, ...]:
        """Enumerate local immutable definitions for audits, without lazy loading."""
        return tuple(self._versions.values())

    def resolve_reference(self, value: Mapping[str, Any]) -> T:
        if set(value) != {
            "template_id", "template_version", "template_sha256",
        }:
            raise ValueError("Template reference fields are invalid")
        if type(value["template_version"]) is not int or value["template_version"] < 1:
            raise ValueError("Template version must be a positive integer")
        try:
            definition = self._versions[(str(value["template_id"]), value["template_version"])]
        except (KeyError, TypeError) as error:
            if self._version_loader is None:
                raise ValueError("Template reference is stale or not registered") from error
            definition = self._version_loader(value)
        identity = definition.identity
        if (
            value["template_version"] != identity.template_version
            or value["template_sha256"] != identity.template_sha256
        ):
            raise ValueError("Template reference is stale")
        return definition
