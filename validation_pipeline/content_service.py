"""Durable five-Creative owner-review orchestration."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import Any, Mapping, Sequence
from uuid import UUID

from commander.ids import new_uuid7

from .content import (
    CandidateV2, ContentContextAssembler, INSTAGRAM_REQUIRED_VISUAL_ROLES,
    REQUIRED_COPY_SLOTS, SLIDER_NAMES, STATIC_SOCIAL_PROFILES, StrategyTemplate, TemplateRegistry,
    candidate_output_schema, sha256_json,
)
from .content_adapters import adapter_for_profile
from .natal_brand import natal_logo_bytes
from .studio import tool_catalog, tool_catalog_for_profile


@dataclass(frozen=True, slots=True)
class GeneratedCandidate:
    value: Mapping[str, Any]


class CandidateGenerationOrchestrator:
    """Server-authorized generation of five owner-reviewable Creatives."""

    def __init__(
        self, *, repository: Any, bridge: Any, context_assembler: ContentContextAssembler,
        template_registry: TemplateRegistry, recipe_renderer: Any, pexels: Any,
        notifier: Any,
    ) -> None:
        self.repository = repository
        self.bridge = bridge
        self.context_assembler = context_assembler
        self.template_registry = template_registry
        self.recipe_renderer = recipe_renderer
        self.pexels = pexels
        self.notifier = notifier

    def create_run(
        self, *, request_id: str, brief_id: str, task: str, output_profile: str,
        requested_by: str, parent_run_id: str | None = None,
        revision_instruction: Mapping[str, Any] | None = None,
        revision_feedback: Mapping[str, Any] | None = None,
    ) -> tuple[dict[str, Any], bool]:
        if self.notifier is None:
            raise RuntimeError("Commander review-notification relay is not configured")
        brief = self.repository.authority.get_brief(brief_id)
        if not brief["approved"] or brief["status"] != "completed":
            raise ValueError("Result generation requires an approved completed Product Brief")
        brand_kit = self.repository.authority.ensure_natal_brand_kit(
            brief["project_id"], logo_data=natal_logo_bytes(), requested_by=requested_by,
        )
        approved_sources = [
            item for item in self.repository.authority.list_project_assets(
                brief["project_id"], approved_only=True
            )
            if item["origin"] in {"owner_upload", "pexels", "canonical_brand"}
            or (
                item["origin"] == "ai_generated"
                and item.get("metadata", {}).get("owner_reviewed") is True
                and item.get("metadata", {}).get("no_synthetic_people") is True
            )
        ]
        templates = self.template_registry.load_active()
        catalog = (
            tool_catalog_for_profile(output_profile)
            if output_profile in STATIC_SOCIAL_PROFILES else tool_catalog()
        )
        context = self.context_assembler.assemble_run(
            brief=brief, task=task, output_profile=output_profile, brand_kit=brand_kit,
            approved_sources=approved_sources,
            tool_catalog=catalog, templates=templates,
            revision_instruction=revision_instruction,
        )
        create_arguments = dict(
            request_id=request_id, brief_id=brief_id, task=task, output_profile=output_profile,
            context=context, templates=templates, requested_by=requested_by,
            parent_run_id=parent_run_id,
        )
        if revision_feedback is not None:
            create_arguments["revision_feedback"] = revision_feedback
        return self.repository.create_run(**create_arguments)

    @staticmethod
    def _deadline_ok(run: Mapping[str, Any]) -> None:
        deadline = datetime.fromisoformat(str(run["deadline_at"]))
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) >= deadline:
            raise TimeoutError("Result run exceeded the 45-minute wall-clock limit")

    @staticmethod
    def _supplied_uuid_ids(value: Any) -> list[str]:
        identifiers: set[str] = set()

        def collect(item: Any) -> None:
            if isinstance(item, Mapping):
                for nested in item.values():
                    collect(nested)
            elif isinstance(item, (list, tuple)):
                for nested in item:
                    collect(nested)
            elif isinstance(item, str):
                try:
                    parsed = UUID(item)
                except ValueError:
                    return
                if parsed.version == 7:
                    identifiers.add(str(parsed))

        collect(value)
        return sorted(identifiers)

    @staticmethod
    def _candidate_system_prompt(context: Mapping[str, Any]) -> str:
        writing = context["writing"]
        required_language = str(context["brief"]["document"]["language"])
        profile_rule = (
            "For instagram_static_ad_v1, visual_components must contain exactly these nine roles "
            "once each and in this order: " + ", ".join(INSTAGRAM_REQUIRED_VISUAL_ROLES) + ". "
            "Do not replace a required role with badge or decorative_element."
            if context["output_profile"] in STATIC_SOCIAL_PROFILES
            else "For marketing_copy_v1, visual_components must be empty."
        )
        revision_rule = ""
        if context.get("revision_instruction"):
            revision = context["revision_instruction"]
            revision_rule = (
                "Generate a fresh exploration direction. Do not reuse any identity listed in "
                "revision_instruction.excluded_identities. Keep the Brief, task, offer, CTA, "
                "brand, placement, and source policy protected."
                if revision.get("action") == "regenerate_all" else
                "Apply the supplied revision_instruction comment exactly as the requested change. "
                "Keep the Brief, task, offer, CTA, brand, placement, and source policy protected. "
                "Do not infer any other owner history."
            )
        return "\n\n".join((
            writing["generator_core"], writing["principles"], writing["anti_patterns"],
            writing["technique"], writing.get("post_copy_style") or "",
            writing["owner_lessons"],
            "ACTIVE_PROJECT_OWNER_LEARNING:\n" + json.dumps(
                context.get("owner_learning") or {"rules": []}, ensure_ascii=False,
            ),
            context["template"]["document"]["prompt_fragment"],
            f"REQUIRED_OUTPUT_LANGUAGE: {required_language}. The approved Brief language is "
            "authoritative for hook, headline, primary_text, supporting_text, offer, CTA, "
            "caption, and alt_text. Style examples in another language never change it.",
            "Return exactly one strict CandidateV2 JSON object. Do not mention any other candidate. "
            "Preserve the supplied offer and CTA exactly. Use only supplied identifiers. "
            "The supplied Studio template is the authoritative render contract: its frames, tools, "
            "bindings, palette, and resolved media placement cannot be replaced by a proposed layout. "
            "The visible headline binds to candidate.headline and the visible supporting block binds "
            "to candidate.primary_text. Make alt_text and all semantic visual_components describe "
            "that exact template composition; do not invent a different background, panel, logo "
            "position, typography treatment, or subject. " + profile_rule,
            revision_rule,
        ))

    @staticmethod
    def _candidate_payload(
        run: Mapping[str, Any], template: StrategyTemplate, parameters: Mapping[str, int],
        *, candidate_id: str,
    ) -> dict[str, Any]:
        context = run["context_bundle"]["candidate_contexts"][template.template_id]
        payload = {
            "candidate_id": candidate_id,
            "run_id": run["run_id"],
            "context_digest": sha256_json(context),
            "required_language": context["brief"]["document"]["language"],
            "approved_brief": context["brief"], "task": context["task"],
            "output_profile": context["output_profile"], "brand_kit": context["brand_kit"],
            "approved_sources": context["approved_sources"],
            "tool_catalog": context["tool_catalog"],
            "strategy": context["template"],
            "studio_template": context["studio_template"],
            "parameters": dict(parameters),
            "runtime_bands": template.runtime_bands(parameters),
            "retrieved_examples": [{
                "example_id": example_id, "excerpt": excerpt,
            } for example_id, excerpt in zip(
                context["writing"]["example_ids"], context["writing"]["examples"],
            )],
            "owner_learning": context.get("owner_learning") or {"rules": []},
            "excluded_context": context["source_policy"],
        }
        if context.get("revision_instruction"):
            payload["revision_instruction"] = dict(context["revision_instruction"])
        return payload

    @staticmethod
    def _element_type(slot: str) -> str:
        if slot == "media_request":
            return "media_request"
        if slot in REQUIRED_COPY_SLOTS:
            return "copy"
        return "visual_component"

    @classmethod
    def _normalize_elements(
        cls, *, alias: str, candidate: CandidateV2,
        reserved_instance_ids: Mapping[str, str] | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, str]]:
        raw: list[tuple[str, int, Mapping[str, Any]]] = []
        for slot in REQUIRED_COPY_SLOTS:
            payload = (
                dict(candidate.value[slot]) if slot == "media_request"
                else {"value": candidate.value[slot]}
            )
            raw.append((slot, 0, payload))
        role_counts: dict[str, int] = {}
        for component in candidate.value["visual_components"]:
            slot = str(component["role"])
            ordinal = role_counts.get(slot, 0)
            role_counts[slot] = ordinal + 1
            raw.append((slot, ordinal, {
                "content": component["content"], "source_ids": list(component["source_ids"]),
            }))
        elements: list[dict[str, Any]] = []
        instance_ids: dict[str, str] = {}
        for slot, ordinal, payload in raw:
            element = {
                "element_id": (
                    (reserved_instance_ids or {})[slot]
                    if slot in (reserved_instance_ids or {}) else new_uuid7()
                ),
                "display_alias": f"{alias}.{slot.upper()}.{ordinal + 1:02d}",
                "slot": slot, "ordinal": ordinal, "element_type": cls._element_type(slot),
                "payload": dict(payload), "reuse_mode": "generated",
                "source_element_ids": [],
            }
            elements.append(element)
            if ordinal == 0:
                instance_ids[slot] = str(element["element_id"])
        return elements, instance_ids

    def _call_creative(
        self, *, run: Mapping[str, Any], creative_id: str, alias: str,
        template: StrategyTemplate, parameters: Mapping[str, int], round_number: int,
        generation_kind: str, parent_creative_id: str | None,
    ) -> dict[str, Any]:
        self._deadline_ok(run)
        payload = self._candidate_payload(
            run, template, parameters, candidate_id=creative_id,
        )
        allowed_source_ids = self._supplied_uuid_ids(payload)
        approved_asset_ids = sorted({
            str(item["source_asset_id"])
            for item in payload["approved_sources"] if item.get("source_asset_id")
        })
        key = f"{run['run_id']}:{creative_id}:content_candidate_generation"
        brief = run["context_bundle"]["brief"]["document"]

        def validate_response(value: Mapping[str, Any]) -> Mapping[str, Any]:
            return CandidateV2.from_dict(
                value, brief=brief, output_profile=run["output_profile"],
                allowed_source_ids=allowed_source_ids,
                approved_asset_ids=approved_asset_ids,
            ).value

        attempt_id, invocation_id = self.repository.start_invocation(
            creative_id, mode="content_candidate_generation", idempotency_key=key, request=payload,
        )
        try:
            response = self.bridge.generate_content_candidate(
                system_prompt=self._candidate_system_prompt(
                    run["context_bundle"]["candidate_contexts"][template.template_id]
                ),
                input_payload=payload,
                output_schema=candidate_output_schema(
                    output_profile=run["output_profile"],
                    allowed_source_ids=allowed_source_ids,
                    approved_asset_ids=approved_asset_ids,
                ),
                prompt_version=f"ptw-content-candidate-v2.2-{template.template_id}-v{template.version}",
                idempotency_key=key,
                response_validator=validate_response,
            )
            invocation = dict(response["invocation"])
            self.repository.finish_invocation(
                attempt_id, invocation_id, response=response["response"], provenance=invocation,
            )
            candidate = CandidateV2.from_dict(
                response["response"], brief=brief, output_profile=run["output_profile"],
                allowed_source_ids=allowed_source_ids,
                approved_asset_ids=approved_asset_ids,
            )
            existing_recipe = self.repository.authority.get_creative_recipe(creative_id)
            reserved_instance_ids: dict[str, str] = {}
            if existing_recipe is not None:
                role_for_tool = {
                    "studio.frame.media.v1": "primary_subject",
                    "studio.frame.headline.v1": "headline_block",
                    "studio.frame.body.v1": "supporting_text_block",
                    "studio.frame.offer.v1": "offer_block",
                    "studio.frame.cta.v1": "cta_block",
                    "studio.frame.logo.v1": "brand_mark",
                }
                for frame in existing_recipe["document"]["frames"]:
                    role = (
                        "background" if frame["tool_id"] == "studio.frame.shape.v1"
                        and int(frame["z_index"]) == 0 else role_for_tool.get(frame["tool_id"])
                    )
                    if role is not None:
                        reserved_instance_ids[role] = frame["instance_id"]
            elements, instance_ids = self._normalize_elements(
                alias=alias, candidate=candidate, reserved_instance_ids=reserved_instance_ids,
            )
            if (
                candidate.value["media_request"]["kind"] == "non_human_graphic"
                and existing_recipe is None
            ):
                self.repository.consume_budget(run["run_id"], "graphic_generation_remaining")
                run = {**run, "budget_state": {
                    **run["budget_state"], "graphic_generation_remaining": 1,
                }}
            adapter = adapter_for_profile(
                run["output_profile"], repository=self.repository.authority,
                renderer=self.recipe_renderer, pexels=self.pexels, bridge=self.bridge,
            )
            parent_recipe = (
                None if parent_creative_id is None
                else self.repository.authority.get_creative_recipe(parent_creative_id)
            )
            materialized = adapter.materialize(
                candidate=candidate,
                run={
                    **run,
                    "creative_id": creative_id,
                    "candidate_template_id": template.template_id,
                    "candidate_parameters": dict(parameters),
                    "parent_recipe_id": None if parent_recipe is None else parent_recipe["recipe_id"],
                    "base_recipe_sha256": None if parent_recipe is None else parent_recipe["document_sha256"],
                },
                element_ids=instance_ids,
                requested_by=run["requested_by"],
            )
            media_source = materialized.get("media_source")
            if media_source is not None:
                resolved_media_id = str(media_source["source_asset_id"])
                for element in elements:
                    if element["slot"] != "primary_subject":
                        continue
                    existing_sources = list(element["payload"].get("source_ids") or [])
                    if element["reuse_mode"] == "reuse_exact" and existing_sources != [resolved_media_id]:
                        raise ValueError(
                            "an exactly reused primary subject must retain its resolved media source"
                        )
                    element["payload"]["source_ids"] = [resolved_media_id]
            stored = self.repository.persist_creative(
                run_id=run["run_id"], creative_id=creative_id, slot=alias,
                round_number=round_number, generation_kind=generation_kind,
                parent_creative_id=parent_creative_id, template=template,
                parameters=parameters, candidate=candidate, elements=elements,
                materialized=materialized, provider_provenance=invocation,
                provider_invocation_id=invocation_id,
            )
            self._checkpoint_creative(stored)
            return stored
        except Exception as error:
            self.repository.finish_invocation(
                attempt_id, invocation_id, response=None,
                provenance=getattr(
                    error, "invocation", getattr(self.bridge, "last_invocation", {})
                ),
                error=error,
            )
            raise

    def _initial_creatives(
        self, run: Mapping[str, Any], templates: Sequence[StrategyTemplate],
    ) -> list[dict[str, Any]]:
        parent = None
        if run["generation_kind"] == "tune":
            parent = self.repository.get_creative(run["tuned_creative_id"])
            templates = [next(item for item in templates if item.template_id == run["tuned_strategy_id"])]
        existing = {item["creative_id"]: item for item in self.repository.list_creatives(run["run_id"])}
        jobs: list[tuple[int, str, StrategyTemplate]] = []
        for index, (creative_id, template) in enumerate(zip(run["reserved_creative_ids"], templates), start=1):
            if creative_id not in existing:
                jobs.append((index, creative_id, template))
        if jobs:
            with ThreadPoolExecutor(max_workers=2, thread_name_prefix="ptw-result-generator") as executor:
                futures = {
                    executor.submit(
                        self._call_creative, run=run, creative_id=creative_id,
                        alias=parent["slot"] if parent is not None else f"C{index}",
                        template=template,
                        parameters=parent["parameters"] if parent is not None else template.defaults,
                        round_number=0 if parent is None else int(parent["round"]) + 1,
                        generation_kind=run["generation_kind"],
                        parent_creative_id=None if parent is None else parent["creative_id"],
                    ): creative_id
                    for index, creative_id, template in jobs
                }
                errors: list[Exception] = []
                for future in as_completed(futures):
                    try:
                        existing[futures[future]] = future.result()
                    except Exception as error:
                        errors.append(error)
                if errors:
                    raise RuntimeError(
                        f"An initial Result direction failed after its fresh structured retry: {errors[0]}"
                    ) from errors[0]
        values = [existing[creative_id] for creative_id in run["reserved_creative_ids"]]
        expected = 1 if run["generation_kind"] == "tune" else 5
        if len(values) != expected or (
            expected == 5 and len({item["template_id"] for item in values}) != 5
        ):
            raise RuntimeError("Result run did not materialize its isolated Creative directions")
        for item in values:
            self._checkpoint_creative(item)
        return values

    def _checkpoint_creative(self, creative: Mapping[str, Any]) -> None:
        self.repository.checkpoint(
            creative["run_id"], stage="creative_rendered", target_id=creative["creative_id"],
            payload={
                "creative_id": creative["creative_id"], "slot": creative["slot"],
                "round": creative["round"], "template_id": creative["template_id"],
                "document_sha256": creative["document_sha256"],
                "recipe_id": creative["recipe_id"], "render_id": creative["render_id"],
                "preview_sha256": self.repository.creative_preview(creative["creative_id"])["sha256"],
            },
        )

    def execute(self, run_id: str) -> dict[str, Any]:
        run = self.repository.get_run(run_id)
        if run["status"] in {"awaiting_review", "approved", "superseded", "failed"}:
            return run
        try:
            self.repository.set_stage(run_id, "generating_creatives")
            templates = self.template_registry.load_active()
            creatives = self._initial_creatives(self.repository.get_run(run_id), templates)
            creative_ids = [item["creative_id"] for item in creatives]
            expected = 1 if run["generation_kind"] == "tune" else 5
            if len(creative_ids) != expected or len(set(creative_ids)) != expected:
                raise RuntimeError("Result run did not create the required distinct Creatives")
            document_digests = {item["document_sha256"] for item in creatives}
            render_digests = {
                self.repository.creative_preview(item["creative_id"])["sha256"]
                for item in creatives
            }
            if len(document_digests) != expected or len(render_digests) != expected:
                raise RuntimeError("generated review Creatives must have distinct documents and renders")
            if len({item["provider_invocation_id"] for item in creatives}) != expected:
                raise RuntimeError("generated Creatives must have distinct provider invocation identities")
            if run["output_profile"] in STATIC_SOCIAL_PROFILES:
                media_digests = [item["media_identity_sha256"] for item in creatives]
                if None in media_digests or len(set(media_digests)) != expected:
                    raise RuntimeError("generated social Creatives must have distinct media identities")
            if run["generation_kind"] == "regenerate_all" and run["parent_run_id"]:
                parent_review = self.repository.get_review(run["parent_run_id"])["creatives"]
                if document_digests & {item["document_sha256"] for item in parent_review}:
                    raise RuntimeError("regenerate-all reused an excluded Creative document")
                if render_digests & {
                    self.repository.creative_preview(item["creative_id"])["sha256"]
                    for item in parent_review
                }:
                    raise RuntimeError("regenerate-all reused an excluded Creative render")
                media_digests = {
                    item["media_identity_sha256"] for item in creatives
                    if item["media_identity_sha256"] is not None
                }
                if media_digests & {
                    item["media_identity_sha256"] for item in parent_review
                    if item["media_identity_sha256"] is not None
                }:
                    raise RuntimeError("regenerate-all reused an excluded Creative media identity")
                if {item["provider_invocation_id"] for item in creatives} & {
                    item["provider_invocation_id"] for item in parent_review
                }:
                    raise RuntimeError("regenerate-all reused an excluded provider invocation")
            awaiting = self.repository.mark_awaiting_review(run_id, creative_ids)
            try:
                self.repository.deliver_review_notification(
                    run_id, notifier=self.notifier, manual_retry=False,
                )
            except Exception:
                # Notification delivery is observable and retryable; it never hides
                # an otherwise valid review set.
                pass
            return self.repository.get_run(awaiting["run_id"])
        except Exception as error:
            return self.repository.fail_run(run_id, error)

    def approve(
        self, *, run_id: str, request_id: str, creative_id: str, requested_by: str,
    ) -> dict[str, Any]:
        return self.repository.approve_review(
            run_id=run_id, request_id=request_id, creative_id=creative_id,
            requested_by=requested_by,
        )

    def regenerate_all(
        self, *, run_id: str, request_id: str, requested_by: str,
    ) -> tuple[dict[str, Any], bool]:
        child, created = self.repository.create_regenerate_all(
            run_id=run_id, request_id=request_id, requested_by=requested_by,
            create_run=self.create_run,
        )
        return child, created

    def tune(
        self, *, run_id: str, request_id: str, creative_id: str,
        comment: str, requested_by: str,
    ) -> tuple[dict[str, Any], bool]:
        return self.repository.create_tune(
            run_id=run_id, request_id=request_id, creative_id=creative_id,
            comment=comment, requested_by=requested_by, create_run=self.create_run,
        )

    def retry_notification(self, run_id: str) -> dict[str, Any]:
        return self.repository.deliver_review_notification(
            run_id, notifier=self.notifier, manual_retry=True,
        )

    def resume_incomplete(self) -> dict[str, int]:
        resumed = 0
        for run_id in self.repository.recoverable_runs():
            self.execute(run_id)
            resumed += 1
        notifications = 0
        for run_id in self.repository.recoverable_notification_runs():
            self.repository.deliver_review_notification(
                run_id, notifier=self.notifier, manual_retry=False,
            )
            notifications += 1
        return {"resumed": resumed, "notifications": notifications}
