# BAQT Installer Integration (WS15)

This document describes the technical architecture of the BAQT unified installer and its integration with BMAD-METHOD, TELIS, and QUINT components.

## Architecture Overview

```text
BAQT Repository
├── BMAD-METHOD/         (git submodule)
│   └── src/             (BMAD assets to install)
├── quint-code/          (git submodule)
│   └── src/             (QUINT Go source)
├── runtime/             (BAQT Python runtime)
│   ├── telis/           (TELIS context management)
│   └── quint/           (QUINT evidence store)
├── installer/           (Unified installer module)
│   ├── __init__.py
│   ├── cli.py           (CLI entry point)
│   ├── core.py          (Installation orchestrator)
│   ├── manifest.py      (Installation tracking)
│   └── verify.py        (Verification checks)
├── bin/
│   └── baqt.js         (Node.js wrapper for npx)
└── config/
    └── runtime.yaml     (Default configuration)
```

## Installer Module

### manifest.py

Defines data structures for tracking installations:

- `ComponentVersion` - Version info for installed components
- `FileRecord` - File path, checksum, and size
- `InstallManifest` - Complete installation state

Key functions:

- `compute_checksum(file_path)` - SHA256 file checksum
- `read_manifest(path)` - Load manifest from JSON
- `write_manifest(path, manifest)` - Save manifest to JSON
- `get_git_commit(repo_path)` - Get current git commit

### core.py

Main installation orchestrator:

- `BaqtInstaller` - Primary installer class
- `InstallConfig` - Installation configuration
- `InstallResult` - Installation outcome

Installation methods:

- `install(config)` - Full installation
- `update(target_dir)` - Update existing installation
- `status(target_dir)` - Get installation status

Component installers:

- `_install_bmad()` - Copy BMAD assets from submodule
- `_install_quint()` - Copy QUINT source, optionally build
- `_install_runtime()` - Copy Python runtime
- `_install_docs()` - Copy documentation
- `_install_config()` - Copy configuration files
- `_install_ide_commands()` - Generate IDE slash commands

### verify.py

Installation verification:

- `InstallationVerifier` - Verification runner
- `VerificationCheck` - Single check result
- `VerificationReport` - Complete verification report

Verification checks:

1. `_check_manifest_exists()` - Manifest validity
2. `_check_bmad_assets()` - BMAD directories present
3. `_check_quint_available()` - QUINT binary or source
4. `_check_runtime_importable()` - Runtime modules exist
5. `_check_telis_registry()` - TELIS shards module
6. `_check_config_valid()` - Configuration YAML
7. `_check_ide_commands()` - Slash commands registered
8. `_check_file_integrity()` - Checksum validation
9. `_check_component_versions()` - Version records
10. `_check_python_deps()` - Python dependencies

### cli.py

Command-line interface:

Commands:

- `install [target]` - Install to directory
- `update [target]` - Update installation
- `verify [target]` - Verify installation
- `status [target]` - Show status
- `version` - Show version

All commands support `--json` for machine-readable output.

## Component Integration

### BMAD Integration

BMAD assets are copied from `BMAD-METHOD/src/`:

```text
BMAD-METHOD/src/
├── core/          -> _baqt/bmad/core/
├── modules/       -> _baqt/bmad/modules/
└── utility/       -> _baqt/bmad/utility/
```

BMAD slash command templates are maintained in `BMAD-METHOD/tools/cli/installers/lib/ide/templates/`
and module injections under `BMAD-METHOD/src/modules/*/sub-modules/claude-code/injections.yaml`.
BAQT installs its own slash commands from `installer/commands/` and does not currently regenerate BMAD
commands from templates.

### QUINT Integration

QUINT can be installed as:

1. **Source only** - Go source files for later building
2. **Binary** - Pre-built Go binary (if `--build-quint` specified)

Source location: `quint-code/src/`
Binary location: `_baqt/quint/bin/quint`

### Runtime Integration

The Python runtime is copied with cache exclusions:

- `__pycache__/` - Excluded
- `*.pyc` - Excluded
- `.pytest_cache/` - Excluded

Key runtime modules:

- `runtime/engine.py` - Workflow execution
- `runtime/telis/` - Context management
- `runtime/quint/` - Evidence store

## Manifest Format

```json
{
  "install_id": "abc123def456",
  "installed_at": "2025-01-02T12:00:00Z",
  "updated_at": "2025-01-02T12:00:00Z",
  "target_dir": "/path/to/project",
  "baqt_version": "0.2.0",
  "components": [
    {
      "name": "bmad",
      "version": "1.0.0",
      "commit": "e39aa33eea15",
      "installed_at": "2025-01-02T12:00:00Z",
      "source_path": "/path/to/BMAD-METHOD/src"
    }
  ],
  "files": [
    {
      "path": "bmad/core/agent.md",
      "checksum": "sha256...",
      "size": 1234,
      "installed_at": "2025-01-02T12:00:00Z"
    }
  ],
  "config": {
    "include_bmad": true,
    "include_quint": true,
    "include_runtime": true,
    "include_docs": true
  }
}
```

## Update Strategy

### Submodule Updates

1. Update submodules in BAQT repository:

   ```bash
   git submodule update --remote BMAD-METHOD quint-code
   ```

2. Reinstall to target projects:

   ```bash
   baqt update /path/to/project
   ```

The update process:

1. Reads existing manifest
2. Preserves configuration options
3. Reinstalls with `force=True`
4. Updates manifest timestamps

### Version Tracking

Each component tracks:

- `version` - Semantic version
- `commit` - Git commit hash (12 chars)
- `installed_at` - ISO timestamp

This enables:

- Version comparison for updates
- Rollback identification
- Audit trail

## IDE Command Generation

BAQT generates slash commands for Claude Code:

### baqt-status.md

Shows installation status and run summary:

- Installed component versions
- Active workflow runs
- Evidence chain summary
- Recent activity log

### baqt-run.md

Executes a BAQT workflow:

- Parses workflow specification
- Creates run in runs directory
- Executes steps
- Records evidence

### baqt-evidence.md

Queries QUINT evidence chain:

- Loads evidence records
- Calculates WLNK scores
- Displays confidence levels
- Highlights gaps

## Extension Points

### Custom Components

Add new components by extending `BaqtInstaller`:

```python
class CustomInstaller(BaqtInstaller):
    def _install_custom(self, target, manifest):
        # Custom installation logic
        pass
```

### Custom Verification

Add verification checks by extending `InstallationVerifier`:

```python
class CustomVerifier(InstallationVerifier):
    def _check_custom(self):
        # Custom verification logic
        return VerificationCheck(...)
```

### Custom Commands

Add IDE commands by modifying `_install_ide_commands()`:

```python
baqt_commands = [
    ("baqt-status.md", self._generate_status_command()),
    ("baqt-custom.md", self._generate_custom_command()),
]
```

## Error Handling

The installer uses a structured error/warning system:

- **Errors** - Installation failures that prevent completion
- **Warnings** - Non-fatal issues (e.g., optional component skipped)

Both are collected in `InstallResult` and reported to the user.

## Testing

Smoke test the installer module:

```bash
# Test CLI
python -m installer.cli --help
python -m installer.cli install --help
python -m installer.cli verify --help
```

## Related Documents

- [Installation Guide](installation-guide.md) - User documentation
- [v1-plan.md](v1-plan.md) - Project plan
- [traceability-audit.md](traceability-audit.md) - Audit trail
