#!/usr/bin/env python3
"""
Validate the Kite plugin registry: JSON syntax and schema invariants.
Used by pre-commit and CI.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

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


def main() -> int:
    all_errors: list[str] = []

    all_errors.extend(validate_index())

    if not PLUGINS_DIR.exists():
        if all_errors:
            for e in all_errors:
                err(e)
            return 1
        return 0

    for meta_path in PLUGINS_DIR.rglob("meta.json"):
        all_errors.extend(validate_meta(meta_path))

    for version_path in PLUGINS_DIR.rglob("versions/*.json"):
        if version_path.name.endswith(".json"):
            all_errors.extend(validate_version(version_path))

    if all_errors:
        for e in all_errors:
            err(e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
