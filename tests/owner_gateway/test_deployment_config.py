from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class DeploymentConfigTests(unittest.TestCase):
    def test_idea_service_uses_an_isolated_compose_project(self) -> None:
        compose = (ROOT / "docker-compose.idea-generation.yml").read_text()

        self.assertTrue(compose.startswith("name: ptw-idea-generation\n"))
        self.assertNotEqual(ROOT.name, "ptw-idea-generation")
        self.assertIn("aliases: [ptw-idea-api]", compose)
        self.assertIn("name: ptw_default", compose)
        self.assertIn(
            "LAVAL_TELEGRAM_NOTIFICATIONS_ENABLED: ${LAVAL_TELEGRAM_NOTIFICATIONS_ENABLED:-true}",
            compose,
        )

    def test_one_gigabyte_profile_retires_workers_and_tunes_commander_postgres(self) -> None:
        compose = (ROOT / "docker-compose.commander.yml").read_text()
        self.assertIn("profiles: [retired-outbound]", compose)
        self.assertIn("profiles: [retired-creative]", compose)
        self.assertGreaterEqual(compose.count("OUTBOUND_NOTIFICATIONS_ENABLED"), 2)
        self.assertGreaterEqual(compose.count("CREATIVE_RUNTIME_ENABLED"), 2)
        for value in (
            "shared_buffers=48MB", "effective_cache_size=192MB", "work_mem=1MB",
            "maintenance_work_mem=32MB", "max_connections=20",
            "autovacuum_max_workers=1",
        ):
            self.assertIn(value, compose)

    def test_production_release_is_locked_prebuilt_and_serial(self) -> None:
        deploy = (ROOT / "scripts/deploy_ptw_serial.sh").read_text()
        publish = (ROOT / "scripts/publish_ptw_release_serial.sh").read_text()
        self.assertIn("/run/lock/ptw-maintenance.lock", deploy)
        self.assertIn("flock -n 9", deploy)
        self.assertNotIn("docker build", deploy)
        self.assertNotIn("xargs -P", deploy)
        self.assertNotIn("GNU Parallel", deploy)
        self.assertIn("export LAVAL_TELEGRAM_NOTIFICATIONS_ENABLED=true", deploy)
        self.assertEqual(1, publish.count("ssh -i"))
        self.assertLess(deploy.index("receive_image commander"), deploy.index("receive_image idea-generation"))
        self.assertLess(deploy.index("receive_image idea-generation"), deploy.index("receive_image owner-gateway"))
        for service in ("commander-db", "commander-api", "idea-generation-api", "owner-gateway"):
            self.assertIn(f"--no-deps --wait --no-build {service}", deploy)


if __name__ == "__main__":
    unittest.main()
