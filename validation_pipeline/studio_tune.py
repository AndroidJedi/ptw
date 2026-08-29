"""Local-only isolated coding-agent loop for Universal Studio Tune mode."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Response
from fastapi.params import Depends as DependsParameter


TUNE_RUN_SCHEMA = "ptw.studio.tune-run.v1"
TUNE_SERVICE_SCHEMA = "ptw.studio.tune-service.v1"
TUNE_RULE_APPROVAL_SCHEMA = "ptw.studio.tune-rule-approval.v1"
ACTIVE_STATUSES = frozenset({"queued", "running"})
MAX_AGENT_SECONDS = 2_400
MAX_SUMMARY_CHARACTERS = 12_000
MAX_COMMAND_OUTPUT_CHARACTERS = 12_000
PREVIEW_FILENAME = "preview.png"
PREVIEW_SIZE = 1_080
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
SKILL_RULES_PATH = Path("skills/studio-tune-local/references/owner-approved-rules.md")
SKILL_RULES_START = "<!-- PTW-STUDIO-TUNE-RULES-START -->"
SKILL_RULES_END = "<!-- PTW-STUDIO-TUNE-RULES-END -->"
SAFE_ENVIRONMENT_KEYS = frozenset({
    "CODEX_HOME", "HOME", "LANG", "LC_ALL", "LOGNAME", "PATH", "SHELL",
    "SSL_CERT_DIR", "SSL_CERT_FILE", "TERM", "TMPDIR", "USER",
})

# This is also the copy-back security boundary. The agent works in a disposable
# mirror, so writes elsewhere never touch the owner's checkout and fail the run.
TUNE_EXACT_PATHS = frozenset({
    "apps/commander-web/src/styles.css",
    "apps/commander-web/src/types.ts",
    "apps/commander-web/src/views/StudioView.test.tsx",
    "apps/commander-web/src/views/StudioView.tsx",
    "docs/architecture/universal-ad-studio.md",
    "tests/validation_pipeline/test_studio_primitives.py",
    "tests/validation_pipeline/test_studio_workspace.py",
    "validation_pipeline/studio_primitives.py",
    "validation_pipeline/studio_universal.py",
    "validation_pipeline/studio_workspace.py",
})
TUNE_PATH_PREFIXES = (
    "apps/commander-web/src/components/studio/",
    "validation_pipeline/studio_assets/",
    "validation_pipeline/studio_components/",
    "validation_pipeline/studio_templates/",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canonical_sha256(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def _trim_output(value: str, limit: int = MAX_COMMAND_OUTPUT_CHARACTERS) -> str:
    value = value.strip()
    return value if len(value) <= limit else value[-limit:]


def _normalize_text(name: str, value: Any, *, minimum: int, maximum: int) -> str:
    if not isinstance(value, str):
        raise ValueError(f"Tune {name} must be text")
    normalized = value.strip()
    if not minimum <= len(normalized) <= maximum:
        raise ValueError(f"Tune {name} must contain {minimum} to {maximum} characters")
    return normalized


def _normalize_rule(value: Any) -> str:
    rule = _normalize_text("reusable rule", value, minimum=10, maximum=2_000)
    rule = re.sub(r"\s+", " ", rule).strip()
    if "<!--" in rule or "-->" in rule:
        raise ValueError("Tune reusable rule contains reserved Markdown control text")
    return rule


def _is_allowed_path(value: str) -> bool:
    path = value.replace(os.sep, "/")
    return path in TUNE_EXACT_PATHS or any(path.startswith(prefix) for prefix in TUNE_PATH_PREFIXES)


def _preview_metadata(value: bytes) -> dict[str, Any]:
    if len(value) < 24 or value[:8] != PNG_SIGNATURE or value[12:16] != b"IHDR":
        raise ValueError("Studio Tune preview is not a valid PNG")
    width = int.from_bytes(value[16:20], "big")
    height = int.from_bytes(value[20:24], "big")
    if (width, height) != (PREVIEW_SIZE, PREVIEW_SIZE):
        raise ValueError(
            f"Studio Tune preview must be {PREVIEW_SIZE}x{PREVIEW_SIZE}; got {width}x{height}"
        )
    return {
        "mime_type": "image/png",
        "sha256": hashlib.sha256(value).hexdigest(),
        "width": width,
        "height": height,
    }


class StudioTuneService:
    """Run Codex in a mirror, verify its Studio-only diff, then copy it back."""

    def __init__(
        self,
        repository_root: Path | str,
        state_root: Path | str,
        *,
        codex_binary: str | None = None,
        executor: Callable[[Path, str, Path], str] | None = None,
        verifier: Callable[[Path], Sequence[str]] | None = None,
        preview_renderer: Callable[[Path], bytes] | None = None,
    ) -> None:
        self.repository_root = Path(repository_root).resolve()
        self.state_root = Path(state_root).resolve()
        self.runs_root = self.state_root / "runs"
        self.codex_binary = codex_binary or shutil.which("codex") or ""
        self.executor = executor or self._codex_exec
        self.verifier = verifier or self._verify_snapshot
        self.preview_renderer = preview_renderer or self._render_snapshot_preview
        self._lock = threading.RLock()
        self._threads: dict[str, threading.Thread] = {}
        self.runs_root.mkdir(parents=True, exist_ok=True)
        if not (self.repository_root / ".git").exists():
            raise ValueError("Studio Tune repository root must be a Git checkout")
        self._recover_interrupted()

    def _run_path(self, run_id: str) -> Path:
        if not re.fullmatch(r"[0-9a-f-]{36}", str(run_id)):
            raise KeyError(f"Studio Tune run not found: {run_id}")
        return self.runs_root / str(run_id) / "run.json"

    def _preview_path(self, run_id: str) -> Path:
        return self._run_path(run_id).with_name(PREVIEW_FILENAME)

    @staticmethod
    def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(dict(value), ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        )
        temporary.replace(path)

    def _read_run(self, run_id: str) -> dict[str, Any]:
        path = self._run_path(run_id)
        if not path.is_file():
            raise KeyError(f"Studio Tune run not found: {run_id}")
        try:
            value = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"Studio Tune run is unreadable: {run_id}") from error
        if value.get("schema") != TUNE_RUN_SCHEMA or value.get("run_id") != run_id:
            raise ValueError(f"Studio Tune run is invalid: {run_id}")
        return value

    def _write_run(self, value: Mapping[str, Any]) -> dict[str, Any]:
        record = json.loads(json.dumps(dict(value), ensure_ascii=False))
        self._atomic_json(self._run_path(str(record["run_id"])), record)
        return record

    def _update_run(self, run_id: str, **values: Any) -> dict[str, Any]:
        with self._lock:
            current = self._read_run(run_id)
            current.update(values)
            current["updated_at"] = _now()
            return self._write_run(current)

    def _records(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for path in self.runs_root.glob("*/run.json"):
            try:
                value = json.loads(path.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            if value.get("schema") == TUNE_RUN_SCHEMA:
                records.append(value)
        return sorted(records, key=lambda item: str(item.get("created_at", "")), reverse=True)

    def _recover_interrupted(self) -> None:
        for record in self._records():
            if record.get("status") in ACTIVE_STATUSES:
                self._write_run({
                    **record,
                    "status": "failed",
                    "stage": "failed",
                    "error": "The local Tune service restarted before this run completed. Start a new iteration.",
                    "completed_at": _now(),
                    "updated_at": _now(),
                })

    def _unavailable_reason(self) -> str:
        if not self.codex_binary:
            return "Codex CLI is not available on PATH."
        if not (self.repository_root / ".venv" / "bin" / "python").is_file():
            return "The local Python environment is missing; run the Studio setup first."
        if not (self.repository_root / "apps" / "commander-web" / "node_modules").is_dir():
            return "Owner Console dependencies are missing; run npm ci first."
        return ""

    def detail(self) -> dict[str, Any]:
        records = []
        with self._lock:
            for record in self._records()[:10]:
                try:
                    records.append(self._ensure_run_preview(record))
                except (OSError, RuntimeError, ValueError):
                    records.append({**record, "preview": None})
        reason = self._unavailable_reason()
        return {
            "schema": TUNE_SERVICE_SCHEMA,
            "mode": "local_only",
            "available": not reason,
            "unavailable_reason": reason or None,
            "active_run_id": next((
                item["run_id"] for item in records if item.get("status") in ACTIVE_STATUSES
            ), None),
            "allowed_paths": sorted(TUNE_EXACT_PATHS) + [f"{item}*" for item in TUNE_PATH_PREFIXES],
            "runs": records,
        }

    def run_detail(self, run_id: str) -> dict[str, Any]:
        with self._lock:
            record = self._read_run(run_id)
            try:
                return self._ensure_run_preview(record)
            except (OSError, RuntimeError, ValueError):
                return {**record, "preview": None}

    def preview(self, run_id: str) -> tuple[bytes, dict[str, Any]]:
        with self._lock:
            record = self._ensure_run_preview(self._read_run(run_id))
            if record.get("status") != "completed" or not record.get("preview"):
                raise RuntimeError("Studio Tune preview is available only for a completed run")
            value = self._preview_path(run_id).read_bytes()
            metadata = _preview_metadata(value)
            if metadata != record["preview"]:
                raise ValueError("Studio Tune preview metadata does not match its bytes")
            return value, metadata

    def start(self, *, project_idea: Any, implementation: Any, feedback: Any) -> dict[str, Any]:
        project_idea = _normalize_text("project idea", project_idea, minimum=10, maximum=4_000)
        implementation = _normalize_text(
            "desired implementation", implementation, minimum=10, maximum=6_000,
        )
        feedback = _normalize_text("feedback", feedback, minimum=0, maximum=4_000)
        reason = self._unavailable_reason()
        if reason:
            raise RuntimeError(reason)
        with self._lock:
            if any(item.get("status") in ACTIVE_STATUSES for item in self._records()):
                raise RuntimeError("Another Studio Tune run is already active")
            run_id = str(uuid4())
            created_at = _now()
            request_value = {
                "project_idea": project_idea,
                "implementation": implementation,
                "feedback": feedback,
            }
            record = self._write_run({
                "schema": TUNE_RUN_SCHEMA,
                "run_id": run_id,
                "iteration": len(self._records()) + 1,
                "status": "queued",
                "stage": "queued",
                **request_value,
                "request_sha256": _canonical_sha256(request_value),
                "changed_files": [],
                "verification": [],
                "summary": None,
                "error": None,
                "preview": None,
                "approved_rules": [],
                "created_at": created_at,
                "updated_at": created_at,
                "started_at": None,
                "completed_at": None,
            })
            thread = threading.Thread(
                target=self._execute_run, args=(run_id,), daemon=True,
                name=f"studio-tune-{run_id[:8]}",
            )
            self._threads[run_id] = thread
            thread.start()
            return record

    def save_rule(self, run_id: str, *, rule: Any) -> dict[str, Any]:
        """Promote one explicit owner-approved feedback rule into the canonical skill."""

        normalized = _normalize_rule(rule)
        rules_path = self.repository_root / SKILL_RULES_PATH
        with self._lock:
            record = self._read_run(run_id)
            if record.get("status") not in {"completed", "failed"}:
                raise RuntimeError("Finish the current Tune iteration before saving a reusable rule")
            if any(item.get("status") in ACTIVE_STATUSES for item in self._records()):
                raise RuntimeError("Wait for the active Studio Tune run before saving a reusable rule")
            if not rules_path.is_file() or rules_path.is_symlink():
                raise RuntimeError("The canonical Studio Tune rules file is unavailable")

            original = rules_path.read_bytes()
            content = original.decode()
            if content.count(SKILL_RULES_START) != 1 or content.count(SKILL_RULES_END) != 1:
                raise RuntimeError("The canonical Studio Tune rules file has invalid boundaries")
            start = content.index(SKILL_RULES_START) + len(SKILL_RULES_START)
            end = content.index(SKILL_RULES_END)
            if start >= end:
                raise RuntimeError("The canonical Studio Tune rules file has invalid ordering")
            existing_rules = {
                line[2:].strip().casefold(): line[2:].strip()
                for line in content[start:end].splitlines()
                if line.startswith("- ")
            }
            existing = existing_rules.get(normalized.casefold())
            created = existing is None
            if existing is not None:
                normalized = existing
            rule_sha256 = hashlib.sha256(normalized.encode()).hexdigest()
            if created:
                updated = content[:end] + f"- {normalized}\n" + content[end:]
                temporary = rules_path.with_name(rules_path.name + ".studio-tune-rule.tmp")
                temporary.write_text(updated)
                if rules_path.read_bytes() != original:
                    temporary.unlink(missing_ok=True)
                    raise RuntimeError("Studio Tune rules changed while approval was being saved")
                temporary.replace(rules_path)

            approval = {
                "rule": normalized,
                "rule_sha256": rule_sha256,
                "skill_path": SKILL_RULES_PATH.as_posix(),
            }
            approved_rules = list(record.get("approved_rules") or [])
            if not any(item.get("rule_sha256") == rule_sha256 for item in approved_rules):
                approved_rules.append(approval)
                try:
                    self._update_run(run_id, approved_rules=approved_rules)
                except Exception:
                    if created:
                        rollback = rules_path.with_name(rules_path.name + ".studio-tune-rule-rollback.tmp")
                        rollback.write_bytes(original)
                        rollback.replace(rules_path)
                    raise
            return {
                "schema": TUNE_RULE_APPROVAL_SCHEMA,
                "run_id": run_id,
                **approval,
                "created": created,
            }

    def _git(self, root: Path, *arguments: str, timeout: int = 120) -> subprocess.CompletedProcess[str]:
        completed = subprocess.run(
            ["git", "-C", str(root), *arguments], text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, check=False,
        )
        if completed.returncode:
            raise RuntimeError(_trim_output(completed.stdout) or f"git {' '.join(arguments)} failed")
        return completed

    def _copy_repository_snapshot(self, destination: Path) -> None:
        destination.mkdir(parents=True, exist_ok=False)
        completed = subprocess.run(
            [
                "git", "-C", str(self.repository_root), "ls-files", "-co",
                "--exclude-standard", "-z",
            ],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        if completed.returncode:
            raise RuntimeError(_trim_output(completed.stderr.decode(errors="replace")))
        for raw_name in completed.stdout.split(b"\0"):
            if not raw_name:
                continue
            name = raw_name.decode()
            relative = Path(name)
            if relative.is_absolute() or ".." in relative.parts:
                raise RuntimeError("Git returned an unsafe path while preparing Tune mode")
            source, target = self.repository_root / relative, destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if source.is_symlink():
                target.symlink_to(os.readlink(source))
            elif source.is_file():
                shutil.copy2(source, target)
        self._git(destination, "init", "--quiet")
        self._git(destination, "config", "user.name", "PTW Studio Tune")
        self._git(destination, "config", "user.email", "studio-tune@localhost")
        self._git(destination, "add", "--all")
        self._git(destination, "commit", "--quiet", "-m", "Studio Tune input snapshot")

        dependency_links = (
            (self.repository_root / ".venv", destination / ".venv"),
            (
                self.repository_root / "apps" / "commander-web" / "node_modules",
                destination / "apps" / "commander-web" / "node_modules",
            ),
        )
        for source, target in dependency_links:
            if source.exists() and not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.symlink_to(source, target_is_directory=True)
        exclude_path = destination / ".git" / "info" / "exclude"
        with exclude_path.open("a") as exclude:
            exclude.write("\n/.venv\n/apps/commander-web/node_modules\n")

    @staticmethod
    def _prompt(record: Mapping[str, Any]) -> str:
        feedback = str(record["feedback"]) or "No prior feedback; this is the first implementation pass."
        allowed = "\n".join(
            f"- {item}" for item in (
                *sorted(TUNE_EXACT_PATHS), *(f"{prefix}*" for prefix in TUNE_PATH_PREFIXES),
            )
        )
        return f"""You are implementing one owner-requested Universal Studio experiment in PTW Tune mode.

This is an isolated disposable snapshot. The host already synchronized and captured the owner's
current working tree. Do not fetch, pull, deploy, publish, contact production, mutate a database,
or inspect secrets. Read AGENTS.md, docs/README.md, the current-state resume point,
skills/studio-tune-local/SKILL.md, and only the Universal Studio documentation needed for the
change. Preserve the generic architecture and keep Instagram-specific behavior behind its adapter.

You may create or edit only these paths:
{allowed}

The Tune runner, local API, launcher, authentication, production routes, and files outside this
list are a fixed safety boundary. Do not change them. Implement the request, add or update focused
tests, and run the most relevant checks available in this snapshot. Keep the Studio useful at
360 CSS pixels and preserve keyboard/reduced-motion behavior.

PROJECT IDEA
<project_idea>
{record['project_idea']}
</project_idea>

DESIRED IMPLEMENTATION
<desired_implementation>
{record['implementation']}
</desired_implementation>

OWNER FEEDBACK FOR THIS ITERATION
<owner_feedback>
{feedback}
</owner_feedback>

Finish with a concise summary of what changed and what you verified. Do not merely propose code;
make the changes in this snapshot.
"""

    def _codex_exec(self, snapshot: Path, prompt: str, output_path: Path) -> str:
        events_path = output_path.with_name("events.jsonl")
        error_path = output_path.with_name("stderr.log")
        command = [
            self.codex_binary,
            "exec",
            "--ephemeral",
            "--ignore-user-config",
            "--sandbox", "workspace-write",
            "--cd", str(snapshot),
            "--json",
            "--output-last-message", str(output_path),
            "-",
        ]
        environment = {
            key: value for key, value in os.environ.items() if key in SAFE_ENVIRONMENT_KEYS
        }
        environment["NO_COLOR"] = "1"
        with events_path.open("w") as events, error_path.open("w") as errors:
            completed = subprocess.run(
                command, input=prompt, text=True, stdout=events, stderr=errors,
                cwd=snapshot, env=environment, timeout=MAX_AGENT_SECONDS, check=False,
            )
        if completed.returncode:
            stderr = error_path.read_text(errors="replace") if error_path.is_file() else ""
            events = events_path.read_text(errors="replace") if events_path.is_file() else ""
            raise RuntimeError(_trim_output(stderr or events) or "Codex exited without a result")
        if not output_path.is_file():
            raise RuntimeError("Codex completed without a final Tune summary")
        summary = _trim_output(output_path.read_text(errors="replace"), MAX_SUMMARY_CHARACTERS)
        if not summary:
            raise RuntimeError("Codex returned an empty Tune summary")
        return summary

    def _changed_paths(self, snapshot: Path) -> list[str]:
        tracked = subprocess.run(
            ["git", "-C", str(snapshot), "diff", "--name-only", "--no-renames", "-z", "HEAD"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        untracked = subprocess.run(
            ["git", "-C", str(snapshot), "ls-files", "--others", "--exclude-standard", "-z"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        if tracked.returncode or untracked.returncode:
            raw_error = tracked.stderr or untracked.stderr
            raise RuntimeError(_trim_output(raw_error.decode(errors="replace")))
        names = {
            item.decode() for item in (tracked.stdout + untracked.stdout).split(b"\0") if item
        }
        return sorted(names)

    @staticmethod
    def _run_verification_command(snapshot: Path, command: Sequence[str], label: str) -> str:
        environment = {
            key: value for key, value in os.environ.items() if key in SAFE_ENVIRONMENT_KEYS
        }
        environment.update({"NO_COLOR": "1", "PYTHONDONTWRITEBYTECODE": "1"})
        completed = subprocess.run(
            list(command), cwd=snapshot, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, timeout=600, check=False, env=environment,
        )
        if completed.returncode:
            output = _trim_output(completed.stdout)
            raise RuntimeError(f"{label} failed\n{output}".strip())
        return label

    def _verify_snapshot(self, snapshot: Path) -> Sequence[str]:
        commands = (
            (
                [
                    str(snapshot / ".venv" / "bin" / "python"), "-m", "unittest", "discover",
                    "-s", "tests/validation_pipeline", "-p", "test_studio*.py", "-v",
                ],
                "Universal Studio Python tests",
            ),
            (
                [
                    "npm", "--prefix", "apps/commander-web", "test", "--",
                    "src/views/StudioView.test.tsx",
                ],
                "Studio web unit tests",
            ),
            (
                ["npm", "--prefix", "apps/commander-web", "run", "build"],
                "Owner Console production build",
            ),
            (["git", "diff", "--check"], "Git whitespace validation"),
        )
        return [self._run_verification_command(snapshot, command, label) for command, label in commands]

    def _render_snapshot_preview(self, snapshot: Path) -> bytes:
        script = "\n".join((
            "import sys",
            "from validation_pipeline.studio_workspace import UniversalStudioWorkspace",
            "workspace = UniversalStudioWorkspace(sys.argv[1])",
            "detail = workspace.detail()",
            "render = workspace.render_preview(state_sha256=detail['state_sha256'])",
            "sys.stdout.buffer.write(render['bytes'])",
        ))
        environment = {
            key: value for key, value in os.environ.items() if key in SAFE_ENVIRONMENT_KEYS
        }
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        with tempfile.TemporaryDirectory(prefix="preview-", dir=self.state_root) as workspace:
            completed = subprocess.run(
                [str(snapshot / ".venv" / "bin" / "python"), "-c", script, workspace],
                cwd=snapshot, env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=120, check=False,
            )
        if completed.returncode:
            error = _trim_output(completed.stderr.decode(errors="replace"))
            raise RuntimeError(error or "Studio Tune preview renderer failed")
        return completed.stdout

    def _store_snapshot_preview(self, run_id: str, snapshot: Path) -> dict[str, Any]:
        value = self.preview_renderer(snapshot)
        metadata = _preview_metadata(value)
        target = self._preview_path(run_id)
        temporary = target.with_suffix(".tmp")
        temporary.write_bytes(value)
        temporary.replace(target)
        return metadata

    def _ensure_run_preview(self, record: Mapping[str, Any]) -> dict[str, Any]:
        value = dict(record)
        if value.get("status") != "completed":
            value["preview"] = None
            return value
        run_id = str(value["run_id"])
        preview_path = self._preview_path(run_id)
        if preview_path.is_file():
            metadata = _preview_metadata(preview_path.read_bytes())
        else:
            snapshot = self._run_path(run_id).parent / "workspace"
            if not snapshot.is_dir():
                raise RuntimeError("Studio Tune snapshot is unavailable for preview rendering")
            metadata = self._store_snapshot_preview(run_id, snapshot)
        if value.get("preview") != metadata:
            value = self._write_run({**value, "preview": metadata})
        return value

    def _copy_back(self, snapshot: Path, changed_paths: Sequence[str]) -> None:
        originals: dict[str, bytes | None] = {}
        modes: dict[str, int | None] = {}
        for name in changed_paths:
            source_snapshot = snapshot / name
            source_checkout = self.repository_root / name
            baseline = subprocess.run(
                ["git", "-C", str(snapshot), "show", f"HEAD:{name}"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False,
            )
            expected = baseline.stdout if baseline.returncode == 0 else None
            actual = source_checkout.read_bytes() if source_checkout.is_file() else None
            if actual != expected:
                raise RuntimeError(f"Studio source changed during Tune run: {name}; no changes were copied back")
            if source_snapshot.is_symlink() or not source_snapshot.is_file():
                raise RuntimeError(f"Tune mode does not delete Studio files or copy symlinks: {name}")
            originals[name] = actual
            modes[name] = source_checkout.stat().st_mode if source_checkout.exists() else None

        applied: list[str] = []
        try:
            for name in changed_paths:
                source_snapshot = snapshot / name
                source_checkout = self.repository_root / name
                source_checkout.parent.mkdir(parents=True, exist_ok=True)
                temporary = source_checkout.with_name(source_checkout.name + ".studio-tune.tmp")
                shutil.copy2(source_snapshot, temporary)
                temporary.replace(source_checkout)
                applied.append(name)
        except Exception:
            for name in reversed(applied):
                target = self.repository_root / name
                original = originals[name]
                if original is None:
                    target.unlink(missing_ok=True)
                else:
                    temporary = target.with_name(target.name + ".studio-tune-rollback.tmp")
                    temporary.write_bytes(original)
                    if modes[name] is not None:
                        temporary.chmod(modes[name] & 0o7777)
                    temporary.replace(target)
            raise

    def _execute_run(self, run_id: str) -> None:
        summary: str | None = None
        try:
            record = self._update_run(
                run_id, status="running", stage="preparing", started_at=_now(), error=None,
            )
            run_root = self._run_path(run_id).parent
            snapshot = run_root / "workspace"
            self._copy_repository_snapshot(snapshot)
            record = self._update_run(run_id, stage="generating")
            summary = self.executor(snapshot, self._prompt(record), run_root / "summary.txt")
            changed_paths = self._changed_paths(snapshot)
            if not changed_paths:
                raise RuntimeError("Tune agent completed without changing a Studio file")
            outside = [name for name in changed_paths if not _is_allowed_path(name)]
            if outside:
                raise RuntimeError(
                    "Tune agent changed files outside its Studio allowlist: " + ", ".join(outside)
                )
            deleted = [
                name for name in changed_paths
                if (snapshot / name).is_symlink() or not (snapshot / name).is_file()
            ]
            if deleted:
                raise RuntimeError(
                    "Tune agent attempted to delete Studio files or copy symlinks: "
                    + ", ".join(deleted)
                )
            self._update_run(run_id, stage="verifying", changed_files=changed_paths, summary=summary)
            verification = list(self.verifier(snapshot))
            preview = self._store_snapshot_preview(run_id, snapshot)
            self._update_run(run_id, stage="applying", verification=verification)
            self._copy_back(snapshot, changed_paths)
            self._update_run(
                run_id, status="completed", stage="completed", summary=summary,
                changed_files=changed_paths, verification=verification, preview=preview,
                completed_at=_now(), error=None,
            )
        except subprocess.TimeoutExpired:
            self._update_run(
                run_id, status="failed", stage="failed", summary=summary,
                error="Studio Tune exceeded its 40-minute execution limit.", completed_at=_now(),
            )
        except Exception as error:
            self._update_run(
                run_id, status="failed", stage="failed", summary=summary,
                error=_trim_output(str(error), MAX_SUMMARY_CHARACTERS), completed_at=_now(),
            )
        finally:
            with self._lock:
                self._threads.pop(run_id, None)


def studio_tune_router(
    service: StudioTuneService, *, prefix: str,
    dependencies: Sequence[DependsParameter] = (),
) -> APIRouter:
    """Expose Tune mode only when explicitly mounted by the loopback app."""

    router = APIRouter(prefix=prefix, dependencies=list(dependencies))

    def fail(error: Exception) -> HTTPException:
        if isinstance(error, KeyError):
            return HTTPException(status_code=404, detail=str(error).strip("'"))
        if isinstance(error, RuntimeError):
            return HTTPException(status_code=409, detail=str(error))
        return HTTPException(status_code=400, detail=str(error))

    @router.get("/tune")
    def tune_detail() -> dict[str, Any]:
        return service.detail()

    @router.post("/tune-runs", status_code=202)
    def start_tune(request: Mapping[str, Any]) -> dict[str, Any]:
        if set(request) != {"project_idea", "implementation", "feedback"}:
            raise HTTPException(status_code=400, detail="Studio Tune fields are invalid")
        try:
            return service.start(
                project_idea=request["project_idea"],
                implementation=request["implementation"],
                feedback=request["feedback"],
            )
        except (ValueError, RuntimeError) as error:
            raise fail(error) from error

    @router.get("/tune-runs/{run_id}")
    def tune_run(run_id: str) -> dict[str, Any]:
        try:
            return service.run_detail(run_id)
        except (KeyError, ValueError) as error:
            raise fail(error) from error

    @router.post("/tune-runs/{run_id}/rules")
    def save_tune_rule(run_id: str, request: Mapping[str, Any]) -> dict[str, Any]:
        if set(request) != {"rule"}:
            raise HTTPException(status_code=400, detail="Studio Tune rule fields are invalid")
        try:
            return service.save_rule(run_id, rule=request["rule"])
        except (KeyError, RuntimeError, ValueError) as error:
            raise fail(error) from error

    @router.get("/tune-runs/{run_id}/preview", response_class=Response)
    def tune_run_preview(run_id: str) -> Response:
        try:
            value, metadata = service.preview(run_id)
        except (KeyError, RuntimeError, ValueError) as error:
            raise fail(error) from error
        digest = str(metadata["sha256"])
        return Response(
            content=value,
            media_type="image/png",
            headers={
                "Cache-Control": "private, no-store",
                "ETag": f'"{digest}"',
                "X-PTW-Content-SHA256": digest,
            },
        )

    return router
