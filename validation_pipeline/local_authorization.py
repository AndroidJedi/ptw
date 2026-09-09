"""Local Codex authorization: expose status and device prompt, never CLI output."""

import os
import pty
import re
import select
import shutil
import signal
import subprocess
import threading
import time

from fastapi import APIRouter, Depends

from .commander_chat import SAFE_ENV, local_request


class LocalAuthorization:
    def __init__(self, binary="codex"):
        self.binary = shutil.which(binary)
        self.environment = {k: v for k, v in os.environ.items() if k in SAFE_ENV}
        self.lock = threading.RLock()
        self.process = None
        self.thread = None
        self.closed = False
        self.value = None

    def _check(self):
        if not self.binary:
            return {"status": "authorization_required", "test_status": None}
        try:
            result = subprocess.run([self.binary, "login", "status"], env=self.environment,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
            return {"status": "authorized" if result.returncode == 0 else "authorization_required", "test_status": None}
        except (OSError, subprocess.TimeoutExpired):
            return {"status": "failed", "test_status": None}

    def detail(self):
        with self.lock:
            return dict(self.value) if self.value is not None else self._check()

    def refresh(self):
        with self.lock:
            if self.closed or not self.binary:
                return {"status": "failed", "test_status": None}
            if self.thread and self.thread.is_alive():
                return dict(self.value)
            self.value = {"status": "authorizing", "test_status": None}
            self.thread = threading.Thread(target=self._login, daemon=True)
            self.thread.start()
            return dict(self.value)

    def _login(self):
        master, slave = pty.openpty()
        process = None
        try:
            with self.lock:
                if self.closed:
                    return
                process = subprocess.Popen([self.binary, "login", "--device-auth"],
                                           stdin=slave, stdout=slave, stderr=slave,
                                           env=self.environment, start_new_session=True)
                self.process = process
            os.close(slave)
            slave = None
            deadline = time.monotonic() + 900
            buffer = ""
            while process.poll() is None and time.monotonic() < deadline:
                if select.select([master], [], [], .2)[0]:
                    try:
                        chunk = os.read(master, 4096)
                    except OSError:
                        break
                    if not chunk:
                        break
                    buffer = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", buffer + chunk.decode(errors="replace"))[-16000:]
                    url = re.search(r"https://auth\.openai\.com/codex/device\b", buffer)
                    code = re.search(r"\b[A-Z0-9]{4}-[A-Z0-9]{5}\b|\b[A-Z0-9]{4}-[A-Z0-9]{4}\b", buffer)
                    if url and code:
                        with self.lock:
                            self.value = {"status": "authorizing", "test_status": None,
                                          "authorization_url": url.group(), "device_code": code.group()}
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            with self.lock:
                self.value = self._check() if process.returncode == 0 else {"status": "failed", "test_status": None}
        except Exception:
            with self.lock:
                self.value = {"status": "failed", "test_status": None}
        finally:
            if process and process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            os.close(master)
            if slave is not None:
                os.close(slave)
            with self.lock:
                self.process = None

    def close(self):
        with self.lock:
            self.closed = True
            if self.process and self.process.poll() is None:
                os.killpg(self.process.pid, signal.SIGKILL)
        if self.thread:
            self.thread.join(timeout=3)


def local_authorization_router(service, dependencies):
    router = APIRouter(prefix="/api/v1/settings/chatgpt-authorization",
                       dependencies=[*dependencies, Depends(local_request)])

    @router.get("")
    def detail():
        return service.detail()

    @router.post("/refresh", status_code=202)
    def refresh():
        return service.refresh()

    return router
