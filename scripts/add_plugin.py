#!/usr/bin/env python3
"""
Scaffold a new plugin or version in the Kite plugin registry.
Creates meta.json, version file, and updates index.json.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_PATH = REPO_ROOT / "index.json"
PLUGINS_DIR = REPO_ROOT / "plugins"

DIGEST_RE = re.compile(r"^[a-f0-9]{40}$|^[a-f0-9]{64}$")
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
# Artifact URLs must point to archive files (no raw binaries).
ARCHIVE_URL_SUFFIXES = (".tar.gz", ".zip")
VALID_PLATFORMS = frozenset(
    {"darwin_amd64", "darwin_arm64", "linux_amd64", "linux_arm64", "windows_amd64", "windows_arm64"}
)
VALID_TYPES = frozenset({"validator", "transformer", "emitter", "diff", "secret"})


def err(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Add or update a plugin in the Kite plugin registry.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # New plugin with platforms from a JSON file
  python3 scripts/add_plugin.py --name my-emitter --digest abc123... --type emitter \\
    --formats toml --platforms-file platforms.json

  # New version for existing plugin
  python3 scripts/add_plugin.py --name toml-emitter --digest def456... --type emitter \\
    --formats toml --platforms-file platforms.json
""",
    )
    parser.add_argument("--author", default="_", help="Author namespace (default: _)")
    parser.add_argument("--name", required=True, help="Plugin name")
    parser.add_argument("--digest", required=True, help="Version digest (40 or 64 hex chars)")
    parser.add_argument(
        "--type",
        dest="plugin_type",
        required=True,
        choices=sorted(VALID_TYPES),
        help="Plugin type",
    )
    parser.add_argument("--description", default="", help="Short description for discovery")
    parser.add_argument("--formats", nargs="*", default=[], help="Output formats (for emitter)")
    parser.add_argument("--schemes", nargs="*", default=[], help="URI schemes (for secret)")
    parser.add_argument(
        "--deterministic",
        type=lambda x: x.lower() in ("1", "true", "yes"),
        default=True,
        help="Deterministic output (default: true)",
    )
    parser.add_argument(
        "--network",
        type=lambda x: x.lower() in ("1", "true", "yes"),
        default=False,
        help="Requires network (default: false)",
    )
    parser.add_argument(
        "--platforms-file",
        required=True,
        type=Path,
        help="Path to JSON file with platforms",
    )
    return parser.parse_args()


def validate_digest(digest: str) -> bool:
    return bool(DIGEST_RE.match(digest))


def validate_platforms(platforms: dict) -> list[str]:
    errors: list[str] = []
    for plat, art in platforms.items():
        if plat not in VALID_PLATFORMS:
            errors.append(f"unknown platform: {plat}")
        if not isinstance(art, dict):
            errors.append(f"platforms.{plat} must be an object")
            continue
        if "url" not in art or "sha256" not in art:
            errors.append(f"platforms.{plat} must have url and sha256")
        elif not SHA256_RE.match(str(art["sha256"])):
            errors.append(f"platforms.{plat}.sha256 must be 64 lowercase hex chars")
        else:
            url = str(art.get("url", ""))
            if not url.endswith(ARCHIVE_URL_SUFFIXES):
                errors.append(
                    f"platforms.{plat}.url must point to an archive (end with .tar.gz or .zip)"
                )
    return errors


def main() -> int:
    args = parse_args()

    if not validate_digest(args.digest):
        err("digest must be 40 or 64 lowercase hex characters")
        return 1

    if args.plugin_type == "emitter" and not args.formats:
        err("--formats required for emitter")
        return 1
    if args.plugin_type == "secret" and not args.schemes:
        err("--schemes required for secret")
        return 1

    platforms_path = args.platforms_file
    if not platforms_path.is_absolute():
        platforms_path = (Path.cwd() / platforms_path).resolve()
    if not platforms_path.exists():
        err(f"platforms file not found: {platforms_path}")
        return 1

    try:
        platforms = json.loads(platforms_path.read_text())
    except json.JSONDecodeError as e:
        err(f"invalid JSON in platforms file: {e}")
        return 1

    if not isinstance(platforms, dict):
        err("platforms file must contain a JSON object")
        return 1

    plat_errors = validate_platforms(platforms)
    if plat_errors:
        for e in plat_errors:
            err(e)
        return 1

    plugin_dir = PLUGINS_DIR / args.author / args.name
    versions_dir = plugin_dir / "versions"
    meta_path = plugin_dir / "meta.json"
    version_path = versions_dir / f"{args.digest}.json"

    metadata: dict = {
        "name": args.name,
        "type": args.plugin_type,
        "deterministic": args.deterministic,
        "network": args.network,
    }
    if args.plugin_type == "emitter":
        metadata["formats"] = args.formats
    if args.plugin_type == "secret":
        metadata["schemes"] = args.schemes

    version_data = {"metadata": metadata, "platforms": platforms}

    versions_dir.mkdir(parents=True, exist_ok=True)

    if not meta_path.exists():
        meta_data = {
            "name": args.name,
            "description": args.description,
            "types": [args.plugin_type],
        }
        meta_path.write_text(json.dumps(meta_data, indent=2) + "\n")
        print(f"Created {meta_path}")

    version_path.write_text(json.dumps(version_data, indent=2) + "\n")
    print(f"Created {version_path}")

    index_data: dict
    if INDEX_PATH.exists():
        index_data = json.loads(INDEX_PATH.read_text())
    else:
        index_data = {"schema_version": 2, "plugins": []}

    plugins = index_data["plugins"]
    entry = next(
        (p for p in plugins if p.get("author") == args.author and p.get("name") == args.name),
        None,
    )
    new_entry = {
        "author": args.author,
        "name": args.name,
        "description": args.description,
        "types": [args.plugin_type],
        "latest": args.digest,
    }
    if entry:
        entry.update(new_entry)
        print(f"Updated index.json entry for {args.author}/{args.name}")
    else:
        plugins.append(new_entry)
        plugins.sort(key=lambda p: (p.get("author", ""), p.get("name", "")))
        print(f"Added index.json entry for {args.author}/{args.name}")

    INDEX_PATH.write_text(json.dumps(index_data, indent=2) + "\n")
    print(f"Updated {INDEX_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
