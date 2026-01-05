# BAQT v1.0.0 Release Checklist

Status: Complete
Date: 2026-01-03

## Pre-Release Verification

- [x] All tests pass (309 tests)
- [x] Coverage gate met (92.10% >= 85%)
- [x] Lint passes (ruff, markdownlint, eslint)
- [x] Type checking passes (mypy, pyright)
- [x] Integration tests pass for all BMAD modules

## Version Updates

- [x] VERSION file: 1.0.0
- [x] pyproject.toml: version = "1.0.0"
- [x] package.json: version: "1.0.0"
- [x] installer/**init**.py: **version** = "1.0.0"
- [x] installer/manifest.py: get_baqt_version() -> "1.0.0"

## Documentation

- [x] docs/v1-plan.md: Status updated to Complete
- [x] docs/v1-plan.md: Master checklist complete (17/17 items)
- [x] docs/traceability-audit.md: Sign-off complete
- [x] docs/unified-framework-documentation-index.md: WS15 docs added
- [x] CHANGELOG.md: [1.0.0] section added with date

## Workstream Completion

| Workstream | Description                      | Status   |
| ---------- | -------------------------------- | -------- |
| WS1        | Governance and repo hygiene      | Complete |
| WS2        | Canonical runtime data model     | Complete |
| WS3        | Mapping and registry pipeline    | Complete |
| WS4        | Workflow executor                | Complete |
| WS5        | Tool adapter layer               | Complete |
| WS6        | TELIS context manager            | Complete |
| WS7        | QUINT evidence engine            | Complete |
| WS8        | Provider routing and reliability | Complete |
| WS9        | HITL gate enforcement            | Complete |
| WS10       | Artifact index and audit trail   | Complete |
| WS11       | CLI and user experience          | Complete |
| WS12       | Guardrails and safety            | Complete |
| WS13       | Observability                    | Complete |
| WS14       | Test strategy and CI hardening   | Complete |
| WS15       | Distribution and installer       | Complete |
| WS16       | Release readiness                | Complete |

## Components Included

- **BMAD-METHOD**: Workflow definitions, agents, slash commands
- **TELIS**: LSP symbiosis, shards, negotiation, cache, validation gates
- **QUINT**: Evidence store, ADI, WLNK, congruence, decay, DRR
- **Runtime**: Engine, providers, guardrails, observability
- **Installer**: Unified CLI with install/update/verify/status

## Known Gaps (Post-v1.0)

These items are documented as out-of-scope for v1.0:

- BMAD-006: Full orchestrator routing (basic engine exists)
- QUINT-007/008: Surface vs grounding separation, context drift
- GUIDE-008: Optimistic execution with concurrent guardrails
- SPEC-001/009/010: Event bus, context fingerprint, gates as DRRs
- SPEC-005/006: Full plugin pipeline (minimal manager exists)

## Release Steps

1. Commit WS16 changes to development branch
2. Verify CI passes on development
3. Merge development to main
4. Tag v1.0.0 on main
5. Create GitHub release with release notes

## Sign-off

Release prepared and verified: 2026-01-03
