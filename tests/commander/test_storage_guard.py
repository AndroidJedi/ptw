"""Exercise real recovery directories, integrity guards and low-space writes."""
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import ptw_storage_guard as guard


class StorageGuardTests(unittest.TestCase):
    def point(self, root, day, content=b'recovery'):
        path = root / f'202609{day:02d}T031701Z'
        path.mkdir()
        (path / 'database.dump').write_bytes(content)
        (path / 'SHA256SUMS').write_text(f'{guard.sha256(path / "database.dump")}  database.dump\n')
        return path

    def test_dated_points_are_pruned_by_count_with_latest_two_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            points = [self.point(root, day) for day in range(1, 11)]
            expired = guard.maintain(root, keep=3, max_bytes=10000, reserve=0)
            self.assertEqual(7, len(expired))
            self.assertEqual([False] * 7 + [True] * 3, [path.exists() for path in points])

    def test_byte_budget_applies_even_below_the_count_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            points = [self.point(root, day, b'x' * 100) for day in range(1, 5)]
            guard.maintain(root, max_bytes=400, reserve=0)
            self.assertEqual([False, False, True, True], [path.exists() for path in points])

    def test_corrupt_replacement_prevents_any_retention_deletion(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            points = [self.point(root, day) for day in range(1, 5)]
            (points[-1] / 'database.dump').write_bytes(b'tampered')
            with self.assertRaisesRegex(RuntimeError, 'checksum'):
                guard.maintain(root, keep=2, reserve=0)
            self.assertTrue(all(path.exists() for path in points))

    def test_incomplete_and_symlinked_points_are_never_deleted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            incomplete = root / '20260801T031701Z'
            incomplete.mkdir()
            outside = root / 'outside'
            outside.mkdir()
            linked = root / '20260802T031701Z'
            linked.symlink_to(outside, target_is_directory=True)
            for day in range(1, 5):
                self.point(root, day)
            guard.maintain(root, keep=2, reserve=0)
            self.assertTrue(incomplete.exists())
            self.assertTrue(linked.is_symlink())
            self.assertTrue(outside.exists())

    def test_manifest_cannot_read_outside_the_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            point = self.point(root, 1)
            (point / 'SHA256SUMS').write_text('a' * 64 + '  ../secret\n')
            with self.assertRaises(RuntimeError):
                guard.manifest(point, verify=True)

    def test_low_space_write_stops_before_consuming_the_reserve(self):
        output = io.BytesIO()
        with self.assertRaisesRegex(RuntimeError, 'reserve'):
            guard.copy_with_reserve(io.BytesIO(b'x' * 20), output, Path('/'), reserve=100, free=lambda: 110)
        self.assertEqual(b'', output.getvalue())

    def test_low_space_cannot_delete_the_last_two_backups(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            points = [self.point(root, day) for day in range(1, 3)]
            with self.assertRaisesRegex(RuntimeError, 'reserve'):
                guard.maintain(root, reserve=100, free=lambda: 10)
            self.assertTrue(all(path.exists() for path in points))

    def test_export_byte_budget_rejects_growth_before_writing(self):
        output = io.BytesIO()
        with self.assertRaisesRegex(RuntimeError, 'byte budget'):
            guard.copy_with_reserve(io.BytesIO(b'x' * 20), output, Path('/'),
                                    reserve=0, max_bytes=10, free=lambda: 100)
        self.assertEqual(b'', output.getvalue())

    def test_lock_refuses_a_concurrent_writer_and_releases_after_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            lock = Path(directory) / 'maintenance.lock'
            with self.assertRaisesRegex(RuntimeError, 'test failure'):
                with guard.maintenance_lock(lock):
                    with self.assertRaisesRegex(RuntimeError, 'active'):
                        with guard.maintenance_lock(lock):
                            self.fail('Concurrent maintenance obtained the lock')
                    raise RuntimeError('test failure')
            with guard.maintenance_lock(lock):
                pass

    def test_failed_backup_removes_its_partial_attempt_and_preserves_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository = root / 'repo'
            (repository / '.local').mkdir(parents=True)
            (repository / '.local/deployed-revision').write_text('a' * 40)
            backups = root / 'backups'
            backups.mkdir()
            original = [self.point(backups, day) for day in (1, 2)]
            def fail_export(command, target, backup_root, budget):
                target.write_bytes(b'partial database')
                raise RuntimeError('export failed')
            with patch.object(guard, 'REPOSITORY', repository), \
                    patch.object(guard, 'command_to_file', fail_export), \
                    patch.object(guard.shutil, 'disk_usage', return_value=guard.shutil._ntuple_diskusage(100 * guard.GIB, 0, 100 * guard.GIB)):
                with self.assertRaisesRegex(RuntimeError, 'export failed'):
                    guard.backup(backups)
            self.assertEqual({path.name for path in original}, {path.name for path in backups.iterdir()})
