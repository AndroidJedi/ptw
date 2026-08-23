from __future__ import annotations

import gzip
from pathlib import Path
import tempfile
import unittest

from owner_gateway.firebase_hosting import HOSTING_CONTRACT, FirebaseHostingPublisher, public_files
from owner_gateway.landing_pipeline import LandingBuildCoordinator


SITE = "natal-landings-test"
BUILD_ID = "01234567-89ab-7def-8123-456789abcdef"


class Response:
    def __init__(self, status_code: int, body: dict) -> None:
        self.status_code = status_code
        self._body = body

    def json(self):
        return self._body


class Session:
    def __init__(
        self, *, current_build_id: str | None = None, current_contract: str | None = HOSTING_CONTRACT
    ) -> None:
        self.current_build_id = current_build_id
        self.current_contract = current_contract
        self.requests: list[tuple[str, str, dict]] = []
        self.uploads: list[tuple[str, bytes, dict]] = []

    def request(self, method: str, url: str, **kwargs):
        self.requests.append((method, url, kwargs))
        if method == "GET" and url.endswith(f"/sites/{SITE}/releases"):
            releases = []
            if self.current_build_id:
                releases = [{
                    "version": {
                        "name": f"sites/{SITE}/versions/existing-version",
                        "labels": {
                            "natal-build-id": self.current_build_id,
                            **({"natal-hosting-contract": self.current_contract} if self.current_contract else {}),
                        },
                    }
                }]
            return Response(200, {"releases": releases})
        if method == "POST" and url.endswith(f"/sites/{SITE}/versions"):
            return Response(200, {"name": f"sites/{SITE}/versions/new-version"})
        if method == "POST" and url.endswith(":populateFiles"):
            hashes = list(kwargs["json"]["files"].values())
            return Response(200, {
                "uploadRequiredHashes": hashes,
                "uploadUrl": "https://upload-firebasehosting.googleapis.com/upload/sites/test/versions/new",
            })
        if method == "PATCH" and url.endswith("/versions/new-version"):
            return Response(200, {"status": "FINALIZED"})
        if method == "POST" and url.endswith(f"/sites/{SITE}/releases"):
            return Response(200, {"name": f"sites/{SITE}/releases/1"})
        return Response(500, {"error": {"status": "UNEXPECTED", "message": f"{method} {url}"}})

    def post(self, url: str, data: bytes, **kwargs):
        self.uploads.append((url, data, kwargs))
        return Response(200, {})


class FirebaseHostingPublisherTests(unittest.TestCase):
    def make_site(self, root: Path) -> None:
        (root / "assets").mkdir()
        (root / "index.html").write_text("<h1>Natal test landing</h1>")
        (root / "styles.css").write_text("body { color: #fff; }")
        (root / "app.js").write_text("document.documentElement.dataset.ready='1'")
        (root / "assets" / "logo.svg").write_text("<svg></svg>")
        (root / "brief.json").write_text('{"private":"source brief"}')
        (root / "build.json").write_text('{"private":"manifest"}')
        (root / "page_content.json").write_text('{"private":"draft snapshot"}')

    def test_public_file_allowlist_excludes_internal_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_site(root)
            files = public_files(root)
        self.assertEqual(
            ["/app.js", "/assets/logo.svg", "/index.html", "/styles.css"],
            sorted(files),
        )
        self.assertNotIn("/brief.json", files)
        self.assertNotIn("/build.json", files)
        self.assertNotIn("/page_content.json", files)

    def test_publish_hashes_gzip_payloads_finalizes_and_releases(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_site(root)
            session = Session()
            publisher = FirebaseHostingPublisher(project_id="project", site_id=SITE, session=session)
            result = publisher.publish(root, build_id=BUILD_ID)
        self.assertEqual("new-version", result["version"])
        self.assertEqual(f"https://{SITE}.web.app/builds/{BUILD_ID}/", result["public_url"])
        methods = [method for method, _url, _kwargs in session.requests]
        self.assertEqual(["GET", "POST", "POST", "PATCH", "POST"], methods)
        created = session.requests[1][2]["json"]
        self.assertEqual(BUILD_ID, created["labels"]["natal-build-id"])
        self.assertEqual(HOSTING_CONTRACT, created["labels"]["natal-hosting-contract"])
        csp = created["config"]["headers"][0]["headers"]["Content-Security-Policy"]
        self.assertIn("https://project.firebaseapp.com", csp)
        self.assertIn("https://project.web.app", csp)
        populated = session.requests[2][2]["json"]["files"]
        self.assertEqual(4, len(populated))
        self.assertEqual(4, len(session.uploads))
        decoded = {gzip.decompress(payload) for _url, payload, _kwargs in session.uploads}
        self.assertIn(b"<h1>Natal test landing</h1>", decoded)
        self.assertNotIn(b'{"private":"source brief"}', decoded)
        self.assertEqual({"updateMask": "status"}, session.requests[3][2]["params"])

    def test_matching_current_release_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_site(root)
            session = Session(current_build_id=BUILD_ID)
            result = FirebaseHostingPublisher(
                project_id="project", site_id=SITE, session=session
            ).publish(root, build_id=BUILD_ID)
        self.assertEqual("existing-version", result["version"])
        self.assertEqual(1, len(session.requests))
        self.assertEqual([], session.uploads)

    def test_matching_build_with_legacy_security_contract_is_republished(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_site(root)
            session = Session(current_build_id=BUILD_ID, current_contract=None)
            result = FirebaseHostingPublisher(
                project_id="project", site_id=SITE, session=session
            ).publish(root, build_id=BUILD_ID)
        self.assertEqual("new-version", result["version"])
        self.assertEqual(["GET", "POST", "POST", "PATCH", "POST"], [
            method for method, _url, _kwargs in session.requests
        ])

    def test_publish_rejects_unknown_public_file_and_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_site(root)
            (root / "notes.txt").write_text("not public")
            with self.assertRaisesRegex(ValueError, "unsupported public landing file"):
                public_files(root)
            (root / "notes.txt").unlink()
            (root / "linked.css").symlink_to(root / "styles.css")
            with self.assertRaisesRegex(ValueError, "must not contain symlinks"):
                public_files(root)

    def test_release_keeps_prior_build_and_publishes_current_snapshot_at_root_and_build_path(self) -> None:
        prior_id = "01234567-89ab-7def-8123-456789abcdea"

        class Repository:
            def __init__(self, prior_output: Path) -> None:
                self.prior_output = prior_output

            def published(self) -> list[dict[str, str]]:
                return [{"id": prior_id, "output_path": str(self.prior_output)}]

        with tempfile.TemporaryDirectory() as directory:
            output_root = Path(directory)
            prior = output_root / "builds" / prior_id
            current = output_root / "builds" / BUILD_ID
            prior.mkdir(parents=True)
            current.mkdir(parents=True)
            self.make_site(prior)
            self.make_site(current)
            (prior / "index.html").write_text("<h1>Prior snapshot</h1>")
            (current / "index.html").write_text("<h1>Current exact snapshot</h1>")
            release = output_root / "release"
            release.mkdir()
            coordinator = LandingBuildCoordinator(
                repository=Repository(prior),  # type: ignore[arg-type]
                publisher=object(),  # type: ignore[arg-type]
                output_root=output_root,
                stopped=lambda: False,
                lead_api_base_url="https://api.example.com/api/v1/public/landings",
            )
            coordinator._assemble_release(release, BUILD_ID, current)

            self.assertEqual(
                public_files(current), public_files(release / "builds" / BUILD_ID)
            )
            self.assertEqual(
                (release / "index.html").read_bytes(),
                (release / "builds" / BUILD_ID / "index.html").read_bytes(),
            )
            self.assertEqual(
                "<h1>Prior snapshot</h1>",
                (release / "builds" / prior_id / "index.html").read_text(),
            )
            self.assertFalse((release / "brief.json").exists())
            self.assertFalse((release / "builds" / BUILD_ID / "page_content.json").exists())


if __name__ == "__main__":
    unittest.main()
