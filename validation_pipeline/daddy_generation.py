"""Resumable Brief → composition → independent assets → editable draft."""
from __future__ import annotations

from copy import deepcopy
import json
import re
from uuid import NAMESPACE_URL, uuid5

from .studio_daddy import PRESETS, STYLES, COPY, SLOTS, default_configuration, normalize_configuration, normalize_content, required_slots, agent_catalog
from .image_generation_policy import build_image_context, instruction_context
from .template_components import bounded_text
from .agent_context import compact_active_skills

POLICY = """Daddy is a professional modular Post art director. Produce one post from the exact approved Brief.
Keep one primary message and a coherent visual idea. Inherit marketing_approach, positioning and brand_identity.
For Identity-led use belief, identity_signal, category_reframe and voice to express a purposeful choice;
connect emotional_reward with recognizable product action and proof_anchor. For Benefit-led lead with a concrete useful outcome.
Preserve Natal colors and identity. No invented prices, discounts, metrics, testimonials, availability, urgency or proof.
All supplied presets are design hypotheses, never performance evidence. Prefer the simplest suitable composition.
Keep headline short and complete. Use real product context, not generic luxury or arbitrary metaphors.
Phone imagery uses standalone devices, with no hands or fingers. Separate copy from artwork. A screen slot requests a generated app interior with short domain-correct labels.
Scene has negative space for copy; subjects and props are complete, coordinated and semantically purposeful.
Choose photography, illustration, drawing, paper collage or 3D deliberately; do not force a phone into every ad.
Respect explicit owner direction. Return only the requested schema. Never approve, publish or activate learning."""


def obj(properties):
    return {"type":"object","properties":properties,"required":list(properties),"additionalProperties":False}


def string(maximum=600, values=None):
    return {"type":"string", **({"enum":list(values)} if values is not None else {"maxLength":maximum})}


def asset_context(service, creative, detail, slot, direction, *, owner=False, enhance=False):
    config = detail["configuration"]
    mode = "app_screen" if slot=="screen" else "image"
    style_map = {"photography":"ultra_realistic_lifestyle","editorial_illustration":"artistic_illustration","line_drawing":"artistic_illustration","paper_collage":"tactile_handmade","contemporary_3d":"contemporary_3d"}
    current = next((v.get("source") or {} for v in detail["assets"] if v["slot"]==slot),{})
    settings = {"style":style_map[config["style"]],"background":"scene" if slot=="scene" else "isolated_key_element",
                "palette":{k:config["background"][k] for k in ("color","end_color")},"art_treatment":config["style"]}
    if slot=="screen":
        settings.update(screen_language=service.authority.brief(creative["source_brief_id"])["document"].get("language","uk"),screen_design="Clean native interface with the supplied palette and brief-grounded features")
    destination = {"surface":"post","template_id":"daddy","template_reference":detail.get("template_reference"),"slot":slot,"mode":mode,
        "canvas":{"width":1080,"height":1350},"pose":config["device"]["pose"],"description":SLOTS[slot]["description"]}
    return build_image_context(direction=direction,instruction=instruction_context(direction,origin="owner" if owner else "generated"),
        brief=service.authority.brief(creative["source_brief_id"]),settings=settings,destination=destination,
        operation="enhance_current" if enhance else "generate_new",base_sha256=detail["state_sha256"],previous=current)


def generate_slot(service, creative, slot, direction, key, *, enhance=False, run=None, persist=None):
    """Reconcile uncertain work; only proven corrupt output advances the attempt key."""
    from .image_errors import CONFIRMED_IMAGE_FAILURES, InvalidGeneratedImage
    workspace = service._workspace(creative["creative_id"])
    operations = run.setdefault("asset_operations", {}) if run is not None else {}
    record = operations.setdefault(key, {"slot":slot,"attempt":0,"max_attempt":1,"attempts":{}})
    def save():
        if persist:
            persist()
    while True:
        attempt = record["attempt"]
        receipt = record["attempts"].setdefault(str(attempt), {"status":"pending"})
        if receipt.get("failure_code") in CONFIRMED_IMAGE_FAILURES:
            if attempt >= record["max_attempt"]:
                raise InvalidGeneratedImage(receipt.get("provider_request_id"), receipt["failure_code"])
            record["attempt"] += 1
            save()
            continue
        detail = workspace.detail()
        request_id = str(uuid5(NAMESPACE_URL, key if attempt == 0 else f"{key}:recovery:{attempt}"))
        current = workspace._asset_record(slot)
        if current and current.get("source", {}).get("request_id") == request_id:
            receipt.update(status="completed", asset_sha256=current["sha256"])
            save()
            return detail
        def progress(value):
            receipt.update(status=value.get("stage", "pending"))
            if isinstance(value.get("provider_request_id"), int):
                receipt["provider_request_id"] = value["provider_request_id"]
            save()
        try:
            result = workspace.daddy_asset_operation(slot=slot,base_sha256=detail["state_sha256"],request_id=request_id,
                action="generate",options={"visual_direction":direction,"enhance_current":enhance},
                image_context=asset_context(service,creative,detail,slot,direction,enhance=enhance),progress=progress)
            receipt.update(status="completed",asset_sha256=workspace._asset_record(slot)["sha256"])
            receipt.pop("failure_code", None)
            save()
            return result
        except InvalidGeneratedImage as error:
            receipt.update(status="failed",failure_code=error.failure_code,provider_request_id=error.provider_request_id)
            save()
        except Exception:
            receipt.update(status="interrupted",failure_code="unconfirmed")
            save()
            raise


def generate(service, creative_id):
    from .studio_creatives import _json_schema
    creative = service.authority.get_creative(creative_id)
    workspace = service._workspace(creative_id)
    definition = workspace._definition()
    tuned = definition.identity.template_id != "daddy"
    starting_config = definition.default_configuration()
    eligible = {k:v for k,v in PRESETS.items() if not tuned or k==starting_config["preset"]}
    planned_slots = {key: required_slots(starting_config if tuned else value["configuration"]) for key,value in eligible.items()}
    brief = service.authority.brief(creative["source_brief_id"])
    if not brief.get("approved") or not brief.get("document"):
        raise ValueError("Daddy requires its approved source Brief")
    generation = deepcopy(creative.get("generation") or {})
    run = generation.setdefault("daddy",{"phase":"strategy","assets":{},"corrections":0})
    operation = run.get("operation_id",creative_id)
    def progress(phase, status="composing"):
        run["phase"] = phase
        generation["stage"] = phase
        service.authority.update_creative(creative_id,status=status,generation=generation,state_sha256=workspace.state_sha256())
    def asset_progress():
        service.authority.update_creative(creative_id,generation=generation)
    def call(phase,payload,schema,validator,*,artifacts=None,mode="studio_creative_generation",key=None):
        result = service._provider_call(mode=mode,system_prompt=service.composer_skill+"\n\n"+POLICY,input_payload=payload,output_schema=schema,
            idempotency_key=f"daddy:{operation}:{key or phase}",prompt_version="daddy-v1",response_validator=validator,
            **({"input_artifacts":artifacts} if artifacts else {}))
        service.authority.record_generation(creative_id=creative_id,stage=f"daddy_{phase}",status="completed",
            provenance={"source_brief_id":creative["source_brief_id"],"template_reference":workspace._definition().identity.to_reference(),"provider":result.get("invocation",{})})
        return result["response"]
    try:
        if "strategy" not in run:
            progress("strategy")
            def strategy(value):
                if set(value)!={"preset","style","reason","assets"} or value["preset"] not in eligible or value["style"] not in STYLES:
                    raise ValueError("Daddy strategy is invalid")
                bounded_text(value["reason"],500,"Creative rationale")
                slots = [v["slot"] for v in value["assets"]]
                if len(slots)!=len(set(slots)) or set(slots)!=set(planned_slots[value["preset"]]):
                    raise ValueError("Asset plan must match the chosen composition")
                for item in value["assets"]:
                    if set(item)!={"slot","direction"}:
                        raise ValueError("Asset plan fields are invalid")
                    bounded_text(item["direction"],600,"Asset direction")
                return value
            run["strategy"] = call("strategy",{"approved_product_brief":brief["document"],"presets":[{"id":k,"description":v["description"],"slots":planned_slots[k]} for k,v in eligible.items()],
                "styles":list(STYLES),"owner_direction":generation.get("creative_direction"),"owner_instruction":generation.get("daddy_owner_instruction", ""),"active_creative_skills":compact_active_skills(service._active_skills(creative["project_id"]), surface="post")},
                obj({"preset":string(values=eligible),"style":string(values=STYLES),"reason":string(500),"assets":{"type":"array","maxItems":6,
                    "items":obj({"slot":string(values=SLOTS),"direction":string()})}}),strategy)
            progress("composition")
        selected = run["strategy"]
        if not run.get("composed"):
            progress("composition")
            config = deepcopy(starting_config) if tuned else default_configuration(selected["preset"])
            config["style"] = selected["style"]
            config["logo"] = workspace.detail()["configuration"]["logo"]
            schema = obj({"configuration":_json_schema(config),"content":_json_schema(COPY)})
            def compose(value):
                if set(value)!={"configuration","content"}:
                    raise ValueError("Daddy composition fields are invalid")
                value = {"configuration":normalize_configuration(value["configuration"]),"content":normalize_content(value["content"])}
                if value["configuration"]["preset"]!=selected["preset"] or value["configuration"]["logo"]!=config["logo"]:
                    raise ValueError("Preserve the selected composition and Natal colors")
                # Generated copy must not turn illustrative or plausible quantities into claims.
                supplied = set(re.findall(r"\d+(?:[.,]\d+)?",json.dumps({k:v for k,v in brief["document"].items() if k != "schema_version"},ensure_ascii=False)))
                written = set(re.findall(r"\d+(?:[.,]\d+)?"," ".join(value["content"].values())))
                if written-supplied:
                    raise ValueError("Copy contains a quantity absent from the approved Brief")
                if not value["content"]["hero_title"]:
                    raise ValueError("Supply a complete headline")
                return value
            result = call("composition",{"approved_product_brief":brief["document"],"strategy":selected,"configuration":config,"content_fields":list(COPY),
                "bounds":agent_catalog()["bounds"],"enums":agent_catalog()["enums"],"rule":"Preserve block placement unless needed to fit the Brief. Empty optional copy stays empty; do not fill absent offers."},schema,compose)
            workspace.save_configuration(base_sha256=workspace.state_sha256(),**result)
            run["composed"] = True
            progress("assets","generating_image")
        directions = {v["slot"]:v["direction"] for v in selected["assets"]}
        for slot in required_slots(workspace.detail()["configuration"]):
            if run["assets"].get(slot)=="completed":
                continue
            progress(f"asset:{slot}","generating_image")
            if not workspace._asset_record(slot):
                direction = directions.get(slot, f"{SLOTS[slot]['description']} Interpret the approved Brief and the chosen creative strategy.")
                generate_slot(service,creative,slot,direction,f"daddy:{operation}:asset:{slot}",run=run,persist=asset_progress)
            run["assets"][slot] = "completed"
            progress("assets","generating_image")
        # Rendering checks that the complete composition is usable. Its layout
        # diagnostics are shown in the editor; the owner decides what to change.
        # A saved polish proposal from an older interrupted run is never applied
        # implicitly after switching to manual review.
        if run.get("pending_polish"):
            run["skipped_polish"] = run.pop("pending_polish")
        progress("render")
        detail = workspace.detail()
        rendered = workspace.render_preview(state_sha256=detail["state_sha256"])
        run["render_sha256"] = rendered["bytes_sha256"]
        run["review_mode"] = "manual"
        run["issues"] = [str(v.get("issue", v)) for v in rendered.get("layout_issues",[])]
        run["phase"] = "ready_for_manual_edit"
        run.pop("error", None)
        run.pop("failure", None)
        generation.pop("error_type", None)
        generation.pop("error_message", None)
        return service._finish_draft(creative_id,workspace.detail(),generation)
    except Exception as error:
        from .image_errors import InvalidGeneratedImage
        run["error"] = "The current stage did not complete. Retry resumes saved progress."
        slot = run["phase"].partition(":")[2] if run["phase"].startswith("asset:") else None
        if run["phase"] == "polish" and run.get("pending_polish"):
            slot = run["pending_polish"][0]["slot"]
        run["failure"] = {"code":error.failure_code if isinstance(error,InvalidGeneratedImage) else "stage_failed", "slot":slot,
            "provider_request_id":getattr(error,"provider_request_id",None)}
        if slot and not run["failure"]["provider_request_id"]:
            for record in reversed(list(run.get("asset_operations", {}).values())):
                if record["slot"] == slot:
                    run["failure"]["provider_request_id"] = record["attempts"].get(str(record["attempt"]),{}).get("provider_request_id")
                    break
        generation.update(error_type=type(error).__name__,error_message=run["error"])
        service.authority.update_creative(creative_id,status="failed",generation=generation,state_sha256=workspace.state_sha256())
        service.authority.record_generation(creative_id=creative_id,stage=f"daddy_{run['phase']}",status="failed",provenance={"source_brief_id":creative["source_brief_id"]},error=error)
        raise
