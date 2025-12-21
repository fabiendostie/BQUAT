# BQUAT Unified Agentic Framework

![CI](https://github.com/fabiendostie/BQUAT/actions/workflows/ci.yml/badge.svg?branch=development)
![Coverage](https://img.shields.io/badge/coverage->=85%25-brightgreen)
![SemVer](https://img.shields.io/badge/semver-2.0.0-blue)
![HITL](https://img.shields.io/badge/HITL-blocking-orange)

BQUAT consolidates BMAD-METHOD with Quint-code (FPF reasoning) and TELIS (token optimization) into a single, fully automated framework with blocking human-in-the-loop gates.

## Highlights

- Preserves BMAD workflows and output conventions.
- Enforces TELIS context policy and validation gates.
- Applies QUINT evidence, ADI checkpoints, and DRR discipline.
- CLI-first approvals with blocking HITL gates.

## Quick start

```bash
uv pip install -r requirements-dev.txt
# or: pip install -r requirements-dev.txt
npm install
npm run prepare
python methodology/tools/generate_mapping.py
python tests/run_tests.py
pytest
```

## Quality checks

```bash
npm run lint
npm run format:check
npm test
```

Linting uses Ruff for Python, ESLint JSON rules for duplicate keys, markdownlint-cli2 for Markdown, and Prettier for formatting.

## Core docs

- Unified method specification: methodology/unified_method_specification.md
- v1.0 release plan and checklist: docs/v1-plan.md
- Traceability audit and requirement coverage: docs/traceability-audit.md
- Runtime step contract: docs/runtime-step-contract.md
- Documentation index: docs/unified-framework-documentation-index.md

## Registries and mappings

- Agent and workflow registries: methodology/registry-agents.md, methodology/registry-workflows.md
- Agent menu bindings: methodology/registry-agent-menus.md
- Workflow to Quint/TELIS mapping: methodology/integration-mapping.md

## Runtime and tooling

- Runtime configuration: config/runtime.yaml
- Runtime engine scaffolding: runtime/
- CI/CD blueprint: cicd/ci-cd-blueprint.md
- Security audit template: security/security-audit-report-template.md

## CLI

```bash
python -m cli.main validate
python -m cli.main run bmm prd --agent bmad --provider mock
python -m cli.main approve <run-id> --by you
python -m cli.main status <run-id>
```

## Timezone and timestamps

All runtime timestamps use getCurrentTime and default to America/Toronto. Override with `BQUAT_TIMEZONE` if needed.

## Change control and branch policy

Scope changes must be recorded in docs/v1-plan.md with an owner and rationale. The development branch is primary; main is release only.

## Versioning

This repository follows SemVer (see docs/versioning.md). The source of truth is the root VERSION file.

## Notes

- Sample and reference workflows are excluded from production registries and mappings.
- Mapping artifacts only include explicit outputs and templates from workflow definitions.
