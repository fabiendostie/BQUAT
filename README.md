# BQUAT Unified Agentic Framework

This repository consolidates BMAD-METHOD with Quint-code (FPF reasoning) and TELIS (token optimization) into a single, fully automated framework with blocking human-in-the-loop gates.

## What is here

- Unified method specification: methodology/unified_method_specification.md
- v1.0 release plan and checklist: docs/v1-plan.md
- Traceability audit and requirement coverage: docs/traceability-audit.md
- Agent and workflow registries: methodology/registry-agents.md, methodology/registry-workflows.md
- Agent menu bindings: methodology/registry-agent-menus.md
- Workflow to Quint/TELIS mapping: methodology/integration-mapping.md
- CI/CD blueprint: cicd/ci-cd-blueprint.md
- Security audit template: security/security-audit-report-template.md
- Documentation index: docs/unified-framework-documentation-index.md
- Runtime configuration: config/runtime.yaml
- Runtime engine scaffolding: runtime/

## v1.0 plan and checklist

The authoritative plan and checklist live at docs/v1-plan.md. Update that file to track progress and keep scope locked.

## Change control and branch policy

Scope changes must be recorded in docs/v1-plan.md with an owner and rationale. The development branch is primary; main is release only.

## Regenerate registries and mappings

```bash
python methodology/tools/generate_mapping.py
```

Generated machine-readable outputs are written to methodology/mapping/.

## Tests

Run the automated checks (mapping accuracy, gate consistency, style, coverage):

```bash
python tests/run_tests.py
```

Run the pytest suite:

```bash
pytest
```

## CLI

Examples:

```bash
python -m cli.main validate
python -m cli.main run bmm prd --agent bmad --provider mock
python -m cli.main approve <run-id> --by you
python -m cli.main status <run-id>
```

## Human-in-the-loop gates

Planning, architecture, and release gates are blocking. Conditional gates apply to implementation review, test failures, and security risk acceptance. See methodology/unified_method_specification.md.

## Runtime notes

- Config uses JSON syntax in runtime.yaml to avoid external YAML dependencies.
- Run manifests and approvals are stored under runs/<run_id>/ when executing workflows.

## Versioning

This repository follows SemVer (see docs/versioning.md). The source of truth is the root VERSION file.

## Developer tooling

Install dev tools and hooks:

```bash
pip install -r requirements-dev.txt
npm install
npm run prepare
```

`npm install` runs the Husky prepare script automatically; use `npm run prepare` if hooks are missing.

## Notes

- Sample and reference workflows are excluded from production registries and mappings.
- Mapping artifacts only include explicit outputs and templates from workflow definitions.
