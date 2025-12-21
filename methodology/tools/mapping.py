from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List


@dataclass(frozen=True)
class WorkflowRecord:
    module: str
    workflow: str
    phase: str
    quint: str
    telis: str
    validation: str
    human: str
    evidence: str
    artifacts: List[str]
    scope: str
    path: str


@dataclass(frozen=True)
class WorkflowRegistryRecord:
    module: str
    workflow: str
    phase: str
    definition: str
    scope: str
    path: str


def module_from_path(path: Path) -> str:
    parts = [p.lower() for p in path.parts]
    if "src" in parts and "modules" in parts:
        idx = parts.index("modules")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    if "src" in parts and "core" in parts:
        return "core"
    if "docs" in parts and "sample-custom-modules" in parts:
        return "sample"
    return "misc"


def classify_scope(path: Path) -> str:
    parts = [p.lower() for p in path.parts]
    if "test" in parts or "fixtures" in parts:
        return "test"
    if "sample-custom-modules" in parts:
        return "sample"
    if "reference" in parts:
        return "reference"
    if "docs" in parts and "sample" in parts:
        return "sample"
    return "production"


def phase_from_path(rel: str, module: str) -> str:
    rel_lower = rel.lower()
    if module == "bmm":
        if "/1-analysis/" in rel_lower:
            return "Phase 1 Analysis"
        if "/2-plan-workflows/" in rel_lower:
            return "Phase 2 Planning"
        if "/3-solutioning/" in rel_lower:
            return "Phase 3 Solutioning"
        if "/4-implementation/" in rel_lower:
            return "Phase 4 Implementation"
        if "/testarch/" in rel_lower:
            return "Testing/QA"
        if "/bmad-quick-flow/" in rel_lower:
            return "Quick Flow"
        if "/document-project/" in rel_lower:
            return "Phase 0 Documentation"
        if "/generate-project-context/" in rel_lower:
            return "Context Generation"
        if "/excalidraw-diagrams/" in rel_lower:
            return "Diagramming"
        if "/workflow-status/" in rel_lower:
            return "Meta"
        return "BMM"
    if module == "bmgd":
        if "/1-preproduction/" in rel_lower:
            return "Phase 1 Preproduction"
        if "/2-design/" in rel_lower:
            return "Phase 2 Design"
        if "/3-technical/" in rel_lower:
            return "Phase 3 Technical"
        if "/4-production/" in rel_lower:
            return "Phase 4 Production"
        if "/gametest/" in rel_lower:
            return "Testing/QA"
        if "/bmgd-quick-flow/" in rel_lower:
            return "Quick Flow"
        if "/workflow-status/" in rel_lower:
            return "Meta"
        return "BMGD"
    if module == "bmb":
        if "/workflows-legacy/" in rel_lower:
            return "Builder Legacy"
        return "Builder"
    if module == "cis":
        return "CIS"
    if module == "core":
        if "/party-mode/" in rel_lower or "/workflow-status/" in rel_lower:
            return "Meta"
        return "Core"
    return "Uncategorized"


def quint_checkpoint(phase: str) -> str:
    if phase in ["Phase 1 Analysis", "Phase 1 Preproduction", "CIS", "Core"]:
        return "Abduction (L0)"
    if phase in [
        "Phase 2 Planning",
        "Phase 2 Design",
        "Phase 3 Solutioning",
        "Phase 3 Technical",
        "Builder",
        "Builder Legacy",
        "Diagramming",
        "Context Generation",
        "BMM",
        "BMGD",
    ]:
        return "Deduction (L1)"
    if phase in ["Phase 4 Implementation", "Phase 4 Production", "Testing/QA"]:
        return "Induction (L2)"
    if phase in ["Phase 0 Documentation"]:
        return "Observation (L0)"
    if phase in ["Meta"]:
        return "Audit/Decision"
    if phase == "Quick Flow":
        return "Mixed (ADI compressed)"
    return "Deduction (L1)"


def telis_policy(phase: str) -> str:
    if phase in ["Phase 1 Analysis", "Phase 1 Preproduction", "CIS", "Core"]:
        return "Tier 1 minimal, Tier 2 on demand"
    if phase in [
        "Phase 2 Planning",
        "Phase 2 Design",
        "Phase 3 Solutioning",
        "Phase 3 Technical",
        "Builder",
        "Builder Legacy",
        "Diagramming",
        "Context Generation",
        "Phase 0 Documentation",
        "BMM",
        "BMGD",
    ]:
        return "Tier 2 shards + progressive negotiation"
    if phase in [
        "Phase 4 Implementation",
        "Phase 4 Production",
        "Testing/QA",
        "Quick Flow",
    ]:
        return "LSP-first + Tier 2 + validation gate"
    if phase in ["Meta"]:
        return "Tier 1 minimal"
    return "Tier 2 shards + progressive negotiation"


def validation_gate(phase: str) -> str:
    if phase in [
        "Phase 4 Implementation",
        "Phase 4 Production",
        "Testing/QA",
        "Quick Flow",
    ]:
        return "AST + type + lint (as applicable)"
    if phase in [
        "Phase 2 Planning",
        "Phase 2 Design",
        "Phase 3 Solutioning",
        "Phase 3 Technical",
        "Builder",
        "Builder Legacy",
        "Diagramming",
        "Context Generation",
        "Phase 0 Documentation",
    ]:
        return "Template/schema validation"
    if phase in ["Phase 1 Analysis", "Phase 1 Preproduction", "CIS", "Core"]:
        return "Format validation"
    if phase in ["Meta"]:
        return "N/A"
    return "Template/schema validation"


def evidence_required(phase: str) -> str:
    if phase in [
        "Phase 1 Analysis",
        "Phase 1 Preproduction",
        "CIS",
        "Core",
        "Phase 0 Documentation",
    ]:
        return "L0"
    if phase in [
        "Phase 2 Planning",
        "Phase 2 Design",
        "Phase 3 Solutioning",
        "Phase 3 Technical",
        "Builder",
        "Builder Legacy",
        "Diagramming",
        "Context Generation",
        "BMM",
        "BMGD",
    ]:
        return "L1"
    if phase in ["Phase 4 Implementation", "Phase 4 Production", "Testing/QA"]:
        return "L2"
    if phase == "Quick Flow":
        return "L1/L2"
    if phase == "Meta":
        return "L1"
    return "L1"


def human_gate(phase: str, workflow: str) -> str:
    wf = workflow.lower()
    if "workflow-status" in wf:
        return "none"
    if any(
        k in wf
        for k in [
            "install",
            "uninstall",
            "deploy",
            "release",
            "migration",
            "delete",
            "remove",
        ]
    ):
        return "required"
    if phase in [
        "Phase 2 Planning",
        "Phase 2 Design",
        "Phase 3 Solutioning",
        "Phase 3 Technical",
    ]:
        return "required"
    if phase in ["Phase 4 Implementation", "Phase 4 Production"]:
        if any(
            k in wf
            for k in [
                "code-review",
                "correct-course",
                "sprint-planning",
                "create-story",
                "dev-story",
            ]
        ):
            return "conditional"
        return "optional"
    if phase in ["Testing/QA"]:
        return "conditional"
    if phase in ["Phase 0 Documentation"]:
        return "recommended"
    if phase in ["Quick Flow"]:
        return "conditional"
    if phase in ["Meta"]:
        return "none"
    return "optional"


def artifact_from_workflow(phase: str, workflow: str) -> str:
    wf = workflow.lower()
    if "prd" in wf:
        return "PRD"
    if "tech-spec" in wf or "techspec" in wf:
        return "Tech Spec"
    if "gdd" in wf:
        return "GDD"
    if "architecture" in wf:
        return "Architecture"
    if "ux" in wf or "wireframe" in wf or "flowchart" in wf or "diagram" in wf:
        return "UX/Design Artifacts"
    if "story" in wf:
        return "Story"
    if "sprint" in wf:
        return "Sprint Plan/Status"
    if "document-project" in wf:
        return "Project Documentation"
    if "research" in wf:
        return "Research Brief"
    if "brainstorm" in wf:
        return "Idea Set"
    if "test" in wf or phase == "Testing/QA":
        return "Test Artifacts"
    if "code-review" in wf:
        return "Code Review"
    if "retrospective" in wf:
        return "Retrospective"
    if "correct-course" in wf:
        return "Course Correction Plan"
    return "Workflow Output"


def safe_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return path.read_text(encoding="utf-8", errors="ignore")


def extract_outputs(text: str) -> List[str]:
    outputs: List[str] = []
    for match in re.finditer(r"(?im)^\s*output(?:file|_file|_path)\s*:\s*(.+)$", text):
        val = match.group(1).strip().strip('"').strip("'")
        if val:
            outputs.append(val)

    for match in re.finditer(r"(?im)^\s*outputs\s*:\s*$", text):
        start = match.end()
        tail = text[start:]
        for line in tail.splitlines():
            if not line.strip():
                continue
            if re.match(r"^\s*-\s+", line):
                val = re.sub(r"^\s*-\s+", "", line).strip().strip('"').strip("'")
                if val:
                    outputs.append(val)
                continue
            if re.match(r"^\S", line):
                break
            if not line.startswith(" ") and not line.startswith("\t"):
                break

    return outputs


def artifacts_from_workflow_dir(workflow_dir: Path) -> List[str]:
    artifacts = set()

    for wf in [
        workflow_dir / "workflow.yaml",
        workflow_dir / "workflow.yml",
        workflow_dir / "workflow.md",
    ]:
        if wf.exists():
            artifacts.update(extract_outputs(safe_text(wf)))

    step_dir = workflow_dir / "steps"
    if step_dir.exists():
        for step_file in step_dir.glob("step-*.md"):
            artifacts.update(extract_outputs(safe_text(step_file)))

    for tmpl in workflow_dir.rglob("*"):
        if not tmpl.is_file():
            continue
        name_lower = tmpl.name.lower()
        if "template" in name_lower:
            rel = tmpl.relative_to(workflow_dir).as_posix()
            artifacts.add(f"template:{rel}")

    return sorted(artifacts)


def list_workflow_files(root: Path) -> List[Path]:
    files = list(root.rglob("workflow.md"))
    files.extend(root.rglob("workflow.yaml"))
    return sorted(set(files))


def generate_mapping_records(bmad_root: Path) -> List[WorkflowRecord]:
    records: List[WorkflowRecord] = []
    for path in list_workflow_files(bmad_root):
        rel = path.relative_to(bmad_root).as_posix()
        module = module_from_path(path)
        phase = phase_from_path(rel, module)
        workflow_dir = path.parent
        workflow_name = workflow_dir.name
        scope = classify_scope(path)
        if scope != "production":
            continue
        artifacts = artifacts_from_workflow_dir(workflow_dir)
        records.append(
            WorkflowRecord(
                module=module,
                workflow=workflow_name,
                phase=phase,
                quint=quint_checkpoint(phase),
                telis=telis_policy(phase),
                validation=validation_gate(phase),
                human=human_gate(phase, workflow_name),
                evidence=evidence_required(phase),
                artifacts=artifacts,
                scope=scope,
                path=rel,
            )
        )
    return records


def generate_registry_workflows(bmad_root: Path) -> List[WorkflowRegistryRecord]:
    records: List[WorkflowRegistryRecord] = []
    for path in list_workflow_files(bmad_root):
        rel = path.relative_to(bmad_root).as_posix()
        module = module_from_path(path)
        phase = phase_from_path(rel, module)
        workflow_name = path.parent.name
        scope = classify_scope(path)
        if scope != "production":
            continue
        records.append(
            WorkflowRegistryRecord(
                module=module,
                workflow=workflow_name,
                phase=phase,
                definition=path.name,
                scope=scope,
                path=rel,
            )
        )
    return records


def write_mapping(records: Iterable[WorkflowRecord], path: Path) -> None:
    lines: List[str] = []
    lines.append("# Integration Mapping: Workflows to Quint and TELIS")
    lines.append("")
    lines.append(
        "This table maps every BMAD workflow to Quint ADI checkpoints, TELIS "
        "context policies, validation gates, human-in-loop requirements, evidence "
        "levels, and concrete artifacts derived from explicit outputs and templates."
    )
    lines.append("")
    lines.append(
        "| Module | Workflow | Phase | Quint Checkpoint | TELIS Policy | "
        "Validation Gate | Human Gate | Evidence Level | Artifacts | Scope | Path |"
    )
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for row in records:
        artifacts_text = "; ".join(row.artifacts) if row.artifacts else "none"
        lines.append(
            "| "
            + " | ".join(
                [
                    row.module,
                    row.workflow,
                    row.phase,
                    row.quint,
                    row.telis,
                    row.validation,
                    row.human,
                    row.evidence,
                    artifacts_text,
                    row.scope,
                    row.path,
                ]
            )
            + " |"
        )
    path.write_bytes("\n".join(lines).encode("ascii", "ignore"))


def mapping_record_to_dict(record: WorkflowRecord) -> dict:
    return {
        "module": record.module,
        "workflow": record.workflow,
        "phase": record.phase,
        "quint": record.quint,
        "telis": record.telis,
        "validation": record.validation,
        "human": record.human,
        "evidence": record.evidence,
        "artifacts": record.artifacts,
        "scope": record.scope,
        "path": record.path,
    }


def write_registry_workflows(records: Iterable[WorkflowRegistryRecord], path: Path) -> None:
    lines: List[str] = []
    lines.append("# BMAD Workflow Registry")
    lines.append("")
    rows = list(records)
    lines.append(f"Total workflows: {len(rows)}")
    lines.append("")
    lines.append("| Module | Workflow | Phase | Definition | Scope | Path |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    row.module,
                    row.workflow,
                    row.phase,
                    row.definition,
                    row.scope,
                    row.path,
                ]
            )
            + " |"
        )
    path.write_bytes("\n".join(lines).encode("ascii", "ignore"))


def registry_record_to_dict(record: WorkflowRegistryRecord) -> dict:
    return {
        "module": record.module,
        "workflow": record.workflow,
        "phase": record.phase,
        "definition": record.definition,
        "scope": record.scope,
        "path": record.path,
    }


def write_mapping_json(records: Iterable[WorkflowRecord], path: Path) -> None:
    payload = {"records": [mapping_record_to_dict(record) for record in records]}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="ascii")


def write_registry_workflows_json(records: Iterable[WorkflowRegistryRecord], path: Path) -> None:
    payload = {"records": [registry_record_to_dict(record) for record in records]}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="ascii")


def project_root_from_here() -> Path:
    return Path(__file__).resolve().parents[2]
