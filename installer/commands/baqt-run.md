---
description: "Run a BAQT workflow with full BMAD, TELIS, and QUINT integration"
arguments:
  - name: module
    description: "BMAD module (core, bmm, bmgd, cis)"
    required: true
  - name: workflow
    description: "Workflow name (e.g., brainstorming, prd, create-architecture)"
    required: true
  - name: provider
    description: "LLM provider to use (ollama, anthropic, openai, gemini)"
    required: false
---

<!-- markdownlint-disable MD033 -->

# BAQT Run - Execute Workflow

Execute a complete BAQT workflow from start to finish with integrated tooling.

## Workflow Execution

Run the specified workflow using the BAQT runtime:

```bash
python -m cli.main run $ARGUMENTS.module $ARGUMENTS.workflow --agent bmad --provider $ARGUMENTS.provider
```

<critical-steps>

## Step 1: Validate Environment

Before running, verify BAQT is properly installed:

1. Check `_baqt/manifest.json` exists and is valid
2. Verify workflow exists in registry: `python -m cli.main list --module $ARGUMENTS.module`
3. Confirm provider is configured in `config/runtime.yaml`

## Step 2: Initialize Run Context

The runtime will:

1. Create a new run directory in `runs/{run-id}/`
2. Initialize TELIS context with appropriate shards
3. Set up QUINT evidence tracking
4. Load workflow step specifications

## Step 3: Execute Workflow Steps

For each step in the workflow:

1. **TELIS Context**: Load relevant knowledge shards based on step requirements
2. **Tool Execution**: Use registered tools (readTextFile, writeTextFile, etc.)
3. **Evidence Recording**: Track decisions and outputs with WLNK scoring
4. **Human Gates**: Pause for approval on required/conditional gates

## Step 4: Generate Artifacts

Workflow outputs are saved to:

- `runs/{run-id}/outputs/` - Generated documents
- `runs/{run-id}/evidence.json` - QUINT evidence chain
- `runs/{run-id}/manifest.json` - Run state and metadata

</critical-steps>

## Available Tools

The BMAD agent has access to these tools during execution:

| Tool             | Category   | Description                       |
| ---------------- | ---------- | --------------------------------- |
| `readTextFile`   | IO         | Read files within project         |
| `writeTextFile`  | IO         | Write files with template support |
| `listDirectory`  | IO         | List directory contents           |
| `getCurrentTime` | TIME       | Get current timestamp             |
| `gitStatus`      | REPO       | Get repository status             |
| `gitDiff`        | REPO       | Get file differences              |
| `validateAst`    | VALIDATION | Validate source syntax            |
| `typecheck`      | VALIDATION | Run type checker                  |
| `lint`           | VALIDATION | Run linter                        |

## Examples

Run brainstorming workflow:

```bash
/run core brainstorming
```

Run PRD workflow with Anthropic:

```bash
/run bmm prd anthropic
```

Run architecture workflow with Ollama:

```bash
/run bmm create-architecture ollama
```

## Monitoring

Check run status:

```bash
python -m cli.main status {run-id}
```

View run history:

```bash
python -m cli.main history --limit 5
```

Export run data:

```bash
python -m cli.main export {run-id} --report
```
