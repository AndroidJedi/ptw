"""Durable five-template Result orchestration with three bounded critic passes."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import Any, Mapping, Sequence

from commander.ids import new_uuid7

from .content import (
    CandidateV2, ContentContextAssembler, REQUIRED_COPY_SLOTS, SLIDER_NAMES,
    StrategyTemplate, TemplateRegistry, candidate_output_schema, canonical_json,
    critic_output_schema, sha256_json, validate_critic_response,
)
from .content_adapters import adapter_for_profile
from .natal_brand import natal_logo_bytes
from .studio import tool_catalog


@dataclass(frozen=True, slots=True)
class GeneratedCandidate:
    value: Mapping[str, Any]


class CandidateGenerationOrchestrator:
    """Server-authorized execution of isolated generators and typed critic actions."""

    def __init__(
        self, *, repository: Any, bridge: Any, context_assembler: ContentContextAssembler,
        template_registry: TemplateRegistry, recipe_renderer: Any, pexels: Any,
    ) -> None:
        self.repository = repository
        self.bridge = bridge
        self.context_assembler = context_assembler
        self.template_registry = template_registry
        self.recipe_renderer = recipe_renderer
        self.pexels = pexels

    def create_run(
        self, *, request_id: str, brief_id: str, task: str, output_profile: str,
        requested_by: str, parent_run_id: str | None = None,
    ) -> tuple[dict[str, Any], bool]:
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
        context = self.context_assembler.assemble_run(
            brief=brief, task=task, output_profile=output_profile, brand_kit=brand_kit,
            approved_sources=approved_sources, tool_catalog=tool_catalog(), templates=templates,
        )
        return self.repository.create_run(
            request_id=request_id, brief_id=brief_id, task=task, output_profile=output_profile,
            context=context, templates=templates, requested_by=requested_by,
            parent_run_id=parent_run_id,
        )

    @staticmethod
    def _deadline_ok(run: Mapping[str, Any]) -> None:
        deadline = datetime.fromisoformat(str(run["deadline_at"]))
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) >= deadline:
            raise TimeoutError("Result run exceeded the 45-minute wall-clock limit")

    @staticmethod
    def _candidate_system_prompt(context: Mapping[str, Any]) -> str:
        writing = context["writing"]
        return "\n\n".join((
            writing["generator_core"], writing["principles"], writing["anti_patterns"],
            writing["technique"], writing["owner_lessons"],
            context["template"]["document"]["prompt_fragment"],
            "Return exactly one strict CandidateV2 JSON object. Do not mention any other candidate. "
            "Preserve the supplied offer and CTA exactly. Use only supplied identifiers.",
        ))

    @staticmethod
    def _candidate_payload(
        run: Mapping[str, Any], template: StrategyTemplate, parameters: Mapping[str, int],
        *, action: Mapping[str, Any] | None, source_elements: Sequence[Mapping[str, Any]],
        candidate_id: str,
    ) -> dict[str, Any]:
        context = run["context_bundle"]["candidate_contexts"][template.template_id]
        return {
            "candidate_id": candidate_id,
            "run_id": run["run_id"],
            "context_digest": sha256_json(context),
            "approved_brief": context["brief"], "task": context["task"],
            "output_profile": context["output_profile"], "brand_kit": context["brand_kit"],
            "approved_sources": context["approved_sources"],
            "tool_catalog": context["tool_catalog"],
            "strategy": context["template"],
            "parameters": dict(parameters),
            "runtime_bands": template.runtime_bands(parameters),
            "retrieved_examples": [{
                "example_id": example_id, "excerpt": excerpt,
            } for example_id, excerpt in zip(
                context["writing"]["example_ids"], context["writing"]["examples"],
            )],
            "improvement_action": None if action is None else dict(action),
            "source_elements": [dict(item) for item in source_elements],
            "excluded_context": context["source_policy"],
        }

    @staticmethod
    def _merge_locked(
        candidate: CandidateV2, locked: Sequence[Mapping[str, Any]], *, brief: Mapping[str, Any],
        output_profile: str,
    ) -> CandidateV2:
        if not locked:
            return candidate
        value = json.loads(canonical_json(candidate.value))
        components = list(value["visual_components"])
        for element in locked:
            slot, payload, ordinal = element["slot"], element["payload"], int(element["ordinal"])
            if slot in REQUIRED_COPY_SLOTS[:-1]:
                value[slot] = payload["value"]
            elif slot == "media_request":
                value["media_request"] = dict(payload)
            else:
                matches = [index for index, item in enumerate(components) if item["role"] == slot]
                if ordinal < len(matches):
                    components[matches[ordinal]] = {
                        "role": slot, "content": payload["content"],
                        "source_ids": list(payload.get("source_ids") or []),
                    }
        value["visual_components"] = components
        return CandidateV2.from_dict(value, brief=brief, output_profile=output_profile)

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
        locked: Sequence[Mapping[str, Any]], source_elements: Sequence[Mapping[str, Any]],
        target_elements: Sequence[Mapping[str, Any]], action_type: str | None,
        reserved_instance_ids: Mapping[str, str] | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, str]]:
        locked_by_slot = {(item["slot"], int(item["ordinal"])): item for item in locked}
        source_ids = [item["element_id"] for item in source_elements]
        target_by_slot = {(item["slot"], int(item["ordinal"])): item for item in target_elements}
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
            locked_item = locked_by_slot.get((slot, ordinal))
            if locked_item is not None:
                element = {
                    **dict(locked_item), "reuse_mode": "reuse_exact",
                    "source_element_ids": [],
                }
            else:
                target = target_by_slot.get((slot, ordinal))
                reuse_mode = (
                    "replacement" if target is not None
                    else "adapt_concept" if action_type == "recompose" and slot in {
                        "visual_concept", "background", "primary_subject", "lighting_style", "composition",
                    }
                    else "generated"
                )
                contributing = (
                    [target["element_id"]] if target is not None
                    else source_ids if reuse_mode == "adapt_concept" else []
                )
                element = {
                    "element_id": (
                        (reserved_instance_ids or {})[slot]
                        if slot in (reserved_instance_ids or {}) else new_uuid7()
                    ),
                    "display_alias": f"{alias}.{slot.upper()}.{ordinal + 1:02d}",
                    "slot": slot, "ordinal": ordinal, "element_type": cls._element_type(slot),
                    "payload": dict(payload), "reuse_mode": reuse_mode,
                    "source_element_ids": contributing,
                }
            elements.append(element)
            if ordinal == 0:
                instance_ids[slot] = str(element["element_id"])
        return elements, instance_ids

    def _call_candidate(
        self, *, run: Mapping[str, Any], candidate_id: str, alias: str,
        template: StrategyTemplate, parameters: Mapping[str, int], round_number: int,
        generation_kind: str, parent_candidate_id: str | None,
        action: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._deadline_ok(run)
        all_candidates = self.repository.list_candidates(run["run_id"])
        elements_by_id = {
            item["element_id"]: item for candidate in all_candidates for item in candidate["elements"]
        }
        locked = [elements_by_id[item] for item in (action or {}).get("locked_element_ids", [])]
        sources = [elements_by_id[item] for item in (action or {}).get("source_element_ids", [])]
        targets = [elements_by_id[item] for item in (action or {}).get("target_element_ids", [])]
        payload = self._candidate_payload(
            run, template, parameters, action=action, source_elements=sources,
            candidate_id=candidate_id,
        )
        key = f"{run['run_id']}:{candidate_id}:content_candidate_generation"
        attempt_id, invocation_id = self.repository.start_invocation(
            candidate_id, mode="content_candidate_generation", idempotency_key=key, request=payload,
        )
        try:
            response = self.bridge.generate_content_candidate(
                system_prompt=self._candidate_system_prompt(
                    run["context_bundle"]["candidate_contexts"][template.template_id]
                ),
                input_payload=payload, output_schema=candidate_output_schema(),
                prompt_version=f"ptw-content-candidate-v2-{template.template_id}-v{template.version}",
                idempotency_key=key,
            )
            invocation = dict(response["invocation"])
            self.repository.finish_invocation(
                attempt_id, invocation_id, response=response["response"], provenance=invocation,
            )
            brief = run["context_bundle"]["brief"]["document"]
            candidate = CandidateV2.from_dict(
                response["response"], brief=brief, output_profile=run["output_profile"],
            )
            candidate = self._merge_locked(
                candidate, locked, brief=brief, output_profile=run["output_profile"],
            )
            existing_recipe = self.repository.authority.get_candidate_recipe(candidate_id)
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
                alias=alias, candidate=candidate, locked=locked, source_elements=sources,
                target_elements=targets, action_type=None if action is None else str(action["action_type"]),
                reserved_instance_ids=reserved_instance_ids,
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
            materialized = adapter.materialize(
                candidate=candidate,
                run={
                    **run,
                    "candidate_id": candidate_id,
                    "candidate_template_id": template.template_id,
                    "candidate_parameters": dict(parameters),
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
            stored = self.repository.persist_candidate(
                run_id=run["run_id"], candidate_id=candidate_id, alias=alias,
                round_number=round_number, generation_kind=generation_kind,
                parent_candidate_id=parent_candidate_id, template=template,
                parameters=parameters, candidate=candidate, elements=elements,
                materialized=materialized, provider_provenance=invocation,
            )
            self._checkpoint_candidate(stored)
            return stored
        except Exception as error:
            self.repository.finish_invocation(
                attempt_id, invocation_id, response=None,
                provenance=getattr(self.bridge, "last_invocation", {}), error=error,
            )
            raise

    def _initial_candidates(
        self, run: Mapping[str, Any], templates: Sequence[StrategyTemplate],
    ) -> list[dict[str, Any]]:
        existing = {item["candidate_id"]: item for item in self.repository.list_candidates(run["run_id"])}
        jobs: list[tuple[int, str, StrategyTemplate]] = []
        for index, (candidate_id, template) in enumerate(zip(run["initial_candidate_ids"], templates), start=1):
            if candidate_id not in existing:
                jobs.append((index, candidate_id, template))
        if jobs:
            with ThreadPoolExecutor(max_workers=2, thread_name_prefix="ptw-result-generator") as executor:
                futures = {
                    executor.submit(
                        self._call_candidate, run=run, candidate_id=candidate_id, alias=f"C{index}",
                        template=template, parameters=template.defaults, round_number=0,
                        generation_kind="initial", parent_candidate_id=None,
                    ): candidate_id
                    for index, candidate_id, template in jobs
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
        values = [existing[candidate_id] for candidate_id in run["initial_candidate_ids"]]
        if len(values) != 5 or len({item["template_id"] for item in values}) != 5:
            raise RuntimeError("Result run did not materialize five isolated template candidates")
        for item in values:
            self._checkpoint_candidate(item)
        return values

    def _checkpoint_candidate(self, candidate: Mapping[str, Any]) -> None:
        self.repository.checkpoint(
            candidate["run_id"], stage="candidate_rendered", target_id=candidate["candidate_id"],
            payload={
                "candidate_id": candidate["candidate_id"], "alias": candidate["alias"],
                "round": candidate["round"], "template_id": candidate["template_id"],
                "document_sha256": candidate["document_sha256"],
                "recipe_id": candidate["recipe_id"], "render_id": candidate["render_id"],
                "preview_sha256": self.repository.candidate_preview(candidate["candidate_id"])["sha256"],
            },
        )

    @staticmethod
    def _critic_system_prompt(context: Mapping[str, Any], pass_number: int) -> str:
        return "\n\n".join((
            context["critic_core"], context["evaluation_contract"], context["owner_lessons"],
            context["principles"], context["anti_patterns"],
            "Neutral anchors:\n" + "\n".join(item["excerpt"] for item in context["anchors"]),
            f"Perform critic Pass {pass_number}. Candidate strategy names are intentionally hidden. "
            "For rerun_template actions, set template_id to null and adjust only the supplied sliders. "
            "Return reason codes and concise observations, never private reasoning.",
        ))

    def _critic_call(
        self, *, run: Mapping[str, Any], pass_number: int,
        active: Sequence[Mapping[str, Any]], prior_summaries: Sequence[Mapping[str, Any]],
        templates: Mapping[str, StrategyTemplate],
    ) -> dict[str, Any]:
        self._deadline_ok(run)
        maximum = {1: 5, 2: 5, 3: 2}[pass_number]
        if len(active) != maximum:
            raise ValueError(f"critic Pass {pass_number} requires exactly {maximum} active candidates")
        pass_id = self.repository.reserve_critic_pass(run["run_id"], pass_number)
        candidate_ids = [item["candidate_id"] for item in active]
        element_ids = [element["element_id"] for item in active for element in item["elements"]]
        element_map = {
            item["candidate_id"]: [element["element_id"] for element in item["elements"]]
            for item in active
        }
        payload = {
            "run_id": run["run_id"], "pass": pass_number,
            "approved_brief": run["context_bundle"]["brief"], "task": run["task"],
            "output_profile": run["output_profile"],
            "protected": {
                "offer": run["context_bundle"]["brief"]["document"]["offer"],
                "cta": run["context_bundle"]["brief"]["document"]["cta"],
                "project_id": run["project_id"], "brand_kit_id": run["brand_kit_id"],
                "source_policy": run["context_bundle"]["source_policy"],
            },
            "candidates": [{
                "candidate_id": item["candidate_id"], "anonymous_alias": f"A{index}",
                "document": item["document"], "document_sha256": item["document_sha256"],
                "elements": [{
                    "element_id": element["element_id"], "display_alias": element["display_alias"],
                    "slot": element["slot"], "payload": element["payload"],
                } for element in item["elements"]],
                "parameters": item["parameters"], "regeneration_count": item["round"],
                "render_mapping": self.repository.candidate_preview(item["candidate_id"])["sha256"],
            } for index, item in enumerate(active, start=1)],
            "prior_pass_summaries": [dict(item) for item in prior_summaries],
        }
        images = [{
            "candidate_id": item["candidate_id"],
            **self.repository.candidate_preview(item["candidate_id"]),
        } for item in active]
        key = f"{run['run_id']}:critic-pass-{pass_number}"
        attempt_id, invocation_id = self.repository.start_invocation(
            pass_id, mode="content_result_critic", idempotency_key=key, request=payload,
        )
        try:
            response = self.bridge.generate_content_critic(
                system_prompt=self._critic_system_prompt(
                    run["context_bundle"]["critic_context"], pass_number
                ),
                input_payload=payload, images=images,
                output_schema=critic_output_schema(pass_number, candidate_ids, element_ids),
                prompt_version=f"ptw-content-result-critic-v1-pass-{pass_number}",
                idempotency_key=key,
            )
            invocation = dict(response["invocation"])
            self.repository.finish_invocation(
                attempt_id, invocation_id, response=response["response"], provenance=invocation,
            )
            validated = validate_critic_response(
                response["response"], pass_number=pass_number, candidate_ids=candidate_ids,
                element_ids=element_ids, templates=templates,
                candidate_parameters={item["candidate_id"]: item["parameters"] for item in active},
                candidate_templates={item["candidate_id"]: item["template_id"] for item in active},
                candidate_element_ids=element_map,
                candidate_regeneration_counts={
                    item["candidate_id"]: int(item["round"]) for item in active
                },
            )
            generation_actions = [
                item for item in validated["actions"] if item["action_type"] != "discard"
            ]
            if pass_number == 1 and len(generation_actions) > 2:
                raise ValueError("critic Pass 1 exceeded its two-call improvement ceiling")
            self.repository.persist_critic_pass(
                pass_id=pass_id, run_id=run["run_id"], value=validated,
                provider_provenance=invocation,
            )
            stored = {"pass_id": pass_id, **validated}
            self._checkpoint_critic(stored)
            return stored
        except Exception as error:
            self.repository.finish_invocation(
                attempt_id, invocation_id, response=None,
                provenance=getattr(self.bridge, "last_invocation", {}), error=error,
            )
            raise

    def _checkpoint_critic(self, critic_pass: Mapping[str, Any]) -> None:
        self.repository.checkpoint(
            critic_pass.get("run_id") or self.repository.get_candidate(
                critic_pass["ranking"][0]
            )["run_id"],
            stage=f"critic_pass_{critic_pass['pass']}", target_id=critic_pass["pass_id"],
            payload={
                "pass_id": critic_pass["pass_id"], "pass": critic_pass["pass"],
                "ranking": list(critic_pass["ranking"]),
                "action_count": len(critic_pass.get("actions") or []),
                "final_selection": critic_pass["final_selection"],
            },
        )

    def _checkpoint_action(
        self, action: Mapping[str, Any], candidate: Mapping[str, Any],
    ) -> None:
        self.repository.checkpoint(
            action["run_id"], stage="improvement_action_completed", target_id=action["action_id"],
            payload={
                "action_id": action["action_id"], "action_type": action["action_type"],
                "output_candidate_id": candidate["candidate_id"],
            },
        )

    @staticmethod
    def _ordered_candidates(
        ids: Sequence[str], candidates: Mapping[str, Mapping[str, Any]], *, maximum: int,
    ) -> list[Mapping[str, Any]]:
        result: list[Mapping[str, Any]] = []
        for candidate_id in ids:
            if candidate_id in candidates and all(item["candidate_id"] != candidate_id for item in result):
                result.append(candidates[candidate_id])
            if len(result) == maximum:
                break
        if len(result) != maximum:
            raise RuntimeError("Result critic could not form the bounded active candidate set")
        return result

    def _execute_actions(
        self, *, run: Mapping[str, Any], critic_pass: Mapping[str, Any], pass_number: int,
        templates: Mapping[str, StrategyTemplate],
    ) -> list[dict[str, Any]]:
        actions = self.repository.list_actions(critic_pass["pass_id"])
        generated: list[dict[str, Any]] = []
        for action in actions:
            if action["status"] == "completed":
                candidate = self.repository.get_candidate(action["output_candidate_id"])
                self._checkpoint_action(action, candidate)
                generated.append(candidate)
                continue
            if action["status"] in {"failed", "discarded"}:
                continue
            if action["action_type"] == "discard":
                self.repository.discard_action(action["action_id"], reason="critic discarded the direction")
                continue
            try:
                already_materialized = self.repository.get_candidate(action["reserved_candidate_id"])
            except KeyError:
                already_materialized = None
            if already_materialized is not None:
                self.repository.start_action(action["action_id"])
                self.repository.finish_action(
                    action["action_id"], output_candidate_id=already_materialized["candidate_id"],
                )
                self._checkpoint_action(action, already_materialized)
                generated.append(already_materialized)
                continue
            run = self.repository.get_run(run["run_id"])
            if int(run["budget_state"]["improvement_generation_remaining"]) <= 0:
                self.repository.discard_action(action["action_id"], reason="four-call improvement budget exhausted")
                continue
            self.repository.start_action(action["action_id"])
            command = action["command"]
            base = self.repository.get_candidate(command["base_candidate_id"])
            template = templates[str(command.get("template_id") or base["template_id"])]
            parameters = command.get("slider_values") or base["parameters"]
            generation_kind = {
                "recompose": "recomposition",
                "regenerate_elements": "element_regeneration",
                "rerun_template": "template_rerun",
            }[action["action_type"]]
            alias_prefix = "S" if action["action_type"] == "recompose" else "R"
            alias = f"{alias_prefix}{pass_number * 10 + action['ordinal'] + 1}"
            try:
                candidate = self._call_candidate(
                    run=run, candidate_id=action["reserved_candidate_id"], alias=alias,
                    template=template, parameters=parameters, round_number=pass_number,
                    generation_kind=generation_kind, parent_candidate_id=base["candidate_id"],
                    action=command,
                )
                self.repository.finish_action(
                    action["action_id"], output_candidate_id=candidate["candidate_id"],
                )
                self._checkpoint_action(action, candidate)
                generated.append(candidate)
            except Exception as error:
                self.repository.finish_action(action["action_id"], error=error)
                raise
        return generated

    @staticmethod
    def _pass_summary(value: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "pass": value["pass"], "ranking": list(value["ranking"]),
            "observations": list(value["observations"]),
            "weighted_totals": {
                item["candidate_id"]: item["weighted_total"] for item in value["evaluations"]
            },
        }

    def execute(self, run_id: str) -> dict[str, Any]:
        run = self.repository.get_run(run_id)
        if run["status"] == "completed":
            result = self.repository.get_result(run_id)
            self._checkpoint_result(result)
            return result
        if run["status"] == "failed":
            raise ValueError(run["error_message"] or "Result run is failed")
        templates_tuple = self.template_registry.load_active()
        templates = {item.template_id: item for item in templates_tuple}
        try:
            if len(self.repository.list_candidates(run_id)) < 5:
                self.repository.set_stage(run_id, "initial_candidates")
            run = self.repository.get_run(run_id)
            initial = self._initial_candidates(run, templates_tuple)

            pass1 = self.repository.get_critic_pass(run_id, 1)
            if pass1 is None:
                self.repository.set_stage(run_id, "critic_pass_1")
                pass1 = self._critic_call(
                    run=self.repository.get_run(run_id), pass_number=1, active=initial,
                    prior_summaries=[], templates=templates,
                )
            self._checkpoint_critic(pass1)
            improvements1 = self._execute_actions(
                run=self.repository.get_run(run_id), critic_pass=pass1, pass_number=1,
                templates=templates,
            )
            by_id = {item["candidate_id"]: item for item in [*initial, *improvements1]}
            active2 = self._ordered_candidates(
                [*[item["candidate_id"] for item in improvements1], *pass1["ranking"]],
                by_id, maximum=5,
            )

            pass2 = self.repository.get_critic_pass(run_id, 2)
            if pass2 is None:
                self.repository.set_stage(run_id, "critic_pass_2")
                pass2 = self._critic_call(
                    run=self.repository.get_run(run_id), pass_number=2, active=active2,
                    prior_summaries=[self._pass_summary(pass1)], templates=templates,
                )
            self._checkpoint_critic(pass2)
            improvements2 = self._execute_actions(
                run=self.repository.get_run(run_id), critic_pass=pass2, pass_number=2,
                templates=templates,
            )
            by_id.update({item["candidate_id"]: item for item in improvements2})
            finalists = self._ordered_candidates(
                [*[item["candidate_id"] for item in improvements2], *pass2["ranking"]],
                by_id, maximum=2,
            )

            pass3 = self.repository.get_critic_pass(run_id, 3)
            if pass3 is None:
                self.repository.set_stage(run_id, "critic_pass_3")
                pass3 = self._critic_call(
                    run=self.repository.get_run(run_id), pass_number=3, active=finalists,
                    prior_summaries=[self._pass_summary(pass1), self._pass_summary(pass2)],
                    templates=templates,
                )
            self._checkpoint_critic(pass3)
            selection = pass3["final_selection"]
            if selection is None:
                raise ValueError(
                    "No candidate passed every final Result gate. Create another Result with a more "
                    "specific task or add a clearer approved Project asset."
                )
            self.repository.set_stage(run_id, "materializing_result")
            result = self.repository.finalize(
                run_id, selected_candidate_id=selection["candidate_id"],
                decision_summary=selection["decision_summary"],
            )
            self._checkpoint_result(result)
            return result
        except Exception as error:
            self.repository.fail_run(run_id, error)
            raise

    def _checkpoint_result(self, result: Mapping[str, Any]) -> None:
        self.repository.checkpoint(
            result["run_id"], stage="completed", target_id=result["creative_id"],
            payload={
                "creative_id": result["creative_id"],
                "selected_candidate_id": result["selected_candidate_id"],
                "result_sha256": result["result_sha256"],
            },
        )

    def resume_incomplete(self) -> dict[str, int]:
        resumed, failed = 0, 0
        for run_id in self.repository.recoverable_runs():
            try:
                # Lifecycle checkpoints are idempotent. A run is restarted only
                # when no terminal Result exists; completed candidate/pass rows
                # remain the authoritative skip markers.
                self.execute(run_id)
                resumed += 1
            except Exception:
                failed += 1
        return {"resumed": resumed, "failed": failed}
