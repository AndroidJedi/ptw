"""Private, token-safe device authorization controller for the Codex CLI."""

from __future__ import annotations

import os
from pathlib import Path
import pty
import re
import secrets
import subprocess
import tempfile
import threading
import time
from typing import Any, TextIO

from fastapi import FastAPI, Header, HTTPException


AUTHORIZATION_TIMEOUT_SECONDS = 15 * 60
STATUS_TIMEOUT_SECONDS = 15
TEST_TIMEOUT_SECONDS = 90
DEVICE_URL_PATTERN = re.compile(r"https://auth\.openai\.com/codex/device(?:\?[^\s'\"]*)?")
DEVICE_CODE_PATTERN = re.compile(r"\b[A-Z0-9]{4,8}-[A-Z0-9]{4,8}\b")


def device_login_details(output: str) -> tuple[str | None, str | None]:
    """Return only the browser-safe fields from Codex device-login output."""
    return (
        (match.group(0) if (match := DEVICE_URL_PATTERN.search(output)) else None),
        (match.group(0) if (match := DEVICE_CODE_PATTERN.search(output)) else None),
    )


class AuthorizationController:
    def __init__(self, executable: str, codex_home: Path) -> None:
        self.executable = executable
        self.codex_home = codex_home
        self._lock = threading.Lock()
        self._process: subprocess.Popen[bytes] | None = None
        self._started_at = 0.0
        self._authorization_url: str | None = None
        self._device_code: str | None = None
        self._phase = "unverified"
        self._test_status: str | None = None

    def _environment(self) -> dict[str, str]:
        return {"CODEX_HOME": str(self.codex_home), "PATH": os.environ.get("PATH", "")}

    def _logged_in(self) -> bool:
        try:
            completed = subprocess.run(
                [self.executable, "login", "status"],
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, timeout=STATUS_TIMEOUT_SECONDS, env=self._environment(), check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        return completed.returncode == 0 and "logged in" in completed.stdout.lower()

    def _working_test(self) -> bool:
        try:
            with tempfile.TemporaryDirectory(prefix="ptw-codex-auth-") as directory:
                output = Path(directory) / "response.txt"
                completed = subprocess.run(
                    [
                        self.executable, "exec", "--ephemeral", "--ignore-user-config",
                        "--sandbox", "read-only", "--skip-git-repo-check",
                        "--cd", directory, "--output-last-message", str(output),
                        "Reply with exactly PTW_AUTH_OK.",
                    ],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    text=True, timeout=TEST_TIMEOUT_SECONDS, env=self._environment(), check=False,
                )
                return completed.returncode == 0 and output.is_file() and output.read_text(
                    encoding="utf-8"
                ).strip() == "PTW_AUTH_OK"
        except (OSError, subprocess.SubprocessError):
            return False

    def _verify_credentials(self) -> None:
        test_ok = self._logged_in() and self._working_test()
        with self._lock:
            self._test_status = "passed" if test_ok else "failed"
            self._phase = "authorized" if test_ok else "failed"

    def _finish(self) -> None:
        with self._lock:
            self._process = None
            self._authorization_url = None
            self._device_code = None
            self._phase = "verifying"
        self._verify_credentials()

    def _start_device_login(self) -> tuple[subprocess.Popen[bytes], TextIO]:
        master_fd, slave_fd = pty.openpty()
        try:
            process = subprocess.Popen(
                [self.executable, "login", "--device-auth"],
                stdin=slave_fd, stdout=slave_fd, stderr=slave_fd,
                env=self._environment(), close_fds=True,
            )
        except OSError:
            os.close(master_fd)
            raise
        finally:
            os.close(slave_fd)
        return process, os.fdopen(
            master_fd, "r", encoding="utf-8", errors="replace",
        )

    def _collect_login_output(self, process: subprocess.Popen[bytes], output: TextIO) -> None:
        captured: list[str] = []
        try:
            for line in output:
                captured.append(line)
                if len(captured) > 32:
                    captured.pop(0)
                url, code = device_login_details("".join(captured))
                if url or code:
                    with self._lock:
                        self._authorization_url = url or self._authorization_url
                        self._device_code = code or self._device_code
        except OSError:
            # Linux PTYs report EIO rather than EOF after the child closes its
            # slave descriptor.
            pass
        finally:
            output.close()
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=5)
        if process.returncode == 0:
            self._finish()
        else:
            with self._lock:
                self._process = None
                self._authorization_url = None
                self._device_code = None
                self._test_status = None
                self._phase = "authorization_required"

    def _expire_if_needed(self) -> None:
        with self._lock:
            process = self._process
            expired = process is not None and time.monotonic() - self._started_at > AUTHORIZATION_TIMEOUT_SECONDS
        if not expired:
            return
        process.terminate()
        with self._lock:
            self._process = None
            self._authorization_url = None
            self._device_code = None
            self._test_status = None
            self._phase = "authorization_required"

    def status(self) -> dict[str, Any]:
        self._expire_if_needed()
        start_verification = False
        with self._lock:
            if self._process is not None:
                return {
                    "status": "authorizing", "test_status": None,
                    "authorization_url": self._authorization_url,
                    "device_code": self._device_code,
                }
            phase = self._phase
            test_status = self._test_status
            if phase == "unverified":
                self._phase = "verifying"
                phase = "verifying"
                start_verification = True
        if start_verification:
            threading.Thread(target=self._verify_credentials, daemon=True).start()
        if phase in {"authorized", "failed"}:
            return {"status": phase, "test_status": test_status}
        return {"status": phase, "test_status": None}

    def refresh(self) -> dict[str, Any]:
        self._expire_if_needed()
        with self._lock:
            if self._process is not None:
                return {
                    "status": "authorizing", "test_status": None,
                    "authorization_url": self._authorization_url,
                    "device_code": self._device_code,
                }
            if self._phase == "verifying":
                return {"status": "verifying", "test_status": None}
            try:
                process, output = self._start_device_login()
            except OSError as error:
                raise RuntimeError("Codex authorization flow could not start") from error
            self._process = process
            self._started_at = time.monotonic()
            self._authorization_url = None
            self._device_code = None
            self._test_status = None
            self._phase = "authorizing"
            threading.Thread(
                target=self._collect_login_output, args=(process, output), daemon=True,
            ).start()
        # The CLI prints the device prompt asynchronously. Polling status is the durable contract.
        return self.status()


def required_token() -> str:
    token = os.environ.get("PTW_CODEX_AUTH_BRIDGE_TOKEN", "")
    if not token:
        raise RuntimeError("PTW_CODEX_AUTH_BRIDGE_TOKEN is required")
    return token


controller = AuthorizationController(
    os.environ.get("CODEX_EXECUTABLE", "/opt/ptw-codex/bin/codex"),
    Path(os.environ.get("CODEX_HOME", "/root/.codex")),
)
app = FastAPI(title="PTW Codex Authorization", docs_url=None, redoc_url=None)


def authorize(token: str) -> None:
    if not secrets.compare_digest(token, required_token()):
        raise HTTPException(status_code=403, detail="authorization denied")


@app.get("/healthz")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/authorization")
def authorization_status(x_ptw_codex_authorization_token: str = Header(default="")) -> dict[str, Any]:
    authorize(x_ptw_codex_authorization_token)
    return controller.status()


@app.post("/v1/authorization/refresh", status_code=202)
def refresh_authorization(x_ptw_codex_authorization_token: str = Header(default="")) -> dict[str, Any]:
    authorize(x_ptw_codex_authorization_token)
    try:
        return controller.refresh()
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail="authorization service unavailable") from error
