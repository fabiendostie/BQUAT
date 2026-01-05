# BAQT IDE Integration Guide

This guide explains how to use BAQT with AI-powered IDEs like Claude Code, Cursor, and Cline.

## Overview

BAQT provides enhanced slash commands that integrate the BMAD methodology with:

- **TELIS**: Intelligent context management for optimal AI assistance
- **QUINT**: Evidence tracking with confidence scores and decision records

## Installation

After running `baqt install`, slash commands are automatically copied to `.claude/commands/`.

## Available Commands

### Planning Commands (Phases 1-4)

| Command               | Description                                       |
| --------------------- | ------------------------------------------------- |
| `/baqt`               | Show all available commands and workflow guidance |
| `/baqt-brainstorm`    | Start a brainstorming session with idea capture   |
| `/baqt-product-brief` | Create product vision and scope document          |
| `/baqt-prd`           | Create detailed Product Requirements Document     |
| `/baqt-ux-design`     | Design user experience and interface              |
| `/baqt-architecture`  | Define technical architecture                     |
| `/baqt-epics`         | Break down into epics and user stories            |

### Development Commands (Phase 5+)

| Command         | Description                                 |
| --------------- | ------------------------------------------- |
| `/baqt-develop` | Launch autonomous development with evidence |

### Utility Commands

| Command          | Description                              |
| ---------------- | ---------------------------------------- |
| `/baqt-status`   | Show installation status and run summary |
| `/baqt-evidence` | Query QUINT evidence chain               |

## Recommended Workflow

```text
/baqt-brainstorm     --> Explore and capture ideas
        |
        v
/baqt-product-brief  --> Define vision and scope
        |
        v
/baqt-prd            --> Detail requirements
        |
        +---> /baqt-ux-design  --> Design experience
        |
        v
/baqt-architecture   --> Technical design
        |
        v
/baqt-epics          --> Development breakdown
        |
        v
/baqt-develop        --> Autonomous implementation
```

## Using Commands

### Starting a New Project

1. Open your project in Claude Code (or compatible IDE)
2. Type `/baqt-brainstorm` to start ideation
3. Follow the AI's prompts to explore your ideas
4. When ready, move to `/baqt-product-brief`

### Creating Documentation

Each planning command creates output documents:

- `/baqt-brainstorm` -> `analysis/brainstorming-session-{date}.md`
- `/baqt-product-brief` -> `product-brief.md`
- `/baqt-prd` -> `prd.md`
- `/baqt-ux-design` -> `ux-design.md`
- `/baqt-architecture` -> `architecture.md`
- `/baqt-epics` -> `epics/` directory

### Autonomous Development

After completing the planning phases:

1. Ensure you have at minimum:
   - `prd.md` (Product Requirements)
   - `architecture.md` (Technical Design)

2. Run `/baqt-develop`

3. The AI will:
   - Analyze your artifacts
   - Create an implementation plan
   - Work autonomously with checkpoints
   - Track all decisions as evidence

## TELIS Context Management

TELIS optimizes how context is provided to the AI:

### Shards

Knowledge fragments stored in `_baqt/telis/shards/`:

- Product domain knowledge
- Architecture patterns
- Code templates
- Best practices

### Tier Budgets

Context window optimization:

- Critical context always loaded
- Secondary context loaded as needed
- Historical context cached

## QUINT Evidence Tracking

All decisions are tracked with evidence:

### Evidence Records

```yaml
- id: REQ-PRD-001
  type: requirement
  content: "User authentication required"
  source: user-input
  wlnk: 0.85
  timestamp: 2024-01-01T00:00:00Z
```

### WLNK Scores

Confidence metrics (0.0 - 1.0):

- 0.9+ : High confidence, well-supported
- 0.7-0.9 : Good confidence, some assumptions
- 0.5-0.7 : Moderate, needs validation
- <0.5 : Low confidence, requires review

### Decision Records (DRR)

Major decisions are documented:

```yaml
decision: "Use PostgreSQL for data storage"
rationale: "Supports JSON, good scaling, team expertise"
alternatives:
  - MongoDB (rejected: less ACID compliance)
  - MySQL (rejected: less feature-rich)
implements: [REQ-DATA-001, REQ-SCALE-002]
```

## Evidence Directory Structure

```text
_baqt/
  runs/
    {workflow}-{timestamp}/
      manifest.json     # Run metadata
      evidence.yaml     # Evidence entries
      drr/              # Decision records
      artifacts/        # Generated files
```

## IDE Compatibility

### Claude Code

Full support. Commands installed to `.claude/commands/`.

### Cursor

Compatible via Claude Code integration.

### Cline

Compatible via Claude Code integration.

### Other IDEs

If your IDE supports markdown slash commands, copy contents from
`_baqt/commands/` to your IDE's command directory.

## Troubleshooting

### Commands Not Available

1. Verify installation: `baqt verify`
2. Check `.claude/commands/` exists
3. Restart IDE

### Context Not Loading

1. Check `_baqt/telis/shards/` exists
2. Verify shard files are valid YAML
3. Check tier budget configuration

### Evidence Not Recording

1. Check `_baqt/runs/` is writable
2. Verify manifest.json exists
3. Check evidence.yaml syntax

## Best Practices

1. **Start with brainstorming** - Even for small projects
2. **Complete each phase** - Artifacts feed downstream workflows
3. **Review evidence** - Check WLNK scores before moving forward
4. **Use checkpoints** - Don't skip human review in development
5. **Keep documentation current** - Evidence chain maintains traceability
