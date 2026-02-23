"""Unit tests for scripts/add_plugin.py."""

import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import add_plugin as ap


class TestAddPlugin(unittest.TestCase):
    """Tests for add_plugin module."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        ap.REPO_ROOT = self.root
        ap.INDEX_PATH = self.root / "index.json"
        ap.PLUGINS_DIR = self.root / "plugins"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_validate_digest_40_hex(self) -> None:
        self.assertTrue(ap.validate_digest("a" * 40))
        self.assertTrue(ap.validate_digest("0" * 40))

    def test_validate_digest_64_hex(self) -> None:
        self.assertTrue(ap.validate_digest("a" * 64))

    def test_validate_digest_rejects_uppercase(self) -> None:
        self.assertFalse(ap.validate_digest("A" * 40))

    def test_validate_digest_rejects_short(self) -> None:
        self.assertFalse(ap.validate_digest("a" * 39))
        self.assertFalse(ap.validate_digest("a" * 20))

    def test_validate_digest_rejects_non_hex(self) -> None:
        self.assertFalse(ap.validate_digest("g" * 40))

    def test_validate_platforms_unknown_platform(self) -> None:
        errors = ap.validate_platforms({
            "unknown_platform": {"url": "https://x.com/foo.tar.gz", "sha256": "0" * 64},
        })
        self.assertTrue(any("unknown platform" in e for e in errors))

    def test_validate_platforms_bad_sha256(self) -> None:
        errors = ap.validate_platforms({
            "darwin_amd64": {"url": "https://x.com/b.tar.gz", "sha256": "short"},
        })
        self.assertTrue(any("sha256" in e for e in errors))

    def test_validate_platforms_missing_url(self) -> None:
        errors = ap.validate_platforms({
            "darwin_amd64": {"sha256": "0" * 64},
        })
        self.assertTrue(any("url" in e for e in errors))

    def test_validate_platforms_url_must_be_archive(self) -> None:
        errors = ap.validate_platforms({
            "darwin_amd64": {"url": "https://x.com/binary", "sha256": "0" * 64},
        })
        self.assertTrue(any(".tar.gz" in e or "archive" in e for e in errors))

    def test_validate_platforms_valid(self) -> None:
        errors = ap.validate_platforms({
            "darwin_amd64": {"url": "https://x.com/b.tar.gz", "sha256": "0" * 64},
            "linux_amd64": {"url": "https://x.com/b2.zip", "sha256": "1" * 64},
        })
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
