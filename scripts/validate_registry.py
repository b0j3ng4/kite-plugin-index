#!/usr/bin/env python3
"""
Validate the Kite plugin registry: JSON syntax, schema invariants, and artifact integrity.

- Schema validation: index.json, meta.json, version files (metadata, platforms, URL format).
- Artifact validation (unless --fast): download each platform artifact and verify SHA256.

Use --fast for pre-commit (no network, schema only). Run without --fast in CI for full validation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.request import Request, urlopen

DOWNLOAD_TIMEOUT = 60
CHUNK_SIZE = 65536
USER_AGENT = "Kite-Plugin-Registry-Validator/1.0"

REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_PATH = REPO_ROOT / "index.json"
PLUGINS_DIR = REPO_ROOT / "plugins"

DIGEST_RE = re.compile(r"^[a-f0-9]{40}$|^[a-f0-9]{64}$")
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
ARCHIVE_URL_SUFFIXES = (".tar.gz", ".zip")
VALID_PLATFORMS = frozenset(
    {"darwin_amd64", "darwin_arm64", "linux_amd64", "linux_arm64", "windows_amd64", "windows_arm64"}
)
VALID_TYPES = frozenset({"validator", "transformer", "emitter", "diff", "secret"})


def err(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)


def log(msg: str) -> None:
    """Print progress to stderr so stdout stays clean."""
    print(msg, file=sys.stderr)


def validate_index() -> list[str]:
    errors: list[str] = []
    path = INDEX_PATH
    if not path.exists():
        errors.append(f"{path} does not exist")
        return errors

    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        errors.append(f"{path}: invalid JSON: {e}")
        return errors

    if not isinstance(data.get("schema_version"), int):
        errors.append(f"{path}: schema_version must be an integer")
    if not isinstance(data.get("plugins"), list):
        errors.append(f"{path}: plugins must be a list")

    plugins = data.get("plugins") or []
    seen: set[tuple[str, str]] = set()
    for i, p in enumerate(plugins):
        if not isinstance(p, dict):
            errors.append(f"{path}: plugins[{i}] must be an object")
            continue
        author = p.get("author")
        name = p.get("name")
        latest = p.get("latest")
        if not author or not isinstance(author, str):
            errors.append(f"{path}: plugins[{i}] missing or invalid author")
        if not name or not isinstance(name, str):
            errors.append(f"{path}: plugins[{i}] missing or invalid name")
        if not latest or not isinstance(latest, str):
            errors.append(f"{path}: plugins[{i}] missing or invalid latest")
        elif not DIGEST_RE.match(latest):
            errors.append(f"{path}: plugins[{i}].latest must be 40 or 64 lowercase hex chars")

        key = (author, name) if author and name else None
        if key and key in seen:
            errors.append(f"{path}: duplicate plugin {author}/{name}")
        if key:
            seen.add(key)

        if author and name and latest and DIGEST_RE.match(latest):
            version_path = PLUGINS_DIR / author / name / "versions" / f"{latest}.json"
            if not version_path.exists():
                errors.append(f"{path}: plugins[{i}] references non-existent {version_path}")

    return errors


def validate_meta(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        errors.append(f"{path}: invalid JSON: {e}")
        return errors

    if not isinstance(data, dict):
        errors.append(f"{path}: must be a JSON object")
        return errors

    if not data.get("name") or not isinstance(data["name"], str):
        errors.append(f"{path}: missing or invalid name")
    if "types" in data and not isinstance(data["types"], list):
        errors.append(f"{path}: types must be a list")

    return errors


def validate_version(path: Path) -> list[str]:
    errors: list[str] = []
    digest = path.stem
    if not DIGEST_RE.match(digest):
        errors.append(f"{path}: filename must be 40 or 64 lowercase hex chars, got {digest!r}")

    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        errors.append(f"{path}: invalid JSON: {e}")
        return errors

    if not isinstance(data, dict):
        errors.append(f"{path}: must be a JSON object")
        return errors

    meta = data.get("metadata")
    if not isinstance(meta, dict):
        errors.append(f"{path}: metadata must be an object")
        return errors

    name = meta.get("name")
    ptype = meta.get("type")
    if not name or not isinstance(name, str):
        errors.append(f"{path}: metadata.name is required")
    if not ptype or not isinstance(ptype, str):
        errors.append(f"{path}: metadata.type is required")
    elif ptype not in VALID_TYPES:
        errors.append(f"{path}: metadata.type must be one of {sorted(VALID_TYPES)}")

    if "deterministic" not in meta:
        errors.append(f"{path}: metadata.deterministic is required")
    elif meta["deterministic"] not in (True, False):
        errors.append(f"{path}: metadata.deterministic must be boolean")

    if "network" not in meta:
        errors.append(f"{path}: metadata.network is required")
    elif meta["network"] not in (True, False):
        errors.append(f"{path}: metadata.network must be boolean")

    if ptype == "emitter":
        formats = meta.get("formats")
        if not isinstance(formats, list) or len(formats) == 0:
            errors.append(f"{path}: metadata.formats required for emitter (non-empty list)")
    if ptype == "secret":
        schemes = meta.get("schemes")
        if not isinstance(schemes, list) or len(schemes) == 0:
            errors.append(f"{path}: metadata.schemes required for secret (non-empty list)")

    platforms = data.get("platforms")
    if not isinstance(platforms, dict):
        errors.append(f"{path}: platforms must be an object")
        return errors

    for plat, art in platforms.items():
        if plat not in VALID_PLATFORMS:
            errors.append(f"{path}: unknown platform {plat!r}")
        if not isinstance(art, dict):
            errors.append(f"{path}: platforms.{plat} must be an object")
            continue
        url = art.get("url")
        sha = art.get("sha256")
        if not url or not isinstance(url, str):
            errors.append(f"{path}: platforms.{plat}.url is required")
        elif not url.endswith(ARCHIVE_URL_SUFFIXES):
            errors.append(
                f"{path}: platforms.{plat}.url must point to an archive (end with .tar.gz or .zip)"
            )
        if not sha or not isinstance(sha, str):
            errors.append(f"{path}: platforms.{plat}.sha256 is required")
        elif not SHA256_RE.match(sha):
            errors.append(f"{path}: platforms.{plat}.sha256 must be 64 lowercase hex chars")

    return errors


def _fetch_and_verify_artifact(
    version_path: Path, platform: str, url: str, expected_sha: str
) -> str | None:
    """Download artifact, compute SHA256, compare. Returns error message or None if OK."""
    try:
        req = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(req, timeout=DOWNLOAD_TIMEOUT) as resp:
            h = hashlib.sha256()
            while chunk := resp.read(CHUNK_SIZE):
                h.update(chunk)
            actual_sha = h.hexdigest()
    except Exception as e:
        return f"{version_path}: platforms.{platform}: {url}: {e}"

    if actual_sha != expected_sha:
        return (
            f"{version_path}: platforms.{platform}: sha256 mismatch: \n"
            f"\tgot {actual_sha} \n"
            f"\texpected {expected_sha}\n"
        )
    return None


def validate_artifacts() -> list[str]:
    """Download each artifact, verify SHA256. Uses URL cache to avoid re-downloading."""
    errors: list[str] = []
    seen: dict[tuple[str, str], str | None] = {}  # (url, sha) -> error or None

    version_paths = sorted(PLUGINS_DIR.rglob("versions/*.json"))
    log(f"Verifying {len(version_paths)} version file(s)...")

    for version_path in version_paths:
        if not version_path.name.endswith(".json"):
            continue
        try:
            data = json.loads(version_path.read_text())
        except json.JSONDecodeError:
            continue
        platforms = data.get("platforms") or {}
        if not isinstance(platforms, dict):
            continue
        for plat, art in platforms.items():
            if plat not in VALID_PLATFORMS or not isinstance(art, dict):
                continue
            url = art.get("url")
            sha = art.get("sha256")
            if not url or not sha or not isinstance(url, str) or not isinstance(sha, str):
                continue
            if not url.endswith(ARCHIVE_URL_SUFFIXES) or not SHA256_RE.match(sha):
                continue

            key = (url, sha)
            if key in seen:
                if seen[key] is not None:
                    errors.append(seen[key])
                continue

            rel = version_path.relative_to(REPO_ROOT)
            log(f"  Downloading {plat} from {rel}...")
            err_msg = _fetch_and_verify_artifact(version_path, plat, url, sha)
            seen[key] = err_msg
            if err_msg is not None:
                errors.append(err_msg)

    return errors


def run_schema_validation() -> list[str]:
    """Run index, meta, and version schema validation. No network."""
    all_errors: list[str] = []
    log("Validating index.json...")
    all_errors.extend(validate_index())
    if not PLUGINS_DIR.exists():
        return all_errors
    meta_paths = sorted(PLUGINS_DIR.rglob("meta.json"))
    for meta_path in meta_paths:
        log(f"Validating {meta_path.relative_to(REPO_ROOT)}...")
        all_errors.extend(validate_meta(meta_path))
    version_paths = sorted(PLUGINS_DIR.rglob("versions/*.json"))
    for version_path in version_paths:
        if version_path.name.endswith(".json"):
            log(f"Validating {version_path.relative_to(REPO_ROOT)}...")
            all_errors.extend(validate_version(version_path))
    return all_errors


def main(args: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate the Kite plugin registry. Use --fast for schema-only (no network)."
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Skip artifact download/SHA verification; schema validation only",
    )
    parsed = parser.parse_args(args)

    log("Schema validation...")
    all_errors = run_schema_validation()
    if all_errors:
        for e in all_errors:
            err(e)
        return 1

    if parsed.fast:
        log("Done (--fast: skipped artifact verification).")
        return 0

    log("Artifact verification...")
    all_errors.extend(validate_artifacts())
    if all_errors:
        for e in all_errors:
            err(e)
        return 1
    log("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
