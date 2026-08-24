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


if __name__ == "__main__":
    unittest.main()
