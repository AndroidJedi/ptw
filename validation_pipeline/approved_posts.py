"""Provider-neutral access to immutable approved Studio Post versions."""

from __future__ import annotations

from copy import deepcopy
import re
from typing import Any, Mapping
from uuid import UUID


INLINE_MARKERS = ("**", "==")


def normalized_uuid(value: Any, label: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as error:
        raise ValueError(f"{label} must be a UUID") from error


def plain_studio_text(value: Any) -> str:
    """Return renderer-visible text without Studio's bounded inline markers."""

    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    for marker in INLINE_MARKERS:
        text = text.replace(marker, "")
    return "\n".join(" ".join(line.split()) for line in text.split("\n")).strip()


def _enabled(configuration: Mapping[str, Any], key: str, default: bool = True) -> bool:
    value = configuration.get(key)
    return bool(value.get("enabled", default)) if isinstance(value, Mapping) else default


def approved_post_copy(record: Mapping[str, Any], language: str = "uk") -> dict[str, str]:
    content = dict(record.get("content") or {})
    configuration = dict(record.get("configuration") or {})
    headline = plain_studio_text(content.get("hero_title")) if _enabled(configuration, "hero_title") else ""
    supporting = plain_studio_text(content.get("supporting_text")) if _enabled(configuration, "supporting_text") else ""
    offer = plain_studio_text(content.get("offer")) if _enabled(configuration, "offer") else ""
    return {
        "headline": headline,
        "primary_text": "\n\n".join(part for part in (supporting, offer) if part),
        "instagram_caption": "\n\n".join(part for part in (headline, supporting, offer) if part),
        "welcome_message": (
            "Hi! I'd like to learn more."
            if language == "en" else "Вітаю! Хочу дізнатися більше."
        ),
    }


def caption_with_url(caption: Any, url: str, maximum: int = 2200) -> str:
    """Append one Landing URL while reserving its full suffix inside the limit."""

    clean = plain_studio_text(caption)
    url = str(url).strip()
    if not re.fullmatch(r"https://[^\s]+", url):
        raise ValueError("Published Landing URL must use HTTPS")
    # Remove a canonical/tracked URL already present as the final paragraph.
    lines = clean.split("\n")
    while lines and not lines[-1].strip():
        lines.pop()
    if lines and re.fullmatch(r"https://[^\s]+", lines[-1].strip()):
        lines.pop()
        while lines and not lines[-1].strip():
            lines.pop()
    body = "\n".join(lines).strip()
    suffix = ("\n\n" if body else "") + url
    available = maximum - len(suffix)
    if available < 0:
        raise ValueError("Published Landing URL exceeds the Instagram caption limit")
    if len(body) > available:
        body = body[: max(0, available - 1)].rstrip() + ("…" if available else "")
    return (body + ("\n\n" if body else "") + url).strip()


class ApprovedPostSources:
    """Resolve exact approved Post artifacts without an advertising dependency."""

    def __init__(self, studio: Any, landing_publications: Any, configuration: Any | None = None) -> None:
        self.studio = studio
        # Construction is deliberately lazy so narrow test/local adapters do
        # not need database-only attributes until an artifact is resolved.
        self.authority = getattr(studio, "authority", None)
        self.landing_publications = landing_publications
        self.configuration = configuration

    def landing(self, project_id: str) -> dict[str, Any] | None:
        project_id = normalized_uuid(project_id, "project_id")
        publication = self.landing_publications.get(project_id) if self.landing_publications else None
        if not publication or publication["status"] != "published":
            return None
        event = next(
            (item for item in publication["events"] if item["event_id"] == publication["current_event_id"]),
            None,
        )
        if not event:
            return None
        return {
            "publication_id": publication["publication_id"],
            "event_id": event["event_id"],
            "landing_version_id": event.get("landing_version_id"),
            "landing_version": event["landing_version"],
            "landing_version_sha256": event["landing_version_sha256"],
            "canonical_url": publication["canonical_url"],
        }

    def _artifact(self, project_id: str, creative_id: str, version: int) -> dict[str, Any]:
        project_id = normalized_uuid(project_id, "project_id")
        creative_id = normalized_uuid(creative_id, "creative_id")
        detail = self.studio.detail(project_id, creative_id)
        record = self.studio._workspace(creative_id).version_detail(version)
        rendered = self.studio._workspace(creative_id).version_render(version)
        if record.get("render_sha256") != rendered.get("sha256"):
            raise ValueError("Approved Studio render digest mismatch")
        brief = self.studio.authority.brief(detail["source_brief_id"])
        language = str((brief.get("document") or {}).get("language") or brief.get("language") or "uk")
        return {"detail": detail, "record": record, "rendered": rendered, "language": language}

    @staticmethod
    def _defaults(record: Mapping[str, Any], language: str) -> dict[str, str]:
        return approved_post_copy(record, language)

    def _sources(self, project_id: str) -> list[dict[str, Any]]:
        project_id = normalized_uuid(project_id, "project_id")
        items: list[dict[str, Any]] = []
        for creative in self.studio.list_creatives(project_id)["items"]:
            if int(creative.get("approved_version_count", 0)) < 1:
                continue
            detail = self.studio.detail(project_id, creative["creative_id"])
            brief = self.studio.authority.brief(detail["source_brief_id"])
            language = str((brief.get("document") or {}).get("language") or brief.get("language") or "uk")
            for summary in detail.get("versions", []):
                record = self.studio._workspace(creative["creative_id"]).version_detail(int(summary["version"]))
                items.append({
                    "creative_id": creative["creative_id"],
                    "creative_ordinal": creative["ordinal"],
                    "template_id": creative["template_id"],
                    "version": int(record["version"]),
                    "version_id": record.get("version_id"),
                    "version_sha256": record["version_sha256"],
                    "render_sha256": record["render_sha256"],
                    "change_note": record["change_note"],
                    "defaults": self._defaults(record, language),
                })
        return sorted(items, key=lambda item: (item["creative_ordinal"], item["version"]), reverse=True)

    def source(self, project_id: str, creative_id: str, version: int) -> dict[str, Any]:
        artifact = self._artifact(project_id, creative_id, version)
        record, detail = artifact["record"], artifact["detail"]
        return {
            "creative_id": creative_id,
            "creative_ordinal": detail["ordinal"],
            "template_id": detail["template_id"],
            "version": version,
            "version_id": record.get("version_id"),
            "version_sha256": record["version_sha256"],
            "render_sha256": record["render_sha256"],
            "change_note": record["change_note"],
            "defaults": approved_post_copy(record, artifact["language"]),
        }

    def project(self, project_id: str) -> dict[str, Any]:
        return deepcopy(self.authority.project(normalized_uuid(project_id, "project_id")))
