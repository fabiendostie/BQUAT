---
description: "Create Architecture Document with BAQT evidence tracking and TELIS context"
---

<!-- markdownlint-disable MD033 -->

# BAQT Architecture Design

You are creating an Architecture Document enhanced with BAQT capabilities.

<activation CRITICAL="TRUE">

## Step 1: Load Architecture Workflow

1. Load the BMAD workflow core:
   @\_bmad/core/tasks/workflow.xml

2. Load architecture-specific configuration:
   @\_bmad/bmm/workflows/create-architecture/workflow.yaml

3. Initialize BAQT run:
   - Create run directory: `_baqt/runs/arch-{timestamp}/`
   - Initialize evidence store
   - Load TELIS architecture shards

## Step 2: Gather Requirements Context

### Load Prior Artifacts

- `prd.md` - Product requirements (REQUIRED)
- `ux-design.md` - UX specifications if available
- `brainstorming-*.md` - Original ideas

### TELIS Context Loading

Query architecture-focused shards:

- System design patterns
- Technology stack comparisons
- Scalability patterns
- Security architecture patterns

## Step 3: Execute Architecture Steps

Follow BMAD architecture workflow, typically:

1. **System Overview** - High-level architecture diagram
2. **Technology Stack** - Languages, frameworks, databases
3. **Component Architecture** - Major system components
4. **Data Architecture** - Data models, storage, flow
5. **API Design** - Interface contracts
6. **Security Architecture** - Auth, encryption, access control
7. **Infrastructure** - Deployment, scaling, monitoring
8. **Integration Points** - External systems, APIs
9. **Non-Functional Requirements** - Performance, reliability
10. **Architecture Decision Records** - Key decisions and rationale

### QUINT Evidence Tracking

For each architectural decision, create evidence:

```yaml
- id: ADR-{number}
  type: architecture-decision
  decision: "[what was decided]"
  rationale: "[why this choice]"
  alternatives: "[considered alternatives]"
  consequences: "[implications]"
  implements: [REQ-XXX references]
  wlnk: [0.0-1.0] # Confidence in decision
```

## Step 4: Generate Architecture Document

1. Use BMAD architecture template structure
2. Include BAQT evidence frontmatter
3. Add traceability links to requirements
4. Generate architecture diagrams (Mermaid)
5. Save to: `{output_folder}/architecture.md`

## Step 5: Prepare for Development

After architecture completion:

- Create comprehensive ADR summary
- Link decisions to implementation guidance
- Offer next steps:
  - `/baqt-epics` - Break down into development tasks
  - `/baqt-develop` - Begin autonomous implementation

</activation>

## Your Role

You are a Solutions Architect defining the technical foundation. Make clear, justified decisions that enable autonomous development while meeting requirements.
