# BQUAT Unified Agentic Framework

This repository consolidates BMAD-METHOD with Quint-code (FPF reasoning) and TELIS (token optimization) into a single, fully automated framework with blocking human-in-the-loop gates.

## What is here

- Unified method specification: methodology/unified_method_specification.md
- Agent and workflow registries: methodology/registry-agents.md, methodology/registry-workflows.md
- Agent menu bindings: methodology/registry-agent-menus.md
- Workflow to Quint/TELIS mapping: methodology/integration-mapping.md
- CI/CD blueprint: cicd/ci-cd-blueprint.md
- Security audit template: security/security-audit-report-template.md
- Documentation index: docs/unified-framework-documentation-index.md

## Regenerate registries and mappings

```bash
python methodology/tools/generate_mapping.py
```

## Tests

Run the automated checks (mapping accuracy, gate consistency, style, coverage):

```bash
python tests/run_tests.py
```

## Human-in-the-loop gates

Planning, architecture, and release gates are blocking. Conditional gates apply to implementation review, test failures, and security risk acceptance. See methodology/unified_method_specification.md.

## Notes

- Sample and reference workflows are excluded from production registries and mappings.
- Mapping artifacts only include explicit outputs and templates from workflow definitions.
