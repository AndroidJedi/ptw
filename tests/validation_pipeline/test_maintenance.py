import fcntl
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from fastapi import BackgroundTasks, FastAPI
from fastapi.testclient import TestClient

from validation_pipeline.maintenance import (
    MaintenanceWriteGuard, analytics_cycle, verify_maintenance_signal, write_slot,
)


class MaintenanceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "maintenance.lock"
        self.path.touch()
        environment = patch.dict(os.environ, {"PTW_MAINTENANCE_LOCK_PATH": str(self.path)})
        environment.start()
        self.addCleanup(environment.stop)

    def test_runtime_writes_hold_the_deploy_lock_until_background_work_finishes(self):
        app = FastAPI()
        app.add_middleware(MaintenanceWriteGuard)
        completed = []

        def background_write():
            with self.path.open("rb") as deployment:
                with self.assertRaises(BlockingIOError):
                    fcntl.flock(deployment, fcntl.LOCK_EX | fcntl.LOCK_NB)
            completed.append(True)

        @app.post("/write")
        def write(background: BackgroundTasks):
            background.add_task(background_write)
            return {"accepted": True}

        with TestClient(app) as client:
            self.assertEqual(200, client.post("/write").status_code)
        self.assertEqual([True], completed)
        with self.path.open("rb") as deployment:
            fcntl.flock(deployment, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_deployment_blocks_writes_and_analytics_then_resumes_without_touching_reads_or_stop(self):
        app = FastAPI()
        app.add_middleware(MaintenanceWriteGuard)
        writes = []

        @app.get("/read")
        def read():
            return {"readable": True}

        @app.post("/write")
        def write():
            writes.append(True)
            return {"saved": True}

        @app.post("/internal/emergency-stop")
        def stop():
            return {"stopped": True}

        analytics = Mock()
        with TestClient(app) as client, self.path.open("rb") as deployment:
            fcntl.flock(deployment, fcntl.LOCK_EX | fcntl.LOCK_NB)
            verify_maintenance_signal()
            response = client.post("/write")
            self.assertEqual(503, response.status_code)
            self.assertEqual("30", response.headers["retry-after"])
            self.assertEqual([], writes)
            self.assertEqual(200, client.get("/read").status_code)
            self.assertEqual(200, client.post("/internal/emergency-stop").status_code)
            self.assertIsNone(analytics_cycle(analytics))
            analytics.maintain.assert_not_called()
            fcntl.flock(deployment, fcntl.LOCK_UN)
            self.assertEqual(200, client.post("/write").status_code)
            analytics_cycle(analytics)
            analytics.maintain.assert_called_once_with()
        self.assertEqual([True], writes)

    def test_missing_configured_mount_fails_closed_and_rejects_readiness(self):
        self.path.unlink()
        with write_slot() as allowed:
            self.assertFalse(allowed)
        with self.assertRaises(FileNotFoundError):
            verify_maintenance_signal()

    def test_local_runtime_without_deployment_mount_keeps_writes_available(self):
        with patch.dict(os.environ, {"PTW_MAINTENANCE_LOCK_PATH": ""}):
            verify_maintenance_signal()
            with write_slot() as allowed:
                self.assertTrue(allowed)
