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

## TELIS Context Management

TELIS manages context efficiently using tiered knowledge shards. After installation:

### Check TELIS Status

```bash
python -m cli.main telis status
```

Shows current configuration including tier budgets and loaded shards.

### Initialize Sample Shards

```bash
python -m cli.main telis init --output config/telis-shards.yaml
```

Creates a sample configuration with Python, JavaScript, and JSON shards.

### Configure Shards

Add to `_baqt/config/runtime.yaml`:

```yaml
telis:
  policy: default
  use_lsp: true
  progressive: true
  shards_path: "config/telis-shards.yaml"
  tier_budgets:
    tier_1_nano: 50
    tier_2_micro: 500
    tier_3_full: 2000
```

### List and Manage Shards

```bash
# List all loaded shards
python -m cli.main telis list

# Filter by language
python -m cli.main telis list --language python

# Filter by tier
python -m cli.main telis list --tier tier_1_nano

# Add shards from external file
python -m cli.main telis add my-shards.yaml
```

## QUINT Evidence Tracking

QUINT provides evidence-based validation and decision tracking for workflow runs.

### Check Evidence Status

```bash
python -m cli.main quint status <run_id>
```

Shows evidence records count, DRRs, fingerprints, and drift detection.

### List Evidence Records

```bash
# List all evidence for a run
python -m cli.main quint evidence <run_id>

# Filter by level (L1=Asserted, L2=Validated, L3=Proven)
python -m cli.main quint evidence <run_id> --level L2
```

### View Decision Review Records

```bash
python -m cli.main quint drr <run_id>
```

Shows DRRs with options evaluated, evidence linked, and final decisions.

### Evidence Levels

| Level | Name      | Description                            |
| ----- | --------- | -------------------------------------- |
| L1    | Asserted  | Claim made without external validation |
| L2    | Validated | Claim verified by tool or test         |
| L3    | Proven    | Claim confirmed by multiple sources    |

## Support

For issues and feedback, visit:
<https://github.com/anthropics/baqt/issues>
