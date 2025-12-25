# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and this project adheres to Semantic Versioning.
Last updated: 2025-12-25T06:54:23-05:00

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

### Changed

- Step contract and tool execution pipeline documentation updates.
- Governance hardening with lint/typecheck/format hooks and changelog enforcement.
- Allow duplicate changelog headings across releases in markdownlint config.
- Align traceability audit and unified spec to the plan and BMAD-METHOD canonical layout.
- Add engine tests covering step state transitions.

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
