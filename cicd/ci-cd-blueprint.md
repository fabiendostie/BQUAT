# CI/CD Blueprint

## Purpose

Define a CI/CD pipeline that enforces BMAD quality gates, TELIS validation, and Quint evidence capture for autonomous delivery.

## Pipeline Stages

1) Pre-merge checks
   - Formatting and linting
   - Type checks where applicable
   - Unit tests and fast integration tests
   - Security baseline scan (static analysis)

2) Build and package
   - Build artifacts
   - Generate checksums
   - Produce release notes stubs

3) Integration and E2E
   - ATDD or integration test suite
   - E2E tests when required
   - Performance smoke checks for critical paths

4) Release preparation
   - Version bump (if required)
   - SBOM and dependency report
   - Signed artifacts

5) Deployment
   - Environment promotion (dev -> staging -> prod)
   - Health checks and rollback hooks

## Quality Gates

- All required tests pass
- Lint and type checks pass
- Security scan has no criticals
- Evidence recorded for key decisions and risk acceptance

## Evidence and Audit (Quint)

- Attach test reports, scan results, and build metadata to L2 evidence
- Track evidence validity windows and decay
- Record release decisions as DRRs

## TELIS Validation Hooks

- AST, type, and lint checks required before code output or merge
- LSP data must be used for API signatures

## Failure Handling

- Auto-retry transient failures once
- Block on repeat failure and log for review
- Escalate if failures indicate tool risk or policy violation

## Recommended Triggers

- Pull request: Pre-merge checks
- Main branch: Full pipeline
- Tagged release: Full pipeline + deployment
