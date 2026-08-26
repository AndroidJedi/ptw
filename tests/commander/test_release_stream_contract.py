import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class ReleaseStreamContractTests(unittest.TestCase):
    def test_non_tar_artifacts_preserve_exact_size_across_transport(self) -> None:
        publisher = (ROOT / "scripts/publish_ptw_release_serial.sh").read_text()
        deployer = (ROOT / "scripts/deploy_ptw_serial.sh").read_text()
        emit_file = publisher.split("emit_file() {", 1)[1].split("\n}\n", 1)[0]

        self.assertIn("printf 'FILE %s %s %s %s\\n'", emit_file)
        self.assertNotIn('digest=$(sha256_file "$padded")', emit_file)
        self.assertIn("read -r kind name blocks size digest", deployer)
        self.assertIn("size <= blocks * 1048576", deployer)
        truncate = deployer.index('truncate --size "$size" "$artifact_file"')
        checksum = deployer.index('checksum_line=$(sha256sum "$artifact_file")', truncate)
        self.assertLess(truncate, checksum)

    def test_release_has_only_the_clean_reset_path(self) -> None:
        publisher = (ROOT / "scripts/publish_ptw_release_serial.sh").read_text()
        deployer = (ROOT / "scripts/deploy_ptw_serial.sh").read_text()

        self.assertIn('[[ $confirmation == "RESET PTW PRODUCTION" ]]', publisher)
        self.assertIn('[[ $confirmation == "RESET PTW PRODUCTION" ]]', deployer)
        self.assertNotIn("DEPLOY PTW IN PLACE", publisher)
        self.assertNotIn("DEPLOY PTW IN PLACE", deployer)
        self.assertNotIn("preserve the validation artifacts", deployer)
        self.assertEqual(1, deployer.count("reset_ptw.sh"))

    def test_platform_enforcement_and_canaries_precede_reset(self) -> None:
        deployer = (ROOT / "scripts/deploy_ptw_serial.sh").read_text()
        rollout = deployer.index('export PTW_PLATFORM_IMAGE_TAG=$release_tag')
        compose_render = deployer.index('config > "$rendered_platform_compose"', rollout)
        worker = deployer.index('commander-worker', rollout)
        api = deployer.index('commander-api', worker)
        bridge_canary = deployer.index('validation_pipeline.verify_bridge_contract', api)
        pexels_canary = deployer.index('validation_pipeline.verify_pexels', bridge_canary)
        reset = deployer.index('reset_ptw.sh', pexels_canary)

        self.assertLess(compose_render, worker)
        self.assertLess(worker, api)
        self.assertLess(api, bridge_canary)
        self.assertLess(bridge_canary, pexels_canary)
        self.assertLess(pexels_canary, reset)

    def test_release_does_not_deploy_a_landing_site(self) -> None:
        publisher = (ROOT / "scripts/publish_ptw_release_serial.sh").read_text()
        self.assertNotIn("firebase.natal-placeholder.json", publisher)
        self.assertEqual(1, publisher.count("firebase deploy --only hosting"))


if __name__ == "__main__":
    unittest.main()
