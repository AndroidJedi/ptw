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

    def test_reset_and_in_place_entrypoints_require_mutually_exclusive_confirmations(self) -> None:
        publisher = (ROOT / "scripts/publish_ptw_release_serial.sh").read_text()
        deployer = (ROOT / "scripts/deploy_ptw_serial.sh").read_text()
        in_place_publisher = (ROOT / "scripts/publish_ptw_in_place_serial.sh").read_text()
        in_place_deployer = (ROOT / "scripts/deploy_ptw_in_place.sh").read_text()

        self.assertIn('[[ $confirmation == "RESET PTW PRODUCTION" ]]', publisher)
        self.assertIn('PTW_IN_PLACE_DEPLOY_ENTRYPOINT', publisher)
        self.assertIn('[[ $confirmation == "DEPLOY PTW IN PLACE" ]]', in_place_deployer)
        self.assertIn('$6 != "DEPLOY PTW IN PLACE"', in_place_publisher)
        self.assertNotIn("RESET PTW PRODUCTION", in_place_deployer)
        self.assertNotIn("RESET PTW PRODUCTION", in_place_publisher)
        self.assertEqual(1, deployer.count("reset_ptw.sh"))
        self.assertEqual(1, deployer.count("deploy_ptw_in_place.sh"))

    def test_in_place_deployment_backs_up_and_proves_row_preservation_before_cutover(self) -> None:
        deployer = (ROOT / "scripts/deploy_ptw_in_place.sh").read_text()
        stop = deployer.index('stop owner-gateway commander-api')
        backup = deployer.index('pg_dump -Fc', stop)
        before = deployer.index('snapshot_database > "$before_snapshot"', backup)
        migrate = deployer.index('commander-migrate', before)
        after = deployer.index('snapshot_database > "$after_snapshot"', migrate)
        compare = deployer.index('cmp -s "$before_snapshot" "$after_snapshot"', after)
        commander = deployer.index('commander-api >/dev/null', compare)
        validation = deployer.index('validation-api >/dev/null', commander)
        gateway = deployer.index('owner-gateway >/dev/null', validation)

        self.assertLess(stop, backup)
        self.assertLess(backup, before)
        self.assertLess(before, migrate)
        self.assertLess(migrate, after)
        self.assertLess(after, compare)
        self.assertLess(compare, commander)
        self.assertLess(commander, validation)
        self.assertLess(validation, gateway)
        self.assertIn('chmod 0600 "$backup_file"', deployer)
        self.assertIn('sha256sum "$backup_file"', deployer)
        self.assertIn("landing_publication_events", deployer)
        self.assertIn("a mutable PTW operation is active; in-place deployment refused", deployer)
        self.assertIn('run -T --rm --no-deps commander-migrate', deployer)
        self.assertIn("Commander authority remained unchanged during rejected in-place deployment", deployer)
        self.assertIn("CRITICAL: Commander authority changed during rejected in-place deployment", deployer)
        self.assertIn("CRITICAL: in-place deployment could not verify complete application rollback", deployer)

    def test_preserving_rollout_verifies_failed_path_data_and_all_image_rollbacks(self) -> None:
        deployer = (ROOT / "scripts/deploy_ptw_preserving.sh").read_text()

        self.assertNotIn("reset_ptw.sh", deployer)
        self.assertIn("pending migrations require the confirmation-gated in-place deployment path", deployer)
        self.assertIn(
            "SELECT count(*) FROM commander_schema_migrations WHERE name=:'migration_name';",
            deployer,
        )
        self.assertNotIn(
            '-c "SELECT count(*) FROM commander_schema_migrations',
            deployer,
        )
        self.assertIn('snapshot_ready=1', deployer)
        self.assertIn('snapshot_authority > "$after"', deployer)
        self.assertIn("Commander authority remained unchanged during rejected rollout", deployer)
        self.assertIn("CRITICAL: Commander authority changed during rejected rollout", deployer)
        self.assertIn("CRITICAL: preserving rollout could not verify complete image rollback", deployer)
        for image in (
            "ptw-commander:$old_app_tag",
            "ptw-validation:$old_app_tag",
            "ptw-owner-gateway:$old_app_tag",
            "ptw-agent-platform-commander-api:$old_platform_tag",
            "ptw-agent-platform-commander-worker:$old_platform_tag",
            "ptw-agent-platform-codex-auth:$old_platform_tag",
        ):
            self.assertIn(image, deployer)

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
            "landing_publications",
            "landing_publication_events",
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
        self.assertEqual(2, deployer.count('"${validation_compose[@]}" run -T --rm --no-deps validation-api'))
        self.assertIn('up -d --no-deps --no-build --wait codex-auth', deployer)
        self.assertIn("CRITICAL: platform rollback could not be fully verified", deployer)

    def test_in_place_outer_rollout_restores_both_service_sets_on_any_incomplete_exit(self) -> None:
        deployer = (ROOT / "scripts/deploy_ptw_serial.sh").read_text()

        self.assertIn("cleanup_release()", deployer)
        self.assertIn('trap cleanup_release EXIT', deployer)
        self.assertIn("trap 'exit 1' HUP INT TERM", deployer)
        self.assertIn('if [[ $confirmation == "DEPLOY PTW IN PLACE" ]]', deployer)
        self.assertIn('rollout_rollback_ready=1', deployer)
        self.assertIn('restore_application_images || status=1', deployer)
        self.assertIn('restore_platform_images || status=1', deployer)
        self.assertIn('rollout_committed=1', deployer)
        self.assertIn("CRITICAL: application rollback could not be fully verified", deployer)

    def test_release_uses_named_multisite_targets_and_public_shell_first_for_in_place(self) -> None:
        publisher = (ROOT / "scripts/publish_ptw_release_serial.sh").read_text()
        self.assertNotIn("firebase.natal-placeholder.json", publisher)
        public = publisher.index("firebase deploy --only hosting:public-landings")
        ssh = publisher.index('ssh -i "$HOME/.ssh/ptw_commander"')
        owner = publisher.index("firebase deploy --only hosting:owner-console", ssh)
        self.assertLess(public, ssh)
        self.assertLess(ssh, owner)
        self.assertIn("hosting:owner-console,hosting:public-landings", publisher)

    def test_owner_console_releases_require_cross_browser_e2e_and_live_audit(self) -> None:
        publisher = (ROOT / "scripts/publish_ptw_release_serial.sh").read_text()
        web_deployer = (ROOT / "scripts/deploy_owner_console_web.sh").read_text()

        publisher_e2e = publisher.index("npm --prefix apps/commander-web run test:e2e")
        publisher_hosting = publisher.index("firebase deploy --only hosting:owner-console", publisher_e2e)
        self.assertLess(publisher_e2e, publisher_hosting)

        self.assertIn('"DEPLOY OWNER CONSOLE WEB"', web_deployer)
        self.assertIn("git rev-parse origin/main", web_deployer)
        web_check = web_deployer.index("npm --prefix apps/commander-web run check")
        web_e2e = web_deployer.index("npm --prefix apps/commander-web run test:e2e", web_check)
        web_skills = web_deployer.index("python3 scripts/verify_ptw_skills.py", web_e2e)
        web_hosting = web_deployer.index("firebase deploy --only hosting:owner-console", web_skills)
        web_audit = web_deployer.index("audit_live_owner_console.py", web_hosting)
        self.assertLess(web_check, web_e2e)
        self.assertLess(web_e2e, web_skills)
        self.assertLess(web_skills, web_hosting)
        self.assertLess(web_hosting, web_audit)
        self.assertNotIn("ssh ", web_deployer)
        self.assertNotIn("docker", web_deployer)
        self.assertNotIn("reset_ptw", web_deployer)


if __name__ == "__main__":
    unittest.main()
