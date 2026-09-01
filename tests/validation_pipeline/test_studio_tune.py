from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

from validation_pipeline.studio_tune import StudioTuneService


HAS_FASTAPI = importlib.util.find_spec("fastapi") is not None
PREVIEW_BYTES = (
    b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\x0dIHDR"
    + (1_080).to_bytes(4, "big") + (1_080).to_bytes(4, "big")
)


class StudioTuneServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.repository = root / "repository"
        self.state = root / "state"
        self.repository.mkdir()
        (self.repository / ".gitignore").write_text(".venv/\nnode_modules/\n.local/\n")
        self.studio_view = self.repository / "apps/commander-web/src/views/StudioView.tsx"
        self.studio_view.parent.mkdir(parents=True)
        self.studio_view.write_text("export const studioVersion = 'before'\n")
        (self.repository / "README.md").write_text("PTW test repository\n")
        self.skill_rules = (
            self.repository
            / "skills/studio-tune-local/references/owner-approved-rules.md"
        )
        self.skill_rules.parent.mkdir(parents=True)
        self.skill_rules.write_text(
            "# Owner-approved Studio Tune rules\n\n"
            "<!-- PTW-STUDIO-TUNE-RULES-START -->\n"
            "<!-- PTW-STUDIO-TUNE-RULES-END -->\n"
        )
        (self.repository / ".venv/bin").mkdir(parents=True)
        (self.repository / ".venv/bin/python").write_text("test executable placeholder\n")
        (self.repository / "apps/commander-web/node_modules").mkdir(parents=True)
        self._git("init", "--quiet")
        self._git("config", "user.name", "Studio Tune Test")
        self._git("config", "user.email", "studio-tune-test@localhost")
        self._git("add", "--all")
        self._git("commit", "--quiet", "-m", "baseline")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _git(self, *arguments: str) -> None:
        subprocess.run(
            ["git", "-C", str(self.repository), *arguments], check=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )

    @staticmethod
    def _wait(service: StudioTuneService, run_id: str) -> dict:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            value = service.run_detail(run_id)
            if value["status"] in {"completed", "failed"}:
                return value
            time.sleep(0.01)
        raise AssertionError("Studio Tune run did not finish")

    def _service(self, executor, *, studio_context_provider=None) -> StudioTuneService:
        return StudioTuneService(
            self.repository,
            self.state,
            codex_binary="/bin/true",
            executor=executor,
            verifier=lambda _snapshot: ["focused tests", "production build"],
            preview_renderer=lambda _snapshot: PREVIEW_BYTES,
            studio_context_provider=studio_context_provider,
        )

    def test_verified_allowlisted_change_is_copied_back(self) -> None:
        prompts: list[str] = []

        def execute(snapshot: Path, prompt: str, _output: Path) -> str:
            prompts.append(prompt)
            target = snapshot / "apps/commander-web/src/views/StudioView.tsx"
            target.write_text("export const studioVersion = 'after'\n")
            return "Updated the local Studio presentation and verified it."

        service = self._service(execute)
        started = service.start(
            project_idea="A planning product for independent founders.",
            implementation="Use a calm editorial layout and one primary action.",
            feedback="Reduce the visual noise in the prior pass.",
        )
        completed = self._wait(service, started["run_id"])

        self.assertEqual("completed", completed["status"])
        self.assertEqual(["apps/commander-web/src/views/StudioView.tsx"], completed["changed_files"])
        self.assertEqual(["focused tests", "production build"], completed["verification"])
        self.assertEqual("image/png", completed["preview"]["mime_type"])
        self.assertEqual(1_080, completed["preview"]["width"])
        preview, metadata = service.preview(started["run_id"])
        self.assertEqual(PREVIEW_BYTES, preview)
        self.assertEqual(completed["preview"], metadata)
        self.assertIn("studioVersion = 'after'", self.studio_view.read_text())
        self.assertIn("A planning product for independent founders.", prompts[0])
        self.assertIn("Reduce the visual noise in the prior pass.", prompts[0])

    def test_agent_prompt_and_run_capture_exact_component_settings_json(self) -> None:
        prompts: list[str] = []
        context = {
            "schema": "ptw.studio.universal-ad-agent-context.v2",
            "template_id": "universal_ad",
            "state_sha256": "a" * 64,
            "component_settings": {
                "schema": "ptw.studio.universal-ad-component-settings.v2",
                "components": [{
                    "component_id": "universal_ad.cta",
                    "node_ids": ["cta"],
                    "asset_slot_ids": [],
                    "settings": [{
                        "setting_id": "configuration.cta.style", "value": "outlined",
                    }],
                }],
                "sha256": "b" * 64,
            },
            "sha256": "c" * 64,
        }

        def execute(snapshot: Path, prompt: str, _output: Path) -> str:
            prompts.append(prompt)
            target = snapshot / "apps/commander-web/src/views/StudioView.tsx"
            target.write_text("export const studioVersion = 'context-aware'\n")
            return "Used the captured component settings."

        service = self._service(execute, studio_context_provider=lambda: context)
        started = service.start(
            project_idea="A focused Studio experiment with a current saved setup.",
            implementation="Use the current CTA component identity and selected style.",
            feedback="Preserve the exact machine-readable component mapping.",
        )
        completed = self._wait(service, started["run_id"])

        self.assertEqual("completed", completed["status"])
        self.assertEqual(context, completed["studio_context"])
        self.assertIn('"component_id": "universal_ad.cta"', prompts[0])
        self.assertIn('"setting_id": "configuration.cta.style"', prompts[0])
        self.assertIn('"value": "outlined"', prompts[0])
        self.assertIn("machine-readable authority", prompts[0])

    def test_outside_allowlist_change_fails_without_touching_checkout(self) -> None:
        def execute(snapshot: Path, _prompt: str, _output: Path) -> str:
            (snapshot / "README.md").write_text("unsafe change\n")
            return "Changed an out-of-scope file."

        service = self._service(execute)
        run = service.start(
            project_idea="A bounded Studio experiment for a product idea.",
            implementation="Keep the implementation inside the Studio surface.",
            feedback="",
        )
        failed = self._wait(service, run["run_id"])

        self.assertEqual("failed", failed["status"])
        self.assertIn("outside its Studio allowlist", failed["error"])
        self.assertEqual("PTW test repository\n", (self.repository / "README.md").read_text())

    def test_owner_approved_rule_is_saved_to_skill_once_and_linked_to_run(self) -> None:
        def execute(snapshot: Path, _prompt: str, _output: Path) -> str:
            target = snapshot / "apps/commander-web/src/views/StudioView.tsx"
            target.write_text("export const studioVersion = 'approved'\n")
            return "Implemented the requested reusable Studio behavior."

        service = self._service(execute)
        started = service.start(
            project_idea="A reusable Studio behavior for future experiments.",
            implementation="Implement the behavior and preserve it in future Tune work.",
            feedback="Give isolated stickers a smooth white die-cut contour.",
        )
        completed = self._wait(service, started["run_id"])
        rule = "Give isolated stickers a smooth white die-cut contour."

        first = service.save_rule(completed["run_id"], rule=rule)
        second = service.save_rule(completed["run_id"], rule=rule.upper())

        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        self.assertEqual(first["rule_sha256"], second["rule_sha256"])
        self.assertEqual(1, self.skill_rules.read_text().count(f"- {rule}"))
        stored = service.run_detail(completed["run_id"])
        self.assertEqual([first["rule_sha256"]], [
            item["rule_sha256"] for item in stored["approved_rules"]
        ])

    def test_concurrent_source_change_fails_copy_back(self) -> None:
        def execute(snapshot: Path, _prompt: str, _output: Path) -> str:
            target = snapshot / "apps/commander-web/src/views/StudioView.tsx"
            target.write_text("export const studioVersion = 'agent'\n")
            self.studio_view.write_text("export const studioVersion = 'owner'\n")
            return "Prepared a conflicting Studio change."

        service = self._service(execute)
        run = service.start(
            project_idea="A conflict-safe Studio iteration for local testing.",
            implementation="Change the Studio view while preserving owner edits.",
            feedback="Keep the owner's concurrent change intact.",
        )
        failed = self._wait(service, run["run_id"])

        self.assertEqual("failed", failed["status"])
        self.assertIn("source changed during Tune run", failed["error"])
        self.assertIn("studioVersion = 'owner'", self.studio_view.read_text())

    def test_allowlisted_symlink_is_rejected(self) -> None:
        def execute(snapshot: Path, _prompt: str, _output: Path) -> str:
            target = snapshot / "apps/commander-web/src/components/studio/Leaked.tsx"
            target.parent.mkdir(parents=True)
            target.symlink_to(snapshot / "README.md")
            return "Created a symlink instead of a Studio component."

        service = self._service(execute)
        run = service.start(
            project_idea="A Studio component experiment with a strict file boundary.",
            implementation="Create a normal source component without external links.",
            feedback="Keep all generated source material self-contained.",
        )
        failed = self._wait(service, run["run_id"])

        self.assertEqual("failed", failed["status"])
        self.assertIn("copy symlinks", failed["error"])
        self.assertFalse((
            self.repository / "apps/commander-web/src/components/studio/Leaked.tsx"
        ).exists())

    @unittest.skipUnless(HAS_FASTAPI, "FastAPI is required")
    def test_loopback_tune_routes_are_authenticated_and_explicit(self) -> None:
        from fastapi.testclient import TestClient
        from validation_pipeline.studio_local_api import create_app

        class Service:
            def detail(self):
                return {
                    "schema": "ptw.studio.tune-service.v1", "mode": "local_only",
                    "available": True, "unavailable_reason": None,
                    "active_run_id": None, "allowed_paths": [], "runs": [],
                }

            def start(self, **values):
                return {"schema": "ptw.studio.tune-run.v1", "run_id": "run", **values}

            def run_detail(self, run_id):
                return {"schema": "ptw.studio.tune-run.v1", "run_id": run_id}

            def preview(self, _run_id):
                return PREVIEW_BYTES, {
                    "mime_type": "image/png", "sha256": "a" * 64,
                    "width": 1_080, "height": 1_080,
                }

            def save_rule(self, run_id, *, rule):
                return {
                    "schema": "ptw.studio.tune-rule-approval.v1",
                    "run_id": run_id,
                    "rule": rule,
                    "rule_sha256": "b" * 64,
                    "skill_path": "skills/studio-tune-local/references/owner-approved-rules.md",
                    "created": True,
                }

        headers = {
            "Authorization": "Bearer e2e-owner-token",
            "X-Firebase-AppCheck": "e2e-app-check",
        }
        with tempfile.TemporaryDirectory() as workspace, patch.dict(
            "os.environ", {
                "STUDIO_WORKSPACE_PATH": workspace,
                "LOCAL_EXPERIMENT_PATH": str(Path(workspace) / "owner-experiments"),
                "STUDIO_TUNE_MODE": "0",
            },
            clear=False,
        ):
            with TestClient(create_app(tune_service=Service())) as client:
                self.assertEqual(401, client.get("/api/v1/studio/tune").status_code)
                self.assertEqual(200, client.get("/api/v1/studio/tune", headers=headers).status_code)
                response = client.post("/api/v1/studio/tune-runs", headers=headers, json={
                    "project_idea": "A local test idea.",
                    "implementation": "A local implementation.",
                    "feedback": "",
                })
                self.assertEqual(202, response.status_code, response.text)
                self.assertEqual(
                    401,
                    client.get("/api/v1/studio/tune-runs/run/preview").status_code,
                )
                preview = client.get(
                    "/api/v1/studio/tune-runs/run/preview", headers=headers,
                )
                self.assertEqual(200, preview.status_code, preview.text)
                self.assertEqual("image/png", preview.headers["content-type"])
                self.assertEqual("private, no-store", preview.headers["cache-control"])
                self.assertEqual(PREVIEW_BYTES, preview.content)
                approval = client.post(
                    "/api/v1/studio/tune-runs/run/rules", headers=headers,
                    json={"rule": "Preserve this reusable Studio behavior."},
                )
                self.assertEqual(200, approval.status_code, approval.text)
                self.assertEqual("ptw.studio.tune-rule-approval.v1", approval.json()["schema"])
                self.assertEqual(
                    401,
                    client.post(
                        "/api/v1/studio/tune-runs/run/rules",
                        json={"rule": "Preserve this reusable Studio behavior."},
                    ).status_code,
                )


if __name__ == "__main__":
    unittest.main()
