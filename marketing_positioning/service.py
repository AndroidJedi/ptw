from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit

from .domain import PositioningDocumentV1, SECTION_IDS
from .provider import (
    BridgeProvider, DataForSEOProvider, POSITIONING_DOCUMENT_SCHEMA,
    RESEARCH_PLAN_SCHEMA, SafePageFetcher,
)
from .repository import PositioningRepository
from .research import ResearchKnowledgeService


class PositioningRunner:
    def __init__(
        self,
        repository: PositioningRepository,
        bridge: BridgeProvider,
        research_provider: DataForSEOProvider,
        *,
        skill_path: Path,
        max_spend_usd: float = 0.05,
        page_fetcher: SafePageFetcher | None = None,
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
        self.research_provider = research_provider
        self.research = ResearchKnowledgeService(repository)
        self.max_spend_usd = min(0.05, max_spend_usd)
        self.page_fetcher = page_fetcher or SafePageFetcher()

    def verify_ready(self) -> dict[str, Any]:
        capabilities = self.bridge.capabilities()
        return {
            "ready": True,
            "research_provider": self.research_provider.name,
            "max_spend_usd": self.max_spend_usd,
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
            if revision["revision_number"] == 1:
                self._research(project, revision, attempt_id)
            sources = self.repository.sources(revision_id)
            if not sources or not any(item["source_type"] == "research_finding" for item in sources):
                raise RuntimeError("strict positioning synthesis requires persisted live research")
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

    def _research(self, project: Mapping[str, Any], revision: Mapping[str, Any], attempt_id: str) -> None:
        plan_request = {
            "owner_idea": project["raw_idea"],
            "target_country": project["target_country"],
            "research_language": project["research_language"],
            "requirements": {
                "query_count": "2-4", "intents": ["alternatives", "jobs_pains_gains", "category_language", "limitations"],
            },
        }
        plan_key = f"{revision['id']}:research-plan"
        invocation = self.repository.create_invocation(
            revision_id=revision["id"], attempt_id=attempt_id, provider="codex_bridge",
            mode="marketing_positioning_research_plan", idempotency_key=plan_key, request=plan_request,
        )
        try:
            plan = self.bridge.generate(
                mode="marketing_positioning_research_plan",
                system_prompt=(
                    "Use the canonical Marketing Positioning skill. Return a small market-research plan only. "
                    "Queries must fit the selected country and research language and must not assert facts.\n\n"
                    + self.skill_contract
                ),
                input_payload=plan_request,
                output_schema=RESEARCH_PLAN_SCHEMA,
                prompt_version="marketing_positioning_v1:research_plan",
            )
            queries = self._validate_plan(plan)
            self.repository.complete_invocation(invocation["id"], plan, self.bridge.last_invocation)
        except Exception as error:
            self.repository.fail_invocation(invocation["id"], error)
            raise

        depth = 10
        estimated = sum(self.research_provider.estimate_cost(depth) for _ in queries)
        if self.repository.spend(revision["id"]) + estimated > self.max_spend_usd + 1e-9:
            raise RuntimeError("research plan exceeds the USD 0.05 positioning ceiling")
        rows: list[tuple[Mapping[str, Any], Mapping[str, Any]]] = []
        for index, query in enumerate(queries):
            request = {
                "query": query["query"], "country": project["target_country"],
                "language": project["research_language"], "depth": depth,
            }
            key_digest = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
            key = f"dataforseo:{project['id']}:{key_digest}"
            paid = self.repository.invocation(key)
            if paid is None:
                paid = self.repository.create_invocation(
                    revision_id=revision["id"], attempt_id=attempt_id, provider="dataforseo",
                    mode="dataforseo_serp", idempotency_key=key, request=request,
                )
            remote_task_id = paid.get("remote_task_id")
            if not remote_task_id:
                remote_task_id, cost, provider_record = self.research_provider.submit(
                    **request, tag=f"positioning:{project['id']}:{index}"
                )
                if self.repository.spend(revision["id"]) + cost > self.max_spend_usd + 1e-9:
                    raise RuntimeError("provider cost would exceed the positioning research ceiling")
                self.repository.attach_remote_task(paid["id"], remote_task_id, cost, provider_record)
            try:
                result = self.research_provider.wait(str(remote_task_id))
                if not result:
                    raise RuntimeError("DataForSEO returned no organic findings")
                self.repository.complete_invocation(paid["id"], {"rows": result})
            except Exception as error:
                self.repository.fail_invocation(paid["id"], error)
                raise
            rows.extend((query, row) for row in result[:2])

        if not rows:
            raise RuntimeError("live positioning research returned no selectable findings")
        for query, row in rows[:8]:
            page_text = ""
            try:
                page_text = self.page_fetcher.fetch(str(row["url"]))
            except Exception:
                # The paid SERP excerpt remains a live provider finding. A page
                # failure does not fabricate or substitute evidence.
                page_text = ""
            summary = page_text[:6000] or str(row.get("snippet") or "").strip()
            if not summary:
                continue
            publisher = str(row.get("domain") or urlsplit(str(row["url"])).hostname or "unknown")
            external_id = hashlib.sha256(
                f"{row.get('remote_task_id')}|{row.get('url')}|{row.get('position')}".encode()
            ).hexdigest()
            self.research.record_finding(
                revision["id"], title=str(row.get("title") or publisher),
                source_uri=str(row["url"]), publisher=publisher, finding_summary=summary,
                country=project["target_country"], language=project["research_language"],
                provider="dataforseo_safe_page" if page_text else "dataforseo_serp",
                external_id=external_id,
                metadata={
                    "intent": query["intent"], "query": query["query"],
                    "position": row.get("position"), "remote_task_id": row.get("remote_task_id"),
                    "page_fetched": bool(page_text),
                },
            )
        if len(self.repository.sources(revision["id"])) < 2:
            raise RuntimeError("research produced no durable findings")

    @staticmethod
    def _validate_plan(value: Mapping[str, Any]) -> list[dict[str, str]]:
        if set(value) != {"queries"} or not isinstance(value.get("queries"), list):
            raise ValueError("research plan did not match the strict schema")
        queries = value["queries"]
        if not 2 <= len(queries) <= 4:
            raise ValueError("research plan must contain 2-4 queries")
        allowed = {"alternatives", "jobs_pains_gains", "category_language", "limitations"}
        result = []
        for item in queries:
            if not isinstance(item, Mapping) or set(item) != {"intent", "query"}:
                raise ValueError("research queries must match the strict schema")
            intent, query = str(item["intent"]), str(item["query"]).strip()
            if intent not in allowed or not 2 <= len(query) <= 200:
                raise ValueError("research query is invalid")
            result.append({"intent": intent, "query": query})
        return result

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
                "research_language": project["research_language"],
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
                    + "Every factual field must cite only an allowed source UUID. Mark uncited inferences as assumptions. "
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
        raise ValueError("country or language is outside the verified provider catalog")
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
