from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from .control_store import ControlStore
from .platform import PlatformRepository


class CommandRunner:
    def __init__(self, executable: str, cwd: Path, store: ControlStore, platform: PlatformRepository) -> None:
        self.executable = executable
        self.cwd = cwd
        self.store = store
        self.platform = platform
        self.processes: dict[str, asyncio.subprocess.Process] = {}

    async def execute(self, session_id: str) -> None:
        command = self.store.command(session_id)
        job_id: int | None = None
        try:
            job_id = self.platform.create_running_job(command["instruction"], session_id)
            self.store.update(session_id, "running", platform_job_id=job_id)
            self.store.event(session_id, {"type": "execution.started", "task_id": f"TASK-{job_id}"})
            prompt = (
                "Execute exactly the approved plan below. Preserve unrelated work. Run required checks, "
                "emit no secrets, and do not broaden scope. After all required checks pass, complete any "
                "non-destructive deployment named by the plan and record the deployed revision, health, "
                "and rollback evidence in the final result. Destructive work is authorized only when the "
                "approved plan names exact targets and has explicit owner confirmation.\n\n"
                f"Instruction:\n{command['instruction']}\n\nApproved plan ({command['plan_digest']}):\n{command['plan']}"
            )
            process = await asyncio.create_subprocess_exec(
                self.executable, "exec", "--json", "--ephemeral", "--approve-for-me",
                "--cd", str(self.cwd), "-",
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT, cwd=self.cwd,
            )
            self.processes[session_id] = process
            if process.stdin is None or process.stdout is None:
                raise RuntimeError("Codex execution stdio is unavailable")
            process.stdin.write(prompt.encode())
            await process.stdin.drain()
            process.stdin.close()
            last_event: dict[str, Any] = {}
            while raw := await process.stdout.readline():
                line = raw.decode(errors="replace").rstrip()
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    event = {"type": "raw", "text": line}
                last_event = event
                self.store.event(session_id, {"type": "execution.event", "event": event})
            returncode = await process.wait()
            success = returncode == 0
            result = {"returncode": returncode, "last_event": last_event, "plan_digest": command["plan_digest"]}
            self.platform.complete_job(job_id, success=success, result=result)
            self.store.update(session_id, "completed" if success else "failed", **({} if success else {"error": f"codex exit {returncode}"}))
            self.store.event(session_id, {"type": "execution.completed", **result})
        except Exception as error:
            if job_id is not None:
                self.platform.complete_job(job_id, success=False, result={"error": type(error).__name__})
            self.store.update(session_id, "failed", error=f"{type(error).__name__}: {str(error)[:1000]}")
            self.store.event(session_id, {"type": "execution.failed", "error": type(error).__name__})
        finally:
            self.processes.pop(session_id, None)

    async def cancel(self, session_id: str) -> None:
        process = self.processes.get(session_id)
        if process and process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=10)
            except asyncio.TimeoutError:
                process.kill()
        command = self.store.command(session_id)
        if command.get("platform_job_id"):
            self.platform.cancel(int(command["platform_job_id"]))
        self.store.update(session_id, "cancelled")
        self.store.event(session_id, {"type": "execution.cancelled"})
