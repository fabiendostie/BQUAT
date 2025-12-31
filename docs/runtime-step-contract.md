# Runtime Step Contract

Status: Draft
Owner: Core maintainers
Last updated: 2025-12-30T17:17:51-05:00

## Purpose

Define the canonical step execution contract that the runtime uses to execute BMAD workflows. This is the interface between parsed BMAD workflow steps and the runtime engine.

## Goals

- Deterministic execution and state transitions.
- Explicit inputs, outputs, tools, and validations per step.
- Blocking human gates at required points.
- Tool invocation is explicit and auditable.
- All timestamps come from getCurrentTime (runtime/tools/time_tool.py) or runtime/time_provider.py.

## StepSpec (Canonical)

Every step is represented as a StepSpec. It is serialized and stored in the run manifest.

Fields:

- id: stable step identifier (string)
- name: short name (string)
- description: human-readable step intent (string)
- phase: BMAD phase label (string)
- inputs: structured inputs required by the step (object)
- outputs: explicit artifact outputs (list of strings)
- templates: template artifacts (list of strings)
- tools: list of tool call specifications (list)
- validation: validation gate policy (string)
- evidence: QUINT evidence requirement (string)
- human_gate: required, conditional, or optional (string)
- retries: retry policy (object)

## StepSpec JSON shape

```json
{
  "id": "step-02",
  "name": "draft-prd",
  "description": "Generate the PRD using the BMAD template",
  "phase": "Phase 2 Planning",
  "inputs": {
    "context": "minimal",
    "artifacts": ["{output_folder}/product-brief.md"]
  },
  "outputs": ["{output_folder}/prd.md"],
  "templates": ["template:{template_folder}/prd.template.md"],
  "tools": [
    {
      "name": "getCurrentTime",
      "args": { "timezone": "UTC" },
      "required": false,
      "risk": "low"
    }
  ],
  "validation": "Template/schema validation",
  "evidence": "L1",
  "human_gate": "required",
  "retries": {
    "max": 1,
    "backoff_seconds": 2
  }
}
```

## RunStep Runtime Fields

At execution time, each step is converted into a RunStep entry stored in the run manifest. It records runtime state and results.

- name
- status: pending, running, blocked, failed, completed
- attempts
- started_at, ended_at (ISO 8601 from getCurrentTime)
- error
- step_id
- inputs
- outputs
- tools (tool execution results)
- telis_context (resolved TELIS context payload)

## Step State Machine

Allowed transitions:

- pending -> running
- running -> completed, failed, blocked
- failed -> running
- blocked -> running
- completed -> (terminal)

## Tool Call Contract

Tool calls are explicit and auditable. Each call definition includes:

- name: tool identifier
- args: JSON arguments
- required: whether failure blocks the step
- risk: low, medium, high
- gate: optional gate name if a HITL approval is required

Tool specifications are defined in runtime/tools/base.py via ToolSpec; step tool calls should map to ToolCall records.

Execution details are defined in docs/tool-execution-pipeline.md and enforced before validation gates.

Tool results are stored as part of the step execution context and may be written to artifacts.

Tool execution records are persisted to tool_results.json in the run directory.

## TELIS Context Manager

TELIS context is resolved before executor execution so the agent can consume LSP/shard context.

Inputs (optional keys in StepSpec.inputs):

- telis_query: string query used for shard/LSP lookup
- telis_language: language identifier (python, typescript, javascript, json, yaml)
- telis_document_path: file path for LSP-backed requests
- telis_document_text: inline document text when no file exists
- telis_method: LSP method (hover or signatureHelp)
- telis_line / telis_character: cursor position for LSP calls
- telis_shard_limit: limit shard count for retrieval
- telis_min_score: minimum shard score threshold
- telis_max_phase: cap negotiation phases
- telis_phase_tiers: explicit tiers for negotiation escalation

Outputs:

- telis_context is attached to the RunStep and passed to executors.

## Tool Definition (getCurrentTime)

The runtime must expose a getCurrentTime tool to return the current time from the system clock.

- Definition: runtime/tools/time_tool.py
- Purpose: ensure all timestamps are real-time and not from model memory
- Parameters:
  - timezone: IANA name (default America/Toronto)

Additional tool specs for safe file IO and repo inspection live in runtime/tools/file_io.py and runtime/tools/repo_tool.py.

LSP adapters for signature/hover queries live in runtime/tools/lsp.py and are consumed by TELIS routing when enabled.

## Validation Gate Contract

Validation gates execute after tool calls and before outputs are accepted. Validation policies are defined in TELIS.

Examples:

- Format validation
- Template/schema validation
- AST + type + lint (as applicable)

AST/type/lint runners live in runtime/tools/validation.py and currently support Python (ast.parse, mypy,
ruff) plus JSON/YAML parse checks when available.

Validation failures:

- add error details to step.error
- retry if allowed by retries.max
- if retries exhausted, mark step failed and run failed

## Timeouts and Retry Policy

- Step execution time is bounded by runtime.step_timeout_seconds (default 1800s).
- Retry behavior uses StepSpec.retries when present; max controls retry count and backoff_seconds sleeps between attempts.
- If retries are not set on the step, runtime.max_retries is used as the fallback.
- Retries apply to execution errors and validation failures; once retries are exhausted the run is marked failed.

Validation inputs:

- validation_targets: optional list of file paths (relative to project root) to validate for this step.

Output layout enforcement:

- Outputs must include {output_folder} or {bmb_creations_output_folder} placeholders when specified.

## Human Gate Contract

Human gates are blocking checkpoints. The runtime must enforce them before moving to the next step based on
StepSpec.human_gate plus the HITL policy (phase/risk rules in config runtime.hitl.policy).

- required: always block
- conditional: block only if policy enables
- optional: no block

Operator note: HITL policy config keys live under config/runtime.yaml at hitl.policy.

- required_phases: exact phase strings that always block.
- conditional_phases: phase strings that block only when conditional_required is true.
- high_risk_keywords: substring match against workflow id to force blocking.
- conditional_keywords: substring match against workflow id gated by conditional_required.
- conditional_required: boolean toggle for conditional blocks.
- recommended_required: boolean toggle to enforce human_gate = recommended.

Approvals are stored in approvals.json with audit metadata. Gate audit records are stored in gates.json and include
status, reason, phase/workflow, and approval details.

## Evidence Contract (QUINT)

Steps with evidence requirements must emit evidence records. The evidence schema is defined in methodology/evidence-schema.yaml.

Minimum fields:

- id, claim, level, source, date, valid_until, congruence, reliability, wlnk, carrier_ref

Evidence links are stored in evidence.json and cross-linked to artifacts.

## Execution Lifecycle

1. Load StepSpec from parsed workflow.
2. Create or update RunStep with status=running and started_at.
3. Persist run state after each step update and on errors.
4. Enforce human gate if required.
5. Execute tool calls through the tool execution pipeline and record results.
6. Run validation gate; retry or fail on error.
7. Write outputs and update artifact index.
8. Record evidence links as required.
9. Emit run timeline JSON from events, artifacts, gates, evidence, and DRRs.
10. Mark RunStep completed and set ended_at.

## Resume Semantics

- Resume starts from the first step that is not completed.
- Completed steps are not re-executed.

## Required Events

- WorkflowStarted
- WorkflowStepStarted
- WorkflowStepCompleted
- ArtifactReady
- ValidationPassed / ValidationFailed
- EvidenceRecorded
- HumanGateRequired / HumanGateApproved

Event payloads must include run_id and ISO 8601 timestamps.
