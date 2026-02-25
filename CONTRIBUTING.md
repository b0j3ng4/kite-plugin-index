# Contributing

Thank you for your interest in contributing to the Kite Plugin Registry.

## How to contribute

### Proposing registry changes

1. **Read the guide**: See [docs/adding-plugins.md](docs/adding-plugins.md) for the full step-by-step process to add or update a plugin.
2. **Use the helper script**: Run `python3 scripts/add_plugin.py --help` to scaffold new plugin entries and version files. The script creates the required directory structure, `meta.json`, version manifests, and updates `index.json`.
3. **Validate locally**: Before opening a pull request, run:
   - `python3 scripts/validate_registry.py --fast` — validates JSON syntax and schema invariants (no network; used by pre-commit)
   - `python3 scripts/validate_registry.py` — full validation including artifact download and SHA256 verification (run before PR)
   - `python3 -m unittest` — runs unit tests for the scripts
   - `pre-commit run -a` — runs formatting and lint checks (after `pre-commit install`; uses `--fast` for registry validation)

### Commit messages

This project uses [Conventional Commits](https://www.conventionalcommits.org/). Please format your commit messages as:

```
<type>(<scope>): <description>

[optional body]
```

Examples:

- `feat(registry): add my-plugin to index`
- `fix(validation): allow 64-char digests in version filenames`
- `docs: update adding-plugins guide`

Types include: `feat`, `fix`, `doc`, `perf`, `refactor`, `style`, `test`, `chore`.

### Pull request process

1. Fork the repository and create a branch.
2. Make your changes, ensuring validation and tests pass.
3. Open a pull request with a clear description of the change.
4. CI will run registry validation and commit message checks.

## Development setup

1. **Pre-commit** (recommended):

   ```bash
   pip install pre-commit  # or: brew install pre-commit
   pre-commit install
   pre-commit run -a
   ```

2. **Manual validation**:

   ```bash
   python3 scripts/validate_registry.py --fast   # schema only, no network
   python3 scripts/validate_registry.py          # full validation (downloads artifacts, verifies SHA256)
   python3 -m unittest
   ```

## Questions?

Open an [issue](https://github.com/b0j3ng4/kite-plugin-index/issues) if you have questions or need help.
