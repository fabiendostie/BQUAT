# Tool Execution Pipeline

Status: Draft
Owner: Core maintainers
Last updated: 2025-12-23T03:43:46-05:00

## Purpose

Define the canonical pipeline for resolving, approving, executing, and recording tool calls during
runtime step execution. This closes the gap between tool definitions (ToolSpec) and step execution.

## Scope

In scope:

- Resolving ToolCall entries against a ToolSpec registry.
- Enforcing allow-lists, block-lists, and risk-based HITL policy.
- Executing tool handlers with timeouts and structured results.
- Recording tool execution artifacts in run storage.

Out of scope:

- Adding new tools or changing tool implementations.
- External orchestration or GUI approvals.

## Inputs and Outputs

Inputs:

- StepSpec.tools (ToolCall list)
- ToolSpec registry (runtime/tools/\*)
- Runtime config: tools.allowlist, tools.blocklist, tools.timeout_seconds, tools.risk_policy
- Approvals store (approvals.json)

Outputs:

- tool_results.json stored under the run directory
- Step state updates (status/error)
- Plugin events (ToolCallStarted/Completed/Failed)

## Tool Registry

Tool registry is a mapping from tool name to:

- ToolSpec (name, parameters, risk)
- Handler (callable that executes the tool)

Default registry is built from runtime/tools/\* exports. Additional tools must be explicitly registered.

## Tool Result Shape

```json
{
  "name": "readTextFile",
  "status": "completed",
  "risk": "low",
  "started_at": "2025-12-23T03:43:46-05:00",
  "ended_at": "2025-12-23T03:43:47-05:00",
  "duration_ms": 120,
  "result": { "content": "..." },
  "stdout": "",
  "stderr": "",
  "error": "",
  "artifacts": []
}
```

All timestamps must come from getCurrentTime (runtime/tools/time_tool.py) or runtime/time_provider.py.

## Pipeline Stages

1. Resolve: Load registry and match ToolCall.name to ToolSpec.
2. Validate: Confirm args schema, normalize risk, and reject unknown tools.
3. Policy Gate:
   - Deny if name in blocklist.
   - If allowlist is configured, require tool to be listed.
4. HITL Gate:
   - If risk is high (or configured), require approval before execution.
5. Execute: Invoke handler with args and enforce timeout.
6. Record: Write ToolResult entries to tool_results.json and update step.tools.
7. Error Handling:
   - If ToolCall.required and execution fails, fail the step.
   - If not required, record error and continue.

## Policy and Configuration

Proposed config block in config/runtime.yaml:

```json
{
  "tools": {
    "allowlist": ["getCurrentTime", "readTextFile", "writeTextFile", "listDirectory"],
    "blocklist": [],
    "timeout_seconds": 30,
    "risk_policy": {
      "high_requires_approval": true,
      "medium_requires_approval": false
    }
  }
}
```

Allow-list is recommended to default to the runtime tool registry. Block-list is always enforced.

## Integration Points

- Workflow execution: StepExecutor must run this pipeline before validation gates and output writes.
- HITL: gate ids should be namespaced by tool and step (example: tool:writeTextFile:step-02).
- Plugins: emit ToolCallStarted/Completed/Failed for observability.

## Acceptance Criteria

- Tool calls are executed only through the pipeline.
- High-risk tools require approval and are blocked by default.
- Tool results are persisted for audit and reproducibility.
- Failure behavior respects ToolCall.required and step retry policy.
