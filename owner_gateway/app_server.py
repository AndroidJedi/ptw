from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Awaitable, Callable


EventSink = Callable[[dict[str, Any]], Awaitable[None]]


class AppServerPlanner:
    """Minimal Codex App Server v2 client for immutable read-only plans."""

    def __init__(self, executable: str, cwd: Path) -> None:
        self.executable = executable
        self.cwd = cwd

    async def plan(self, instruction: str, sink: EventSink) -> str:
        process = await asyncio.create_subprocess_exec(
            self.executable, "app-server", "--stdio",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.cwd,
        )
        if process.stdin is None or process.stdout is None:
            raise RuntimeError("Codex App Server stdio is unavailable")

        request_id = 0
        async def send(method: str, params: dict[str, Any] | None = None, *, notification: bool = False) -> None:
            nonlocal request_id
            payload: dict[str, Any] = {"method": method}
            if params is not None:
                payload["params"] = params
            if not notification:
                request_id += 1
                payload["id"] = request_id
            process.stdin.write((json.dumps(payload) + "\n").encode())
            await process.stdin.drain()

        try:
            await send("initialize", {"clientInfo": {"name": "ptw-owner-gateway", "title": "PTW Owner Gateway", "version": "1.0.0"}})
            initialized = await self._response(process.stdout, 1, sink)
            if "result" not in initialized:
                raise RuntimeError(f"App Server initialize failed: {initialized.get('error')}")
            await send("initialized", notification=True)
            await send("thread/start", {
                "cwd": str(self.cwd),
                "approvalPolicy": "never",
                "sandbox": "read-only",
                "ephemeral": True,
                "baseInstructions": "Create a concrete implementation plan only. Do not modify files or external state.",
            })
            thread_response = await self._response(process.stdout, 2, sink)
            thread_id = str(thread_response["result"]["thread"]["id"])
            await send("turn/start", {
                "threadId": thread_id,
                "input": [{"type": "text", "text": instruction}],
                "approvalPolicy": "never",
                "sandboxPolicy": {"type": "readOnly", "networkAccess": False},
            })
            await self._response(process.stdout, 3, sink)

            plan_deltas: list[str] = []
            message_deltas: list[str] = []
            final_plan: str | None = None
            final_message: str | None = None
            while True:
                raw = await asyncio.wait_for(process.stdout.readline(), timeout=900)
                if not raw:
                    raise RuntimeError("App Server exited before completing the plan")
                message = json.loads(raw)
                await sink({"type": "app_server.event", "event": message})
                method = message.get("method")
                params = message.get("params") or {}
                if method in {"item/agentMessage/delta", "item/plan/delta"}:
                    delta = params.get("delta")
                    if isinstance(delta, str):
                        (plan_deltas if method == "item/plan/delta" else message_deltas).append(delta)
                elif method == "item/completed":
                    item = params.get("item") or {}
                    text = item.get("text") or item.get("content")
                    if isinstance(text, str) and item.get("type") == "plan":
                        # The protocol defines the completed plan item—not its
                        # streamed deltas—as authoritative.
                        final_plan = text
                    elif isinstance(text, str) and item.get("type") == "agentMessage":
                        final_message = text
                elif method == "turn/completed":
                    turn = params.get("turn") or {}
                    if turn.get("status") != "completed":
                        error = (turn.get("error") or {}).get("message") or turn.get("status")
                        raise RuntimeError(f"App Server planning turn did not complete: {error}")
                    break
            plan = (
                final_plan
                or "".join(plan_deltas).strip()
                or final_message
                or "".join(message_deltas).strip()
            )
            plan = plan.strip()
            if not plan:
                raise RuntimeError("App Server completed without a plan")
            return plan
        finally:
            if process.returncode is None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=5)
                except asyncio.TimeoutError:
                    process.kill()

    @staticmethod
    async def _response(reader: asyncio.StreamReader, response_id: int, sink: EventSink) -> dict[str, Any]:
        while True:
            raw = await asyncio.wait_for(reader.readline(), timeout=60)
            if not raw:
                raise RuntimeError("App Server closed while waiting for response")
            message = json.loads(raw)
            await sink({"type": "app_server.event", "event": message})
            if message.get("id") == response_id:
                return message
