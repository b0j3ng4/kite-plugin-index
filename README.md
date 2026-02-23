# Kite Plugin Registry

This repository is the official plugin registry for Kite, a configuration language for sane DevOps engineers.

## Links

- [Contributing](CONTRIBUTING.md) — How to propose changes and use the helper scripts
- [Security](SECURITY.md) — How to report vulnerabilities
- [Code of Conduct](CODE_OF_CONDUCT.md)

## Layout

- `index.json` — Registry manifest: list of plugins with `author`, `name`, `description`, `types`, and `latest`.
- `plugins/<author>/<name>/meta.json` — Optional plugin-level metadata used for discovery.
- `plugins/<author>/<name>/versions/<git-sha>.json` — One file per version (`<git-sha>.json`) with plugin metadata and platform artifacts.

## Versioning model

- Versions are git commit hashes
- Each artifact is platform-specific (`darwin_amd64`, `darwin_arm64`, `linux_amd64`, `windows_amd64`, etc.) and has:
  - `url` — download URL for the platform archive (`.tar.gz` or `.zip`)
  - `sha256` — lowercase 64-char hex checksum of the archive (tar.gz or zip) for integrity verification
- The binary inside each archive must be named after the plugin: `kite-plugin-<name>` (or `kite-plugin-<name>.exe` on Windows), e.g. `kite-plugin-toml-emitter` for plugin `toml-emitter`.

## Adding a new plugin

See **[docs/adding-plugins.md](docs/adding-plugins.md)** for a full step-by-step guide. In short:

1. Build the plugin binary for each target platform and package each as a `.tar.gz` or `.zip` archive.
2. Compute SHA256 for each archive (not the binary inside).
3. Host the archives at stable URLs (e.g. GitHub Releases).
4. Add a version file to `plugins/<author>/<name>/versions/<git-sha>.json` (and `meta.json` if new plugin).
5. Add or update the plugin entry in `index.json` (set `latest` if this is the default version).
6. Validate JSON and checksums, then open a pull request.

**Contributors:** Install [pre-commit](https://pre-commit.com/) and run `pre-commit install`, then `python3 scripts/validate_registry.py` before opening a PR. See [CONTRIBUTING.md](CONTRIBUTING.md) for details.
