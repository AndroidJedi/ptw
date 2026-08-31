"""Local structured-output boundary for an authenticated Codex CLI.

The child process receives an empty working directory, a read-only sandbox, an
ephemeral session, and a strict output schema.  Authentication remains owned by
the installed CLI; PTW never copies or persists credentials.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any


class LocalCodexError(RuntimeError):
    """Terminal structured-call failure with sanitized attempt provenance."""

    def __init__(self, message: str, attempts: Sequence[Mapping[str, Any]]) -> None:
        super().__init__(message)
        self.attempts = [dict(item) for item in attempts]


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def sanitized(value: Any) -> Any:
    """Remove binary/credential-shaped values before durable local persistence."""

    if isinstance(value, bytes):
        return {"byte_count": len(value), "sha256": hashlib.sha256(value).hexdigest()}
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).casefold()
            if any(marker in lowered for marker in ("token", "secret", "credential", "password")):
                result[str(key)] = "[redacted]"
            elif "base64" in lowered:
                result[str(key)] = "[binary omitted]"
            else:
                result[str(key)] = sanitized(item)
        return result
    if isinstance(value, (list, tuple)):
        return [sanitized(item) for item in value]
    return value


class LocalCodexStructuredProvider:
    """Bounded non-interactive Codex calls with one fresh retry."""

    def __init__(
        self,
        codex_binary: str | None = None,
        *,
        model: str | None = None,
        timeout_seconds: int = 420,
        maximum_attempts: int = 2,
        executor: Callable[..., subprocess.CompletedProcess[str]] | None = None,
    ) -> None:
        binary = codex_binary or shutil.which("codex")
        if not binary:
            raise RuntimeError("authenticated Codex CLI is required for local generation")
        if maximum_attempts != 2:
            raise ValueError("local structured calls use exactly two bounded attempts")
        self.codex_binary = str(binary)
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.maximum_attempts = maximum_attempts
        self.executor = executor or subprocess.run

    @staticmethod
    def _environment() -> dict[str, str]:
        allowed = {
            "PATH", "CODEX_HOME", "TMPDIR", "TMP", "TEMP", "LANG", "LC_ALL",
            "SSL_CERT_FILE", "SSL_CERT_DIR", "HTTP_PROXY", "HTTPS_PROXY",
            "ALL_PROXY", "NO_PROXY",
        }
        return {key: value for key, value in os.environ.items() if key in allowed}

    def _command(
        self, *, workdir: Path, schema_path: Path, output_path: Path,
        image_paths: Sequence[Path],
    ) -> list[str]:
        command = [
            self.codex_binary, "exec", "--ephemeral", "--ignore-rules",
            "--sandbox", "read-only", "--skip-git-repo-check", "--color", "never",
            "--output-schema", str(schema_path), "--output-last-message", str(output_path),
            "-C", str(workdir),
        ]
        if self.model:
            command.extend(("--model", self.model))
        for path in image_paths:
            command.extend(("--image", str(path)))
        command.append("-")
        return command

    @staticmethod
    def _prompt(system_prompt: str, input_payload: Mapping[str, Any]) -> str:
        return (
            f"{system_prompt.strip()}\n\n"
            "Return only the JSON object required by the supplied output schema. "
            "Do not include chain-of-thought, hidden reasoning, markdown, or credentials.\n\n"
            f"INPUT_JSON:\n{canonical_json(input_payload)}\n"
        )

    def call(
        self,
        *,
        mode: str,
        system_prompt: str,
        input_payload: Mapping[str, Any],
        output_schema: Mapping[str, Any],
        idempotency_key: str,
        prompt_version: str,
        images: Sequence[Mapping[str, Any]] = (),
        response_validator: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
    ) -> dict[str, Any]:
        attempts: list[dict[str, Any]] = []
        input_digest = sha256_json(sanitized(input_payload))
        image_digests: list[str] = []
        for item in images:
            data = bytes(item["bytes"])
            digest = hashlib.sha256(data).hexdigest()
            if digest != str(item["sha256"]):
                raise ValueError("Codex critic image digest mismatch")
            if str(item.get("mime_type")) != "image/jpeg":
                raise ValueError("Codex critic accepts exact JPEG attachments only")
            image_digests.append(digest)

        last_error: Exception | None = None
        for attempt in range(1, self.maximum_attempts + 1):
            with tempfile.TemporaryDirectory(prefix="ptw-local-codex-") as temporary:
                root = Path(temporary)
                schema_path = root / "output-schema.json"
                output_path = root / "response.json"
                schema_path.write_text(canonical_json(output_schema), encoding="utf-8")
                image_paths: list[Path] = []
                for index, item in enumerate(images, 1):
                    path = root / f"critic-{index}.jpg"
                    path.write_bytes(bytes(item["bytes"]))
                    image_paths.append(path)
                command = self._command(
                    workdir=root, schema_path=schema_path, output_path=output_path,
                    image_paths=image_paths,
                )
                record: dict[str, Any] = {
                    "attempt": attempt,
                    "mode": mode,
                    "idempotency_key": f"{idempotency_key}:attempt:{attempt}",
                    "prompt_version": prompt_version,
                    "input_sha256": input_digest,
                    "image_sha256": image_digests,
                    "model": self.model or "codex-cli-default",
                    "sandbox": "read-only",
                    "ephemeral": True,
                }
                try:
                    completed = self.executor(
                        command,
                        input=self._prompt(system_prompt, input_payload),
                        text=True,
                        capture_output=True,
                        cwd=root,
                        env=self._environment(),
                        timeout=self.timeout_seconds,
                        check=False,
                    )
                    record.update({
                        "exit_code": int(completed.returncode),
                        "stdout_sha256": hashlib.sha256(completed.stdout.encode()).hexdigest(),
                        "stderr_sha256": hashlib.sha256(completed.stderr.encode()).hexdigest(),
                    })
                    if completed.returncode != 0:
                        raise RuntimeError(f"Codex CLI exited with status {completed.returncode}")
                    raw = output_path.read_text(encoding="utf-8")
                    response = json.loads(raw)
                    if not isinstance(response, Mapping):
                        raise ValueError("Codex structured output must be one JSON object")
                    validated = dict(response_validator(response) if response_validator else response)
                    record.update({
                        "status": "completed",
                        "response_sha256": sha256_json(validated),
                    })
                    attempts.append(record)
                    return {
                        "response": validated,
                        "invocation": {
                            "provider": "codex-cli",
                            "model": self.model or "codex-cli-default",
                            "mode": mode,
                            "prompt_version": prompt_version,
                            "input_sha256": input_digest,
                            "image_sha256": image_digests,
                            "attempts": attempts,
                        },
                    }
                except Exception as error:
                    last_error = error
                    record.update({"status": "failed", "error_type": type(error).__name__})
                    attempts.append(record)
        raise LocalCodexError(
            f"local Codex structured call failed after two attempts: {type(last_error).__name__}",
            attempts,
        ) from last_error

    def generate(self, **kwargs: Any) -> dict[str, Any]:
        return self.call(**kwargs)

    def generate_content_critic(self, **kwargs: Any) -> dict[str, Any]:
        return self.call(mode="content_result_critic", **kwargs)
