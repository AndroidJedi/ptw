"""Supervised, ephemeral Codex app-server transport. Never log protocol payloads."""
from __future__ import annotations

import json
import os
from pathlib import Path
import queue
import signal
import subprocess
import sys
import threading
import time
from typing import Callable

import httpx


class RPCRejected(RuntimeError):
    """Explicit server rejection, distinct from an ambiguous timeout."""


class CodexRPC:
    def __init__(self, binary: str, repository: Path, environment: dict, callback: Callable):
        self.callback = callback
        self.pending: dict[int, queue.Queue] = {}
        self.lock = threading.RLock()
        self.counter = 0
        read_fd, write_fd = os.pipe()
        self.liveness = os.fdopen(write_fd, "wb")
        try:
            self.process = subprocess.Popen(
                [sys.executable, str(Path(__file__).with_name("commander_chat_worker.py")), str(read_fd),
                 binary, "app-server", "--listen", "stdio://", "-c", "analytics.enabled=false"],
                cwd=repository, env=environment, pass_fds=(read_fd,), stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                start_new_session=True, bufsize=1,
            )
        finally:
            os.close(read_fd)
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()
        try:
            self.request("initialize", {"clientInfo": {"name": "ptw_commander", "version": "2.0.0"},
                                        "capabilities": {"experimentalApi": True}})
            self.write({"method": "initialized"})
        except Exception:
            self.close()
            raise

    def write(self, value):
        with self.lock:
            if self.process.poll() is not None:
                raise RuntimeError("Commander runtime disconnected")
            self.process.stdin.write(json.dumps(value) + "\n")
            self.process.stdin.flush()

    def request(self, method: str, params: dict, timeout: float = 25):
        with self.lock:
            self.counter += 1
            identifier = self.counter
            inbox = self.pending[identifier] = queue.Queue(maxsize=1)
        try:
            self.write({"id": identifier, "method": method, "params": params})
            result = inbox.get(timeout=timeout)
            if "error" in result:
                raise RPCRejected("Commander runtime rejected " + method)
            return result.get("result", {})
        except queue.Empty:
            raise RuntimeError("Commander runtime timed out during " + method) from None
        finally:
            with self.lock:
                self.pending.pop(identifier, None)

    def respond(self, identifier, result):
        self.write({"id": identifier, "result": result})

    def _read(self):
        try:
            for line in self.process.stdout:
                value = json.loads(line)
                if "method" not in value and "id" in value:
                    with self.lock:
                        inbox = self.pending.get(value["id"])
                    if inbox:
                        inbox.put(value)
                else:
                    self.callback(value)
        except (ValueError, OSError, RuntimeError):
            pass
        finally:
            with self.lock:
                for inbox in self.pending.values():
                    if inbox.empty():
                        inbox.put({"error": {"message": "disconnected"}})
            self.callback({"method": "ptw/disconnected", "params": {}})

    def close(self):
        try:
            os.killpg(self.process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        self.liveness.close()
        self.process.wait(timeout=10)
        self.reader.join(timeout=2)
        self.process.stdin.close()
        self.process.stdout.close()


class PlanRPC:
    """Same transport through a private worker whose checkout is mounted read-only."""
    def __init__(self, url: str, token: str, callback: Callable):
        self.client = httpx.Client(base_url=url, headers={"X-PTW-Owner-Gateway-Token": token}, timeout=30)
        self.callback = callback
        self.closed = threading.Event()
        response = self.client.post("/session")
        response.raise_for_status()
        self.session = response.json()["id"]
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()

    def request(self, method, params, timeout=25):
        response = self.client.post(f"/session/{self.session}/request", json={"method": method, "params": params})
        if response.status_code == 409:
            raise RPCRejected("Plan runtime rejected " + method)
        response.raise_for_status()
        return response.json()

    def respond(self, identifier, result):
        response = self.client.post(f"/session/{self.session}/respond", json={"id": identifier, "result": result})
        response.raise_for_status()

    def _read(self):
        cursor = 0
        while not self.closed.is_set():
            try:
                response = self.client.get(f"/session/{self.session}/events", params={"after": cursor})
                response.raise_for_status()
                for event in response.json()["events"]:
                    cursor = event["id"]
                    self.callback(event["value"])
            except (httpx.HTTPError, ValueError):
                self.callback({"method": "ptw/disconnected", "params": {}})
                return
            self.closed.wait(.2)

    def close(self):
        self.closed.set()
        self.reader.join(timeout=35)
        try:
            self.client.delete(f"/session/{self.session}")
        finally:
            self.client.close()
