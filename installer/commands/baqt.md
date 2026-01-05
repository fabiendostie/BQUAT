---
description: "BAQT - The unified framework - Show available commands and workflow guidance"
---

# BAQT Command Center

**B**MAD Method + **A**utonomous Agents + **Q**UINT-Code + **T**ELIS = ****BAQT: The unified framework****

BAQT enhances the BMAD methodology with:

- **TELIS**: Intelligent context management and knowledge retrieval
- **QUINT**: Evidence tracking with WLNK scoring and Decision Records

## Available Commands

### Planning Phase (1-4)

| Command               | Description                                     |
| --------------------- | ----------------------------------------------- |
| `/baqt-brainstorm`    | Start a brainstorming session with idea capture |
| `/baqt-product-brief` | Create product vision and scope document        |
| `/baqt-prd`           | Create detailed Product Requirements Document   |
| `/baqt-ux-design`     | Design user experience and interface            |
| `/baqt-architecture`  | Define technical architecture                   |
| `/baqt-epics`         | Break down into epics and user stories          |

### Development Phase (5+)

| Command         | Description                                 |
| --------------- | ------------------------------------------- |
| `/baqt-develop` | Launch autonomous development with evidence |

## Recommended Workflow

```
Start Here
    |
    v
/baqt-brainstorm  --> Explore and capture ideas
    |
    v
/baqt-product-brief  --> Define vision and scope
    |
    v
/baqt-prd  --> Detail requirements
    |
    +---> /baqt-ux-design  --> Design experience
    |
    v
/baqt-architecture  --> Technical design
    |
    v
/baqt-epics  --> Development breakdown
    |
    v
/baqt-develop  --> Autonomous implementation
```

## BAQT Enhancements

### TELIS Context Management

- Shards: Reusable knowledge fragments
- Tier budgets: Optimized context window usage
- Behavioral cache: Fast repeated queries

### QUINT Evidence Tracking

- Evidence links: Traceable decisions
- WLNK scores: Confidence metrics
- DRR: Decision Record Rationale

## Quick Start

1. **New Project**: Start with `/baqt-brainstorm`
2. **Have Requirements**: Skip to `/baqt-prd`
3. **Ready to Build**: Use `/baqt-develop`

## Evidence Directory

All runs create evidence at:

```
_baqt/runs/{workflow}-{timestamp}/
  evidence.yaml    # Evidence entries
  manifest.json    # Run metadata
  drr/             # Decision records
```

## Need Help?

- Check `_baqt/docs/` for detailed documentation
- View evidence with `baqt export {run-id}`
- List runs with `baqt history`
