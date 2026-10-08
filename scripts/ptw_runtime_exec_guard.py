#!/usr/bin/env python3
"""Reclaim only old, closed PTW exec PID records and their unused FIFOs."""
from __future__ import annotations

import argparse
import errno
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import time


TASK_ROOT = Path('/run/containerd/io.containerd.runtime.v2.task/moby')
PIPE_ROOT = Path('/run/docker/containerd')
MIN_AGE = 86400
IDENTIFIER = re.compile(r'[0-9a-f]{64}')
CONTAINERS = frozenset({
    'ptw-validation-validation-api-1', 'ptw-owner-gateway-1',
    'ptw-agent-platform-commander-worker-1', 'ptw-agent-platform-codex-auth-1',
    'ptw-agent-platform-commander-api-1', 'ptw-agent-platform-caddy-1',
    'ptw-agent-platform-postgres-1', 'ptw-commander-api-1',
    'ptw-commander-god-1', 'ptw-commander-release-1',
    'ptw-commander-plan-1', 'ptw-commander-db-1',
})


def open_inodes(proc: Path = Path('/proc')) -> set[tuple[int, int]]:
    """Unreadable live descriptors fail closed; exited processes may disappear."""
    result = set()
    for process in proc.iterdir():
        if not process.name.isdigit():
            continue
        try:
            for descriptor in (process / 'fd').iterdir():
                try:
                    info = descriptor.stat()
                    result.add((info.st_dev, info.st_ino))
                except OSError as error:
                    if error.errno not in (errno.ENOENT, errno.ESRCH):
                        raise
        except OSError as error:
            if error.errno not in (errno.ENOENT, errno.ESRCH):
                raise
    return result


def identity(info: os.stat_result) -> tuple[int, ...]:
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid,
            info.st_nlink, info.st_size, info.st_mtime_ns)


def old_record(path: Path, *, fifo: bool, opened: set, now: float):
    info = path.lstat()
    kind = stat.S_ISFIFO if fifo else stat.S_ISREG
    if (not kind(info.st_mode) or info.st_uid != os.geteuid()
            or info.st_nlink != 1 or now - info.st_mtime < MIN_AGE
            or (info.st_dev, info.st_ino) in opened
            or (not fifo and not 1 <= info.st_size <= 32)):
        raise ValueError('runtime entry is not an old closed record')
    return info


def reclaim_container(container: str, task_root: Path, pipe_root: Path, *,
                      active: set[str], opened: set, now: float,
                      pid_alive, clean: bool, retire_exec=None) -> dict[str, int]:
    """Directories come from the explicit Docker name allowlist, never a glob."""
    result = {'eligible_execs': 0, 'removed_files': 0, 'skipped_records': 0}
    if not IDENTIFIER.fullmatch(container):
        raise ValueError('invalid container identity')
    task = task_root / container
    pipes = pipe_root / container
    for directory in (task_root, pipe_root, task, pipes):
        if directory.resolve() != directory or not directory.is_dir():
            raise ValueError('runtime directory missing or redirected')
    for record in task.glob('*.pid'):
        exec_id = record.stem
        if (not IDENTIFIER.fullmatch(exec_id) or exec_id == container
                or exec_id in active):
            continue
        try:
            record_info = old_record(record, fifo=False, opened=opened, now=now)
            descriptor = os.open(record, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            try:
                if identity(os.fstat(descriptor)) != identity(record_info):
                    raise ValueError('PID record changed')
                pid_text = os.read(descriptor, 33).decode('ascii').strip()
            finally:
                os.close(descriptor)
            if not re.fullmatch(r'[1-9][0-9]{0,9}', pid_text):
                raise ValueError('invalid PID record')
            pid = int(pid_text)
            if pid <= 1 or pid_alive(pid):
                raise ValueError('PID is live or reused')
            candidates = []
            for stream in ('stdin', 'stdout', 'stderr'):
                path = pipes / f'{exec_id}-{stream}'
                try:
                    info = old_record(path, fifo=True, opened=opened, now=now)
                except FileNotFoundError:
                    continue
                candidates.append((path, info))
            candidates.append((record, record_info))
            # Check the entire group before unlinking anything; remove the PID
            # last so interruption leaves a discoverable, safe partial cleanup.
            if pid_alive(pid) or any(identity(p.lstat()) != identity(i) for p, i in candidates):
                raise ValueError('runtime group changed')
            result['eligible_execs'] += 1
            if clean:
                # Retire the stopped shim process through containerd first.
                # Unlinking its files alone leaves the in-memory exec record.
                if retire_exec is None or not retire_exec(container, exec_id):
                    raise ValueError('stopped runtime process could not be retired')
                for path, info in candidates:
                    if pid_alive(pid):
                        raise ValueError('PID became live during cleanup')
                    try:
                        current = path.lstat()
                    except FileNotFoundError:
                        # Normal containerd deletion removes its PID record.
                        result['removed_files'] += 1
                        continue
                    if identity(current) != identity(info):
                        raise ValueError('runtime group changed during cleanup')
                    path.unlink()
                    result['removed_files'] += 1
        except (OSError, ValueError, UnicodeError):
            result['skipped_records'] += 1
    return result


def retire_stopped_exec(container: str, exec_id: str) -> bool:
    # Without --force, ctr uses Process.Delete without WithProcessKill. It
    # refuses live processes. Successful deletion returns the old process's
    # exit code (often 137 for a timed-out health probe), with empty stderr.
    try:
        result = subprocess.run(
            ['ctr', '--namespace', 'moby', 'tasks', 'delete', '--exec-id', exec_id, container],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE, timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return ((0 <= result.returncode <= 255 and not result.stderr.strip())
            or b'not found' in result.stderr.lower())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('check', 'clean'))
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise RuntimeError('runtime guard requires root')
    with open('/run/lock/ptw-maintenance.lock', 'r') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('Runtime exec guard deferred: PTW operation is active')
            return
        ids = subprocess.check_output(
            ['docker', 'ps', '-q', '--no-trunc'], text=True,
            stderr=subprocess.DEVNULL, timeout=20,
        ).split()
        if not ids:
            raise RuntimeError('Docker inventory is empty')
        # Request only lifecycle metadata, never container environment/secrets.
        template = ('{"Id":{{json .Id}},"Name":{{json .Name}},'
                    '"Running":{{json .State.Running}},"ExecIDs":{{json .ExecIDs}}}')
        records = [json.loads(line) for line in subprocess.check_output(
            ['docker', 'inspect', '--format', template, *ids], text=True,
            stderr=subprocess.DEVNULL, timeout=20,
        ).splitlines()]
        active = {value for item in records for value in (item.get('ExecIDs') or [])}
        opened = open_inodes()
        totals = {'eligible_execs': 0, 'removed_files': 0, 'skipped_records': 0}
        for item in records:
            if item['Name'].removeprefix('/') not in CONTAINERS or not item['Running']:
                continue
            values = reclaim_container(
                item['Id'], TASK_ROOT, PIPE_ROOT, active=active, opened=opened,
                now=time.time(), pid_alive=lambda pid: Path('/proc', str(pid)).exists(),
                clean=args.mode == 'clean', retire_exec=retire_stopped_exec,
            )
            for key, value in values.items():
                totals[key] += value
        print(json.dumps({'mode': args.mode, **totals}, sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
        # Docker inspection can contain secrets. Never reflect command output.
        print('Runtime exec guard failed closed; inspect its exact runtime paths and locks')
        raise SystemExit(1)
