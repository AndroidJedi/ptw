#!/usr/bin/env python3
"""Bound PTW recovery copies without touching application authority or secrets."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

GIB = 1024 ** 3
BACKUP_ROOT = Path('/opt/ptw/commander-backups')
REPOSITORY = Path('/root/ptw')
SNAPSHOT_NAME = re.compile(r'20\d{6}T\d{6}Z\Z')
FILES = {'database.dump', 'assets.tar.gz', 'git-revision.txt', 'policies.json', 'metadata.json'}
KEEP = 7
MIN_KEEP = 2
MAX_BYTES = 4 * GIB
RESERVE = 3 * GIB


def sha256(path: Path) -> str:
    with path.open('rb') as source:
        digest = hashlib.sha256()
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def manifest(path: Path, verify: bool = False) -> dict[str, str]:
    """Accept only complete, closed manifests; never follow recovery symlinks."""
    if path.is_symlink() or not path.is_dir():
        raise RuntimeError('Backup is not a plain directory')
    index = path / 'SHA256SUMS'
    if index.is_symlink() or not index.is_file() or index.stat().st_size > 4096:
        raise RuntimeError('Backup has no bounded completion manifest')
    entries = {}
    for line in index.read_text().splitlines():
        match = re.fullmatch(r'([0-9a-f]{64})  ([a-zA-Z0-9_.-]+)', line)
        if not match or match[2] not in FILES or match[2] in entries:
            raise RuntimeError('Backup manifest contains an unexpected entry')
        entries[match[2]] = match[1]
    if 'database.dump' not in entries or set(p.name for p in path.iterdir()) != set(entries) | {'SHA256SUMS'}:
        raise RuntimeError('Backup files do not match its completion manifest')
    for name, digest in entries.items():
        target = path / name
        if target.is_symlink() or not target.is_file() or target.stat().st_size == 0:
            raise RuntimeError('Backup contains an invalid file')
        if verify and sha256(target) != digest:
            raise RuntimeError('Backup checksum mismatch; retention refused')
    return entries


def snapshots(root: Path) -> list[tuple[Path, int]]:
    result = []
    for path in root.iterdir():
        if not SNAPSHOT_NAME.fullmatch(path.name):
            continue
        try:
            entries = manifest(path)
        except RuntimeError:
            # An old incomplete recovery point needs explicit inspection, not
            # automatic deletion. New failed attempts clean their own staging.
            continue
        result.append((path, sum((path / name).stat().st_size for name in entries)
                       + (path / 'SHA256SUMS').stat().st_size))
    return sorted(result, key=lambda item: item[0].name, reverse=True)


def maintain(root: Path, *, keep: int = KEEP, max_bytes: int = MAX_BYTES,
             reserve: int = RESERVE, free=None) -> list[str]:
    free = free or (lambda: shutil.disk_usage(root).free)
    points = snapshots(root)
    retained = list(points)
    selected = []
    total = sum(size for _, size in points)
    available = free()
    while len(retained) > MIN_KEEP and (len(retained) > keep or total > max_bytes or available < reserve):
        point, size = retained.pop()
        selected.append(point)
        total -= size
        available += size
    if selected:
        # Verify the newest two complete replacements before deleting any copy.
        for point, _ in retained[:MIN_KEEP]:
            manifest(point, verify=True)
        for point in selected:
            shutil.rmtree(point)
            print('Expired recovery copy:', point.name, flush=True)
    if free() < reserve:
        raise RuntimeError('Storage reserve below 3 GiB; new backup refused; inspect disk usage')
    if total > max_bytes:
        raise RuntimeError('Newest recovery copies exceed the storage budget; move backups off-host')
    return [point.name for point in selected]


def copy_with_reserve(source, target, root: Path, *, reserve: int = RESERVE,
                      max_bytes: int = MAX_BYTES, free=None) -> None:
    free = free or (lambda: shutil.disk_usage(root).free)
    written = 0
    for chunk in iter(lambda: source.read(1024 * 1024), b''):
        if written + len(chunk) > max_bytes:
            raise RuntimeError('Recovery export exceeds its byte budget; move backups off-host')
        if free() - len(chunk) < reserve:
            raise RuntimeError('Backup stopped before exhausting the storage reserve')
        target.write(chunk)
        target.flush()
        written += len(chunk)


def command_to_file(command: list[str], target: Path, root: Path, max_bytes: int) -> None:
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        with target.open('xb') as output:
            copy_with_reserve(process.stdout, output, root, max_bytes=max_bytes)
            os.fsync(output.fileno())
        if process.wait() != 0:
            raise RuntimeError('Recovery export failed; incomplete attempt removed')
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        process.stdout.close()


def backup(root: Path) -> None:
    maintain(root)
    current = snapshots(root)
    estimate = max(512 * 1024 ** 2, current[0][1] * 2 if current else 0)
    if shutil.disk_usage(root).free < RESERVE + estimate:
        raise RuntimeError('Insufficient headroom for the next recovery copy; backup refused')
    # Leave room for two complete recovery points, including bounded metadata.
    export_budget = MAX_BYTES - (current[0][1] if current else 0) - 1024 * 1024
    if export_budget <= 0:
        raise RuntimeError('Recovery byte budget exhausted; move backups off-host')
    revision = (REPOSITORY / '.local/deployed-revision').read_text().strip()
    if not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise RuntimeError('Accepted revision marker is unavailable')
    with tempfile.TemporaryDirectory(prefix='.incomplete-', dir=root) as temporary:
        staging = Path(temporary)
        command_to_file(['docker', 'exec', 'ptw-commander-db-1', 'pg_dump', '-U', 'ptw_commander',
                         '-d', 'ptw_commander', '--format=custom', '--no-owner', '--no-acl'],
                        staging / 'database.dump', root, export_budget)
        export_budget -= (staging / 'database.dump').stat().st_size
        # Retain historical file authority as well as the complete current DB.
        mount = subprocess.check_output(['docker', 'volume', 'inspect', 'ptw_commander-assets',
                                        '--format', '{{.Mountpoint}}'], text=True).strip()
        assets = Path(mount)
        if not assets.is_dir() or assets.is_symlink() or not str(assets).startswith('/var/lib/docker/volumes/'):
            raise RuntimeError('Historical assets volume cannot be resolved safely')
        command_to_file(['tar', '-C', str(assets), '-czf', '-', '.'], staging / 'assets.tar.gz', root, export_budget)
        (staging / 'git-revision.txt').write_text(revision + '\n')
        (staging / 'metadata.json').write_text(json.dumps({
            'schema': 'ptw.recovery.v1', 'accepted_revision': revision,
            'database': 'ptw_commander', 'historical_volume': 'ptw_commander-assets',
        }, sort_keys=True) + '\n')
        names = sorted(path.name for path in staging.iterdir())
        (staging / 'SHA256SUMS').write_text(''.join(f'{sha256(staging / name)}  {name}\n' for name in names))
        manifest(staging, verify=True)
        for path in staging.iterdir():
            path.chmod(0o600)
        destination = root / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        if destination.exists():
            raise RuntimeError('Recovery timestamp already exists')
        staging.rename(destination)
        print('Completed recovery copy:', destination.name, flush=True)
    maintain(root)


@contextmanager
def maintenance_lock(path: Path = Path('/run/lock/ptw-maintenance.lock')):
    with path.open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Another PTW maintenance operation is active') from None
        yield


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('check', 'maintain', 'backup'))
    arguments = parser.parse_args()
    if os.geteuid() != 0 or BACKUP_ROOT.is_symlink() or BACKUP_ROOT.resolve() != BACKUP_ROOT:
        raise RuntimeError('Storage guard requires root and its exact backup allowlist')
    os.umask(0o077)
    BACKUP_ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
    with maintenance_lock():
        if arguments.mode == 'backup':
            backup(BACKUP_ROOT)
        elif arguments.mode == 'maintain':
            maintain(BACKUP_ROOT)
        elif shutil.disk_usage(BACKUP_ROOT).free < RESERVE:
            raise RuntimeError('Storage reserve below 3 GiB')
        print('Storage guard passed; free GiB:', round(shutil.disk_usage(BACKUP_ROOT).free / GIB, 2), flush=True)


if __name__ == '__main__':
    try:
        main()
    except RuntimeError as error:
        print('Storage guard failed:', str(error), flush=True)
        raise SystemExit(1)
    except (OSError, subprocess.SubprocessError):
        # Never reflect paths, credentials, pg_dump output or provider data.
        print('Storage guard failed: inspect headroom, recovery manifests and the maintenance lock.', flush=True)
        raise SystemExit(1)
