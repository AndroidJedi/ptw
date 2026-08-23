from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

from .domain import PositioningDocumentV1, SECTION_IDS
from .provider import BridgeProvider, POSITIONING_DOCUMENT_SCHEMA
from .repository import PositioningRepository


class TerminalNotifier(Protocol):
    def notify(self, revision_id: str, generation_attempt_id: str) -> Mapping[str, Any]: ...


class PositioningRunner:
    def __init__(
        self,
        repository: PositioningRepository,
        bridge: BridgeProvider,
        *,
        skill_path: Path,
        notifier: TerminalNotifier | None = None,
    ) -> None:
        if not skill_path.is_file():
            raise RuntimeError("canonical Marketing Positioning skill is unavailable")
        parts = [skill_path.read_text(encoding="utf-8")]
        for name in ("output-contract.md", "evidence-policy.md", "owner-lessons.md"):
            reference = skill_path.parent / "references" / name
            if reference.is_file():
                parts.append(f"\nREFERENCE {name}:\n{reference.read_text(encoding='utf-8')}")
        self.skill_contract = "\n".join(parts)[:40_000]
        self.repository = repository
        self.bridge = bridge
        self.notifier = notifier

    def verify_ready(self) -> dict[str, Any]:
        capabilities = self.bridge.capabilities()
        return {
            "ready": True,
            "evidence_mode": "owner_input_only",
            "external_research": False,
            **capabilities,
        }

    def generate(self, revision_id: str, *, operation_reserved: bool = False) -> dict[str, Any]:
        revision = self.repository.get_revision(revision_id)
        if revision["status"] not in {"queued", "failed"}:
            raise ValueError("only a queued or failed revision can be generated")
        if not operation_reserved:
            self.repository.acquire_operation("marketing_positioning", revision_id)
        attempt_id = ""
        try:
            attempt_id, attempt_number = self.repository.start_attempt(revision_id)
            project = self.repository.get_project(revision["project_id"])
            sources = [
                item for item in self.repository.sources(revision_id)
                if item["source_type"] == "owner_idea"
            ]
            if len(sources) != 1:
                raise RuntimeError("owner-input-only positioning requires exactly one owner idea source")
            document = self._synthesize(project, revision, attempt_id, attempt_number, sources)
            self.repository.finish_attempt(
                revision_id, attempt_id, document.to_dict(), document.digest, document.quality_gates
            )
            return self.repository.get_revision(revision_id)
        except Exception as error:
            if attempt_id:
                self.repository.fail_attempt(revision_id, attempt_id, error)
            raise
        finally:
            self.repository.release_operation(revision_id)
            if attempt_id and self.notifier is not None:
                try:
                    self.notifier.notify(revision_id, attempt_id)
                except Exception:
                    # Terminal revision state is authoritative; notification
                    # failures must never change or mask generation outcome.
                    pass

    def _synthesize(
        self,
        project: Mapping[str, Any],
        revision: Mapping[str, Any],
        attempt_id: str,
        attempt_number: int,
        sources: Sequence[Mapping[str, Any]],
    ) -> PositioningDocumentV1:
        base = None
        feedback = None
        mode = "marketing_positioning_document"
        if revision.get("base_revision_id"):
            base = self.repository.get_revision(revision["base_revision_id"])
            if not base.get("document"):
                raise RuntimeError("base positioning document is unavailable")
            project_detail = self.repository.get_project(project["id"])
            current = next(item for item in project_detail["revisions"] if item["id"] == revision["id"])
            # The full document and focused correction are always supplied.
            correction = self._feedback(revision["feedback_id"])
            feedback = {
                "feedback_id": current["feedback_id"],
                "section_id": correction["section_id"],
                "instruction": correction["instruction"],
            }
            mode = "marketing_positioning_revision"
        source_payload = [
            {
                "id": item["id"], "type": item["source_type"], "title": item["title"],
                "uri": item["source_uri"], "publisher": item["publisher"],
                "content": item["content"][:8000], "metadata": item["metadata"],
            }
            for item in sources
        ]
        request = {
            "project": {
                "id": project["id"], "owner_idea": project["raw_idea"],
                "target_country": project["target_country"],
                "market_language": project["research_language"],
                "output_language": project["output_language"],
            },
            "allowed_sources": source_payload,
            "base_document": None if base is None else base["document"],
            "focused_correction": feedback,
        }
        key = f"{revision['id']}:{mode}:attempt-{attempt_number}"
        invocation = self.repository.create_invocation(
            revision_id=revision["id"], attempt_id=attempt_id, provider="codex_bridge",
            mode=mode, idempotency_key=key, request=request,
        )
        correction = (
            "Apply the focused owner correction to the requested section, then return a complete coherent document. "
            "Do not mutate the base document in place. " if feedback else ""
        )
        try:
            result = self.bridge.generate(
                mode=mode,
                system_prompt=(
                    "Use the canonical Marketing Positioning skill and return only the strict PositioningDocumentV1 object. "
                    + correction
                    + "The owner idea is the only factual source. Cite it only for claims it directly states, including intended "
                    "capabilities and intended users. Treat category choice, audience narrowing, customer jobs, pains, gains, "
                    "competitive alternatives, emotional rewards, and every market inference as an explicit assumption unless "
                    "the owner idea directly states it. Every uncited inference must have source_ids=[] and assumption=true and "
                    "must also appear in the top-level assumptions list. "
                    "Never invent metrics, proof, testimonials, limitations, or competitive facts. The honest limitation "
                    "must be real and supplied or say results are not yet verified. Produce exactly two ordered ad concepts, "
                    "exactly three value sections, and exactly three Definition-Data-Context FAQs.\n\nCANONICAL_SKILL:\n"
                    + self.skill_contract
                ),
                input_payload=request,
                output_schema=POSITIONING_DOCUMENT_SCHEMA,
                prompt_version=f"marketing_positioning_v1:{mode}",
            )
            document = PositioningDocumentV1.from_dict(
                result,
                allowed_source_ids=[item["id"] for item in sources],
                output_language=project["output_language"],
            )
            self.repository.complete_invocation(invocation["id"], document.to_dict(), self.bridge.last_invocation)
            return document
        except Exception as error:
            self.repository.fail_invocation(invocation["id"], error)
            raise

    def _feedback(self, feedback_id: str) -> dict[str, str]:
        from uuid import UUID
        with self.repository.connection() as connection:
            row = connection.execute(
                "SELECT section_id,instruction FROM commander_human_feedback WHERE entity_id=%s",
                (UUID(feedback_id),),
            ).fetchone()
        if row is None:
            raise RuntimeError("revision feedback is unavailable")
        return {"section_id": row[0], "instruction": row[1]}


def validate_create_input(value: Mapping[str, Any]) -> dict[str, str]:
    from uuid import UUID
    from .catalog import COUNTRIES, RESEARCH_LANGUAGES
    required = {"request_id", "raw_idea", "target_country", "research_language", "output_language"}
    if set(value) != required:
        raise ValueError("create request fields do not match the v1 contract")
    request_id = str(UUID(str(value["request_id"])))
    raw_idea = str(value["raw_idea"]).strip()
    if not 1 <= len(raw_idea) <= 10_000:
        raise ValueError("raw_idea must contain 1-10000 characters")
    country = str(value["target_country"]).upper()
    language = str(value["research_language"]).lower()
    output = str(value["output_language"]).lower()
    if country not in COUNTRIES or language not in RESEARCH_LANGUAGES or output not in {"uk", "en"}:
        raise ValueError("country or language is outside the supported market catalog")
    return {"request_id": request_id, "raw_idea": raw_idea, "target_country": country, "research_language": language, "output_language": output}


def validate_revision_input(value: Mapping[str, Any]) -> dict[str, str]:
    from uuid import UUID
    required = {"request_id", "base_revision_id", "section_id", "instruction"}
    if set(value) != required:
        raise ValueError("revision request fields do not match the v1 contract")
    section = str(value["section_id"])
    instruction = str(value["instruction"]).strip()
    if section not in SECTION_IDS or not 1 <= len(instruction) <= 2000:
        raise ValueError("section_id or instruction is invalid")
    return {
        "request_id": str(UUID(str(value["request_id"]))),
        "base_revision_id": str(UUID(str(value["base_revision_id"]))),
        "section_id": section, "instruction": instruction,
    }
