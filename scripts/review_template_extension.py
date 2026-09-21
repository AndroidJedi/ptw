#!/usr/bin/env python3
"""Prepare/verify/apply an owner-reviewed reusable capability in an isolated snapshot.

No HTTP endpoint calls this tool. Prepare captures all current source, including
uncommitted work. Apply requires the exact review digest and rejects concurrent edits.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from validation_pipeline.template_components import canonical, sha
from validation_pipeline.template_extensions import allowed_path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_files(root):
    result = {}
    for path in root.rglob('*'):
        relative = path.relative_to(root)
        if any(p in {'.git', '.local', '.venv', 'node_modules', 'dist', '__pycache__', 'test-results', 'playwright-report'} for p in relative.parts):
            continue
        if path.is_symlink():
            raise ValueError(f'Source symlink rejected: {relative}')
        if path.is_file():
            result[str(relative)] = digest(path)
    return result


def changes(snapshot, baseline):
    current = source_files(snapshot)
    changed = sorted(k for k in set(current) | set(baseline) if current.get(k) != baseline.get(k))
    if not changed or any(not allowed_path(k) or k not in current for k in changed):
        raise ValueError('Capability extension contains no changes, deletes source, or writes outside its allowlist')
    return {k: current[k] for k in changed}


def atomic_write(path, data, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
        temporary_path = Path(temporary.name)
        temporary.write(data)
    try:
        temporary_path.chmod(mode)
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def apply_review(snapshot, root, state, review_sha256):
    changed = changes(snapshot, state['baseline'])
    if review_sha256 != state.get('review_sha256') or not review_sha256 or changed != state['verified']['sources'] or review_sha256 != sha(state['verified']):
        raise ValueError('Apply requires the exact verified review digest; rerun verification after changes')
    preview = snapshot / '.local/template-capability-preview.png'
    if preview.is_symlink() or not preview.is_file() or digest(preview) != state['verified']['visual_review_sha256']:
        raise ValueError('The reviewed visual preview changed; rerun verification and inspection')
    originals = {}
    for name in changed:
        current = root / name
        if current.is_symlink() or not current.resolve().is_relative_to(root.resolve()) or (digest(current) if current.is_file() else None) != state['baseline'].get(name):
            raise ValueError(f'Concurrent source change: {name}')
        originals[name] = (current.read_bytes(), current.stat().st_mode & 0o777) if current.is_file() else None
    receipt = root / 'validation_pipeline/studio_components/capability_reviews' / f"{state['capability']}.json"
    if receipt.exists() or receipt.is_symlink() or not receipt.resolve().is_relative_to(root.resolve()):
        raise ValueError('Capability review is immutable; create a new named capability version')
    applied = []
    try:
        for name in changed:
            applied.append(name)
            atomic_write(root / name, (snapshot / name).read_bytes(), (snapshot / name).stat().st_mode & 0o777)
        atomic_write(receipt, (canonical(state['verified']) + '\n').encode())
    except Exception:
        receipt.unlink(missing_ok=True)
        for name in reversed(applied):
            original = originals[name]
            if original is None:
                (root / name).unlink(missing_ok=True)
            else:
                atomic_write(root / name, *original)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'verify', 'apply'])
    parser.add_argument('directory', type=Path)
    parser.add_argument('--capability')
    parser.add_argument('--review-sha256')
    args = parser.parse_args()
    directory = args.directory.resolve()
    if directory == ROOT or directory.is_relative_to(ROOT / 'validation_pipeline'):
        raise ValueError('Use a separate disposable review directory')
    snapshot = directory / 'workspace'
    state_path = directory / 'review.json'
    if args.action == 'prepare':
        import re
        if not args.capability or not re.fullmatch(r'[a-z][a-z0-9_]{2,59}', args.capability):
            raise ValueError('A reusable capability name is required')
        directory.mkdir(parents=True, exist_ok=False)
        names = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=ROOT).decode().split('\0')
        baseline = {}
        for name in filter(None, names):
            source = ROOT / name
            if not source.is_file():
                continue
            if source.is_symlink():
                raise ValueError('Source symlinks cannot enter a capability snapshot')
            target = snapshot / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            baseline[name] = digest(source)
        for name in ('.venv', 'apps/commander-web/node_modules'):
            (snapshot / name).symlink_to(ROOT / name, target_is_directory=True)
        state_path.write_text(canonical({'capability': args.capability, 'baseline': baseline}))
        print(f'Prepared isolated source: {snapshot}. Use Commander GOD mode on this directory; no production operations.')
        return
    state = json.loads(state_path.read_text())
    changed = changes(snapshot, state['baseline'])
    if args.action == 'verify':
        expected_test = f"tests/validation_pipeline/test_template_capability_{state['capability']}.py"
        if expected_test not in changed:
            raise ValueError('Add focused reusable-capability geometry tests')
        commands = [[str(ROOT / '.venv/bin/python'), '-m', 'unittest', 'discover', '-s', 'tests/validation_pipeline', '-p', 'test_template*.py', '-v'],
                    [str(ROOT / '.venv/bin/python'), 'skills/studio-ui-visual-audit/scripts/audit_post_studio.py']]
        if any(k.startswith('apps/') for k in changed):
            commands += [['npm', '--prefix', 'apps/commander-web', 'test'], ['npm', '--prefix', 'apps/commander-web', 'run', 'build']]
        for command in commands:
            subprocess.run(command, cwd=snapshot, check=True, timeout=300)
        preview = snapshot / '.local/template-capability-preview.png'
        if not preview.is_file() or preview.is_symlink():
            raise ValueError('Focused tests must render the actual capability to .local/template-capability-preview.png for owner inspection')
        from PIL import Image
        with Image.open(preview) as image:
            image.verify()
        verified = {'capability': state['capability'], 'sources': changed, 'verification': 'passed', 'visual_review_sha256': digest(preview)}
        state.update(verified=verified, review_sha256=sha(verified))
        state_path.write_text(canonical(state))
        print(f"Inspect {preview} at full resolution, then apply --review-sha256 {state['review_sha256']}")
        return
    apply_review(snapshot, ROOT, state, args.review_sha256)
    print('Applied reviewed local source. Restart the local API and resume the template run. Nothing deployed.')


if __name__ == '__main__':
    main()
