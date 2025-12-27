# Traceability Audit (v1.0)

Status: Draft
Owner: Core maintainers
Last updated: 2025-12-27T02:04:31-05:00

## Purpose

This audit verifies that the v1.0 plan covers all requirements from BMAD, TELIS, QUINT, and the practical agent guide. It maps each requirement to current implementation evidence and highlights gaps.

## Sources Audited

- BMAD-METHOD documentation index (BMAD-METHOD/docs/index.md)
- TELIS methodology (docs/Token-Efficient_Language_Intelligence_System_TELIS.md)
- QUINT architecture and FPF engine (quint-code/docs/architecture.md, quint-code/docs/fpf-engine.md)
- Practical guide to building agents (docs/a-practical-guide-to-building-agents.md)
- Unified method specification (methodology/unified_method_specification.md)

## Status Legend

- done: implemented and tested
- partial: implemented in part, missing key behavior or tests
- missing: not implemented

## BMAD Coverage

| ID       | Requirement                                                | Status  | Evidence                                                  | Gap Notes                                  |
| -------- | ---------------------------------------------------------- | ------- | --------------------------------------------------------- | ------------------------------------------ |
| BMAD-001 | Preserve BMAD workflows and naming without rewriting logic | done    | tests/test_runtime_bmad_execution.py                      | None                                       |
| BMAD-002 | Exclude sample/reference workflows from production mapping | done    | tests/test_mapping.py                                     | None                                       |
| BMAD-003 | Only explicit outputs/templates listed in mapping          | done    | tests/test_mapping.py                                     | None                                       |
| BMAD-004 | Parse workflow definitions (md/yaml/xml) into steps        | done    | runtime/workflow_parser.py, tests/test_workflow_parser.py | None                                       |
| BMAD-005 | Enforce BMAD output folder/layout conventions              | done    | runtime/engine.py, tests/test_runtime_engine.py           | None                                       |
| BMAD-006 | Orchestrator (BMAD Master) routes workflows and agents     | missing | None                                                      | No orchestration layer beyond basic engine |
| BMAD-007 | Support all BMAD modules (core, BMM, BMB, CIS, BMGD)       | done    | tests/test_runtime_bmad_execution.py                      | None                                       |

## Distribution Coverage

| ID          | Requirement                                            | Status  | Evidence | Gap Notes                                 |
| ----------- | ------------------------------------------------------ | ------- | -------- | ----------------------------------------- |
| INSTALL-001 | Single-command install for full framework distribution | missing | None     | Installer integration not yet implemented |

## TELIS Coverage

| ID        | Requirement                                         | Status  | Evidence                                                                                                       | Gap Notes                                 |
| --------- | --------------------------------------------------- | ------- | -------------------------------------------------------------------------------------------------------------- | ----------------------------------------- |
| TELIS-001 | LSP symbiosis for type/signature accuracy           | partial | runtime/tools/lsp.py, tests/test_runtime_lsp.py                                                                | Adapter present; not yet wired into TELIS |
| TELIS-002 | LSP fallback to shards on failure or timeout        | missing | None                                                                                                           | No fallback path                          |
| TELIS-003 | Tiered knowledge shards with token budgets          | partial | runtime/telis/shards.py, tests/test_runtime_telis_shards.py                                                    | Shard retrieval not yet wired into engine |
| TELIS-004 | Progressive context negotiation protocol            | missing | None                                                                                                           | No negotiation logic or prompts           |
| TELIS-005 | AST/type/lint validation pipeline                   | done    | runtime/tools/validation.py, runtime/engine.py, tests/test_runtime_validation.py, tests/test_runtime_engine.py | None                                      |
| TELIS-006 | Behavioral cache with TTL and invalidation triggers | missing | None                                                                                                           | Cache not implemented                     |
| TELIS-007 | Validation failures trigger retry/escalation        | done    | runtime/engine.py, tests/test_runtime_engine.py                                                                | None                                      |

## QUINT Coverage

| ID        | Requirement                                  | Status  | Evidence | Gap Notes                         |
| --------- | -------------------------------------------- | ------- | -------- | --------------------------------- |
| QUINT-001 | Evidence store for L0/L1/L2 and invalid      | missing | None     | No evidence persistence           |
| QUINT-002 | ADI cycle with promotion rules               | missing | None     | Only mapped in workflow metadata  |
| QUINT-003 | WLNK assurance scoring                       | missing | None     | No assurance calculator           |
| QUINT-004 | Congruence scoring for external evidence     | missing | None     | No congruence model               |
| QUINT-005 | Evidence decay with valid_until checks       | missing | None     | No decay scan                     |
| QUINT-006 | DRR generation for major decisions           | missing | None     | DRR template exists but not used  |
| QUINT-007 | Surface vs grounding separation              | missing | None     | No summary vs stored trace split  |
| QUINT-008 | Bounded context snapshot and drift detection | missing | None     | No context file or drift tracking |

## Practical Guide Coverage

| ID        | Requirement                                     | Status  | Evidence                                                                                                                                     | Gap Notes                                 |
| --------- | ----------------------------------------------- | ------- | -------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------- |
| GUIDE-001 | Model, tools, instructions triad per agent      | partial | runtime/prompts.py, runtime/agents.py, runtime/tools/base.py                                                                                 | Tool schema exists; no per-agent registry |
| GUIDE-002 | Standardized tool definitions and reuse         | partial | runtime/tools/base.py, runtime/tools/file_io.py, runtime/tools/repo_tool.py, tests/test_runtime_file_io.py, tests/test_runtime_repo_tools.py | No tool registry or catalog               |
| GUIDE-003 | Tool risk ratings and safeguards                | partial | runtime/tools/base.py, runtime/tools/time_tool.py                                                                                            | No enforcement or HITL policy             |
| GUIDE-004 | PII filter and data privacy guardrails          | missing | None                                                                                                                                         | No guardrail hooks                        |
| GUIDE-005 | Moderation filters for unsafe inputs            | missing | None                                                                                                                                         | No moderation checks                      |
| GUIDE-006 | Rules-based protections (blocklists/regex)      | missing | None                                                                                                                                         | No rules gate                             |
| GUIDE-007 | HITL on high-risk actions and retry thresholds  | partial | runtime/gates.py                                                                                                                             | Gate depends on workflow metadata only    |
| GUIDE-008 | Optimistic execution with concurrent guardrails | missing | None                                                                                                                                         | No guardrail concurrency model            |

## Unified Spec Coverage

| ID       | Requirement                                         | Status  | Evidence                                                                                                        | Gap Notes                        |
| -------- | --------------------------------------------------- | ------- | --------------------------------------------------------------------------------------------------------------- | -------------------------------- |
| SPEC-001 | Event bus for workflow state transitions            | missing | None                                                                                                            | No event system                  |
| SPEC-002 | State store for workflow progress and artifacts     | done    | runtime/engine.py, runtime/storage.py, tests/test_runtime_artifacts_events.py                                   | None                             |
| SPEC-003 | TELIS policy engine and context manager             | missing | None                                                                                                            | Not implemented                  |
| SPEC-004 | Evidence store for Quint claims and DRRs            | missing | None                                                                                                            | Not implemented                  |
| SPEC-005 | Control plane/data plane split                      | partial | runtime/plugins/manager.py                                                                                      | Only a minimal plugin manager    |
| SPEC-006 | Plugin pipeline for policy/adapters/observability   | partial | runtime/plugins/manager.py                                                                                      | No plugin implementations        |
| SPEC-007 | Failure isolation with bounded retries              | partial | runtime/engine.py                                                                                               | No circuit breakers or isolation |
| SPEC-008 | Artifact index with checksum and provenance         | missing | None                                                                                                            | Not implemented                  |
| SPEC-009 | Context fingerprint tracking                        | missing | None                                                                                                            | Not implemented                  |
| SPEC-010 | Gates recorded as DRRs with evidence links          | missing | None                                                                                                            | Not implemented                  |
| SPEC-011 | Tool execution pipeline (registry, gating, results) | done    | runtime/tools/pipeline.py, runtime/engine.py, tests/test_runtime_tool_pipeline.py, tests/test_runtime_engine.py | None                             |

## Governance Coverage

| ID      | Requirement                                 | Status | Evidence                                  | Gap Notes |
| ------- | ------------------------------------------- | ------ | ----------------------------------------- | --------- |
| GOV-001 | Change control recorded in plan and README  | done   | README.md, docs/v1-plan.md                | None      |
| GOV-002 | Branch policy documented (development/main) | done   | README.md                                 | None      |
| GOV-003 | SemVer enforced in VERSION + release notes  | done   | VERSION, CHANGELOG.md, docs/versioning.md | None      |
| GOV-004 | Conventional Commits enforcement via hook   | done   | .husky/commit-msg                         | None      |
| GOV-005 | CI pinned to latest stable action majors    | done   | .github/workflows/ci.yml                  | None      |

## Audit Summary

- Verified coverage of mapping/registry exclusions and explicit output/template extraction.
- WS1-WS3 tasks are complete; BMAD-001/007 and SPEC-002 are now covered by integration tests and runtime persistence.
- Real BMAD workflow execution, TELIS, and QUINT are mostly missing; TELIS shard registry exists but is not yet integrated.
- Tool schema and risk metadata exist; safe file IO/repo tools, LSP adapter, validation runner, tool execution pipeline, validation gates, and runtime schemas are implemented; enforcement coverage beyond current tools remains pending.

## Required Follow-up

1. Update docs/v1-plan.md requirement matrix to include all requirements above.
2. Implement the missing components in the order defined by the v1 plan.
3. Re-run this audit after each workstream and mark evidence with file/test references.

## Audit Sign-off

- Pending until all requirements are mapped with evidence and verified by tests.
