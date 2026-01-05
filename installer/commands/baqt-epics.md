---
description: "Create Epics and User Stories with BAQT evidence tracking"
---

# BAQT Epics and Stories

You are creating Epics and User Stories enhanced with BAQT capabilities.

<activation CRITICAL="TRUE">

## Step 1: Load Epics Workflow

1. Load the BMAD workflow core:
   @\_bmad/core/tasks/workflow.xml

2. Load epics configuration:
   @\_bmad/bmm/workflows/create-epics-and-stories/workflow.yaml

3. Initialize BAQT run:
   - Create run directory: `_baqt/runs/epics-{timestamp}/`
   - Initialize evidence store
   - Load TELIS agile-development shards

## Step 2: Gather Context

### Load Required Artifacts

- `prd.md` - Product requirements (REQUIRED)
- `architecture.md` - Technical architecture (RECOMMENDED)
- `ux-design.md` - UX specifications (RECOMMENDED)

### TELIS Context Loading

Query agile-focused shards:

- Epic decomposition patterns
- User story templates
- Acceptance criteria examples
- Story point estimation guides

## Step 3: Create Epics

Break down PRD into epics:

```yaml
epic:
  id: EPIC-{number}
  title: "[Epic title]"
  description: "[Epic description]"
  requirements: [REQ-XXX, REQ-YYY] # From PRD
  priority: [must|should|could]
  estimated_effort: [S|M|L|XL]
```

## Step 4: Create User Stories

For each epic, create user stories:

```yaml
story:
  id: STORY-{epic}-{number}
  title: "[Story title]"
  as_a: "[user persona]"
  i_want: "[capability]"
  so_that: "[benefit]"
  acceptance_criteria:
    - Given [context], when [action], then [outcome]
  epic: EPIC-{number}
  requirements: [REQ-XXX]
  priority: [must|should|could]
  points: [1|2|3|5|8|13]
```

### QUINT Evidence Tracking

For each story:

```yaml
- id: STORY-{id}
  type: user-story
  implements: [REQ-XXX]
  epic: EPIC-{number}
  acceptance_criteria_count: [number]
  wlnk: [0.0-1.0] # Confidence in story clarity
```

## Step 5: Generate Outputs

1. Create `epics/` directory with:
   - `epic-{number}.md` for each epic
   - Stories embedded in epic files

2. Create `backlog.md` summary with:
   - All epics and stories
   - Priority ordering
   - Effort estimates

3. Link to PRD requirements

## Step 6: Prepare for Development

After epics completion:

- Recommend implementation order
- Identify dependencies between stories
- Offer next step: `/baqt-develop` for autonomous implementation

</activation>

## Your Role

You are a Product Owner breaking down requirements into actionable development tasks. Create clear, testable stories that enable autonomous development.
