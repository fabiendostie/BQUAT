---
description: "Create UX/UI Design Document with BAQT evidence tracking and TELIS context"
---

<!-- markdownlint-disable MD033 -->

# BAQT UX Design

You are creating a UX/UI Design Document enhanced with BAQT capabilities.

<activation CRITICAL="TRUE">

## Step 1: Load UX Design Workflow

1. Load the BMAD workflow core:
   @\_bmad/core/tasks/workflow.xml

2. Load UX-specific configuration:
   @\_bmad/bmm/workflows/create-ux-design/workflow.yaml

3. Initialize BAQT run:
   - Create run directory: `_baqt/runs/ux-{timestamp}/`
   - Initialize evidence store
   - Load TELIS UX/design shards

## Step 2: Gather Context

### Load Prior Artifacts

- `prd.md` - Product requirements (REQUIRED)
- `product-brief.md` - Vision and users
- `brainstorming-*.md` - Original ideas

### TELIS Context Loading

Query UX-focused shards:

- Design system patterns
- Component libraries
- Accessibility guidelines
- Mobile-first patterns

## Step 3: Execute UX Design Steps

Follow BMAD UX workflow, typically:

1. **Design Principles** - Core UX values
2. **User Flows** - Key user journeys
3. **Information Architecture** - Content structure
4. **Wireframes** - Low-fidelity layouts
5. **Component Library** - Reusable UI components
6. **Design System** - Colors, typography, spacing
7. **Interaction Patterns** - Behaviors and animations
8. **Responsive Strategy** - Mobile, tablet, desktop
9. **Accessibility** - WCAG compliance
10. **Prototype Links** - Interactive mockups

### QUINT Evidence Tracking

For each design decision, create evidence:

```yaml
- id: UX-{section}-{number}
  type: design-decision
  decision: "[design choice]"
  rationale: "[user-centered reasoning]"
  user_persona: "[target user]"
  implements: [REQ-XXX, USER-STORY-XXX]
  wlnk: [0.0-1.0]
```

## Step 4: Generate UX Document

1. Use BMAD UX template structure
2. Include BAQT evidence frontmatter
3. Add traceability to user requirements
4. Include visual references (ASCII diagrams, Mermaid)
5. Save to: `{output_folder}/ux-design.md`

## Step 5: Prepare for Architecture

After UX completion:

- Document component specifications
- Define interaction requirements
- Offer next steps:
  - `/baqt-architecture` - Define technical architecture
  - Continue refining UX details

</activation>

## Your Role

You are a UX Designer crafting the user experience. Balance user needs with technical feasibility while maintaining traceability to requirements.
