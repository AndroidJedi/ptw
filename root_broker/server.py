from __future__ import annotations

import asyncio
import fcntl
import json
import os
from pathlib import Path
import pty
import select
import signal
import socket
import struct
import termios
import time
from typing import Any


class RootBroker:
    def __init__(self, socket_path: Path, allowed_uid: int, allowed_gid: int, *, idle_seconds: int = 900, maximum_seconds: int = 3600) -> None:
        self.socket_path = socket_path
        self.allowed_uid = allowed_uid
        self.allowed_gid = allowed_gid
        self.idle_seconds = idle_seconds
        self.maximum_seconds = maximum_seconds
        self._active = asyncio.Lock()

    async def serve(self) -> None:
        self.socket_path.parent.mkdir(parents=True, exist_ok=True)
        if self.socket_path.exists():
            self.socket_path.unlink()
        server = await asyncio.start_unix_server(self._client, path=str(self.socket_path))
        os.chown(self.socket_path, 0, self.allowed_gid)
        os.chmod(self.socket_path, 0o660)
        async with server:
            await server.serve_forever()

    async def _client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        peer_uid = self._peer_uid(writer)
        if peer_uid != self.allowed_uid or self._active.locked():
            await self._write(writer, {"type": "error", "code": "unauthorized_or_busy"})
            await self._close(writer)
            return
        async with self._active:
            try:
                raw_handshake = await asyncio.wait_for(reader.readline(), timeout=5)
                handshake = json.loads(raw_handshake)
            except (asyncio.TimeoutError, json.JSONDecodeError, UnicodeDecodeError):
                await self._write(writer, {"type": "error", "code": "invalid_handshake"})
                await self._close(writer)
                return
            if handshake.get("type") == "operation":
                await self._operation(handshake, writer)
                await self._close(writer)
                return
            if handshake.get("type") != "terminal":
                await self._write(writer, {"type": "error", "code": "invalid_handshake"})
                await self._close(writer)
                return
            await self._terminal(reader, writer)

    async def _terminal(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        pid, fd = pty.fork()
        if pid == 0:
            os.execv("/bin/bash", ["/bin/bash", "-l"])
        os.set_blocking(fd, False)
        started = time.monotonic()
        last_activity = started
        reason = "shell_exit"
        try:
            await self._write(writer, {"type": "session", "pid": pid, "idle_seconds": self.idle_seconds, "maximum_seconds": self.maximum_seconds})
            while True:
                now = time.monotonic()
                exited, _status = os.waitpid(pid, os.WNOHANG)
                if exited == pid:
                    reason = "shell_exit"; break
                if now - started >= self.maximum_seconds:
                    reason = "maximum_duration"; break
                if now - last_activity >= self.idle_seconds:
                    reason = "idle_timeout"; break
                input_task = asyncio.create_task(reader.readline())
                output_task = asyncio.create_task(asyncio.to_thread(self._read_pty, fd))
                done, pending = await asyncio.wait({input_task, output_task}, timeout=1, return_when=asyncio.FIRST_COMPLETED)
                for task in pending:
                    task.cancel()
                if not done:
                    continue
                for task in done:
                    if task is input_task:
                        raw = task.result()
                        if not raw:
                            reason = "gateway_disconnected"; break
                        message = json.loads(raw)
                        if message.get("type") == "input":
                            data = str(message.get("data", "")).encode()
                            if data:
                                os.write(fd, data); last_activity = now
                        elif message.get("type") == "resize":
                            self._resize(fd, int(message.get("rows", 24)), int(message.get("cols", 80)))
                            last_activity = now
                    else:
                        data = task.result()
                        if data:
                            last_activity = now
                            await self._write(writer, {"type": "output", "data": data.decode(errors="replace")})
                else:
                    continue
                break
        except (BrokenPipeError, ConnectionResetError, json.JSONDecodeError):
            reason = "connection_error"
        finally:
            try:
                os.kill(pid, signal.SIGHUP)
            except ProcessLookupError:
                pass
            try:
                os.waitpid(pid, os.WNOHANG)
            except ChildProcessError:
                pass
            try:
                os.close(fd)
            except OSError:
                pass
            await self._write(writer, {"type": "closed", "reason": reason})
            await self._close(writer)

    async def _operation(self, request: dict[str, Any], writer: asyncio.StreamWriter) -> None:
        if request.get("name") != "reset":
            await self._write(writer, {"type": "operation.failed", "code": "unsupported_operation"})
            return
        await self._write(writer, {"type": "operation.started", "name": "reset"})
        process = await asyncio.create_subprocess_exec(
            "/root/ptw/scripts/reset_ptw.sh",
            "--confirm", "RESET PTW PRODUCTION",
        )
        return_code = await process.wait()
        await self._write(writer, {
            "type": "operation.completed" if return_code == 0 else "operation.failed",
            "name": "reset",
            "return_code": return_code,
        })

    @staticmethod
    async def _write(writer: asyncio.StreamWriter, message: dict[str, Any]) -> bool:
        try:
            writer.write((json.dumps(message, ensure_ascii=False) + "\n").encode())
            await writer.drain()
            return True
        except (BrokenPipeError, ConnectionResetError):
            return False

    @staticmethod
    async def _close(writer: asyncio.StreamWriter) -> None:
        writer.close()
        try:
            await writer.wait_closed()
        except (BrokenPipeError, ConnectionResetError):
            pass

    @staticmethod
    def _read_pty(fd: int) -> bytes:
        ready, _, _ = select.select([fd], [], [], .75)
        if not ready:
            return b""
        try:
            return os.read(fd, 65536)
        except (BlockingIOError, OSError):
            return b""

    @staticmethod
    def _resize(fd: int, rows: int, cols: int) -> None:
        rows, cols = max(1, min(rows, 300)), max(1, min(cols, 500))
        fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))

    @staticmethod
    def _peer_uid(writer: asyncio.StreamWriter) -> int:
        sock = writer.get_extra_info("socket")
        if sock is None or not hasattr(socket, "SO_PEERCRED"):
            return -1
        credentials = sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
        _pid, uid, _gid = struct.unpack("3i", credentials)
        return uid


def main() -> None:
    socket_path = Path(os.environ.get("ROOT_BROKER_SOCKET", "/run/ptw-root-broker/control.sock"))
    raw_uid = os.environ.get("ROOT_BROKER_ALLOWED_UID", "")
    raw_gid = os.environ.get("ROOT_BROKER_ALLOWED_GID", raw_uid)
    if os.geteuid() != 0:
        raise SystemExit("root broker must run as root")
    if not raw_uid.isdigit() or int(raw_uid) == 0 or not raw_gid.isdigit() or int(raw_gid) == 0:
        raise SystemExit("ROOT_BROKER_ALLOWED_UID/GID must be non-root numeric IDs")
    asyncio.run(RootBroker(socket_path, int(raw_uid), int(raw_gid)).serve())


if __name__ == "__main__":
    main()
