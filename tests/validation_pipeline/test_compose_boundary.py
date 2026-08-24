import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class ValidationComposeBoundaryTests(unittest.TestCase):
    def test_validation_container_receives_only_explicit_runtime_settings(self) -> None:
        compose = (ROOT / "docker-compose.validation.yml").read_text()

        self.assertNotIn("env_file:", compose)
        for setting in (
            "DATABASE_URL",
            "OWNER_GATEWAY_BRIDGE_TOKEN",
            "VALIDATION_LLM_BRIDGE_URL",
            "LLM_BRIDGE_TOKEN",
            "VALIDATION_LLM_MODEL",
            "PRODUCT_BRIEF_SKILL_PATH",
            "AD_CREATIVE_SKILL_PATH",
            "PEXELS_API_KEY",
        ):
            self.assertIn(f"      {setting}:", compose)

        for retired_prefix in ("DATAFORSEO_", "POSITIONING_", "LANDING_", "YOUTUBE_"):
            self.assertNotIn(retired_prefix, compose)


if __name__ == "__main__":
    unittest.main()
