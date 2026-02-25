"""Unit tests for scripts/validate_registry.py."""

import hashlib
import json

# Import by modifying sys.path so we can run from repo root
import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import validate_registry as vr


class TestValidateRegistry(unittest.TestCase):
    """Tests for validate_registry module."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        vr.REPO_ROOT = self.root
        vr.INDEX_PATH = self.root / "index.json"
        vr.PLUGINS_DIR = self.root / "plugins"
        self._log_patcher = mock.patch.object(vr, "log", lambda _: None)
        self._log_patcher.start()

    def tearDown(self) -> None:
        self._log_patcher.stop()
        self.tmp.cleanup()

    def test_index_missing(self) -> None:
        vr.INDEX_PATH = self.root / "nonexistent.json"
        errors = vr.validate_index()
        self.assertIn("does not exist", errors[0])

    def test_index_invalid_json(self) -> None:
        (self.root / "index.json").write_text("{ invalid }")
        errors = vr.validate_index()
        self.assertTrue(any("invalid JSON" in e for e in errors))

    def test_index_schema_version_not_int(self) -> None:
        (self.root / "index.json").write_text('{"schema_version": "2", "plugins": []}')
        errors = vr.validate_index()
        self.assertTrue(any("schema_version" in e for e in errors))

    def test_index_plugins_not_list(self) -> None:
        (self.root / "index.json").write_text('{"schema_version": 2, "plugins": {}}')
        errors = vr.validate_index()
        self.assertTrue(any("plugins must be a list" in e for e in errors))

    def test_index_duplicate_plugin(self) -> None:
        plugin_a = {"author": "_", "name": "x", "description": "", "types": ["emitter"], "latest": "a" * 40}
        plugin_b = {"author": "_", "name": "x", "description": "", "types": ["emitter"], "latest": "b" * 40}
        (self.root / "index.json").write_text(
            json.dumps({"schema_version": 2, "plugins": [plugin_a, plugin_b]})
        )
        errors = vr.validate_index()
        self.assertTrue(any("duplicate" in e for e in errors))

    def test_index_bad_latest_digest(self) -> None:
        plugin = {"author": "_", "name": "x", "description": "", "types": ["emitter"], "latest": "not-hex"}
        (self.root / "index.json").write_text(
            json.dumps({"schema_version": 2, "plugins": [plugin]})
        )
        errors = vr.validate_index()
        self.assertTrue(any("latest" in e and "hex" in e for e in errors))

    def test_index_references_missing_version_file(self) -> None:
        plugin = {"author": "_", "name": "x", "description": "", "types": ["emitter"], "latest": "a" * 40}
        (self.root / "index.json").write_text(
            json.dumps({"schema_version": 2, "plugins": [plugin]})
        )
        errors = vr.validate_index()
        self.assertTrue(any("non-existent" in e for e in errors))

    def test_index_valid_with_version_file(self) -> None:
        digest = "a" * 40
        plugin = {"author": "_", "name": "x", "description": "", "types": ["emitter"], "latest": digest}
        (self.root / "index.json").write_text(
            json.dumps({"schema_version": 2, "plugins": [plugin]})
        )
        version_dir = self.root / "plugins" / "_" / "x" / "versions"
        version_dir.mkdir(parents=True)
        (version_dir / f"{digest}.json").write_text(
            json.dumps({
                "metadata": {
                    "name": "x",
                    "type": "emitter",
                    "formats": ["toml"],
                    "deterministic": True,
                    "network": False,
                },
                "platforms": {
                    "darwin_amd64": {
                        "url": "https://example.com/binary.tar.gz",
                        "sha256": "0" * 64,
                    },
                },
            })
        )
        errors = vr.validate_index()
        self.assertEqual(errors, [])

    def test_version_bad_filename(self) -> None:
        path = self.root / "badname.json"
        path.write_text("{}")
        errors = vr.validate_version(path)
        self.assertTrue(any("filename" in e for e in errors))

    def test_version_missing_formats_for_emitter(self) -> None:
        path = self.root / ("a" * 40 + ".json")
        path.write_text(
            json.dumps({
                "metadata": {
                    "name": "x",
                    "type": "emitter",
                    "deterministic": True,
                    "network": False,
                },
                "platforms": {},
            })
        )
        errors = vr.validate_version(path)
        self.assertTrue(any("formats" in e for e in errors))

    def test_version_missing_schemes_for_secret(self) -> None:
        path = self.root / ("a" * 40 + ".json")
        path.write_text(
            json.dumps({
                "metadata": {
                    "name": "x",
                    "type": "secret",
                    "deterministic": True,
                    "network": True,
                },
                "platforms": {},
            })
        )
        errors = vr.validate_version(path)
        self.assertTrue(any("schemes" in e for e in errors))

    def test_version_bad_sha256(self) -> None:
        path = self.root / ("a" * 40 + ".json")
        path.write_text(
            json.dumps({
                "metadata": {
                    "name": "x",
                    "type": "emitter",
                    "formats": ["toml"],
                    "deterministic": True,
                    "network": False,
                },
                "platforms": {
                    "darwin_amd64": {"url": "https://x.com/b.tar.gz", "sha256": "not-64-hex"},
                },
            })
        )
        errors = vr.validate_version(path)
        self.assertTrue(any("sha256" in e for e in errors))

    def test_version_url_must_be_archive(self) -> None:
        path = self.root / ("a" * 40 + ".json")
        path.write_text(
            json.dumps({
                "metadata": {
                    "name": "x",
                    "type": "emitter",
                    "formats": ["toml"],
                    "deterministic": True,
                    "network": False,
                },
                "platforms": {
                    "darwin_amd64": {"url": "https://x.com/binary", "sha256": "0" * 64},
                },
            })
        )
        errors = vr.validate_version(path)
        self.assertTrue(any(".tar.gz" in e or "archive" in e for e in errors))

    def test_main_fast_skips_artifacts(self) -> None:
        digest = "a" * 40
        (self.root / "index.json").write_text(
            json.dumps({"schema_version": 2, "plugins": [
                {"author": "_", "name": "x", "description": "", "types": ["emitter"], "latest": digest}
            ]})
        )
        version_dir = self.root / "plugins" / "_" / "x" / "versions"
        version_dir.mkdir(parents=True)
        (version_dir / f"{digest}.json").write_text(
            json.dumps({
                "metadata": {"name": "x", "type": "emitter", "formats": ["toml"], "deterministic": True, "network": False},
                "platforms": {"darwin_amd64": {"url": "https://example.com/x.tar.gz", "sha256": "0" * 64}},
            })
        )
        rc = vr.main(["--fast"])
        self.assertEqual(rc, 0)

    def test_validate_artifacts_success(self) -> None:
        data = b"test"
        expected_sha = hashlib.sha256(data).hexdigest()
        digest = "a" * 40
        version_dir = self.root / "plugins" / "_" / "x" / "versions"
        version_dir.mkdir(parents=True)
        version_path = version_dir / f"{digest}.json"
        version_path.write_text(
            json.dumps({
                "metadata": {"name": "x", "type": "emitter", "formats": ["toml"], "deterministic": True, "network": False},
                "platforms": {"darwin_amd64": {"url": "https://example.com/x.tar.gz", "sha256": expected_sha}},
            })
        )
        mock_resp = BytesIO(data)

        def fake_urlopen(req, timeout=None):
            return mock_resp

        with mock.patch("validate_registry.urlopen", side_effect=fake_urlopen):
            errors = vr.validate_artifacts()
        self.assertEqual(errors, [])

    def test_validate_artifacts_sha_mismatch(self) -> None:
        data = b"test"
        wrong_sha = "0" * 64
        digest = "a" * 40
        version_dir = self.root / "plugins" / "_" / "x" / "versions"
        version_dir.mkdir(parents=True)
        version_path = version_dir / f"{digest}.json"
        version_path.write_text(
            json.dumps({
                "metadata": {"name": "x", "type": "emitter", "formats": ["toml"], "deterministic": True, "network": False},
                "platforms": {"darwin_amd64": {"url": "https://example.com/x.tar.gz", "sha256": wrong_sha}},
            })
        )
        mock_resp = BytesIO(data)

        def fake_urlopen(req, timeout=None):
            return mock_resp

        with mock.patch("validate_registry.urlopen", side_effect=fake_urlopen):
            errors = vr.validate_artifacts()
        self.assertEqual(len(errors), 1)
        self.assertIn("sha256 mismatch", errors[0])
        self.assertIn(hashlib.sha256(data).hexdigest(), errors[0])
        self.assertIn(wrong_sha, errors[0])

    def test_validate_artifacts_download_error(self) -> None:
        digest = "a" * 40
        version_dir = self.root / "plugins" / "_" / "x" / "versions"
        version_dir.mkdir(parents=True)
        version_path = version_dir / f"{digest}.json"
        version_path.write_text(
            json.dumps({
                "metadata": {"name": "x", "type": "emitter", "formats": ["toml"], "deterministic": True, "network": False},
                "platforms": {"darwin_amd64": {"url": "https://example.com/x.tar.gz", "sha256": "0" * 64}},
            })
        )

        with mock.patch("validate_registry.urlopen", side_effect=OSError("Connection refused")):
            errors = vr.validate_artifacts()
        self.assertEqual(len(errors), 1)
        self.assertIn("Connection refused", errors[0])


if __name__ == "__main__":
    unittest.main()
