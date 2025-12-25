# Runtime Step Contract

Status: Draft
Owner: Core maintainers
Last updated: 2025-12-24T23:35:24-05:00

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
- tools

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

Validation inputs:

- validation_targets: optional list of file paths (relative to project root) to validate for this step.

Output layout enforcement:

- Outputs must include {output_folder} or {bmb_creations_output_folder} placeholders when specified.

## Human Gate Contract

Human gates are blocking checkpoints. The runtime must enforce them before moving to the next step.

- required: always block
- conditional: block only if policy enables
- optional: no block

Approvals are stored in approvals.json with audit metadata.

## Evidence Contract (QUINT)

Steps with evidence requirements must emit evidence records. The evidence schema is defined in methodology/evidence-schema.yaml.

Minimum fields:

- id, claim, level, source, date, valid_until, congruence, reliability, wlnk, carrier_ref

Evidence links are stored in evidence.json and cross-linked to artifacts.

## Execution Lifecycle

1. Load StepSpec from parsed workflow.
2. Create or update RunStep with status=running and started_at.
3. Enforce human gate if required.
4. Execute tool calls through the tool execution pipeline and record results.
5. Run validation gate; retry or fail on error.
6. Write outputs and update artifact index.
7. Record evidence links as required.
8. Mark RunStep completed and set ended_at.

## Required Events

- WorkflowStarted
- WorkflowStepStarted
- WorkflowStepCompleted
- ArtifactReady
- ValidationPassed / ValidationFailed
- EvidenceRecorded
- HumanGateRequired / HumanGateApproved

Event payloads must include run_id and ISO 8601 timestamps.
