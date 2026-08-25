import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class ReleaseStreamContractTests(unittest.TestCase):
    def test_non_tar_artifacts_preserve_exact_size_across_block_transport(self) -> None:
        publisher = (ROOT / "scripts/publish_ptw_release_serial.sh").read_text()
        deployer = (ROOT / "scripts/deploy_ptw_serial.sh").read_text()
        emit_file = publisher.split("emit_file() {", 1)[1].split("\n}\n\nemit_image", 1)[0]

        self.assertIn("printf 'FILE %s %s %s %s\\n'", emit_file)
        self.assertNotIn('digest=$(sha256_file "$padded")', emit_file)
        self.assertIn("read -r kind name blocks size digest", deployer)
        self.assertIn("size <= blocks * 1048576", deployer)

        truncate = deployer.index('truncate --size "$size" "$artifact_file"')
        checksum = deployer.index('checksum_line=$(sha256sum "$artifact_file")', truncate)
        self.assertLess(truncate, checksum)

    def test_in_place_release_never_enters_the_reset_path(self) -> None:
        publisher = (ROOT / "scripts/publish_ptw_release_serial.sh").read_text()
        deployer = (ROOT / "scripts/deploy_ptw_serial.sh").read_text()

        self.assertIn('"DEPLOY PTW IN PLACE"', publisher)
        self.assertIn('confirmation == "RESET PTW PRODUCTION"', deployer)
        branch = deployer.split('if [[ $confirmation == "RESET PTW PRODUCTION" ]]', 1)[1]
        reset_arm, in_place_arm = branch.split("else", 1)
        self.assertIn("reset_ptw.sh", reset_arm)
        self.assertNotIn("reset_ptw.sh", in_place_arm.split("fi", 1)[0])
        self.assertIn("commander-migrate", in_place_arm)
        self.assertIn("in-place deployment did not preserve", in_place_arm)

    def test_platform_worker_precedes_studio_capable_api(self) -> None:
        deployer = (ROOT / "scripts/deploy_ptw_serial.sh").read_text()
        rollout = deployer.index('export PTW_PLATFORM_IMAGE_TAG=$release_tag')
        worker = deployer.index('commander-worker', rollout)
        api = deployer.index('commander-api', worker)
        canary = deployer.index('validation_pipeline.verify_bridge_contract', api)

        self.assertLess(worker, api)
        self.assertLess(api, canary)

    def test_in_place_startup_failure_restores_the_prior_application_tag(self) -> None:
        deployer = (ROOT / "scripts/deploy_ptw_serial.sh").read_text()

        self.assertIn("old_application_tag=", deployer)
        self.assertIn("restore_application_images()", deployer)
        restore = deployer.split("restore_application_images()", 1)[1].split("}", 1)[0]
        self.assertIn("export PTW_IMAGE_TAG=$old_application_tag", restore)
        for failure in (
            "Commander startup failed",
            "Validation startup failed",
            "Owner Gateway startup failed",
            "post-migration preservation verification failed",
            "application readiness failed",
        ):
            branch = deployer.split(failure, 1)[0].rsplit("if !", 1)[-1]
            self.assertIn("restore_application_images", branch)


if __name__ == "__main__":
    unittest.main()
