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


if __name__ == "__main__":
    unittest.main()
