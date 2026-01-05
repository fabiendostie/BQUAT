---
description: "Execute a BAQT-enhanced BMAD workflow with TELIS context and QUINT evidence tracking"
---

<!-- markdownlint-disable MD033 -->

# BAQT Workflow Executor

You are executing a BMAD workflow enhanced with BAQT capabilities:

- **TELIS**: Intelligent context management and shard-based knowledge retrieval
- **QUINT**: Evidence tracking with WLNK scoring and Decision Record Rationale (DRR)

<critical-steps>
## Step 1: Load BMAD Workflow Core

Load and read the BMAD workflow executor:
@\_bmad/core/tasks/workflow.xml

This is the core OS for executing BMAD workflows.

## Step 2: Initialize BAQT Enhancements

Before executing workflow steps, initialize BAQT context:

### TELIS Context Injection

- Load relevant shards from `_baqt/telis/shards/` based on workflow type
- Apply tier budget policy for context window management
- Use behavioral cache for repeated queries

### QUINT Evidence Tracking

- Initialize evidence store at `_baqt/quint/evidence/`
- Create run-specific evidence file: `evidence-{workflow}-{timestamp}.yaml`
- Track all decisions with WLNK scores

## Step 3: Execute Workflow with Evidence

For EACH step in the workflow:

1. **Before step execution**:
   - Query TELIS for relevant context shards
   - Load any prior evidence relevant to this step

2. **During step execution**:
   - Follow BMAD step instructions exactly
   - Record key decisions as evidence entries
   - Track user inputs and AI responses

3. **After step completion**:
   - Create DRR (Decision Record Rationale) for major decisions
   - Update evidence store with step outputs
   - Save progress to run manifest

## Step 4: Generate Outputs with Traceability

When generating documents (PRD, Architecture, etc.):

1. Include evidence links in document frontmatter:

   ```yaml
   ---
   evidence:
     - id: EV-001
       type: user-requirement
       wlnk: 0.85
     - id: EV-002
       type: architecture-decision
       wlnk: 0.92
   ---
   ```

2. Reference evidence in document sections using `[EV-XXX]` markers

3. Generate summary DRR at workflow completion

</critical-steps>

## Usage

Pass the workflow path as parameter:

- `workflow_path`: Path to BMAD workflow config (e.g., `_bmad/bmm/workflows/prd/workflow.yaml`)

Execute the workflow following BMAD instructions while applying BAQT enhancements for context and evidence.
