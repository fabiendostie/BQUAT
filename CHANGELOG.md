# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and this project adheres to Semantic Versioning.
Last updated: 2026-01-05

## [Unreleased]

### Added

- Comprehensive tests for cli/main.py achieving 85%+ coverage (98 test cases).
- TELIS CLI commands for shard management (status, list, add, init).
- QUINT CLI commands for evidence tracking (status, evidence, drr).
- Sample TELIS shards configuration file with Python, JavaScript, and JSON shards.
- Comprehensive BMAD/TELIS/QUINT usage guide in README.md.
- Post-install quickstart guide showing provider setup and workflow commands.
- Installer `__main__.py` for `python -m installer` module execution.
- `baqt-run` command documentation in installer/commands.
- Integration tests for live providers, greenfield pipeline, and full lifecycle.
- PowerShell script for running live Gemini tests.
- WSL Python wrapper (`bin/python-wrapper.sh`) for cross-platform hook compatibility.

### Changed

- Updated runtime quint/assurance module with enhanced validation.
- Updated runtime quint/drr module with expanded DRR handling.
- Updated runtime telis/context with improved context management.
- Enhanced provider registry with additional capabilities.
- Fixed husky pre-commit hook for WSL Python compatibility.

### Fixed

- Installer module now executable via `python -m installer` command.

### Added (continued)

- Event bus for workflow state transitions with pub/sub pattern (REQ-SPEC-001).
- Plugin pipeline with control plane and data plane separation (REQ-SPEC-005, REQ-SPEC-006).
- Built-in plugins: GatePolicyPlugin, AuditPlugin for policy enforcement and audit logging.
- Dynamic tool registry with categories, metadata, and risk levels (REQ-AGENT-002).
- Per-agent tool bindings and instructions with AgentDefinition and AgentRegistry (REQ-AGENT-001).
- Context fingerprint tracking linking TELIS resolution to evidence (REQ-SPEC-009).
- Context snapshot and drift detection for bounded context management (REQ-QUINT-008).
- Surface vs grounding separation with DrrSummary for stakeholder views (REQ-QUINT-007).
- Gates recorded as DRRs with full evidence links (REQ-SPEC-010).
- Concurrent guardrails using asyncio for optimistic execution (REQ-AGENT-008).
- Failure isolation with tool-level and step-level bounded retries (REQ-SPEC-007).
- Full workflow orchestrator with dependency graphs and resource scheduling (REQ-BMAD-006).
- Interactive CLI mode with step executor for guided workflow execution.
- Command-based installer structure with modular command handlers.
- IDE integration documentation for VS Code and JetBrains.
- Run artifact packaging utilities (zip/node/docker) with coverage tests.
- CD workflow for release publishing to PyPI, npm, and GitHub.
- Comprehensive coverage tests for CLI, agents, plugin manager, and packaging.

### Changed (continued)

- Renamed package from bquat to baqt for consistency.
- Updated traceability audit to reflect all requirements as done.
- Enhanced plugin manager with two-phase execution (policy then observation).
- Integrated event bus publishing throughout the workflow engine.
- Config loader now supports JSON or YAML runtime configs.
- npm package marked non-private to allow publishing.
- Enforce LF line endings with repository gitattributes.
- Resolve typecheck issues in orchestrator routing, guardrails, and interactive CLI.
- Refresh installer command documentation formatting and examples.
- Add PyYAML type stubs to unblock mypy in CI.
- Configure explicit setuptools package discovery to fix build packaging.

## [1.0.0] - 2026-01-03

### Added

- Unified installer module with BMAD + TELIS + QUINT integration.
- Installer CLI with install, update, verify, and status commands.
- Installation manifest tracking with component versions and file checksums.
- Installation verification checklist with 10 integrity checks.
- Node.js wrapper for npx support (npx baqt install).
- IDE slash commands generation (baqt-status, baqt-run, baqt-evidence).
- Installation guide and installer integration documentation.
- Tool execution pipeline with registry, risk gating, HITL metadata, and tool results persistence.
- Tool adapters for safe file IO, repo operations, time, and LSP (Pyright/TypeScript) queries.
- Validation runners (AST, typecheck, lint) and engine validation gates with retries and output layout checks.
- Runtime schema registry and stable JSON schema export.
- Canonical workflow parsing for BMAD md/yaml/xml definitions plus step output parsing improvements.
- Deterministic mapping/registry generation with expanded mapping accuracy tests.
- Docs consistency tests enforcing plan/audit alignment and documentation index coverage.
- Step progression state machine enforcing status transitions.
- RunStep tool records now store tool execution results.
- Schema registry output now includes a generated_at timestamp.
- Persist run state after step errors and update timestamps on completion.
- Resume execution from the first incomplete step.
- Per-step retry policies with backoff in the runtime engine.
- PyYAML in dev requirements for workflow parsing in CI.
- TELIS shard registry with tier budgets and retrieval scoring.
- Integration test covering one workflow execution per BMAD module.
- Artifact index and event history persistence with runtime coverage tests.
- TELIS context routing with LSP response compression and shard fallback.
- TELIS progressive context negotiation with phase escalation heuristics.
- TELIS behavioral cache with TTL and invalidation triggers.
- TELIS policy engine and context manager wired into the runtime engine with cached context resolution.
- Plan executor now appends TELIS context to prompts and persists it in plan artifacts.
- QUINT evidence store with record/invalidate helpers and coverage tests.
- QUINT ADI promotion rules with invalidation handling and tests.
- QUINT WLNK assurance scoring and congruence penalties with tests.
- QUINT evidence decay scan with valid_until checks and tests.
- QUINT DRR generation with per-run JSON and markdown outputs.
- Provider routing reliability with retries, backoff, circuit breaker, and streaming support.
- Provider rate-limit handling with normalized error messages and retry hints.
- HITL gate policy enforcement with audit logs and approval events.
- Artifact index linkage to gate state and evidence IDs for audit trails.
- Run timeline JSON emitted with event, artifact, gate, evidence, and DRR entries.
- CLI commands for workflow listing, run history summaries, and export bundles.
- Guardrails for PII, moderation, and rules-based checks with runtime enforcement.
- Observability module with structured logging, event emission, and run report generation.
- StructuredLogger for JSON-formatted run/step/gate/evidence/validation logs.
- EventEmitter with CallbackHandler and ObservabilityPlugin for external tooling integration.
- RunReportGenerator for comprehensive run reports with summary statistics.
- CLI export command extended with --report flag for summary report generation.
- Provider contract tests verifying interface compliance for all 7 providers.
- TELIS + QUINT integration tests for combined policy and evidence flow.
- E2E workflow tests covering human gates, artifacts, events, timeline, and reports.
- Observability config section in runtime.yaml (enabled by default).

### Changed

- Bump version to 1.0.0 for v1.0 release.
- Add installer module to mypy typecheck in package.json.
- Step contract and tool execution pipeline documentation updates.
- Governance hardening with lint/typecheck/format hooks and changelog enforcement.
- Allow duplicate changelog headings across releases in markdownlint config.
- Align traceability audit and unified spec to the plan and BMAD-METHOD canonical layout.
- Add engine tests covering step state transitions.
- Align RunStep tools schema with tool result payloads.
- Include generated_at in runtime schema registry output.
- Add engine test to assert run state persistence on errors.
- Add engine test to assert resume starts from last incomplete step.
- Step retry behavior now honors StepSpec overrides and applies backoff between attempts.

### Fixed

- Remove WARP.md ignore from markdownlint config.

## [0.1.0] - 2025-12-24

### Added

- Unified framework spec, repository overview, release plan, and traceability audit.
- Runtime scaffolding for engine, agents, prompts, storage, and execution flow.
- Provider registry with OpenAI, Anthropic, Gemini, Groq, Ollama, and LiteLLM adapters.
- Plugin system scaffolding and CLI entry points.
- Mapping automation tooling and methodology extraction.
- Husky hooks, SemVer policy, and Conventional Commits enforcement.
- Time tool with timezone-aware formatting.

### Fixed

- CI mapping inputs and timezone-aware UTC timestamps.
