# Adding a new plugin to the registry

This guide walks through every step to publish a new plugin (or a new version of an existing plugin) so users can install it with:

- `kite plugin add <name>[@version]` — install by name (author defaults to `_`)
- `kite plugin add <author>/<name>[@version]` — install by author and name
- `kite plugin add <registry>/<name>[@version]` or `kite plugin add <registry>/<author>/<name>[@version]` — when using multiple registries

## Quick start with the helper script

After building binaries, packaging each platform as a `.tar.gz` or `.zip`, computing SHA256 of each archive, and hosting them (Steps 1–3 below), you can use the helper script to scaffold the registry files:

1. Create a `platforms.json` file with your platform artifacts (one archive per platform; `sha256` is the hash of the archive):

```json
{
  "darwin_amd64": {
    "url": "https://github.com/org/my-plugin/releases/download/v1.0.0/my-plugin-darwin_amd64.tar.gz",
    "sha256": "<64-char hex checksum of the .tar.gz or .zip>"
  },
  "darwin_arm64": { "url": "...", "sha256": "..." },
  "linux_amd64": { "url": "...", "sha256": "..." }
}
```

2. Run the script:

```bash
python3 scripts/add_plugin.py \
  --name my-plugin \
  --digest 78b4dc0f49bf1de2fd2d5d5e716ca1468f46a22d \
  --type emitter \
  --formats toml \
  --platforms-file platforms.json
```

For a secret plugin, use `--type secret` and `--schemes vault` (or your scheme). Run `python3 scripts/add_plugin.py --help` for all options.

3. Validate and open a PR:

```bash
python3 scripts/validate_registry.py
pre-commit run -a
```

---

## Prerequisites

- A kite plugin that builds as a single executable (e.g. Go: `main.go` + `metadata.json`).
- The plugin's `metadata.json` must include: `name`, `type`, and for emitters `formats`, for secrets `schemes`. See [Plugin metadata](#plugin-metadata) below.
- Each platform must have a single archive (`.tar.gz` or `.zip`) containing the plugin binary. The **binary filename inside the archive must match the plugin name**: `kite-plugin-<name>` (or `kite-plugin-<name>.exe` on Windows). For example, for a plugin named `toml-emitter`, the binary inside the archive must be `kite-plugin-toml-emitter`. Supported platform keys are: `darwin_amd64`, `darwin_arm64`, `linux_amd64`, `linux_arm64`, `windows_amd64`, `windows_arm64`. You can list only the platforms you support; install will fail on unsupported platforms with a clear error.

## Step 1: Build the plugin and package as archives per platform

Build the plugin binary for every platform you intend to publish. The binary name must be `kite-plugin-<name>` (or `kite-plugin-<name>.exe` on Windows), where `<name>` is the plugin name from `metadata.json` — the binary inside the archive must match the plugin (e.g. `kite-plugin-toml-emitter` for plugin `toml-emitter`). Then package each binary (and any required files such as `metadata.json`) into a single archive per platform: **`.tar.gz`** or **`.zip`**.

Example for a plugin named `toml-emitter` (from the plugin's source directory):

```bash
# From the plugin project root — build binaries
GOOS=darwin GOARCH=amd64 go build -ldflags "-s -w" -o kite-plugin-toml-emitter .
tar -czf toml-emitter-darwin_amd64.tar.gz kite-plugin-toml-emitter metadata.json

GOOS=darwin GOARCH=arm64 go build -ldflags "-s -w" -o kite-plugin-toml-emitter .
tar -czf toml-emitter-darwin_arm64.tar.gz kite-plugin-toml-emitter metadata.json

GOOS=linux GOARCH=amd64 go build -ldflags "-s -w" -o kite-plugin-toml-emitter .
tar -czf toml-emitter-linux_amd64.tar.gz kite-plugin-toml-emitter metadata.json

# ... repeat for linux_arm64, windows_amd64, windows_arm64 (e.g. zip for Windows)
```

Use `.tar.gz` or `.zip` consistently; the registry accepts both. Each artifact URL must end with `.tar.gz` or `.zip`.

## Step 2: Compute SHA256 for each archive

The registry requires a SHA256 checksum for **the archive** (tar.gz or zip), not for the binary inside. Users' installs will verify the downloaded archive against this value.

**On macOS/Linux:**

```bash
shasum -a 256 toml-emitter-darwin_amd64.tar.gz
shasum -a 256 toml-emitter-darwin_arm64.tar.gz
shasum -a 256 toml-emitter-linux_amd64.tar.gz
# ... for each archive
```

**On Windows (PowerShell):**

```powershell
Get-FileHash -Algorithm SHA256 toml-emitter-darwin_amd64.tar.gz | Select-Object -ExpandProperty Hash
# Repeat for each archive; normalize to lowercase 64-char hex.
```

Record each checksum as a **lowercase** 64-character hex string (no `sha256:` prefix in the checksum or version fields).

## Step 3: Host the archives

Upload the archives to stable URLs that the registry will reference. For example:

- **GitHub Releases**: create a release and attach each `.tar.gz` or `.zip`; use the release asset URLs.
- A CDN or static host: upload to paths like `https://example.com/plugins/toml-emitter/<version>/toml-emitter-darwin_amd64.tar.gz`.

Each artifact in the registry must have a `url` that returns the archive (no redirect that changes the response body, or verification will fail).

## Step 4: Choose a version digest

Versions in this registry are **content-addressable**: each version is identified by a digest — **40 or 64 lowercase hex characters** (no `sha256:` prefix). You have two options:

1. **Git commit SHA**: Use a 40-hex git commit SHA as the version (e.g. `78b4dc0f49bf1de2fd2d5d5e716ca1468f46a22d`). All platforms for that version are listed under that one key.
2. **SHA256 digest**: SHA256 of a canonical binary.

The version string is used as the version file name: `versions/<digest>.json` (e.g. `versions/78b4dc0f49bf1de2fd2d5d5e716ca1468f46a22d.json`).

## Step 5: Choose an author namespace

Each plugin is namespaced by author. This allows two plugins with the same name to coexist in one registry (for example `b0j3ng4/toml-emitter` and `acme/toml-emitter`).

Choose a stable, lowercase author namespace (for example your GitHub org/user). The author `_` is the default namespace in the registry, reserved for plugins developed by first-party; when users run `kite plugin add <name>` without `author/`, the client looks up plugins with author `_`.

## Step 6: Create or update plugin metadata and version file

Each plugin uses:

- `plugins/<author>/<name>/meta.json` (optional plugin-level metadata for discovery)
- `plugins/<author>/<name>/versions/<digest>.json` (one file per published version; digest is the git commit hash, e.g. `78b4dc0f49bf1de2fd2d5d5e716ca1468f46a22d.json`)

For a new plugin, create both. For a new version, create only the new version file.

**Tip:** Use `scripts/add_plugin.py` to scaffold these files automatically (see [Quick start](#quick-start-with-the-helper-script) above).

Version file structure:

```json
{
  "metadata": {
    "name": "my-plugin",
    "type": "emitter",
    "formats": ["toml"],
    "deterministic": true,
    "network": false
  },
  "platforms": {
    "darwin_amd64": {
      "url": "https://github.com/org/my-plugin/releases/download/v1.0.0/my-plugin-darwin_amd64.tar.gz",
      "sha256": "<64-char hex checksum of the .tar.gz or .zip>"
    },
    "darwin_arm64": {
      "url": "https://github.com/org/my-plugin/releases/download/v1.0.0/my-plugin-darwin_arm64.tar.gz",
      "sha256": "<64-char hex>"
    },
    "linux_amd64": {
      "url": "https://github.com/org/my-plugin/releases/download/v1.0.0/my-plugin-linux_amd64.tar.gz",
      "sha256": "<64-char hex>"
    },
    "windows_amd64": {
      "url": "https://github.com/org/my-plugin/releases/download/v1.0.0/my-plugin-windows_amd64.zip",
      "sha256": "<64-char hex>"
    }
  }
}
```

Plugin-level metadata file:

```json
{
  "name": "my-plugin",
  "description": "Short description for search results",
  "types": ["emitter"]
}
```

- `metadata` must match the plugin's `metadata.json` (name, type, and for emitter: formats; for secret: schemes; deterministic, network).
- `platforms`: keys are platform identifiers such as `darwin_amd64`, `darwin_arm64`, `linux_amd64`, `linux_arm64`, `windows_amd64`, `windows_arm64`. Each value needs `url` (download URL for a `.tar.gz` or `.zip` archive) and `sha256` (lowercase 64-char hex of the archive).
- You can list only the platforms you support; `kite plugin add` will fail on unsupported platforms with a clear error.

## Step 7: Update the registry index

Edit `index.json` at the root of this repository.

- **New plugin**: Add an entry to the `plugins` array:

```json
{
  "author": "your-org",
  "name": "my-plugin",
  "description": "Short description",
  "types": ["emitter"],
  "latest": "78b4dc0f49bf1de2fd2d5d5e716ca1468f46a22d"
}
```

Use the git commit hash of the released version for `latest`.

- **Existing plugin (new version)**: Update `latest` to the new version digest if this version should be the default for `kite plugin add <author>/<name>` without `@version`. Optionally update `description` or `types`.

**Tip:** `scripts/add_plugin.py` updates `index.json` automatically.

## Step 8: Validate and open a pull request

1. Run `python3 scripts/validate_registry.py` to validate JSON syntax and schema invariants.
2. Run `pre-commit run -a` (or `pre-commit install` first) to run formatting and checks.
3. Confirm every `url` in the manifest is reachable and the downloaded archive matches the manifest checksum (e.g. `curl -sL <url> | shasum -a 256` matches the `sha256` in the manifest).
4. Commit the changes and open a pull request.

After merge, users can run:

- `kite plugin search <registry> [author/]name[@version]` — search one registry by name (and optional author). Registry must be configured in `project.kite` under `plugins.registries` (or the default registry is used when none is configured).
- `kite plugin add your-org/my-plugin` — install the `latest` version (from the first matching registry).
- `kite plugin add your-org/my-plugin@<digest>` — install a specific version (40 or 64 hex, e.g. `@78b4dc0f49bf1de2fd2d5d5e716ca1468f46a22d`).

**Registry resolution**: Registries are read from `project.kite` → `plugins.registries` (list of `{ name, url }`). If none are configured, a single default registry is used. Install tries each registry in order until the plugin is found. The installed binary is written under `.kite/plugins/` with a registry-qualified name (e.g. `kite-plugin-<registry>-<author>-<name>`) so the same logical plugin from different registries can coexist. For private registries, auth can be provided via environment: `KITE_REGISTRY_<NAME>_TOKEN` (e.g. `KITE_REGISTRY_MYCOMPANY_TOKEN`); the client sends `Authorization: Bearer <token>` for index and artifact requests.

---

## Plugin metadata

The `metadata` block in each version must match what the kite plugin protocol expects. Required fields:

| Field           | Required   | Notes                                                              |
| --------------- | ---------- | ------------------------------------------------------------------ |
| `name`          | Yes        | Must match the plugin name and binary prefix `kite-plugin-<name>`. |
| `type`          | Yes        | One of: `validator`, `transformer`, `emitter`, `diff`, `secret`.   |
| `formats`       | If emitter | At least one format string (e.g. `["toml"]`).                      |
| `schemes`       | If secret  | At least one scheme string (e.g. `["vault"]`).                     |
| `deterministic` | Yes        | `true` or `false`.                                                 |
| `network`       | Yes        | `true` or `false`.                                                 |

Example for an emitter:

```json
"metadata": {
  "name": "toml-emitter",
  "type": "emitter",
  "formats": ["toml"],
  "deterministic": true,
  "network": false
}
```

Example for a secret plugin:

```json
"metadata": {
  "name": "vault-secret",
  "type": "secret",
  "schemes": ["vault"],
  "deterministic": true,
  "network": true
}
```

## Checklist summary

- [ ] Built plugin binary for each target platform and packaged each as a `.tar.gz` or `.zip` archive.
- [ ] Computed SHA256 (lowercase 64-char hex) for each archive (not the binary inside).
- [ ] Hosted archives at stable URLs (e.g. GitHub Releases).
- [ ] Chosen an author namespace (for example `your-org`).
- [ ] Created or updated `plugins/<author>/<name>/meta.json` (optional) and added `plugins/<author>/<name>/versions/<digest>.json`.
- [ ] Updated `index.json`: added plugin entry or set `latest` to the new version digest.
- [ ] Ran `scripts/validate_registry.py` and `pre-commit run -a`, then opened a PR.
