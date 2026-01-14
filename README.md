# BAQT Unified Agentic Framework

[![CI](https://img.shields.io/github/actions/workflow/status/fabiendostie/BAQT/ci.yml?branch=development&logo=github&label=CI)](https://github.com/fabiendostie/BAQT/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/coverage-88.87%25-success?logo=pytest&logoColor=white)](docs/v1-plan.md)
[![Version](https://img.shields.io/badge/v1.0.0-release-blue?logo=semanticrelease&logoColor=white)](VERSION)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](pyproject.toml)
[![Node.js](https://img.shields.io/badge/Node.js-18+-339933?logo=nodedotjs&logoColor=white)](package.json)
[![TypeScript](https://img.shields.io/badge/Types-mypy%20%2B%20pyright-3178C6?logo=typescript&logoColor=white)](pyproject.toml)

[![HITL](https://img.shields.io/badge/HITL-blocking%20gates-orange?logo=shield&logoColor=white)](docs/v1-plan.md)
[![Providers](https://img.shields.io/badge/Providers-7%20LLMs-blueviolet?logo=openai&logoColor=white)](config/runtime.yaml)
[![Tests](https://img.shields.io/badge/Tests-495%20passing-success?logo=checkmarx&logoColor=white)](tests/)
[![License](https://img.shields.io/badge/License-MIT-green?logo=opensourceinitiative&logoColor=white)](LICENSE)

**B**MAD Method +
**A**utonomous Agents +
**Q**UINT-Code +
**T**ELIS =

*BAQT: The unified framework*

> Build production-grade agent workflows by unifying **BMAD-METHOD**, **TELIS**, and **QUINT** under one runtime with blocking human-in-the-loop (HITL) gates.

BAQT preserves the original workflows and artifacts while adding enforceable guardrails, runtime approvals, and a reproducible execution model.

---

## Key Features

| Feature                | Description                                                                    |
| ---------------------- | ------------------------------------------------------------------------------ |
| **Unified Workflows**  | Execute BMAD workflows with consistent outputs and artifact conventions        |
| **HITL Gates**         | Blocking approval gates at planning, architecture, and release stages          |
| **Evidence Engine**    | QUINT-powered evidence store with ADI promotion, WLNK scoring, and DRRs        |
| **FPF Integration**    | Deepened First Principles Framework with Formality (F), ClaimScope (G), Φ(CL)  |
| **Decision Logic**     | Structured Characteristic Space (Justification Matrix) for auditable tradeoffs |
| **Context Management** | TELIS LSP symbiosis, tiered shards, and progressive negotiation                |
| **Multi-Provider**     | Route to Ollama, OpenAI, Anthropic, Gemini, Groq, or LiteLLM                   |
| **Guardrails**         | PII filtering, moderation, and rules-based protections                         |
| **Single Install**     | One command installs BMAD + TELIS + QUINT together                             |

---

## Quick Start

### Installation

```bash
# Option 1: Using npx (recommended)
npx baqt install

# Option 2: Using Python
pip install .
baqt install

# Option 3: From source
git clone https://github.com/fabiendostie/BAQT.git
cd BAQT
pip install -r requirements-dev.txt
npm install
```

### Verify Installation

```bash
baqt verify
baqt status
```

### Run a Workflow

```bash
# Validate configuration
python -m cli.main validate

# Run a workflow
python -m cli.main run bmm prd --agent bmad --provider mock

# Approve a gate
python -m cli.main approve <run-id> --by you

# Check status
python -m cli.main status <run-id>
```

---

## Using BMAD, TELIS, and QUINT

BAQT integrates three powerful methodologies. Here's how to use each component.

### BMAD - Workflow Orchestration

BMAD provides structured agent workflows for software development.

```bash
# List all available workflows
python -m cli.main list

# List workflows for a specific module
python -m cli.main list --module core

# Run a specific workflow
python -m cli.main run core brainstorming --agent bmad --provider ollama

# Interactive mode (guided step-by-step execution)
python -m cli.main interactive --module core --workflow prd --provider ollama

# Quick start from brainstorming
python -m cli.main start --provider ollama
```

**Common Workflows:**

| Module | Workflow      | Purpose                                |
| ------ | ------------- | -------------------------------------- |
| core   | brainstorming | Initial project ideation               |
| core   | prd           | Product Requirements Document creation |
| core   | architecture  | System architecture design             |
| core   | story         | User story creation and refinement     |
| bmm    | analysis      | Business problem analysis              |
| bmm    | planning      | Project planning and estimation        |
| bmm    | solutioning   | Technical solution design              |

**Human Gates:**

Workflows include approval gates at critical stages. Approve them to continue:

```bash
# Check run status (shows if blocked on gate)
python -m cli.main status <run_id>

# Approve a human gate
python -m cli.main approve <run_id> --by "your-name" --notes "Reviewed and approved"

# Resume after approval
python -m cli.main resume <run_id> --agent bmad --provider ollama
```

### TELIS - Context Management

TELIS manages context efficiently using tiered knowledge shards.

```bash
# Check TELIS configuration
python -m cli.main telis status

# List loaded knowledge shards
python -m cli.main telis list

# Filter shards by language or tier
python -m cli.main telis list --language python
python -m cli.main telis list --tier tier_1_nano

# Initialize sample shards configuration
python -m cli.main telis init --output config/telis-shards.yaml

# Add shards from a custom file
python -m cli.main telis add my-shards.yaml
```

**Tier Reference:**

| Tier         | Tokens | Use Case                          |
| ------------ | ------ | --------------------------------- |
| tier_1_nano  | ~50    | Quick facts, cheat sheets         |
| tier_2_micro | ~500   | Common patterns, API summaries    |
| tier_3_full  | ~2000  | Complete docs, detailed tutorials |

**Configuration (config/runtime.yaml):**

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

### QUINT - Evidence Tracking

QUINT provides evidence-based validation and decision tracking.

```bash
# Check evidence status for a run
python -m cli.main quint status <run_id>

# List all evidence records
python -m cli.main quint evidence <run_id>

# Filter evidence by level
python -m cli.main quint evidence <run_id> --level L2

# View Decision Review Records (DRRs)
python -m cli.main quint drr <run_id>
```

**Evidence Levels:**

| Level | Name      | Description                            |
| ----- | --------- | -------------------------------------- |
| L1    | Asserted  | Claim made without external validation |
| L2    | Validated | Claim verified by tool or test         |
| L3    | Proven    | Claim confirmed by multiple sources    |

**WLNK Scoring:**

QUINT uses WLNK (Weighted Link) scoring to assess evidence reliability:

- Score range: 0.0 - 1.0
- Factors: source reliability, claim scope, formality level
- Congruence penalties applied for conflicting evidence

**Decision Review Records (DRRs):**

DRRs document architectural and design decisions with:

- Options evaluated
- Evidence linked to each option
- Final decision and rationale
- Approval status

### Workflow Example

Complete example from ideation to implementation:

```bash
# 1. Configure provider
export OLLAMA_HOST=http://localhost:11434

# 2. Start brainstorming
python -m cli.main run core brainstorming --agent bmad --provider ollama
# Returns: {"run_id": "run-abc123", "status": "blocked"}

# 3. Check what's blocking
python -m cli.main status run-abc123
# Shows: blocked on human_gate "brainstorming-review"

# 4. Approve and continue
python -m cli.main approve run-abc123 --by developer
python -m cli.main resume run-abc123 --agent bmad --provider ollama

# 5. Check evidence collected
python -m cli.main quint status run-abc123
python -m cli.main quint evidence run-abc123

# 6. Export full run data
python -m cli.main export run-abc123 --output run-export.json --report
```

---

## Architecture

```text
+-----------------+     +------------------+     +----------------+
|  BMAD Workflows |---->|  Runtime Engine  |---->|  HITL Gates    |
+-----------------+     +------------------+     +----------------+
                               |                        |
                               v                        v
                        +-------------+          +-------------+
                        |  Providers  |          |  Approvals  |
                        +-------------+          +-------------+
                               |
              +----------------+----------------+
              |                |                |
              v                v                v
        +---------+      +---------+      +---------+
        |  TELIS  |      |  QUINT  |      | Guards  |
        +---------+      +---------+      +---------+
```

### Components

| Component          | Purpose                                                     |
| ------------------ | ----------------------------------------------------------- |
| **Runtime Engine** | Step execution, state machine, artifact indexing            |
| **TELIS**          | LSP symbiosis, shards, negotiation, cache, validation gates |
| **QUINT**          | Evidence store, ADI cycle, WLNK/congruence, decay, DRR      |
| **Providers**      | Multi-LLM routing with retries, circuit breaker, streaming  |
| **Guardrails**     | PII, moderation, blocklists, tool risk gating               |
| **Installer**      | Unified CLI for install, update, verify, status             |

---

## Providers

Configured in `config/runtime.yaml`. All providers support retries, backoff, and circuit breaker.

| Provider  | Type      | Default Base URL                            | Auth    |
| --------- | --------- | ------------------------------------------- | ------- |
| Mock      | mock      | n/a                                         | n/a     |
| Ollama    | ollama    | `http://localhost:11434`                    | none    |
| LiteLLM   | litellm   | `http://localhost:4000`                     | API key |
| OpenAI    | openai    | `https://api.openai.com`                    | API key |
| Anthropic | anthropic | `https://api.anthropic.com`                 | API key |
| Gemini    | gemini    | `https://generativelanguage.googleapis.com` | API key |
| Groq      | groq      | `https://api.groq.com/openai/v1`            | API key |

---

## CLI Reference

```bash
# Workflow execution
python -m cli.main run <module> <workflow> --agent <agent> --provider <provider>
python -m cli.main resume <run-id> --agent <agent> --provider <provider>
python -m cli.main interactive --module <module> --workflow <workflow>
python -m cli.main start --provider <provider>

# Gate management
python -m cli.main approve <run-id> --by <approver>
python -m cli.main status <run-id>

# Run management
python -m cli.main list [--module <module>]
python -m cli.main history --limit 10
python -m cli.main export <run-id> --output bundle.json --report

# TELIS context management
python -m cli.main telis status
python -m cli.main telis list [--language <lang>] [--tier <tier>]
python -m cli.main telis init [--output <path>]
python -m cli.main telis add <shards-file>

# QUINT evidence tracking
python -m cli.main quint status <run-id>
python -m cli.main quint evidence <run-id> [--level <L1|L2|L3>]
python -m cli.main quint drr <run-id>

# Configuration
python -m cli.main validate
python -m cli.main providers

# Installer
baqt install [target] [--force] [--build-quint]
baqt update [target]
baqt verify [target]
baqt status [target]
```

---

## Project Structure

```text
BAQT/
+-- runtime/           # Engine, gates, providers, tools, guardrails
|   +-- telis/         # Context management (shards, cache, negotiation)
|   +-- quint/         # Evidence engine (store, ADI, WLNK, DRR)
|   +-- providers/     # LLM provider adapters
|   +-- guardrails/    # PII, moderation, rules checks
|   +-- tools/         # File IO, repo, LSP, validation
|   +-- logging/       # Structured logging and observability
+-- installer/         # Unified installer module
+-- cli/               # CLI entrypoints
+-- methodology/       # Unified spec, registries, mapping
+-- config/            # Runtime configuration
+-- docs/              # Plans, audits, reference docs
+-- tests/             # Unit, integration, and E2E tests
```

---

## Documentation

| Document                                                    | Description                                  |
| ----------------------------------------------------------- | -------------------------------------------- |
| [v1 Release Plan](docs/v1-plan.md)                          | Source of truth for v1.0 scope and checklist |
| [Traceability Audit](docs/traceability-audit.md)            | Requirement coverage and evidence mapping    |
| [Installation Guide](docs/installation-guide.md)            | Detailed installation instructions           |
| [Unified Spec](methodology/unified_method_specification.md) | Framework specification                      |
| [Runtime Schemas](docs/runtime-schemas.json)                | JSON schema definitions                      |
| [Step Contract](docs/runtime-step-contract.md)              | Step execution contract                      |
| [Tool Pipeline](docs/tool-execution-pipeline.md)            | Tool execution architecture                  |
| [Release Checklist](docs/release-checklist.md)              | v1.0.0 release verification                  |
| [Changelog](CHANGELOG.md)                                   | Version history                              |

---

## Development

### Setup

```bash
git clone https://github.com/fabiendostie/BAQT.git
cd BAQT
pip install -r requirements-dev.txt
npm install
npm run prepare
```

### Quality Gates

```bash
npm run lint          # Ruff, markdownlint, ESLint
npm run format:check  # Ruff, Prettier
npm run typecheck     # mypy, pyright
npm test              # pytest with coverage
```

### Test Coverage

- **495 tests** with **88.87% coverage**
- Unit tests for all runtime modules
- Integration tests for BMAD workflows
- E2E tests for gates, artifacts, and evidence

### Optional Live Provider Smoke Test

Run a single-step workflow against a real provider (skipped unless configured):

```bash
# Example (OpenAI)
export BAQT_LIVE_PROVIDER=openai
export OPENAI_API_KEY=...
python -m pytest tests/test_integration_live_provider.py
```

Optional overrides:

- `BAQT_LIVE_MODEL` to select a model
- `BAQT_LIVE_BASE_URL` for Ollama or LiteLLM

Gemini helper script (uses DPAPI-encrypted secret):

```powershell
.\scripts\run-live-gemini.ps1
```

### Optional Live Full Lifecycle Test

Runs analysis -> planning -> solutioning -> implementation using BMAD templates plus TELIS/QUINT with a dev-story QA loop:

```bash
export BAQT_LIVE_PROVIDER=gemini
export BAQT_LIVE_E2E=1
python -m pytest tests/test_integration_full_lifecycle_live.py
```

Gemini helper script:

```powershell
.\scripts\run-live-gemini.ps1 -Lifecycle
```

---

## Version and Releases

- **Current version:** 1.0.0
- **Version source:** `VERSION` file (SemVer 2.0.0)
- **Primary branch:** `development`
- **Release branch:** `main`

See [versioning policy](docs/versioning.md) for details.

---

## Contributing

1. All changes must map to [docs/v1-plan.md](docs/v1-plan.md)
2. Update [CHANGELOG.md](CHANGELOG.md) for non-doc changes
3. Follow Conventional Commits (enforced by hook)
4. Ensure CI passes before merge

---

## License

MIT License - see [LICENSE](LICENSE) for details.

---

**BAQT** - BMAD + QUINT + TELIS Unified Autonomous Framework
