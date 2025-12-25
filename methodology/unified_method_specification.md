# Unified Agentic Framework Specification

Version: 1.0
Status: Draft

## 1) Objective

Create a single unified multi-agent framework that strictly preserves BMAD-METHOD agents and workflows, and fully integrates Quint-code reasoning patterns and TELIS token-optimization. The system runs autonomously with event-driven coordination and sub-agent hierarchy, with blocking human-in-the-loop gates.

## 2) Scope and Constraints

- BMAD adherence is mandatory and strict. All BMAD agents and workflows are preserved as-is.
- Quint integration is complete. FPF/ADI reasoning, evidence, and decision hygiene are mandatory.
- TELIS integration is complete. LSP symbiosis, knowledge shards, progressive negotiation, and validation gates are mandatory.
- Workflow mode is fully automated with event-driven coordination and blocking human gates where defined.
- Agent coordination uses a sub-agent hierarchy with a single orchestrator.
- Output structure must follow BMAD naming conventions and the required directory layout.

## 3) Source Methodologies and Roles

### 3.1 BMAD-METHOD (foundational framework)

- Role: System substrate and canonical workflows.
- Coverage: 100 percent of BMAD agents and workflows, including core, BMM, BMB, CIS, BMGD.
- Rule: No workflow logic is replaced. The unified method wraps and routes to existing BMAD workflows.

### 3.2 Quint-code (code quality and reasoning patterns)

- Role: First Principles Framework (FPF) reasoning hygiene, auditability, and evidence chains.
- Core concepts: ADI cycle (abduction, deduction, induction), assurance levels L0-L2, WLNK principle, congruence, decay, DRR.
- Rule: Reasoning artifacts are recorded for major decisions and long-lived architecture.

### 3.3 TELIS (token optimization)

- Role: Token-efficient context management and error reduction.
- Core mechanisms: LSP symbiosis, knowledge shards, progressive context negotiation, AST validation gate, behavioral cache.
- Rule: All code generation and workflow steps follow TELIS context policy.

### 3.4 Practical Agent Design Guide (guardrails)

- Role: Model, tools, and instruction clarity; guardrails; human intervention triggers.
- Rule: Guardrails are applied to tool usage, data handling, and output validation.

## 4) Unified Architecture

### 4.1 Layers

1. BMAD Execution Layer
   - Agents, workflows, tasks, tools, and installers (BMAD core + modules).
2. Quint Reasoning Layer
   - Evidence capture, ADI cycle checkpoints, assurance scoring, DRRs.
3. TELIS Context Layer
   - LSP calls, shard retrieval, progressive context negotiation, AST validation, cache.
4. Tooling and Guardrails
   - Risk classification, tool safeguards, input/output validation, retry policy.

### 4.2 Design Principles

- Preserve BMAD workflow behavior. Do not fork or rewrite BMAD flows.
- Make reasoning explicit and auditable (Quint).
- Minimize token usage while maximizing correctness (TELIS).
- Functional core, imperative shell where applicable.
- Explicit failure modes, bounded retries, safe fallbacks.

## 5) Agent Hierarchy and Domain Mapping

### 5.1 Orchestrator

- Primary orchestrator: BMAD Master (core agent).
- Responsibilities: event-driven coordination, routing to workflows, enforcing policy gates.

### 5.2 Domain Agents

- UX/UI Agent
  - Primary: BMM UX Designer.
  - Support: CIS design-thinking coach, brainstorming coach.
  - Outputs: UX specification, design artifacts, accessibility notes.

- Development Agent
  - Primary: BMM DEV, Architect, SM.
  - Quick path: BMM Quick Flow Solo Dev.
  - Game contexts: BMGD Game Developer, Game Architect, Game Scrum Master.
  - Outputs: implementation, stories, code review, architecture docs.

- Testing Agent
  - Primary: BMM TEA.
  - Game contexts: BMGD Game QA.
  - Outputs: test framework, ATDD, automation, NFR assessment, CI quality gates.

- CI/CD Agent
  - Primary: TEA CI workflow and BMM pipeline guidance.
  - Outputs: pipeline configuration, test gates, deployment automation.

- Security Agent
  - Base: BMB security-engineer reference agent template.
  - Outputs: threat review, vulnerability scan plan, security audit report.

### 5.3 Sub-agent Hierarchy

- Level 0: Orchestrator (BMad Master).
- Level 1: Domain leads (PM, Architect, TEA, UX Designer, Security).
- Level 2: Specialists (CIS facilitators, BMGD agents, sub-agents, workflow-specific helpers).

## 6) Workflow Model

### 6.1 Core Phases (BMAD)

- Phase 0 (Documentation, brownfield only): document-project.
- Phase 1 (Analysis): brainstorming, research, product brief.
- Phase 2 (Planning): PRD, tech spec, UX design, GDD for games.
- Phase 3 (Solutioning): architecture, implementation readiness.
- Phase 4 (Implementation): sprint planning, stories, dev-story, code review.
- Testing: test architecture, automation, traceability, CI.

### 6.2 Quint ADI Mapping

- Analysis -> Abduction (hypotheses in L0).
- Planning and Solutioning -> Deduction (verify constraints, promote to L1).
- Implementation and Testing -> Induction (validate with evidence, promote to L2).
- Decisions -> DRR creation and assurance audit.

### 6.3 TELIS Context Policy

- Phase 1: Tier 1 shards + minimal context.
- Phase 2-3: Tier 2 shards with progressive escalation.
- Phase 4: LSP first, shards second, full docs on demand.
- Validation: AST parse, type check, lint before output when applicable.

## 7) Orchestration and Event Model

### 7.1 Event Types

- WorkflowStarted, WorkflowStepCompleted, ArtifactReady, ValidationPassed, ValidationFailed.
- EvidenceRecorded, DecisionLogged, CacheHit, CacheMiss.
- RetryTriggered, FallbackUsed, EscalationQueued.

### 7.2 Routing Rules

- Orchestrator routes events to domain agents based on artifact and phase.
- Validation failures trigger TELIS error context injection and retry.
- Quint audit failures trigger revisit of assumptions and constraints.

### 7.3 Super-Framework Runtime

The runtime is the operational layer that unifies BMAD execution, TELIS context management, and Quint reasoning into a single autonomous loop with defined human gates.

Components:

- Event bus for workflow state transitions and routing.
- State store for workflow progress, artifacts, and context fingerprints.
- Policy engine for TELIS context budgets and validation gates.
- Context manager for LSP calls, shard retrieval, and negotiation.
- Evidence store for Quint L0-L2 claims, WLNK, and DRRs.
- Executor that runs BMAD workflows and tasks.
- Control plane for configuration, policy, and registry management.
- Data plane for execution, tool calls, and artifact IO.

Lifecycle:

1. Ingest request and classify scope and phase.
2. Assemble minimal context (TELIS) and select workflow.
3. Execute BMAD step, emit artifacts and state updates.
4. Validate outputs (TELIS gate) and record evidence (Quint).
5. Apply human gate when required, then advance to next step.

Failure handling:

- Retry once on transient errors with diagnostic context injection.
- Escalate on repeated failure or policy violations.

### 7.4 Runtime State Model

State model anchors runtime determinism and auditability.

Core records:

- WorkflowState: workflow id, current step, phase, status, timestamps.
- ArtifactIndex: artifact type, path, producing workflow, checksum.
- ContextFingerprint: shard ids, LSP lookups, token budget, cache key.
- EvidenceLink: claim id, evidence level, DRR link, validity window.
- HumanGate: gate type, status, approver, decision timestamp.

### 7.5 Event Schemas

Event payloads are normalized for tooling and traceability.

- WorkflowStarted: workflow id, phase, actor, timestamp.
- WorkflowStepCompleted: workflow id, step id, outputs, timestamp.
- ArtifactReady: artifact id, type, path, checksum.
- ValidationFailed: workflow id, rule id, diagnostics, retry count.
- EvidenceRecorded: claim id, level, source, congruence, validity.
- HumanGateRequired: gate id, reason, required evidence, status.

### 7.6 Kong-Inspired Runtime Patterns

The runtime adopts patterns proven in Kong-like gateway architectures and maps them to agentic execution.

- Control plane / data plane split:
  - Control plane: registry, policy, configuration, and orchestration decisions.
  - Data plane: workflow execution, tool calls, LLM requests, and artifact IO.
- Plugin pipeline:
  - Policy plugins: validation gates, HITL enforcement, risk classification.
  - Adapter plugins: provider clients (Ollama/LiteLLM/OpenAI/Claude/Gemini/Groq), tool bindings.
  - Observability plugins: structured logs, metrics, and trace emission.
- Declarative config and drift control:
  - Runtime config is declarative and versioned; changes are audited and tracked.
  - Runtime state snapshots support replay and drift detection.
- Failure isolation:
  - Circuit-breaker style safeguards around provider calls and tool adapters.
  - Bounded retries and explicit backoff rules defined in policy.

## 8) Evidence and Decision Protocol (Quint)

- L0: Hypotheses and early observations.
- L1: Verified constraints and logically consistent plans.
- L2: Empirical validation via tests, checks, or research.
- WLNK: Assurance equals weakest evidence.
- Congruence: External evidence must match context to count.
- Decay: Evidence expires and is revalidated.
- DRR: Required for architecture, platform choices, security posture, and major workflow deviations.

## 9) TELIS Implementation

### 9.1 LSP Symbiosis

- Use LSP for type and signature accuracy before code output.
- If LSP fails, fall back to shards and prompt for clarification.

### 9.2 Knowledge Shards

- Tiered shards for syntax, patterns, and deep references.
- Shards include BMAD templates, workflow instructions, and known conventions.

### 9.3 Progressive Context Negotiation

- Start minimal, escalate on explicit uncertainty.
- Do not guess APIs or signatures.

### 9.4 Validation Gate

- AST parse, type-check, lint before final output.
- On error, inject diagnostics and regenerate with bounded retries.

### 9.5 Behavioral Cache

- Cache common patterns and verified outputs.
- Invalidate on version changes or shard updates.

## 10) Guardrails and Safety

## 10.1 Human-in-the-loop Governance

Human oversight is required at defined gates and is blocking by default.
Mandatory gates: planning signoff, architecture signoff, and release approval.
Conditional gates: implementation review, test failures, and security risk acceptance.
All gates are recorded as DRRs with evidence links.

- Tool safeguards by risk level (read-only, reversible, high-impact).
- PII controls and moderation checks where relevant.
- Output validation for format and policy compliance.
- Bounded retries with clear fallback behavior.
- Human gates are blocking. Execution resumes only after approval or explicit override.

## 11) Testing and Quality

- TEA workflows are mandatory for test strategy and CI integration.
- ATDD preferred when requirements are clear.
- Quality gates: test coverage, lint, type checks, and regression suite.
- Game projects use BMGD QA workflows and engine-specific testing guidance.

## 12) Security

- Security agent performs threat review and vulnerability checklist.
- Required deliverable: security audit report.
- Security checks integrate into CI gate and release readiness.

## 13) Deliverables

- Unified method specification (this document).
- Deployed agent system with registry and orchestration rules.
- Working CI/CD pipeline with quality gates.
- Security audit report.
- Complete documentation set.
- Agent registry: methodology/registry-agents.md.
- Workflow registry: methodology/registry-workflows.md.
- Agent menu registry: methodology/registry-agent-menus.md.
- Integration mapping: methodology/integration-mapping.md.
- CI/CD blueprint: cicd/ci-cd-blueprint.md.
- Security audit template: security/security-audit-report-template.md.
- DRR template: methodology/drr-template.md.
- Evidence schema: methodology/evidence-schema.yaml.
- Documentation index: docs/unified-framework-documentation-index.md.

## 14) Output Structure

Project root contains the following directories:

- /BMAD-METHOD (canonical BMAD assets; use BMAD-METHOD/src for agents/workflows/modules/tasks/resources, BMAD-METHOD/src/utility/agent-components, and BMAD-METHOD/tools)
- /methodology
- /tests
- /cicd
- /security
- /docs

Naming convention: BMAD standard; BMAD-METHOD remains the canonical source.

## 15) Success Criteria Alignment

- 100 percent coverage of BMAD agents and workflows.
- Quint adoption for all decisions with evidence trails.
- TELIS context optimization with measurable token efficiency.
- Autonomous execution between mandatory gates, with no manual intervention outside those gates.
- All deliverables produced and validated.

## 16) Integration Mappings (Required)

- BMAD -> Execution substrate, workflow registry, agent menu and tasks.
- Quint -> Reasoning checkpoints, evidence storage, assurance audits, DRRs.
- TELIS -> Context policy, LSP calls, shards, negotiation, validation gates.
- Practical Guide -> Guardrails, tool risk classification, fallback behavior.

## 17) Open Decisions

- Security tooling selection and scanning scope per target platform.
- CI/CD provider defaults and deployment targets.
- Exact shard schema for BMAD workflow snippets and templates.

## 18) Execution Directive

READ_ALL_SOURCES_THEN_SYNTHESIZE_THEN_BUILD_AUTONOMOUSLY

## 19) Appendices

### 19.1 Agent Registry

See methodology/registry-agents.md

### 19.2 Workflow Registry

See methodology/registry-workflows.md

### 19.3 Integration Mapping

See methodology/integration-mapping.md

### 19.4 CI/CD Blueprint

See cicd/ci-cd-blueprint.md

### 19.5 Security Audit Template

See security/security-audit-report-template.md

### 19.6 Documentation Index

See docs/unified-framework-documentation-index.md

### 19.7 Agent Menu Registry

See methodology/registry-agent-menus.md

### 19.8 DRR Template

See methodology/drr-template.md

### 19.9 Evidence Schema

See methodology/evidence-schema.yaml
