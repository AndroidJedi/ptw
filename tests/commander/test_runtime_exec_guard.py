from pathlib import Path
import importlib.util
import os
import tempfile
import time
import unittest


SPEC = importlib.util.spec_from_file_location(
    'runtime_guard', Path(__file__).resolve().parents[2] / 'scripts/ptw_runtime_exec_guard.py',
)
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)


class RuntimeExecGuardTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.tasks = self.root / 'tasks'
        self.pipes = self.root / 'pipes'
        self.container = 'a' * 64
        self.exec_id = 'b' * 64
        (self.tasks / self.container).mkdir(parents=True)
        (self.pipes / self.container).mkdir(parents=True)
        self.record = self.tasks / self.container / f'{self.exec_id}.pid'
        self.record.write_text('99999999')
        self.streams = [self.pipes / self.container / f'{self.exec_id}-{name}'
                        for name in ('stdout', 'stderr')]
        for path in self.streams:
            os.mkfifo(path)
        self.now = time.time()
        for path in [self.record, *self.streams]:
            os.utime(path, (self.now - 2 * guard.MIN_AGE,) * 2)

    def run_guard(self, *, clean=True, active=None, opened=None, alive=None, retire=None):
        return guard.reclaim_container(
            self.container, self.tasks, self.pipes, active=active or set(),
            opened=opened or set(), now=self.now,
            pid_alive=alive or (lambda _pid: False), clean=clean,
            retire_exec=retire or (lambda _container, _exec: True),
        )

    def assert_preserved(self):
        self.assertTrue(self.record.exists())
        self.assertTrue(all(path.exists() for path in self.streams))

    def test_check_then_clean_only_closed_old_exec_group(self):
        permanent = self.tasks / self.container / 'init.pid'
        permanent.write_text('1')
        self.assertEqual(self.run_guard(clean=False)['eligible_execs'], 1)
        self.assert_preserved()
        self.assertEqual(self.run_guard()['removed_files'], 3)
        self.assertFalse(self.record.exists())
        self.assertEqual(permanent.read_text(), '1')
        self.assertEqual(self.run_guard()['removed_files'], 0)

    def test_live_pid_and_active_exec_are_never_removed(self):
        self.assertEqual(self.run_guard(alive=lambda _pid: True)['removed_files'], 0)
        self.assert_preserved()
        self.assertEqual(self.run_guard(active={self.exec_id})['removed_files'], 0)
        self.assert_preserved()

    def test_open_descriptor_preserves_entire_group(self):
        for path in [self.record, *self.streams]:
            info = path.stat()
            self.assertEqual(self.run_guard(opened={(info.st_dev, info.st_ino)})['removed_files'], 0)
            self.assert_preserved()

    def test_recent_entry_preserves_entire_group(self):
        os.utime(self.streams[1], (self.now,) * 2)
        self.assertEqual(self.run_guard()['removed_files'], 0)
        self.assert_preserved()

    def test_regular_stream_file_and_symlink_are_rejected(self):
        self.streams[1].unlink()
        self.streams[1].write_text('not a FIFO')
        os.utime(self.streams[1], (self.now - 2 * guard.MIN_AGE,) * 2)
        self.assertEqual(self.run_guard()['removed_files'], 0)
        self.assert_preserved()
        self.streams[1].unlink()
        self.streams[1].symlink_to(self.record)
        self.assertEqual(self.run_guard()['removed_files'], 0)
        self.assert_preserved()

    def test_invalid_or_reused_pid_is_rejected(self):
        for value in ('0', '1', '-42', 'invalid', '9' * 33):
            self.record.write_text(value)
            os.utime(self.record, (self.now - 2 * guard.MIN_AGE,) * 2)
            self.assertEqual(self.run_guard()['removed_files'], 0)
            self.assert_preserved()

    def test_redirected_directory_is_rejected(self):
        redirected = self.root / 'redirect'
        redirected.symlink_to(self.tasks, target_is_directory=True)
        with self.assertRaises(ValueError):
            guard.reclaim_container(
                self.container, redirected, self.pipes, active=set(), opened=set(),
                now=self.now, pid_alive=lambda _pid: False, clean=True,
            )
        self.assert_preserved()

    def test_pid_becoming_live_during_check_preserves_group(self):
        states = iter((False, True))
        self.assertEqual(self.run_guard(alive=lambda _pid: next(states))['removed_files'], 0)
        self.assert_preserved()

    def test_failed_runtime_retirement_preserves_group(self):
        self.assertEqual(self.run_guard(retire=lambda _c, _e: False)['removed_files'], 0)
        self.assert_preserved()

    def test_native_cleanup_can_remove_pid_before_fifo_cleanup(self):
        def retire(container, exec_id):
            self.assertEqual((container, exec_id), (self.container, self.exec_id))
            self.record.unlink()
            return True
        self.assertEqual(self.run_guard(retire=retire)['removed_files'], 3)
        self.assertFalse(self.record.exists())
        self.assertTrue(all(not path.exists() for path in self.streams))
