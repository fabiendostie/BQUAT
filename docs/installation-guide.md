# BAQT Installation Guide

This guide covers installing and configuring the BAQT unified framework, which includes BMAD-METHOD, TELIS context management, and QUINT evidence engine.

## Prerequisites

- **Python 3.11+** - Required for the runtime
- **Node.js 18+** - Required for npx installation (optional)
- **Go 1.21+** - Required only if building QUINT binary (optional)
- **Git** - Required for submodule updates

## Quick Start

### Option 1: Using npx (Recommended)

```bash
npx baqt install
```

### Option 2: Using Python

```bash
python -m installer.cli install
```

### Option 3: Using pip

```bash
pip install .
baqt install
```

## Installation Options

### Full Installation (Default)

Installs all components: BMAD, QUINT, Runtime, and Documentation.

```bash
baqt install
```

### Selective Installation

Skip specific components:

```bash
# Skip BMAD assets
baqt install --no-bmad

# Skip QUINT
baqt install --no-quint

# Skip runtime (not recommended)
baqt install --no-runtime

# Skip documentation
baqt install --no-docs
```

### Build QUINT Binary

If you have Go installed, you can build the QUINT binary during installation:

```bash
baqt install --build-quint
```

### Force Reinstall

Overwrite an existing installation:

```bash
baqt install --force
```

## Installed Structure

After installation, the following structure is created:

```text
your-project/
├── _baqt/
│   ├── manifest.json      # Installation manifest
│   ├── bmad/              # BMAD agents and workflows
│   │   ├── core/
│   │   ├── modules/
│   │   └── utility/
│   ├── quint/             # QUINT evidence engine
│   │   ├── bin/           # Go binary (if built)
│   │   └── src/           # Go source
│   ├── runtime/           # BAQT Python runtime
│   │   ├── telis/         # Context management
│   │   ├── quint/         # Evidence store
│   │   └── ...
│   ├── config/            # Configuration files
│   │   └── runtime.yaml
│   └── docs/              # Documentation
└── .claude/
    └── commands/          # IDE slash commands
        ├── baqt-status.md
        ├── baqt-run.md
        ├── baqt-evidence.md
        └── ...            # BMAD commands
```

## Verification

Verify your installation:

```bash
baqt verify
```

This checks:

1. Manifest file exists and is valid
2. BMAD assets are present
3. QUINT binary or source is available
4. Runtime modules are accessible
5. TELIS shard registry is valid
6. Configuration file is present
7. IDE commands are registered
8. File integrity (checksums)
9. Component versions match
10. Python dependencies are satisfied

## Commands

### install

Install BAQT to a target directory.

```bash
baqt install [target] [options]
```

Options:

- `--force, -f` - Overwrite existing installation
- `--no-bmad` - Skip BMAD installation
- `--no-quint` - Skip QUINT installation
- `--no-runtime` - Skip runtime installation
- `--no-docs` - Skip documentation
- `--build-quint` - Build QUINT Go binary
- `--json` - Output result as JSON

### update

Update an existing installation with latest versions.

```bash
baqt update [target] [options]
```

Options:

- `--json` - Output result as JSON

### verify

Verify installation integrity.

```bash
baqt verify [target] [options]
```

Options:

- `--json` - Output verification report as JSON

### status

Show installation status.

```bash
baqt status [target] [options]
```

Options:

- `--json` - Output status as JSON

### version

Show BAQT version.

```bash
baqt version
```

## Updating Components

### Update via Git Submodules

If BMAD-METHOD or quint-code are updated upstream:

```bash
# From BAQT repository
git submodule update --remote BMAD-METHOD
git submodule update --remote quint-code

# Reinstall to target
baqt update /path/to/project
```

### Update Runtime

To update only the runtime:

```bash
baqt install --no-bmad --no-quint --force
```

## IDE Integration

### Claude Code

After installation, the following slash commands are available:

- `/baqt-status` - Show installation status and run summary
- `/baqt-run <workflow>` - Execute a BAQT workflow
- `/baqt-evidence [run_id]` - Query QUINT evidence chain

Plus all BMAD slash commands for workflow execution.

### VS Code

The BAQT runtime works with any IDE that supports Python. For VS Code:

1. Open the project folder
2. Select Python 3.11+ interpreter
3. The runtime modules in `_baqt/runtime/` are automatically available

## Troubleshooting

### Python Not Found

Ensure Python 3.11+ is installed and in your PATH:

```bash
python --version
# or
python3 --version
```

### QUINT Build Fails

QUINT build requires Go 1.21+. If Go is not available, QUINT source is installed instead:

```bash
go version
```

### Manifest Corruption

If the manifest becomes corrupted, reinstall with force:

```bash
baqt install --force
```

### Missing Dependencies

Install Python dependencies:

```bash
pip install pyyaml
```

## Configuration

The runtime is configured via `_baqt/config/runtime.yaml`. Key sections:

```yaml
runtime:
  storage_root: ./runs
  max_retries: 3
  step_timeout_seconds: 300

hitl:
  mode: blocking
  require_conditional: true

observability:
  enabled: true
  log_level: info
```

## Support

For issues and feedback, visit:
<https://github.com/anthropics/baqt/issues>
