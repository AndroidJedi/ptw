"""Private, global Templates workflow; no Project authority or code execution."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
from io import BytesIO
import re
import threading
import time
from typing import Any, Mapping
from uuid import UUID, uuid4

from . import template_agent as agent
from .image_reference import decode_reference
from .template_components import canonical, definition, normalize_document, seed, sha
from .template_previews import builtins, render_builtin, render_designs, geometry
from .template_registry import TemplateRegistry
from .template_store import TemplateConflict, TemplateStore

ACTIVE = {"queued", "analyzing", "composing", "rendering", "comparing"}
TERMINAL = {"accepted", "rejected"}
MAX_ITERATIONS = 4
MAX_TOTAL_ITERATIONS = 12
MAX_CALLS = 32


class TemplateBudgetReached(RuntimeError):
    """Pause at a durable phase boundary before admitting more inference."""


def _safe_failure(error: Exception, *, phase: str, provider: Any) -> dict[str, Any]:
    """Return only bounded, non-sensitive diagnostics suitable for a run record."""

    attempts = [item for item in getattr(error, "attempts", []) if isinstance(item, Mapping)]
    last = attempts[-1] if attempts else {}
    error_types = {str(item.get("error_type", "")) for item in attempts}
    if isinstance(error, TimeoutError) or error_types & {"TimeoutExpired", "TimeoutError"}:
        category = "timeout"
    elif "Cancelled" in type(error).__name__ or any("Cancelled" in value for value in error_types):
        category = "cancelled"
    elif isinstance(error, (ValueError, TypeError)) or error_types & {
        "JSONDecodeError", "TypeError", "ValueError",
    }:
        category = "validation"
    else:
        category = "provider"
    validation_error = str(last.get("error_message", "")) if category == "validation" else ""
    if not validation_error and category == "validation":
        validation_error = str(error)
    validation_error = " ".join(validation_error.split())[:240]
    validation_error = re.sub(
        r"(?i)(token|secret|credential|password)\s*[:=]\s*\S+",
        r"\1=[redacted]", validation_error,
    )
    validation_error = re.sub(r"(?:[A-Za-z]:\\|/)[^\s,;]+", "[path omitted]", validation_error)
    return {
        "phase": phase if phase in {"analyze", "compose", "render", "compare", "adjust"} else "unknown",
        "category": category,
        "model": str(last.get("model") or getattr(provider, "model", None) or "codex-cli-default")[:80],
        "reasoning_effort": agent.REASONING_EFFORT,
        "attempt_count": max(1, len(attempts)),
        "validation_error": validation_error,
    }


def uuid(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("Request ID must be a UUID")
    return str(UUID(value))


def reference_key(value: Mapping) -> str:
    if set(value) != {"surface", "template_id", "template_version", "template_sha256"} or value["surface"] not in {"post", "landing"} or not re.fullmatch(r"[a-z][a-z0-9_]{1,63}", str(value["template_id"])) or type(value["template_version"]) is not int or value["template_version"] < 1 or not re.fullmatch(r"[0-9a-f]{64}", str(value["template_sha256"])):
        raise ValueError("Exact template reference is invalid")
    return f"{value['surface']}:{value['template_id']}:{value['template_version']}"


class TemporaryReferences:
    def __init__(self):
        self._items: dict[str, tuple[float, bytes]] = {}
        self._timers: dict[str, threading.Timer] = {}
        self._lock = threading.Lock()

    def _expire(self):
        now = time.monotonic()
        self._items = {key: value for key, value in self._items.items() if now - value[0] < 600}

    def _expire_one(self, identifier: str, created: float):
        with self._lock:
            if self._items.get(identifier, (None,))[0] != created:
                return
            self._items.pop(identifier, None)
            self._timers.pop(identifier, None)

    def upload(self, request: Mapping) -> dict:
        if set(request) != {"request_id", "image"}:
            raise ValueError("Reference upload fields are invalid")
        identifier = uuid(request["request_id"])
        data = decode_reference(request["image"])
        with self._lock:
            self._expire()
            existing = self._items.get(identifier)
            if existing and existing[1] != data:
                raise TemplateConflict("Reference request ID was reused with different pixels")
            if not existing and (len(self._items) >= 4 or sum(len(v[1]) for v in self._items.values()) + len(data) > 24 * 1024 * 1024):
                raise TemplateConflict("Temporary reference capacity reached; remove an unused upload")
            self._items[identifier] = (time.monotonic(), data)
            if identifier in self._timers:
                self._timers[identifier].cancel()
            timer = threading.Timer(600, self._expire_one, args=(identifier, self._items[identifier][0]))
            timer.daemon = True
            self._timers[identifier] = timer
            timer.start()
        from PIL import Image
        with Image.open(BytesIO(data)) as im:
            width, height = im.size
        return {"reference_id": identifier, "sha256": hashlib.sha256(data).hexdigest(), "mime_type": "image/png", "width": width, "height": height, "expires_in_seconds": 600}

    def take(self, identifier: str) -> bytes:
        with self._lock:
            self._expire()
            identifier = uuid(identifier)
            value = self._items.pop(identifier, None)
            timer = self._timers.pop(identifier, None)
            if timer:
                timer.cancel()
        if value is None:
            raise ValueError("Temporary reference expired; attach it again")
        return value[1]

    def discard(self, identifier: str):
        with self._lock:
            identifier = uuid(identifier)
            self._items.pop(identifier, None)
            timer = self._timers.pop(identifier, None)
            if timer:
                timer.cancel()

    def clear(self):
        with self._lock:
            self._items.clear()
            for timer in self._timers.values():
                timer.cancel()
            self._timers.clear()


class TemplateAuthoringService:
    def __init__(self, store: TemplateStore, provider: Any, *, asynchronous=True):
        self.store, self.provider = store, provider
        self.references = TemporaryReferences()
        self.asynchronous = asynchronous
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="template-authoring")
        self._lock = threading.Lock()
        self._active: set[str] = set()
        self._stopping = threading.Event()
        self._preview_lock = threading.Lock()

    def close(self):
        self._stopping.set()
        self.references.clear()
        self._executor.shutdown(wait=False, cancel_futures=True)

    def recover_interrupted(self):
        # Never replay provider work or a mutation after a process restart.
        self.references.clear()
        for run in self.store.list("run", 200):
            if run["status"] in ACTIVE:
                self._update(run, status="interrupted", error="Run interrupted. Resume from the last saved analysis and composition.")

    def _update(self, run: dict, **changes) -> dict:
        with self.store.transaction() as tx:
            return tx.append("run", run["run_id"], {**run, **changes}, expected=run["state_sha256"])

    def ensure_builtins(self) -> list[dict]:
        items = []
        with self._preview_lock:
            for builtin in builtins():
                key = reference_key({k: builtin[k] for k in ("surface", "template_id", "template_version", "template_sha256")})
                with self.store.transaction() as tx:
                    saved = tx.get("builtin", key)
                if saved is None:
                    try:
                        previews = {}
                        for viewport in (["desktop", "mobile"] if builtin["surface"] == "landing" else ["desktop"]):
                            result = render_builtin(builtin, mobile=viewport == "mobile")
                            observations, failures = geometry(result)
                            with self.store.transaction() as tx:
                                digest = tx.media(result["bytes"])
                            previews[viewport] = {"sha256": digest, "definition_sha256": builtin["template_sha256"], "geometry": observations, "failures": failures}
                        with self.store.transaction() as tx:
                            saved = tx.get("builtin", key) or tx.append("builtin", key, {**builtin, "previews": previews, "preview_status": "ready"})
                    except (RuntimeError, TimeoutError, OSError) as error:
                        saved = {**builtin, "previews": {}, "preview_status": "failed", "preview_error": "Authoritative preview unavailable. Retry after the renderer is ready."}
                items.append(saved)
        return items

    def gallery(self, surface: str | None = None) -> dict:
        if surface not in {None, "post", "landing"}:
            raise ValueError("Template surface is invalid")
        items = {f"{v['surface']}:{v['template_id']}": v for v in self.ensure_builtins()}
        for v in self.store.list("version", 200):
            key = f"{v['surface']}:{v['template_id']}"
            if key not in items or items[key]["template_version"] < v["template_version"]:
                items[key] = v
        summaries = []
        for v in items.values():
            if surface is not None and v["surface"] != surface:
                continue
            summaries.append({k: deepcopy(v[k]) for k in ("surface", "template_id", "template_version", "template_sha256", "name", "description", "builtin", "status", "preview_status", "previews")})
        return {"items": summaries, "limit": 200}

    def read(self, reference: Mapping) -> dict:
        key = reference_key(reference)
        try:
            record = self.store.get("version", key)
        except KeyError:
            self.ensure_builtins()
            record = self.store.get("builtin", key)
        if record["template_sha256"] != reference["template_sha256"]:
            raise TemplateConflict("Template digest does not match its immutable version")
        return record

    def registry(self, surface: str) -> TemplateRegistry:
        from .post_templates import POST_TEMPLATE_REGISTRY
        from .landing_templates import LANDING_TEMPLATE_REGISTRY
        registry = POST_TEMPLATE_REGISTRY if surface == "post" else LANDING_TEMPLATE_REGISTRY
        return TemplateRegistry(surface, (*registry.all(), *(definition(r) for r in self.store.list("version", 200) if r["surface"] == surface)),
            version_loader=lambda reference: definition(self.read({"surface": surface, **reference})))

    def post_registry(self) -> TemplateRegistry:
        from .post_templates import POST_TEMPLATE_REGISTRY
        from .post_template_runtime import post_definition
        return TemplateRegistry("post", (*POST_TEMPLATE_REGISTRY.all(),
            *(post_definition(r) for r in self.store.list("version", 200) if r["surface"] == "post")),
            version_loader=lambda reference: post_definition(self.read({"surface": "post", **reference})))

    def resolve_post_reference(self, reference: Mapping) -> dict:
        if set(reference) != {"template_id", "template_version", "template_sha256"}:
            raise ValueError("Post reference must contain only exact template identity")
        item = self.read({"surface": "post", **reference})
        return {"identity": {k: item[k] for k in ("template_id", "template_version", "template_sha256")},
                "description": item["description"], "canvas": item.get("canvas"),
                "component_roles": item.get("component_roles", [{"type": c["type"], "role": c["role"]} for c in item.get("document", {}).get("components", [])])}

    def _reconcile(self, tx, request_id, digest):
        receipt = tx.get("request", request_id)
        if receipt:
            if receipt["request_sha256"] != digest:
                raise TemplateConflict("Request ID was reused with different input")
            return tx.get("run", receipt["run_id"])
        return None

    def start(self, request: Mapping) -> dict:
        if not {"request_id", "scope", "instruction"} <= set(request) or set(request) - {"request_id", "scope", "instruction", "reference_id", "source", "post_reference"}:
            raise ValueError("Template creation fields are invalid")
        request_id = uuid(request["request_id"])
        digest = sha(dict(request))
        with self.store.transaction() as tx:
            old = self._reconcile(tx, request_id, digest)
        if old:
            return old
        scope = request["scope"]
        if scope not in {"post", "landing", "combined"}:
            raise ValueError("Choose Post, Landing, or coordinated Post + Landing")
        instruction = request["instruction"]
        if not isinstance(instruction, str) or len(instruction.encode()) > 3000:
            raise ValueError("Template instruction exceeds 3000 UTF-8 bytes")
        if not instruction.strip() and not request.get("reference_id"):
            raise ValueError("Provide an instruction, a reference image, or both")
        surfaces = ["post", "landing"] if scope == "combined" else [scope]
        source = self.read(request["source"]) if request.get("source") else None
        if source and (scope == "combined" or source["surface"] != scope):
            raise ValueError("Edit one exact template on its own surface")
        post_reference = request.get("post_reference", source.get("post_reference") if source else None)
        if post_reference:
            if scope != "landing":
                raise ValueError("An external Post template reference applies only to Landing creation")
            self.resolve_post_reference(post_reference)
        documents = {s: deepcopy(source["document"]) if source and not source["builtin"] else seed(s) for s in surfaces}
        base = {k: source[k] for k in ("surface", "template_id", "template_version", "template_sha256")} if source else None
        template_ids = {s: source["template_id"] if source and not source["builtin"] else "design_" + uuid4().hex[:20] for s in surfaces}
        run = {"run_id": request_id, "scope": scope, "instruction": instruction.strip(), "status": "queued", "phase": "analyze",
            "documents": documents, "template_ids": template_ids, "source": base, "post_reference": post_reference,
            "post_design": self.resolve_post_reference(post_reference) if post_reference else None,
            "reference": None, "analysis": None, "previews": {}, "comparison": None, "capability_gap": None,
            "iterations": 0, "calls": 0, "invocations": [], "error": None, "failure": None,
            "accepted_versions": []}
        agent.preflight("analyze", run)  # Reject oversized JSON before reserving a provider job.
        data = None
        if request.get("reference_id"):
            data = self.references.take(request["reference_id"])
        elif source and source["builtin"]:
            with self.store.transaction() as tx:
                data = tx.read_media(source["previews"]["desktop"]["sha256"])
        if data:
            run["reference"] = {"sha256": hashlib.sha256(data).hexdigest(), "mime_type": "image/png", "byte_count": len(data)}
        with self.store.transaction() as tx:
            old = self._reconcile(tx, request_id, digest)
            if old:
                return old
            if any(r["status"] in ACTIVE for r in tx.list("run", 200)):
                raise TemplateConflict("A template creation run is already active")
            run = tx.append("run", request_id, run)
            tx.append("request", request_id, {"run_id": request_id, "request_sha256": digest})
        self._schedule(run["run_id"], data)
        return self.store.get("run", request_id)

    def _schedule(self, run_id: str, data: bytes | None):
        with self._lock:
            if run_id in self._active:
                return
            self._active.add(run_id)
        if self.asynchronous:
            self._executor.submit(self.execute, run_id, data)
        else:
            self.execute(run_id, data)

    def execute(self, run_id: str, data: bytes | None = None):
        run = self.store.get("run", run_id)
        started = time.monotonic()
        def invoke(phase, images):
            nonlocal run
            if time.monotonic() - started > 900:
                raise TemplateBudgetReached()
            if run["calls"] >= MAX_CALLS:
                raise ValueError("Template provider-call budget exhausted")
            measurement = agent.preflight(phase, run)
            pending = {"phase": phase, "contract_bytes": measurement, "response_bytes": 0,
                       "attempt_count": 1, "status": "started",
                       "model": str(getattr(self.provider, "model", None) or "codex-cli-default")[:80],
                       "reasoning_effort": agent.REASONING_EFFORT}
            run = self._update(run, calls=run["calls"] + 1, invocations=[*run["invocations"], pending])
            response, invocation = agent.call(self.provider, phase, run, images, cancel_event=self._stopping)
            run = self._update(run, invocations=[*run["invocations"][:-1], {**invocation, "status": "completed"}])
            return response

        def saved_renders() -> dict[str, dict] | None:
            expected = {
                **({"post:desktop": sha(run["documents"]["post"])} if "post" in run["documents"] else {}),
                **({
                    "landing:desktop": sha(run["documents"]["landing"]),
                    "landing:mobile": sha(run["documents"]["landing"]),
                } if "landing" in run["documents"] else {}),
            }
            previews = run.get("previews") or {}
            if set(previews) != set(expected) or any(
                previews[key].get("definition_sha256") != digest
                or not re.fullmatch(r"[0-9a-f]{64}", str(previews[key].get("sha256", "")))
                for key, digest in expected.items()
            ):
                return None
            with self.store.transaction() as tx:
                return {
                    key: {**previews[key], "bytes": tx.read_media(previews[key]["sha256"])}
                    for key in sorted(expected)
                }
        try:
            if run["analysis"] is None:
                if run["reference"] and data is None:
                    raise ValueError("Reattach the reference to finish its analysis")
                run = self._update(run, status="analyzing", phase="analyze")
                analysis = invoke("analyze", [("reference", data)] if data else [])
                run = self._update(run, analysis=analysis, phase="compose")
            if run["phase"] == "adjust":
                run = self._update(run, documents=agent.apply_edits(run["documents"], run["comparison"]["edits"]), phase="render")
            if run["phase"] == "compose":
                run = self._update(run, status="composing")
                response = invoke("compose", [])
                documents = agent.apply_edits(run["documents"], response["edits"])
                run = self._update(run, documents=documents, phase="render")
            for iteration in range(MAX_ITERATIONS):
                if self._stopping.is_set():
                    run = self._update(run, status="interrupted", error="Worker stopped; resume from saved state")
                    return
                if run["iterations"] >= MAX_TOTAL_ITERATIONS or run["calls"] >= MAX_CALLS or time.monotonic() - started > 900:
                    run = self._update(run, status="paused", error="Bounded iteration budget reached; inspect the saved result")
                    return
                renders = saved_renders() if run["phase"] == "compare" else None
                if renders is None:
                    run = self._update(run, status="rendering", phase="render")
                    renders = render_designs(run["documents"])
                    previews = {}
                    with self.store.transaction() as tx:
                        for key, preview in renders.items():
                            digest = tx.media(preview["bytes"])
                            previews[key] = {k: v for k, v in preview.items() if k != "bytes"}
                            regions = run["analysis"]["regions"]
                            previews[key]["reference_geometry_deltas"] = [{"role": observed["role"], "id": observed["id"],
                                "delta": [round(a - b, 2) for a, b in zip(observed["box"], target["box"])]}
                                for observed in preview["geometry"] for target in regions if target["role"] == observed["role"]][:24]
                            assert digest == previews[key]["sha256"]
                    run = self._update(run, previews=previews, status="comparing", phase="compare", iterations=run["iterations"] + 1)
                else:
                    previews = run["previews"]
                    run = self._update(run, status="comparing", phase="compare")
                images = ([("reference", data)] if data else []) + [(key, value["bytes"]) for key, value in renders.items()]
                response = invoke("compare", images)
                run = self._update(run, comparison=response)
                failures = [f for p in previews.values() for f in p["failures"]]
                meaningful = [d for d in response["differences"] if d["severity"] == "meaningful"]
                if response["capability_gap"]:
                    changes = {"status": "capability_gap", "capability_gap": response["capability_gap"]}
                    if response["edits"]:
                        documents = agent.apply_edits(run["documents"], response["edits"])
                        if sha(documents) != sha(run["documents"]):
                            changes.update(documents=documents, phase="render")
                    run = self._update(run, **changes)
                    return
                if response["complete"] and not meaningful and not failures and not response["edits"]:
                    run = self._update(run, status="proposed", error=None, failure=None)
                    return
                if not response["edits"]:
                    run = self._update(run, status="paused", error="Comparison found unresolved differences. Add a correction and resume.")
                    return
                documents = agent.apply_edits(run["documents"], response["edits"])
                if sha(documents) == sha(run["documents"]):
                    run = self._update(run, status="paused", error="Comparison made no progress. Add a focused correction.")
                    return
                if iteration == MAX_ITERATIONS - 1:
                    run = self._update(run, phase="adjust")
                else:
                    run = self._update(run, documents=documents, phase="render")
            run = self._update(run, status="paused", error="Iteration limit reached; resume the saved composition")
        except TemplateBudgetReached:
            self._update(run, status="paused", error="Segment time budget reached; resume from the saved phase")
        except Exception as error:
            failure = _safe_failure(error, phase=run.get("phase", "unknown"), provider=self.provider)
            # Persist no subprocess stderr, provider output or raw reference bytes.
            message = "Template Agent timed out; resume from saved state" if failure["category"] == "timeout" else "Template Agent could not complete this step. Saved state is available for retry."
            try:
                self._update(run, status="failed", error=message, failure=failure,
                    invocations=[*run["invocations"][:-1], {**run["invocations"][-1], "status": "failed",
                        "attempt_count": failure["attempt_count"]}]
                    if run["invocations"] and run["invocations"][-1].get("status") == "started"
                    else run["invocations"])
            except TemplateConflict:
                pass
        finally:
            data = None
            with self._lock:
                self._active.discard(run_id)

    def resume(self, run_id: str, request: Mapping) -> dict:
        if not {"request_id", "base_sha256", "instruction"} <= set(request) or set(request) - {"request_id", "base_sha256", "instruction", "reference_id"}:
            raise ValueError("Resume fields are invalid")
        request_id, run_id = uuid(request["request_id"]), uuid(run_id)
        digest = sha({"run_id": run_id, "action": "resume", **request})
        with self.store.transaction() as tx:
            old = self._reconcile(tx, request_id, digest)
            if old:
                return old
        run = self.store.get("run", run_id)
        if run["state_sha256"] != request["base_sha256"]:
            raise TemplateConflict("Template run changed; refresh before resuming")
        if run["status"] in ACTIVE | TERMINAL:
            raise TemplateConflict("This template run cannot be resumed")
        if run["iterations"] >= MAX_TOTAL_ITERATIONS or run["calls"] >= MAX_CALLS:
            raise TemplateConflict("This run exhausted its total budget; create a derivative from an accepted version")
        instruction = request["instruction"]
        if not isinstance(instruction, str) or len(instruction.encode()) > 3000:
            raise ValueError("Template correction exceeds 3000 UTF-8 bytes")
        if run["status"] == "capability_gap" and not instruction.strip():
            from .template_extensions import validated_capability
            if not validated_capability(run["capability_gap"]["capability"]):
                raise TemplateConflict("Capability requires reviewed source tests and visual validation before resuming")
        if run["status"] == "capability_gap" and instruction.strip() and (run.get("comparison") or {}).get("edits"):
            # Older run revisions may have paused before persisting otherwise-valid
            # solvable edits. Fold them into the same CAS-protected resume revision.
            run = {**run, "documents": agent.apply_edits(run["documents"], run["comparison"]["edits"])}
        data = self.references.take(request["reference_id"]) if request.get("reference_id") else None
        if data:
            reference = {"sha256": hashlib.sha256(data).hexdigest(), "mime_type": "image/png", "byte_count": len(data)}
            if reference != run["reference"]:
                run = {**run, "analysis": None}
            run = {**run, "reference": reference}
        if run["reference"] and run["analysis"] is None and data is None:
            raise ValueError("Reattach the temporary reference; raw pixels are not retained after interruption")
        updated = {**run, "instruction": instruction.strip() or run["instruction"], "status": "queued", "error": None,
                   "failure": None, "capability_gap": None,
                   "phase": "analyze" if run["analysis"] is None else ("compose" if instruction.strip() else run["phase"])}
        agent.preflight("analyze" if updated["analysis"] is None else "compose", updated)
        with self.store.transaction() as tx:
            old = self._reconcile(tx, request_id, digest)
            if old:
                return old
            if any(r["status"] in ACTIVE for r in tx.list("run", 200)):
                raise TemplateConflict("A template creation run is already active")
            saved = tx.append("run", run_id, updated, expected=request["base_sha256"])
            tx.append("request", request_id, {"run_id": run_id, "request_sha256": digest})
        self._schedule(run_id, data)
        return self.store.get("run", run_id)

    def decide(self, run_id: str, request: Mapping) -> dict:
        if set(request) != {"request_id", "base_sha256", "decision"} or request["decision"] not in {"accept", "reject"}:
            raise ValueError("Template decision fields are invalid")
        request_id, run_id = uuid(request["request_id"]), uuid(run_id)
        digest = sha({"run_id": run_id, "action": "decide", **request})
        with self.store.transaction() as tx:
            old = self._reconcile(tx, request_id, digest)
            if old:
                return old
            run = tx.get("run", run_id)
            if run is None:
                raise KeyError(run_id)
            if run["state_sha256"] != request["base_sha256"] or run["status"] in ACTIVE | TERMINAL:
                raise TemplateConflict("Template run changed or cannot be decided")
            accepted = []
            if request["decision"] == "accept":
                if run["status"] != "proposed" or not run["comparison"] or run["iterations"] < 1:
                    raise TemplateConflict("Accept requires a converged, compared proposal")
                for surface in ("post", "landing"):
                    if surface not in run["documents"]:
                        continue
                    doc = normalize_document(run["documents"][surface])
                    previews = {key.split(":")[1]: value for key, value in run["previews"].items() if key.startswith(surface + ":")}
                    if not previews or any(p["definition_sha256"] != sha(doc) or p["failures"] for p in previews.values()):
                        raise TemplateConflict("Preview does not match the proposed definition")
                    template_id = run["template_ids"][surface]
                    previous = sorted([v for v in tx.list("version", 200) if v["surface"] == surface and v["template_id"] == template_id], key=lambda v: v["template_version"])
                    if previous and (run["source"] is None or previous[-1]["template_sha256"] != run["source"]["template_sha256"]):
                        raise TemplateConflict("Template current version changed; edit the current version")
                    version = previous[-1]["template_version"] + 1 if previous else 1
                    post_reference = None
                    if surface == "landing":
                        post_reference = ({k: accepted[0][k] for k in ("template_id", "template_version", "template_sha256")} if accepted else run["post_reference"])
                    identity_document = {"surface": surface, "template_id": template_id, "template_version": version,
                        "document": doc, "post_reference": post_reference, "renderer_key": "studio.declarative.pillow.v1"}
                    template_sha = sha(identity_document)
                    previews = {k: {**p, "template_sha256": template_sha, "binding_sha256": sha({"template_sha256": template_sha, "preview_sha256": p["sha256"], "viewport": k})} for k, p in previews.items()}
                    record = {**identity_document, "template_sha256": template_sha, "name": doc["name"], "description": doc["description"],
                        "canvas": doc["canvas"], "component_roles": [{"type": c["type"], "role": c["role"]} for c in doc["components"]],
                        "builtin": False, "status": "registered", "preview_status": "ready", "previews": previews,
                        "capabilities": definition({**identity_document, "template_sha256": template_sha}).capabilities.to_dict(),
                        "provenance": {"run_id": run_id, "source": run["source"], "analysis_sha256": sha(run["analysis"]), "reference_sha256": (run["reference"] or {}).get("sha256")}}
                    tx.append("version", f"{surface}:{template_id}:{version}", record)
                    accepted.append({"surface": surface, "template_id": template_id, "template_version": version, "template_sha256": template_sha})
            saved = tx.append("run", run_id, {**run, "status": "accepted" if accepted else "rejected", "accepted_versions": accepted}, expected=run["state_sha256"])
            tx.append("request", request_id, {"run_id": run_id, "request_sha256": digest})
            return saved

    def preview(self, digest: str) -> bytes:
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("Preview digest is invalid")
        with self.store.transaction() as tx:
            return tx.read_media(digest)
