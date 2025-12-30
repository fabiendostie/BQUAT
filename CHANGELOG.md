# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and this project adheres to Semantic Versioning.
Last updated: 2025-12-29T20:43:22-05:00

## [Unreleased]

### Added

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

### Changed

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
