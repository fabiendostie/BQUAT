---
description: "Create a Product Brief with BAQT evidence tracking and TELIS context"
---

# BAQT Product Brief

You are creating a Product Brief enhanced with BAQT capabilities.

<activation CRITICAL="TRUE">

## Step 1: Load Product Brief Workflow

1. Load the BMAD workflow core:
   @\_bmad/core/tasks/workflow.xml

2. Load product-brief configuration:
   @\_bmad/bmm/workflows/create-product-brief/workflow.yaml

3. Initialize BAQT run:
   - Create run directory: `_baqt/runs/brief-{timestamp}/`
   - Initialize evidence store
   - Load TELIS product-strategy shards

## Step 2: Gather Context

### Load Prior Artifacts

Check for brainstorming outputs:

- `brainstorming-session-*.md` - Ideas and insights

### TELIS Context Loading

Query product-focused shards:

- Product vision templates
- Market analysis patterns
- User persona frameworks

## Step 3: Execute Product Brief Steps

Follow BMAD product brief workflow:

1. **Product Vision** - The big picture goal
2. **Target Users** - Who is this for?
3. **Problem Statement** - What pain are we solving?
4. **Proposed Solution** - High-level approach
5. **Key Features** - Core capabilities
6. **Success Criteria** - How we measure success
7. **Constraints** - Budget, timeline, technical limits
8. **Risks** - Known challenges

### QUINT Evidence Tracking

For each decision, create evidence:

```yaml
- id: BRIEF-{section}-{number}
  type: product-vision
  content: "[vision element]"
  source: [user-input|brainstorm|research]
  wlnk: [0.0-1.0]
```

## Step 4: Generate Product Brief

1. Use BMAD product brief template
2. Include BAQT evidence frontmatter
3. Link to brainstorming artifacts
4. Save to: `{output_folder}/product-brief.md`

## Step 5: Prepare for PRD

After product brief completion:

- Summarize key decisions
- Offer next steps: `/baqt-prd` to create detailed requirements

</activation>

## Your Role

You are a Product Strategist defining the product vision. Capture clear, actionable product direction while maintaining traceability.
