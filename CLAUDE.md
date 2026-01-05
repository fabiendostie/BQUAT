# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BAQT is a unified agentic framework that combines BMAD-METHOD (workflow), TELIS (token-efficient context), and QUINT (evidence-based reasoning) under one runtime with blocking human-in-the-loop (HITL) gates.

**Key docs:** `docs/v1-plan.md` (release plan), `methodology/unified_method_specification.md` (unified spec), `docs/runtime-step-contract.md` (step contract), `docs/tool-execution-pipeline.md` (tool pipeline).

## Common Commands

```bash
# Setup
uv pip install -r requirements-dev.txt   # or: pip install -r requirements-dev.txt
npm install
npm run prepare                          # Setup Husky git hooks
python methodology/tools/generate_mapping.py

# Quality gates (pre-commit enforced)
npm run lint          # Ruff + ESLint JSON + markdownlint
npm run format:check  # Ruff formatter + Prettier
npm run typecheck     # mypy + pyright
npm test              # Full test suite

# Running tests
python tests/run_tests.py   # Unit tests with 85% coverage gate
pytest                      # pytest suite

# CLI usage
python -m cli.main validate
python -m cli.main run bmm prd --agent bmad --provider mock
python -m cli.main approve <run-id> --by you
python -m cli.main status <run-id>
python -m cli.main list
python -m cli.main history --limit 5
python -m cli.main export <run-id> --output runs/export.json
```

## Architecture

**Core layers:**

- `runtime/engine.py` - WorkflowEngine orchestrates step execution (pending -> running -> completed|failed|blocked)
- `runtime/models.py` - Dataclass models: WorkflowSpec, RunStep, RunManifest, ArtifactRecord, EvidenceLink
- `runtime/gates.py` - Policy-based HITL gates (blocking by default), gate decisions recorded as DRRs
- `runtime/storage.py` - Persistence layer: manifest.json, approvals.json, artifacts.json, evidence.json
- `runtime/providers/` - Provider adapters: Mock, Ollama, LiteLLM, OpenAI, Anthropic, Gemini, Groq
- `runtime/telis/` - Context management: LSP symbiosis, knowledge shards (Tier 1-3), progressive negotiation
- `runtime/quint/` - Evidence engine: L0/L1/L2 levels, WLNK scoring, ADI cycle, decay tracking
- `runtime/tools/` - Tool registry with risk ratings, allow/block-list enforcement, HITL approval for high-risk
- `runtime/guardrails/` - PII filter, moderation blocklist, rules-based protections

**Run directory structure:** `runs/{run_id}/` contains manifest.json, approvals.json, artifacts.json, evidence.json, tool_results.json

## Critical Patterns

**Time handling:** Always use `runtime/time_provider.py` -> `get_current_time()` for timestamps (never `datetime.now()`). All timestamps use `BAQT_TIMEZONE` env var (defaults to America/Toronto).

**Data models:** Frozen dataclasses for immutable specs (WorkflowSpec, StepSpec, ArtifactRecord). Mutable dataclasses for runtime state (RunStep, RunManifest). Standard `to_dict()` / `from_dict()` serialization.

**JSON serialization:** All JSON written with ASCII encoding (no unicode). 2-space indent, sorted keys for deterministic output. See `runtime/storage.py` for consistency.

**Commit conventions:** Conventional Commits enforced (feat/fix/docs/style/refactor/perf/test/build/ci/chore/revert). All non-doc changes must update CHANGELOG.md. Pre-commit hooks enforce lint/typecheck/format-check.

**Code style:** Python 3.11, Ruff formatter (100 char line length). mypy strict mode, no unused ignores. 85% coverage threshold enforced on core modules.
