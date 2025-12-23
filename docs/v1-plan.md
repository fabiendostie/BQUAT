# BQUAT v1.0 Release Plan

Status: Draft
Owner: Core maintainers
Last updated: 2025-12-23T04:37:42-05:00

## Purpose

This document is the single source of truth for delivering the BQUAT super-framework to v1.0. All work must map to this plan. Anything not listed here is out of scope for v1.0.

## Scope Lock

In scope:

- Fully automated execution with blocking human-in-the-loop (HITL) gates.
- Pre-development phases default to manual; optional CLI menu enables automation with HITL when approved.
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
- docs/traceability-audit.md (requirement mapping and evidence)

## v1.0 Definition of Done

- At least one BMAD workflow executes end-to-end and produces required outputs and templates.
- HITL gates block on planning, architecture, and release stages and can be approved and resumed by CLI.
- TELIS policy is enforced: LSP symbiosis, shards, progressive negotiation, validation gates.
- QUINT evidence and DRR records are generated and linked to decisions.
- Provider routing is robust with retries, backoff, and error normalization.
- Mapping and registry generation excludes sample/reference workflows and lists explicit outputs/templates only.
- CI passes with coverage gate >= 85 percent and integration tests.

## Requirement Coverage Matrix

Status values: todo, in-progress, done, partial, missing, blocked

Full traceability with evidence is maintained in docs/traceability-audit.md. This matrix must stay in sync.

| ID              | Source          | Requirement                                                      | Owner   | Status  | Acceptance Evidence                                                                                                                          |
| --------------- | --------------- | ---------------------------------------------------------------- | ------- | ------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| REQ-BMAD-001    | BMAD            | Preserve BMAD workflows and naming without rewriting logic       | Runtime | partial | Planned: end-to-end workflow run test                                                                                                        |
| REQ-BMAD-002    | BMAD            | Sample/reference workflows excluded from production mapping      | Mapping | done    | tests/test_mapping.py                                                                                                                        |
| REQ-BMAD-003    | BMAD            | Only explicit outputs/templates listed in mapping                | Mapping | done    | tests/test_mapping.py                                                                                                                        |
| REQ-BMAD-004    | BMAD            | Parse workflow definitions (md/yaml/xml) into steps              | Runtime | done    | tests/test_workflow_parser.py                                                                                                                |
| REQ-BMAD-005    | BMAD            | Enforce output folder/layout conventions                         | Runtime | missing | Planned: output validation tests                                                                                                             |
| REQ-BMAD-006    | BMAD            | Orchestrator routes workflows and agents                         | Runtime | missing | Planned: orchestration tests                                                                                                                 |
| REQ-BMAD-007    | BMAD            | Support all BMAD modules (core, BMM, BMB, CIS, BMGD)             | Runtime | partial | methodology/registry-workflows.md                                                                                                            |
| REQ-INSTALL-001 | Distribution    | Single-command install for full framework (BMAD + QUINT + BQUAT) | Release | missing | Planned: installer integration tests                                                                                                         |
| REQ-TELIS-001   | TELIS           | LSP symbiosis for type/signature accuracy                        | Tools   | partial | runtime/tools/lsp.py, tests/test_runtime_lsp.py                                                                                              |
| REQ-TELIS-002   | TELIS           | LSP fallback to shards on failure                                | Tools   | missing | Planned: LSP fallback tests                                                                                                                  |
| REQ-TELIS-003   | TELIS           | Tiered knowledge shards with token budgets                       | TELIS   | missing | Planned: shard retrieval tests                                                                                                               |
| REQ-TELIS-004   | TELIS           | Progressive context negotiation protocol                         | TELIS   | missing | Planned: negotiation tests                                                                                                                   |
| REQ-TELIS-005   | TELIS           | AST/type/lint validation pipeline                                | TELIS   | partial | runtime/tools/validation.py, tests/test_runtime_validation.py                                                                                |
| REQ-TELIS-006   | TELIS           | Behavioral cache with TTL and invalidation                       | TELIS   | missing | Planned: cache hit tests                                                                                                                     |
| REQ-TELIS-007   | TELIS           | Validation failures trigger retry/escalation                     | TELIS   | partial | runtime/engine.py                                                                                                                            |
| REQ-QUINT-001   | QUINT           | Evidence store for L0/L1/L2 and invalid                          | QUINT   | missing | Planned: evidence store tests                                                                                                                |
| REQ-QUINT-002   | QUINT           | ADI cycle with promotion rules                                   | QUINT   | missing | Planned: ADI promotion tests                                                                                                                 |
| REQ-QUINT-003   | QUINT           | WLNK assurance scoring                                           | QUINT   | missing | Planned: assurance tests                                                                                                                     |
| REQ-QUINT-004   | QUINT           | Congruence scoring for external evidence                         | QUINT   | missing | Planned: congruence tests                                                                                                                    |
| REQ-QUINT-005   | QUINT           | Evidence decay and revalidation                                  | QUINT   | missing | Planned: decay scan tests                                                                                                                    |
| REQ-QUINT-006   | QUINT           | DRR generation for major decisions                               | QUINT   | missing | Planned: DRR record tests                                                                                                                    |
| REQ-QUINT-007   | QUINT           | Surface vs grounding separation                                  | QUINT   | missing | Planned: summary vs storage tests                                                                                                            |
| REQ-QUINT-008   | QUINT           | Bounded context snapshot and drift detection                     | QUINT   | missing | Planned: context drift tests                                                                                                                 |
| REQ-AGENT-001   | Practical Guide | Model/tool/instructions triad per agent                          | Runtime | partial | runtime/agents.py, runtime/prompts.py                                                                                                        |
| REQ-AGENT-002   | Practical Guide | Standardized tool definitions and reuse                          | Runtime | partial | runtime/tools/base.py, runtime/tools/file_io.py, runtime/tools/repo_tool.py, tests/test_runtime_file_io.py, tests/test_runtime_repo_tools.py |
| REQ-AGENT-003   | Practical Guide | Tool risk ratings and safeguards                                 | Runtime | partial | runtime/tools/base.py, runtime/tools/time_tool.py, runtime/tools/pipeline.py                                                                 |
| REQ-AGENT-004   | Practical Guide | PII filter and data privacy guardrails                           | Runtime | missing | Planned: PII guardrail tests                                                                                                                 |
| REQ-AGENT-005   | Practical Guide | Moderation filters for unsafe inputs                             | Runtime | missing | Planned: moderation tests                                                                                                                    |
| REQ-AGENT-006   | Practical Guide | Rules-based protections (blocklists/regex)                       | Runtime | missing | Planned: rules gate tests                                                                                                                    |
| REQ-AGENT-007   | Practical Guide | HITL on high-risk actions and retry thresholds                   | Runtime | partial | runtime/gates.py                                                                                                                             |
| REQ-AGENT-008   | Practical Guide | Optimistic execution with concurrent guardrails                  | Runtime | missing | Planned: guardrail concurrency tests                                                                                                         |
| REQ-SPEC-001    | Unified Spec    | Event bus for workflow state transitions                         | Runtime | missing | Planned: event bus tests                                                                                                                     |
| REQ-SPEC-002    | Unified Spec    | State store for workflow progress and artifacts                  | Runtime | partial | runtime/storage.py                                                                                                                           |
| REQ-SPEC-003    | Unified Spec    | TELIS policy engine and context manager                          | TELIS   | missing | Planned: TELIS policy tests                                                                                                                  |
| REQ-SPEC-004    | Unified Spec    | Evidence store for Quint claims and DRRs                         | QUINT   | missing | Planned: evidence store tests                                                                                                                |
| REQ-SPEC-005    | Unified Spec    | Control plane/data plane split                                   | Runtime | partial | runtime/plugins/manager.py                                                                                                                   |
| REQ-SPEC-006    | Unified Spec    | Plugin pipeline for policy/adapters/observability                | Runtime | partial | runtime/plugins/manager.py                                                                                                                   |
| REQ-SPEC-007    | Unified Spec    | Failure isolation with bounded retries                           | Runtime | partial | runtime/engine.py                                                                                                                            |
| REQ-SPEC-008    | Unified Spec    | Artifact index with checksum and provenance                      | Runtime | missing | Planned: artifact index tests                                                                                                                |
| REQ-SPEC-009    | Unified Spec    | Context fingerprint tracking                                     | Runtime | missing | Planned: context fingerprint tests                                                                                                           |
| REQ-SPEC-010    | Unified Spec    | Gates recorded as DRRs with evidence links                       | Runtime | missing | Planned: gate DRR tests                                                                                                                      |
| REQ-SPEC-011    | Unified Spec    | Tool execution pipeline (registry, gating, results)              | Runtime | partial | runtime/tools/pipeline.py, tests/test_runtime_tool_pipeline.py                                                                               |

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
- docs/runtime-step-contract.md
- tests/test_runtime_engine.py

### WS5: Tool adapter layer

1. Define tool interface with risk rating (low, medium, high). (done: runtime/tools/base.py)
2. Implement safe file IO and repo operations. (done: runtime/tools/file_io.py, runtime/tools/repo_tool.py)
3. Implement LSP query adapters for supported languages. (done: runtime/tools/lsp.py)
4. Implement AST and type validation runners. (done: runtime/tools/validation.py, tests/test_runtime_validation.py)
5. Add allow-list and block high-risk tools behind HITL. (in progress: runtime/tools/pipeline.py)
6. Define and implement the tool execution pipeline (registry, gating, results). (in progress: runtime/tools/pipeline.py)

Deliverables:

- runtime/tools/\*
- validation executors
- tool risk policy
- docs/tool-execution-pipeline.md

### WS6: TELIS context manager

1. Implement shard registry, retrieval, and tier budget enforcement.
2. Implement LSP symbiosis routing and compression.
3. Implement progressive negotiation protocol.
4. Implement behavioral cache with TTL and invalidation.
5. Enforce validation gates before output acceptance.

Deliverables:

- runtime/telis/\*
- validation gate hooks
- tests for LSP/shard/cache

### WS7: QUINT evidence engine

1. Implement evidence store with L0, L1, L2 levels.
2. Implement ADI promotion rules and invalidation handling.
3. Implement WLNK and congruence scoring.
4. Implement evidence decay and revalidation checks.
5. Implement DRR generation and linking to decisions.

Deliverables:

- runtime/quint/\*
- DRR records stored per run
- tests for evidence and DRR

### WS8: Provider routing and reliability

1. Normalize provider request/response models.
2. Implement retries, backoff, and timeouts.
3. Add circuit-breaker logic and rate limit handling.
4. Implement streaming support and chunked responses.
5. Add provider-specific response parsing.

Deliverables:

- runtime/providers/\* improvements
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

- runtime/guardrails/\*
- tests for guardrail triggers

### WS13: Observability

1. Structured logs for run, step, gate, evidence, validation.
2. Event emission for external tooling.
3. Export run report artifacts.

Deliverables:

- runtime/logging/\*
- run report JSON

### WS14: Test strategy and CI hardening

1. End-to-end test for at least one BMAD workflow.
2. Integration tests for TELIS and QUINT gates.
3. Provider contract tests (mocked).
4. Coverage gate >= 85 percent.
5. CI passes on development with submodules.

Deliverables:

- tests/\* integration suite
- CI green

### WS15: Distribution and installer integration

1. Package a full framework install through the BMAD installer (`npx bmad-method@alpha install`).
2. Ensure QUINT and BQUAT assets are included alongside BMAD slash commands.
3. Add an installation verification test or checklist.

Deliverables:

- Installer integration notes
- Install validation check

### WS16: Release readiness

1. Final documentation sweep and index update.
2. Version bump to 1.0.0 and changelog.
3. Tag release on main after development is green.
4. Release checklist sign-off.

Deliverables:

- VERSION updated
- release notes
- tags on main

## Master Checklist (v1.0)

- [x] Confirm plan is the source of truth and update README link
- [x] Complete runtime data model and schemas
- [ ] Implement BMAD workflow parsing and canonical registry
- [ ] Build step execution state machine
- [ ] Implement tool adapters, execution pipeline, and risk policy (tool interface, file IO, repo tools done)
- [ ] Implement TELIS LSP, shards, negotiation, cache, and validation gates (LSP adapter done)
- [ ] Implement QUINT evidence engine, WLNK, congruence, decay, and DRR
- [ ] Harden provider routing with retries and circuit breakers
- [ ] Enforce HITL gating with CLI approvals
- [ ] Add artifact indexing and run timeline
- [ ] Expand CLI (list, export, history)
- [ ] Implement guardrails (PII, moderation, rules)
- [ ] Add observability and run reports
- [ ] Integration tests for at least one BMAD workflow
- [ ] CI green with coverage >= 85 percent
- [ ] Package full framework installer (BMAD + QUINT + BQUAT)
- [ ] Release docs and tag v1.0.0 on main

## Verification and Gap Audit

We will not claim full coverage until the traceability audit is complete. The current audit lives at docs/traceability-audit.md and must be updated after each workstream.

Required checks:

- Cross-check all BMAD workflows and outputs against the registry.
- Map TELIS requirements to concrete runtime modules and tests.
- Map QUINT requirements to evidence, DRR, and audit outputs.
- Map Practical Guide guardrails to runtime guardrail implementations.

The traceability audit must be marked done before v1.0 release.
