import json
import base64
import hashlib
from pathlib import Path
import subprocess
import unittest

from validation_pipeline.local_codex import LocalCodexError, LocalCodexStructuredProvider


def _output_path(command: list[str]) -> Path:
    return Path(command[command.index("--output-last-message") + 1])


class LocalCodexStructuredProviderTests(unittest.TestCase):
    def _provider(self, executor):
        return LocalCodexStructuredProvider(
            "/usr/bin/false", executor=executor, timeout_seconds=30,
        )

    @staticmethod
    def _request(provider, **overrides):
        request = {
            "mode": "studio_creative_generation",
            "system_prompt": "Return the bounded object.",
            "input_payload": {"creative_id": "example"},
            "output_schema": {
                "type": "object", "properties": {"value": {"type": "integer"}},
                "required": ["value"], "additionalProperties": False,
            },
            "idempotency_key": "local:creative:example",
            "prompt_version": "test-v1",
            "response_validator": lambda value: (
                value if value.get("value") == 2
                else (_ for _ in ()).throw(ValueError("value must equal 2"))
            ),
        }
        return provider.call(**{**request, **overrides})

    def test_domain_validator_is_mandatory(self):
        provider = self._provider(lambda *_args, **_kwargs: None)
        with self.assertRaisesRegex(ValueError, "domain response validator"):
            self._request(provider, response_validator=None)

    def test_only_completed_invalid_output_receives_a_corrective_attempt(self):
        calls = []

        def executor(command, **_kwargs):
            calls.append(command)
            _output_path(command).write_text(
                json.dumps({"value": len(calls)}), encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        result = self._request(self._provider(executor))

        self.assertEqual(result["response"], {"value": 2})
        self.assertEqual(len(calls), 2)
        attempts = result["invocation"]["attempts"]
        self.assertEqual([item["attempt"] for item in attempts], [1, 2])
        self.assertEqual(
            attempts[0]["request_fingerprint"], attempts[1]["request_fingerprint"],
        )
        self.assertIn(":request:", attempts[0]["idempotency_key"])
        self.assertTrue(attempts[1]["idempotency_key"].endswith(":attempt:2"))

    def test_transport_or_cli_failure_never_receives_a_blind_retry(self):
        cases = (
            lambda command, **_kwargs: subprocess.CompletedProcess(
                command, 7, stdout="", stderr="provider token=should-not-persist",
            ),
            lambda command, **_kwargs: (_ for _ in ()).throw(
                subprocess.TimeoutExpired(command, 30)
            ),
        )
        for executor in cases:
            with self.subTest(executor=executor):
                calls = []

                def counted(command, **kwargs):
                    calls.append(command)
                    return executor(command, **kwargs)

                with self.assertRaises(LocalCodexError) as raised:
                    self._request(self._provider(counted))
                self.assertEqual(len(calls), 1)
                self.assertEqual(len(raised.exception.attempts), 1)
                self.assertNotIn("should-not-persist", str(raised.exception))

    def test_visual_artifact_is_ephemeral_and_digest_bound(self):
        calls = []
        png = b"\x89PNG\r\n\x1a\nexample"
        digest = hashlib.sha256(png).hexdigest()

        def executor(command, **_kwargs):
            calls.append(command)
            image_path = Path(command[command.index("--image") + 1])
            self.assertEqual(png, image_path.read_bytes())
            _output_path(command).write_text(json.dumps({"value": 2}), encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        result = self._request(
            self._provider(executor), mode="creative_visual_analysis",
            input_artifacts=[{
                "name": "approved_png", "mime_type": "image/png", "sha256": digest,
                "bytes_base64": base64.b64encode(png).decode(),
            }],
        )

        self.assertEqual({"approved_png": digest}, result["invocation"]["attempts"][0]["input_artifacts"])
        self.assertEqual(len(png), result["invocation"]["attempts"][0]["input_artifact_bytes"])
        self.assertEqual(1, len(calls))

    def test_studio_manual_artifacts_reach_codex_in_screenshot_order(self):
        screenshots = [b"\x89PNG\r\n\x1a\nfirst", b"\x89PNG\r\n\x1a\nsecond"]

        def executor(command, **_kwargs):
            image_paths = [
                Path(command[index + 1])
                for index, value in enumerate(command) if value == "--image"
            ]
            self.assertEqual(
                ["studio_screenshot_1.png", "studio_screenshot_2.png"],
                [path.name for path in image_paths],
            )
            self.assertEqual(screenshots, [path.read_bytes() for path in image_paths])
            _output_path(command).write_text(json.dumps({"value": 2}), encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        artifacts = [{
            "name": f"studio_screenshot_{index}", "mime_type": "image/png",
            "sha256": hashlib.sha256(png).hexdigest(),
            "bytes_base64": base64.b64encode(png).decode(),
        } for index, png in enumerate(screenshots, start=1)]
        result = self._request(
            self._provider(executor), mode="studio_manual_edit", input_artifacts=artifacts,
        )

        self.assertEqual(
            {item["name"]: item["sha256"] for item in artifacts},
            result["invocation"]["attempts"][0]["input_artifacts"],
        )


if __name__ == "__main__":
    unittest.main()
