import unittest
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class ReleaseStreamContractTests(unittest.TestCase):
    def test_skill_verifier_ignores_generated_python_cache_artifacts(self) -> None:
        script = ROOT / "scripts/verify_ptw_skills.py"
        spec = importlib.util.spec_from_file_location("verify_ptw_skills", script)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        self.assertTrue(module.is_generated_skill_artifact(Path("skill/__pycache__")))
        self.assertTrue(module.is_generated_skill_artifact(Path("skill/__pycache__/audit.cpython-313.pyc")))
        self.assertTrue(module.is_generated_skill_artifact(Path("skill/audit.pyo")))
        self.assertFalse(module.is_generated_skill_artifact(Path("skill/scripts/audit.py")))

    def test_public_auditor_resolves_current_vite_lazy_bundle_forms(self) -> None:
        script = ROOT / "skills/ptw-owner-console-incident/scripts/audit_live_owner_console.py"
        spec = importlib.util.spec_from_file_location("audit_live_owner_console", script)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        origin = "https://owner.example"
        entry = f"{origin}/assets/index-main.js"
        self.assertEqual(
            f"{origin}/assets/App-lazy.js",
            module.resolve_app_bundle_url(origin, entry, 'import("./App-lazy.js")'),
        )
        self.assertEqual(
            f"{origin}/assets/App-lazy.js",
            module.resolve_app_bundle_url(origin, entry, '"assets/App-lazy.js"'),
        )

    def test_dependency_audit_exercises_schema_bound_worker_auth(self) -> None:
        audit = (
            ROOT
            / "skills/ptw-owner-console-incident/scripts/audit_vps_owner_dependencies.sh"
        ).read_text()

        self.assertIn('"--output-schema", str(schema)', audit)
        self.assertIn("stdout=subprocess.DEVNULL", audit)
        self.assertIn("stderr=subprocess.DEVNULL", audit)
        self.assertIn('json.loads(output.read_text(encoding="utf-8")) == {"ready": True}', audit)
        self.assertIn("*/ptw-worker-credential", audit)
        self.assertIn("Platform worker Codex credential mount is stale", audit)
        self.assertIn('"$published_credential_digest" = "$mounted_credential_digest"', audit)
        self.assertNotIn("print(completed.stdout", audit)
        self.assertNotIn("print(completed.stderr", audit)

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

    def test_reset_postcondition_covers_every_landing_table(self) -> None:
        reset = (ROOT / "scripts/reset_ptw.sh").read_text()
        for table in (
            "landing_workspaces",
            "landing_workspace_files",
            "landing_assets",
            "landing_generation_runs",
            "landing_versions",
            "landing_checkpoints",
            "landing_skill_snapshots",
            "landing_learning_proposals",
        ):
            self.assertIn(f"(SELECT count(*) FROM {table})", reset)

    def test_reset_and_schema_checks_cover_every_meta_ads_table(self) -> None:
        reset = (ROOT / "scripts/reset_ptw.sh").read_text()
        schema = (ROOT / "scripts/verify_ptw_brief_schema.sh").read_text()
        for table in (
            "meta_ads_preset_versions",
            "meta_ads_workspaces",
            "meta_ads_audience_versions",
            "meta_ads_deployments",
            "meta_ads_stage_runs",
            "meta_ads_status_snapshots",
        ):
            self.assertIn(table, reset)
            self.assertIn(table, schema)

    def test_meta_token_is_a_validation_only_file_secret(self) -> None:
        compose = (ROOT / "docker-compose.validation.yml").read_text()
        gateway = (ROOT / "docker-compose.commander.yml").read_text()

        self.assertIn("META_ADS_SECRETS_PATH: /run/ptw-meta-ads/config.env", compose)
        self.assertIn("/opt/ptw/secrets/meta-ads:/run/ptw-meta-ads:ro", compose)
        self.assertNotIn("META_SYSTEM_USER_ACCESS_TOKEN", compose)
        self.assertNotIn("ptw-meta-ads", gateway)

        configurator = (ROOT / "scripts/configure_meta_ads.sh").read_text()
        self.assertIn("read -r -s access_token", configurator)
        self.assertIn("oauth2-bearer", configurator)
        self.assertIn("chmod 0440", configurator)
        self.assertIn("chmod 0600", configurator)
        self.assertNotIn("--oauth2-bearer", configurator)

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
