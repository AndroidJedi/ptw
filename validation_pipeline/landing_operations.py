"""Durable, bounded Landing editing operations. Provider work never holds a page lock."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import os
import threading
import time
from uuid import UUID, uuid5, NAMESPACE_URL

from .image_reference import generation_request, generate_image
from .image_generation_policy import compile_image_prompt, image_provenance, IMAGE_POLICY_VERSION
from .landing_delivery import prepare
from .landing_operation_store import OperationStore, ACTIVE
from .landing_workspace import normalize_configuration, normalize_content, sha256_json
from .studio_manual_agent import manual_agent_request


def now():
    return datetime.now(timezone.utc).isoformat()


def failure(error, phase):
    name = type(error).__name__
    category = "timeout" if isinstance(error, (TimeoutError, ConnectionError)) or name in {"HTTPError", "ReadTimeout", "ConnectTimeout", "ConnectionError"} or "timed out" in str(error).lower() else "provider"
    if isinstance(error, ValueError):
        category = "validation"
    elif isinstance(error, RuntimeError) and "changed" in str(error).lower():
        category = "stale"
    return {"phase": phase, "category": category, "code": name,
            "retryable": category not in {"validation", "stale"}}


class LandingOperations:
    def __init__(self, service):
        self.service = service
        self.store = OperationStore(service.root / "operations.sqlite3", getattr(service.authority, "database_url", None))
        self.lock = threading.RLock()
        self.local = threading.local()
        self.references = {}
        self.running = set()
        # Deployment enables two only after the companion/resource canary passes.
        self.concurrency = max(1, min(2, int(os.getenv("PTW_LANDING_IMAGE_CONCURRENCY", "1"))))
        self.image_capacity = threading.BoundedSemaphore(self.concurrency)
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="landing-operation")

    def assert_idle(self, landing_id):
        if not getattr(self.local, "owned", False) and self.store.list(landing_id, active=True):
            raise RuntimeError("A Landing operation is running; wait for it to finish")

    def public(self, value):
        result = {key: deepcopy(value[key]) for key in (
            "operation_id", "request_id", "landing_id", "project_id", "kind", "status", "phase",
            "started_at", "updated_at", "jobs", "error", "result", "revision", "timings",
        ) if key in value}
        result["jobs"] = [{key: item for key, item in job.items() if key != "image_context"} for job in result["jobs"]]
        return result

    def get(self, project, landing, identifier):
        self._authorize(project, landing)
        value = self.store.get(identifier)
        if value["project_id"] != project or value["landing_id"] != landing:
            raise KeyError("Landing operation was not found in this Project")
        return self.public(value)

    def latest(self, project, landing):
        self._authorize(project, landing)
        values = self.store.list(landing, limit=1)
        return self.public(values[0]) if values else None

    def _authorize(self, project, landing):
        if self.service.authority.get_page(landing)["project_id"] != str(UUID(project)):
            raise KeyError("Landing operation was not found in this Project")

    def _save(self, value):
        value["updated_at"] = now()
        return self.store.save(value, value.get("revision"))

    def _update(self, identifier, **changes):
        with self.lock:
            value = self.store.get(identifier)
            value.update(changes)
            return self._save(value)

    def start(self, project, landing, request):
        if set(request) != {"kind", "request"} or request["kind"] not in {"agent", "image"}:
            raise ValueError("Landing operation requires a kind and bounded request")
        kind, incoming = request["kind"], request["request"]
        if not isinstance(incoming, dict):
            raise ValueError("Landing operation request must be an object")
        if kind == "agent":
            options = manual_agent_request(incoming)
            references = options.pop("screenshots")
        else:
            incoming = dict(incoming)
            request_id = str(UUID(incoming.pop("request_id")))
            slot = incoming.pop("slot")
            configuration, content = incoming.pop("configuration"), incoming.pop("content")
            options = generation_request(incoming)
            references = [options.pop("reference_image")] if "reference_image" in options else []
            options.update(request_id=request_id, slot=slot, configuration=configuration, content=content)
        options["configuration"] = normalize_configuration(options["configuration"])
        options["content"] = normalize_content(options["content"])
        reference_digests = [hashlib.sha256(data).hexdigest() for data in references]
        fingerprint = sha256_json({"kind": kind, "options": options, "references": reference_digests})
        identifier = str(uuid5(NAMESPACE_URL, f"ptw:landing-operation:{landing}:{options['request_id']}"))
        with self.lock:
            detail = self.service.detail(project, landing)
            try:
                previous = self.store.get(identifier)
            except KeyError:
                previous = None
            if previous:
                if previous["fingerprint"] != fingerprint or previous["project_id"] != project:
                    raise RuntimeError("Landing request UUID already belongs to different input")
                return self.public(previous)
            self.assert_idle(landing)
            if detail["status"] != "draft" or detail["state_sha256"] != options["base_sha256"]:
                raise RuntimeError("Landing changed; reload before starting the operation")
            workspace = self.service._workspace(landing)
            workspace.validate_template_content(options["configuration"], options["content"])
            if kind == "image" and options["slot"] not in workspace.visual_slots:
                raise ValueError("Landing visual slot is invalid")
            if len(self.running) >= 8:
                raise RuntimeError("Landing execution capacity is occupied; retry shortly")
            value = self.store.save({"operation_id": identifier, "request_id": options["request_id"],
                "landing_id": landing, "project_id": project, "kind": kind, "status": "queued", "phase": "queued",
                "started_at": now(), "updated_at": now(), "fingerprint": fingerprint, "input": options,
                "reference_digests": reference_digests, "jobs": [], "result": None, "error": None,
                "expected_sha256": options["base_sha256"], "baseline_assets": detail["assets"], "timings": {}})
            self.references[identifier] = references
            self._schedule(identifier)
            return self.public(value)

    def _schedule(self, identifier):
        if identifier in self.running:
            return
        self.running.add(identifier)
        self.executor.submit(self.execute, identifier)

    def retry(self, project, landing, identifier, request):
        from .studio_manual_agent import screenshot_artifacts
        from .image_reference import decode_reference
        if set(request) - {"screenshots"}:
            raise ValueError("Retry only accepts temporary screenshot references")
        references = [decode_reference(value) for value in request.get("screenshots", [])]
        screenshot_artifacts(references)
        with self.lock:
            self.get(project, landing, identifier)
            value = self.store.get(identifier)
            if value["status"] in ACTIVE or value["status"] == "completed":
                return self.public(value)
            if value.get("error", {}).get("retryable") is False:
                raise ValueError("Correct the request or reload the Landing before starting a new operation")
            if value["reference_digests"] != [hashlib.sha256(data).hexdigest() for data in references]:
                raise ValueError("Reattach the original screenshots to retry this operation")
            self.assert_idle(landing)
            current = self.service.detail(project, landing)
            recovered_slots = set()
            # Reconcile a committed image whose final progress event was lost.
            for job in value["jobs"]:
                history = self.service._workspace(landing)._history(job["slot"])
                recovered = next((item for item in history if item.get("source", {}).get("landing_operation_id") == identifier), None)
                if recovered:
                    if job["status"] != "completed":
                        recovered_slots.add(job["slot"])
                    job.update(status="completed", sha256=recovered["sha256"])
            if current["state_sha256"] != value["expected_sha256"]:
                original = value.get("result") or value["input"]
                if current["configuration"] != original["configuration"] or current["content"] != original["content"]:
                    raise RuntimeError("Landing changed; review its state before starting a new request")
                expected_selected = {asset["slot"]: asset["sha256"] for asset in value["baseline_assets"]}
                expected_selected.update({job["slot"]: job["sha256"] for job in value["jobs"] if job["status"] == "completed"})
                if any(asset["sha256"] != expected_selected.get(asset["slot"]) for asset in current["assets"]):
                    raise RuntimeError("Landing images changed; review the current selection before retrying")
                if value.get("configured") and not recovered_slots:
                    raise RuntimeError("Landing changed; review its state before starting a new request")
                if not value.get("configured"):
                    if current["assets"] != value["baseline_assets"]:
                        raise RuntimeError("Landing images changed before this operation could apply its settings")
                    value.update(configured=True, configured_sha256=current["state_sha256"])
                value["expected_sha256"] = current["state_sha256"]
            for job in value["jobs"]:
                if job["status"] != "completed":
                    # A known provider failure may receive a fresh attempt. Uncertain work reuses its key.
                    provider = self.service._workspace(landing).image_provider
                    outcome = None
                    if job.get("provider_request_id") and hasattr(provider, "operation_status"):
                        outcome = provider.operation_status(job["provider_request_id"])
                    if outcome in {"failed", "cancelled"} or (outcome is None and (job.get("error") or {}).get("category") == "provider"):
                        job["attempt"] += 1
                    job.update(status="queued", error=None)
            value.update(status="queued", phase="queued", error=None)
            value = self._save(value)
            self.references[identifier] = references
            self._schedule(identifier)
            return self.public(value)

    def recover_interrupted(self):
        with self.lock:
            for value in self.store.list(active=True):
                for job in value["jobs"]:
                    if job["status"] != "completed":
                        job["status"] = "interrupted"
                value.update(status="interrupted", phase="interrupted",
                    error={"phase": value["phase"], "category": "interrupted", "code": "WorkerRestarted", "retryable": True})
                self._save(value)

    def execute(self, identifier):
        self.local.owned = True
        started = time.monotonic()
        try:
            admitted = self.store.get(identifier)
            queue_ms = max(0, round((datetime.now(timezone.utc)-datetime.fromisoformat(admitted["updated_at"])).total_seconds()*1000))
            value = self._update(identifier, status="running", phase="interpreting", timings={**admitted["timings"], "queue_ms": queue_ms})
            options = value["input"]
            project, landing = value["project_id"], value["landing_id"]
            references = self.references.get(identifier, [])
            if value["result"] is None:
                before = time.monotonic()
                if value["kind"] == "agent":
                    result = self.service.manual_agent_edit(project, landing, **options, screenshots=references)
                else:
                    result = {"configuration": options["configuration"], "content": options["content"],
                              "image_actions": [{"slot": options["slot"], "visual_direction": options["visual_direction"],
                                "enhance_current": options.get("enhance_current", False), "reference_index": 1 if references else 0}],
                              "changed_paths": [], "reply": "", "request_id": options["request_id"], "base_sha256": options["base_sha256"]}
                jobs = [{"slot": action["slot"], "status": "queued", "attempt": 1, "error": None} for action in result["image_actions"]]
                value = self._update(identifier, result=result, jobs=jobs, timings={**value["timings"], "interpretation_ms": round((time.monotonic()-before)*1000)})
            result = value["result"]
            if result["image_actions"]:
                if not value.get("configured"):
                    self._update(identifier, phase="applying")
                    saved = self.service.mutate(project, landing, "save_configuration", base_sha256=value["expected_sha256"],
                                                configuration=result["configuration"], content=result["content"])
                    value = self._update(identifier, configured=True, configured_sha256=saved["state_sha256"], expected_sha256=saved["state_sha256"])
                self._update(identifier, phase="images")
                capacity = self.concurrency
                provider = self.service._workspace(landing).image_provider
                if capacity > 1 and hasattr(provider, "bridge_url"):
                    capabilities = provider._request("GET", f"{provider.bridge_url}/capabilities").json()
                    capacity = min(capacity, max(1, int(capabilities.get("media_concurrency", 1))))
                with ThreadPoolExecutor(max_workers=capacity, thread_name_prefix="landing-image") as pool:
                    futures = [pool.submit(self._image, identifier, action, references) for action in result["image_actions"]
                               if next(job for job in value["jobs"] if job["slot"] == action["slot"])["status"] != "completed"]
                    for future in as_completed(futures):
                        future.result()
            value = self.store.get(identifier)
            failed = next((job for job in value["jobs"] if job["status"] != "completed"), None)
            timings = {**value["timings"], "execution_ms": round((time.monotonic()-started)*1000)}
            self._update(identifier, status="failed" if failed else "completed", phase="failed" if failed else "completed",
                         error=failed["error"] if failed else None, timings=timings)
        except Exception as error:
            value = self.store.get(identifier)
            self._update(identifier, status="failed", error=failure(error, value["phase"]), phase="failed")
        finally:
            self.local.owned = False
            with self.lock:
                self.running.discard(identifier)
                # A terminal status can be retried before this worker unwinds.
                if self.store.get(identifier)["status"] == "queued":
                    self._schedule(identifier)
                else:
                    self.references.pop(identifier, None)

    def _job(self, identifier, slot, **changes):
        with self.lock:
            value = self.store.get(identifier)
            job = next(job for job in value["jobs"] if job["slot"] == slot)
            job.update(changes)
            return self._save(value)

    def _image(self, identifier, action, references):
        queued = time.monotonic()
        with self.image_capacity:
            self._job(identifier, action["slot"], queue_ms=round((time.monotonic()-queued)*1000))
            self._generate_image(identifier, action, references)

    def _generate_image(self, identifier, action, references):
        slot = action["slot"]
        started = time.monotonic()
        try:
            with self.lock:
                value = self.store.get(identifier)
                workspace = self.service._workspace(value["landing_id"])
                job = next(job for job in value["jobs"] if job["slot"] == slot)
                options, result = value["input"], value["result"]
                reference = references[action["reference_index"]-1] if action["reference_index"] else None
                if action["enhance_current"]:
                    # Freeze each slot's source at first admission; siblings never replace it.
                    source = job.get("source_sha256") or workspace._selected(slot)
                    if not source:
                        raise ValueError("Select a Landing image before enhancement")
                    reference = (workspace.assets / f"{source}.png").read_bytes()
                    self._job(identifier, slot, source_sha256=source)
                instruction = ({"origin": "agent", "owner_instruction": result["owner_instruction"]} if result.get("owner_instruction") else options.get("instruction_context"))
                context = job.get("image_context") or self.service._image_context(self.service.authority.get_page(value["landing_id"]), slot,
                    action["visual_direction"], result["configuration"], base_sha256=value.get("configured_sha256", options["base_sha256"]),
                    enhance_current=action["enhance_current"], reference_image=reference if action["reference_index"] else None,
                    instruction=instruction, changed_image_settings=options.get("changed_image_settings", []))
                self._job(identifier, slot, status="generating", started_at=now(), image_context=context)
            provider_queued = time.monotonic()
            generation_started = None
            def progress(state):
                nonlocal generation_started
                # Provider completion is not committed-image completion.
                stage = "preparing" if state["stage"] == "completed" else state["stage"]
                if stage == "generating" and generation_started is None:
                    generation_started = time.monotonic()
                    self._job(identifier, slot, provider_queue_ms=round((generation_started-provider_queued)*1000))
                self._job(identifier, slot, status=stage, provider_request_id=state["provider_request_id"])
            generated = generate_image(workspace.image_provider, compile_image_prompt(context), reference_image=reference,
                uploaded_reference=bool(action["reference_index"]), output_spec=context.get("output_spec"),
                operation_key=f"{identifier}:{slot}:{job['attempt']}", progress=progress)
            generated_at = time.monotonic()
            self._job(identifier, slot, status="preparing", generation_ms=round((generated_at-(generation_started or started))*1000))
            if slot == "walkthrough_visual" and context.get("output_spec", {}).get("background") == "transparent":
                from .landing_image_preparation import prepare_mockup
                raw = bytes(generated["bytes"])
                prepared, preparation = prepare_mockup(raw)
                generated = {**generated, "bytes": prepared, "raw_bytes": raw,
                    "source": {**generated.get("source", {}), "preparation": preparation}}
            generated = {**generated, "delivery": prepare(bytes(generated["bytes"]), slot),
                         "source": {**generated.get("source", {}), "landing_operation_id": identifier}}
            prepared_at = time.monotonic()
            self._job(identifier, slot, preparation_ms=round((prepared_at-generated_at)*1000))
            with self.lock:
                value = self.store.get(identifier)
                saved = workspace.commit_prepared_visual(base_sha256=value["expected_sha256"], slot=slot,
                    visual_direction=action["visual_direction"], generated=generated, image_context=context)
                self.service._synchronize_workspace(value["landing_id"], workspace)
                self.service.authority.update_page(value["landing_id"], state_sha256=saved["state_sha256"])
                self.service._record_generation(landing_id=value["landing_id"], stage=slot, status="completed",
                    input_sha256=sha256_json(context), output_sha256=saved["state_sha256"], prompt_version=IMAGE_POLICY_VERSION,
                    invocation={**image_provenance(context), "operation_id": identifier, "elapsed_ms": round((time.monotonic()-started)*1000)})
                self._update(identifier, expected_sha256=saved["state_sha256"])
                self._job(identifier, slot, status="completed", sha256=hashlib.sha256(bytes(generated["bytes"])).hexdigest(),
                          persistence_ms=round((time.monotonic()-prepared_at)*1000),
                          elapsed_ms=round((time.monotonic()-started)*1000))
        except Exception as error:
            self._job(identifier, slot, status="failed", error=failure(error, slot), elapsed_ms=round((time.monotonic()-started)*1000))
            if "context" in locals():
                self.service._record_generation(landing_id=value["landing_id"], stage=slot, status="failed",
                    input_sha256=sha256_json(context), output_sha256=None, prompt_version=IMAGE_POLICY_VERSION,
                    invocation={"operation_id": identifier}, error=error)

    def close(self):
        self.executor.shutdown(wait=False, cancel_futures=True)
