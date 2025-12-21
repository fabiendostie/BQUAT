# BQUAT v1.0 Release Plan

Status: Draft
Owner: Core maintainers
Last updated: TBD

## Purpose

This document is the single source of truth for delivering the BQUAT super-framework to v1.0. All work must map to this plan. Anything not listed here is out of scope for v1.0.

## Scope Lock

In scope:
- Fully automated execution with blocking human-in-the-loop (HITL) gates.
- End-to-end execution of real BMAD workflows with correct artifacts.
- TELIS token efficiency controls and validation gates.
- QUINT evidence and DRR workflows with auditable trails.
- Provider routing across Ollama, LiteLLM, OpenAI, Claude, Gemini, Groq.
- CLI-first approval and control.

Out of scope for v1.0:
- GUI or web-based approvals.
- Long-running distributed execution across multiple hosts.
- Multi-tenant user management.
- Full IDE plugin deployment and installation automation beyond CLI.

Change control:
- Any new requirement must be added here with a linked justification and an owner.
- No implementation work begins without a checklist item.

## Sources of Truth

- BMAD-METHOD (workflows, agents, output conventions)
- TELIS (LSP, shards, progressive negotiation, validation gates)
- QUINT (ADI cycle, evidence levels, DRR, WLNK, congruence, decay)
- docs/a-practical-guide-to-building-agents.md (model-tool-instructions, guardrails, HITL triggers)

## v1.0 Definition of Done

- At least one BMAD workflow executes end-to-end and produces required outputs and templates.
- HITL gates block on planning, architecture, and release stages and can be approved and resumed by CLI.
- TELIS policy is enforced: LSP symbiosis, shards, progressive negotiation, validation gates.
- QUINT evidence and DRR records are generated and linked to decisions.
- Provider routing is robust with retries, backoff, and error normalization.
- Mapping and registry generation excludes sample/reference workflows and lists explicit outputs/templates only.
- CI passes with coverage gate >= 85 percent and integration tests.

## Requirement Coverage Matrix

Status values: todo, in-progress, done, blocked

| ID | Source | Requirement | Owner | Status | Acceptance Evidence |
| --- | --- | --- | --- | --- | --- |
| REQ-BMAD-001 | BMAD | Preserve BMAD workflows and naming without rewriting logic | Runtime | todo | End-to-end BMAD run produces required outputs |
| REQ-BMAD-002 | BMAD | Sample/reference workflows excluded from production mapping | Mapping | done | tests/test_mapping.py passes |
| REQ-BMAD-003 | BMAD | Only explicit outputs/templates listed in mapping | Mapping | done | tests/test_mapping.py passes |
| REQ-TELIS-001 | TELIS | LSP symbiosis for type/signature accuracy | Tools | todo | LSP integration test |
| REQ-TELIS-002 | TELIS | Knowledge shards with tiered retrieval | TELIS | todo | shard retrieval test |
| REQ-TELIS-003 | TELIS | Progressive context negotiation | TELIS | todo | negotiation test |
| REQ-TELIS-004 | TELIS | AST, type, lint validation gates | TELIS | todo | validation gate test |
| REQ-TELIS-005 | TELIS | Behavioral cache with TTL | TELIS | todo | cache hit test |
| REQ-QUINT-001 | QUINT | ADI cycle (L0, L1, L2) with promotion rules | QUINT | todo | evidence workflow test |
| REQ-QUINT-002 | QUINT | WLNK assurance and congruence scoring | QUINT | todo | assurance audit test |
| REQ-QUINT-003 | QUINT | Evidence decay and revalidation | QUINT | todo | decay scan test |
| REQ-QUINT-004 | QUINT | DRR generation on major decisions | QUINT | todo | DRR record present |
| REQ-AGENT-001 | Practical Guide | Guardrails on tools with risk ratings | Runtime | todo | risk gate test |
| REQ-AGENT-002 | Practical Guide | HITL for high-risk actions and retries | Runtime | in-progress | gate tests |

## Workstreams and Steps

### WS1: Governance and repo hygiene
1. Confirm this plan as source of truth and add change-control note to README.
2. Align branch policy: development is primary, main is release only.
3. Ensure SemVer is enforced in VERSION and release notes.
4. Enforce Conventional Commits via commit-msg hook.
5. Verify CI uses latest compatible actions and locks versions.

Deliverables:
- docs/v1-plan.md
- README links to plan
- docs/unified-framework-documentation-index.md updated

### WS2: Canonical runtime data model
1. Define schemas for RunManifest, RunStep, ArtifactIndex, EvidenceLink, HumanGate.
2. Define event schema for run lifecycle and gate state.
3. Store all schema outputs in a stable JSON format.
4. Add schema validation tests.

Deliverables:
- runtime/models.py updates
- tests for schema round trips

### WS3: Mapping and registry pipeline
1. Parse BMAD workflow definitions (md/yaml/xml) into canonical steps.
2. Extract explicit outputs/templates only, exclude samples/references.
3. Generate registry and mapping files deterministically.
4. Add mapping accuracy tests for production workflows.

Deliverables:
- methodology/mapping/registry-workflows.json
- methodology/mapping/integration-mapping.json
- tests/test_mapping.py

### WS4: Workflow executor
1. Build a state machine for step progression (pending, running, blocked, failed, completed).
2. Implement step contract with inputs, outputs, tools, and validation hooks.
3. Persist run state after each step and on errors.
4. Implement resume semantics from the last incomplete step.
5. Enforce step timeouts and bounded retries.

Deliverables:
- runtime/engine.py execution path
- runtime/execution.py step execution contract
- tests/test_runtime_engine.py

### WS5: Tool adapter layer
1. Define tool interface with risk rating (low, medium, high).
2. Implement safe file IO and repo operations.
3. Implement LSP query adapters for supported languages.
4. Implement AST and type validation runners.
5. Add allow-list and block high-risk tools behind HITL.

Deliverables:
- runtime/tools/*
- validation executors
- tool risk policy

### WS6: TELIS context manager
1. Implement shard registry, retrieval, and tier budget enforcement.
2. Implement LSP symbiosis routing and compression.
3. Implement progressive negotiation protocol.
4. Implement behavioral cache with TTL and invalidation.
5. Enforce validation gates before output acceptance.

Deliverables:
- runtime/telis/*
- validation gate hooks
- tests for LSP/shard/cache

### WS7: QUINT evidence engine
1. Implement evidence store with L0, L1, L2 levels.
2. Implement ADI promotion rules and invalidation handling.
3. Implement WLNK and congruence scoring.
4. Implement evidence decay and revalidation checks.
5. Implement DRR generation and linking to decisions.

Deliverables:
- runtime/quint/*
- DRR records stored per run
- tests for evidence and DRR

### WS8: Provider routing and reliability
1. Normalize provider request/response models.
2. Implement retries, backoff, and timeouts.
3. Add circuit-breaker logic and rate limit handling.
4. Implement streaming support and chunked responses.
5. Add provider-specific response parsing.

Deliverables:
- runtime/providers/* improvements
- tests for provider behavior

### WS9: HITL gate enforcement
1. Define gate policy by phase and risk level.
2. Enforce blocking gates at planning, architecture, release.
3. Enforce conditional gates for implementation review, tests, security risk.
4. Add CLI approvals and audit logs.

Deliverables:
- runtime/gates.py updates
- CLI approve/resume flows
- tests for gate consistency

### WS10: Artifact index and audit trail
1. Index every output and template with checksum.
2. Link artifacts to step, evidence, and gate state.
3. Emit run timeline JSON for auditability.

Deliverables:
- runtime/storage.py enhancements
- tests for artifact index

### WS11: CLI and user experience
1. Add commands: run, resume, approve, status, list, export.
2. Add config validation and provider listing.
3. Add run history summary.

Deliverables:
- cli/main.py updates
- CLI tests

### WS12: Guardrails and safety
1. Implement PII filter and output validation hooks.
2. Implement moderation checks for high-risk content.
3. Enforce tool risk safeguards with HITL.
4. Add rules-based protections (blocklists, regex checks).

Deliverables:
- runtime/guardrails/*
- tests for guardrail triggers

### WS13: Observability
1. Structured logs for run, step, gate, evidence, validation.
2. Event emission for external tooling.
3. Export run report artifacts.

Deliverables:
- runtime/logging/*
- run report JSON

### WS14: Test strategy and CI hardening
1. End-to-end test for at least one BMAD workflow.
2. Integration tests for TELIS and QUINT gates.
3. Provider contract tests (mocked).
4. Coverage gate >= 85 percent.
5. CI passes on development with submodules.

Deliverables:
- tests/* integration suite
- CI green

### WS15: Release readiness
1. Final documentation sweep and index update.
2. Version bump to 1.0.0 and changelog.
3. Tag release on main after development is green.
4. Release checklist sign-off.

Deliverables:
- VERSION updated
- release notes
- tags on main

## Master Checklist (v1.0)

- [ ] Confirm plan is the source of truth and update README link
- [ ] Complete runtime data model and schemas
- [ ] Implement BMAD workflow parsing and canonical registry
- [ ] Build step execution state machine
- [ ] Implement tool adapters and risk policy
- [ ] Implement TELIS LSP, shards, negotiation, cache, and validation gates
- [ ] Implement QUINT evidence engine, WLNK, congruence, decay, and DRR
- [ ] Harden provider routing with retries and circuit breakers
- [ ] Enforce HITL gating with CLI approvals
- [ ] Add artifact indexing and run timeline
- [ ] Expand CLI (list, export, history)
- [ ] Implement guardrails (PII, moderation, rules)
- [ ] Add observability and run reports
- [ ] Integration tests for at least one BMAD workflow
- [ ] CI green with coverage >= 85 percent
- [ ] Release docs and tag v1.0.0 on main

## Verification and Gap Audit

We will not claim full coverage until the traceability audit is complete. This includes:
- Cross-checking all BMAD workflows and outputs against the registry.
- Mapping TELIS requirements to concrete runtime modules and tests.
- Mapping QUINT requirements to evidence, DRR, and audit outputs.
- Mapping Practical Guide guardrails to runtime guardrail implementations.

The traceability audit must be marked done before v1.0 release.
