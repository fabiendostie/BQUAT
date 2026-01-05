from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, Optional

from runtime import config as runtime_config
from runtime import engine, execution, models, storage
from runtime.logging.report import RunReportGenerator
from runtime.orchestrator import engine as orchestrator_engine
from runtime.orchestrator.graph import WorkflowNode
from runtime.providers.registry import ProviderRegistry

yaml: ModuleType | None
try:
    import yaml as yaml_module
except ImportError:  # pragma: no cover - optional dependency
    yaml = None
else:
    yaml = yaml_module


def _load_config(path: Optional[str]) -> Dict[str, Any]:
    target = Path(path) if path else None
    return runtime_config.load_config(target)


def _engine(config: Dict[str, Any]) -> engine.WorkflowEngine:
    mapping = engine.load_mapping_records()
    return engine.WorkflowEngine(config, mapping)


def _prompt_automation_choice(spec: models.WorkflowSpec) -> bool:
    message = (
        f"Automation is disabled for phase '{spec.phase}' in {spec.module}/{spec.workflow}.\n"
        "Select: [A] automate anyway, [M] manual (default): "
    )
    print(message, file=sys.stderr, end="")
    try:
        choice = input().strip().lower()
    except EOFError:
        return False
    return choice in {"a", "auto", "automate", "y", "yes"}


def _automation_decision(
    config: Dict[str, Any],
    spec: models.WorkflowSpec,
    args: argparse.Namespace,
) -> Optional[bool]:
    if not getattr(args, "agent", None):
        return None
    phases = config.get("automation", {}).get("phases")
    if not phases or spec.phase in set(phases):
        return None
    if args.auto:
        return True
    if args.manual:
        return False
    if sys.stdin.isatty():
        return _prompt_automation_choice(spec)
    return False


def _with_automation_override(config: Dict[str, Any]) -> Dict[str, Any]:
    updated = dict(config)
    automation = dict(updated.get("automation", {}))
    automation["override"] = True
    updated["automation"] = automation
    return updated


def _workflow_payload(spec: models.WorkflowSpec) -> Dict[str, Any]:
    return {
        "module": spec.module,
        "workflow": spec.workflow,
        "phase": spec.phase,
        "validation": spec.validation,
        "human_gate": spec.human,
        "evidence": spec.evidence,
        "scope": spec.scope,
        "path": spec.path,
        "artifacts": list(spec.artifacts),
    }


def _load_plan_file(path: str) -> Dict[str, Any]:
    content = Path(path).read_text(encoding="ascii")
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        if yaml is None:
            raise RuntimeError("PyYAML is required to load YAML plans") from None
        data = yaml.safe_load(content)
        return data if isinstance(data, dict) else {}


def _load_orchestration_nodes(path: str) -> list[WorkflowNode]:
    data = _load_plan_file(path)
    workflows = data.get("workflows", [])
    nodes: list[WorkflowNode] = []
    if not isinstance(workflows, list):
        return nodes
    for item in workflows:
        if not isinstance(item, dict):
            continue
        module = str(item.get("module", ""))
        workflow = str(item.get("workflow", ""))
        if not module or not workflow:
            continue
        deps = item.get("depends_on") or item.get("dependencies") or []
        dependencies = [str(dep) for dep in deps] if isinstance(deps, list) else []
        nodes.append(
            WorkflowNode(
                module=module,
                workflow=workflow,
                dependencies=dependencies,
                agent=item.get("agent"),
                provider=item.get("provider"),
            )
        )
    return nodes


def _summarize_run(manifest: Dict[str, Any]) -> Dict[str, Any]:
    workflow = manifest.get("workflow", {})
    steps = manifest.get("steps", [])
    completed = sum(1 for step in steps if step.get("status") == "completed")
    return {
        "run_id": manifest.get("run_id", ""),
        "status": manifest.get("status", ""),
        "module": workflow.get("module", ""),
        "workflow": workflow.get("workflow", ""),
        "phase": workflow.get("phase", ""),
        "created_at": manifest.get("created_at", ""),
        "updated_at": manifest.get("updated_at", ""),
        "current_step": manifest.get("current_step", 0),
        "steps_completed": completed,
        "steps_total": len(steps),
        "blocked_reason": manifest.get("blocked_reason"),
        "blocked_gate": manifest.get("blocked_gate"),
    }


def cmd_validate(args: argparse.Namespace) -> int:
    records = engine.load_mapping_records()
    print(json.dumps({"records": len(records)}))
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    config = _load_config(args.config)
    eng = _engine(config)
    spec = eng.get_workflow_spec(args.module, args.workflow)
    decision = _automation_decision(config, spec, args)
    if decision:
        config = _with_automation_override(config)
        eng = _engine(config)
    if getattr(args, "orchestrate", False):
        orchestrator = orchestrator_engine.WorkflowOrchestrator(config)
        node = WorkflowNode(
            module=args.module,
            workflow=args.workflow,
            agent=args.agent,
            provider=args.provider,
        )
        plan = orchestrator.plan_execution([node])
        manifests = orchestrator.execute_plan(plan)
        manifest = manifests[0]
        print(json.dumps({"run_id": manifest["run_id"], "status": manifest["status"]}))
        return 0
    executor = None
    if args.agent:
        provider = None
        if args.provider:
            registry = ProviderRegistry(config)
            provider = registry.get(args.provider)
        executor = execution.PlanExecutor(args.agent, provider)
    manifest = eng.run(
        args.module,
        args.workflow,
        run_id=args.run_id,
        executor=executor,
        agent_name=args.agent,
    )
    print(json.dumps({"run_id": manifest["run_id"], "status": manifest["status"]}))
    return 0


def cmd_resume(args: argparse.Namespace) -> int:
    config = _load_config(args.config)
    root = runtime_config.storage_root(config)
    manifest = storage.read_manifest(root / args.run_id)
    spec = models.WorkflowSpec.from_mapping(manifest["workflow"])
    decision = _automation_decision(config, spec, args)
    if decision:
        config = _with_automation_override(config)
    eng = _engine(config)
    executor = None
    if args.agent:
        provider = None
        if args.provider:
            registry = ProviderRegistry(config)
            provider = registry.get(args.provider)
        executor = execution.PlanExecutor(args.agent, provider)
    manifest = eng.resume(
        args.run_id,
        executor=executor,
        agent_name=args.agent,
    )
    print(json.dumps({"run_id": manifest["run_id"], "status": manifest["status"]}))
    return 0


def cmd_orchestrate(args: argparse.Namespace) -> int:
    config = _load_config(args.config)
    orchestrator = orchestrator_engine.WorkflowOrchestrator(config)
    nodes = _load_orchestration_nodes(args.plan)
    plan = orchestrator.plan_execution(nodes)
    manifests = orchestrator.execute_plan(plan)
    runs = [
        {"run_id": manifest.get("run_id", ""), "status": manifest.get("status", "")}
        for manifest in manifests
    ]
    print(json.dumps({"runs": runs}))
    return 0


def cmd_approve(args: argparse.Namespace) -> int:
    config = _load_config(args.config)
    eng = _engine(config)
    approvals = eng.approve_gate(args.run_id, approved_by=args.by, notes=args.notes or "")
    print(json.dumps(approvals))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    config = _load_config(args.config)
    root = runtime_config.storage_root(config)
    manifest = storage.read_manifest(root / args.run_id)
    print(json.dumps(manifest))
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    records = engine.load_mapping_records()
    if args.module:
        records = [record for record in records if record.module == args.module]
    workflows = [_workflow_payload(record) for record in records]
    print(json.dumps({"workflows": workflows}))
    return 0


def cmd_history(args: argparse.Namespace) -> int:
    config = _load_config(args.config)
    root = runtime_config.storage_root(config)
    runs = []
    for run_dir in storage.list_runs(root):
        manifest = storage.read_manifest(run_dir)
        runs.append(_summarize_run(manifest))
    runs.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
    if args.limit:
        runs = runs[: max(0, args.limit)]
    print(json.dumps({"runs": runs}))
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    config = _load_config(args.config)
    root = runtime_config.storage_root(config)
    run_dir = root / args.run_id
    storage.update_timeline(run_dir)

    if getattr(args, "report", False):
        generator = RunReportGenerator(run_dir)
        report = generator.generate()
        payload = report.to_dict()
    else:
        payload = {
            "manifest": storage.read_manifest(run_dir),
            "approvals": storage.read_approvals(run_dir),
            "gates": storage.read_human_gates(run_dir),
            "events": storage.read_events(run_dir),
            "artifacts": storage.read_artifact_index(run_dir),
            "tool_results": storage.read_tool_results(run_dir),
            "evidence": storage.read_evidence_links(run_dir),
            "drr": storage.read_drrs(run_dir),
            "timeline": storage.read_timeline(run_dir),
        }

    rendered = json.dumps(payload, indent=2, sort_keys=True)
    if args.output:
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered, encoding="ascii")
        print(json.dumps({"output": str(target)}))
    else:
        print(rendered)
    return 0


def cmd_providers(args: argparse.Namespace) -> int:
    config = _load_config(args.config)
    providers = [
        key for key in config.get("providers", {}).keys() if key not in {"default", "reliability"}
    ]
    print(json.dumps({"providers": providers}))
    return 0


def cmd_interactive(args: argparse.Namespace) -> int:
    """Run an interactive BMAD workflow session."""
    from cli.interactive import InteractiveCLI

    config = _load_config(args.config)
    eng = _engine(config)

    provider = None
    if args.provider:
        registry = ProviderRegistry(config)
        provider = registry.get(args.provider)

    cli = InteractiveCLI(
        engine=eng,
        provider=provider,
        bmad_root=Path("BMAD-METHOD"),
    )

    if args.module and args.workflow:
        # Run specific workflow
        run_id = cli.run_workflow(args.module, args.workflow, args.run_id)
        if run_id:
            print(json.dumps({"run_id": run_id, "status": "completed"}))
            return 0
        return 1
    else:
        # Full interactive session
        cli.run_interactive_session()
        return 0


def cmd_start(args: argparse.Namespace) -> int:
    """Start a BMAD workflow from brainstorming."""
    from cli.interactive import InteractiveCLI

    config = _load_config(args.config)
    eng = _engine(config)

    provider = None
    if args.provider:
        registry = ProviderRegistry(config)
        provider = registry.get(args.provider)

    cli = InteractiveCLI(
        engine=eng,
        provider=provider,
        bmad_root=Path("BMAD-METHOD"),
    )

    # Start from brainstorming by default
    module = args.module or "core"
    workflow = args.workflow or "brainstorming"

    print(f"Starting BMAD workflow: {module}/{workflow}")
    print("This will guide you through document creation.")
    print("")

    run_id = cli.run_workflow(module, workflow)
    if run_id:
        print(json.dumps({"run_id": run_id, "status": "completed"}))
        return 0
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="baqt")
    parser.add_argument("--config", help="Path to runtime config JSON")

    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="Validate mapping availability")
    validate.set_defaults(func=cmd_validate)

    run = sub.add_parser("run", help="Run a workflow")
    run.add_argument("module")
    run.add_argument("workflow")
    run.add_argument("--run-id")
    run.add_argument("--agent", choices=["bmad", "telis", "quint"])
    run.add_argument("--provider")
    run.add_argument("--orchestrate", action="store_true")
    run_select = run.add_mutually_exclusive_group()
    run_select.add_argument("--auto", action="store_true")
    run_select.add_argument("--manual", action="store_true")
    run.set_defaults(func=cmd_run)

    resume = sub.add_parser("resume", help="Resume a run")
    resume.add_argument("run_id")
    resume.add_argument("--agent", choices=["bmad", "telis", "quint"])
    resume.add_argument("--provider")
    resume_select = resume.add_mutually_exclusive_group()
    resume_select.add_argument("--auto", action="store_true")
    resume_select.add_argument("--manual", action="store_true")
    resume.set_defaults(func=cmd_resume)

    orchestrate = sub.add_parser("orchestrate", help="Run a workflow plan")
    orchestrate.add_argument("--plan", required=True, help="Path to workflow plan file")
    orchestrate.set_defaults(func=cmd_orchestrate)

    approve = sub.add_parser("approve", help="Approve a human gate")
    approve.add_argument("run_id")
    approve.add_argument("--by", required=True)
    approve.add_argument("--notes")
    approve.set_defaults(func=cmd_approve)

    status = sub.add_parser("status", help="Show run status")
    status.add_argument("run_id")
    status.set_defaults(func=cmd_status)

    list_cmd = sub.add_parser("list", help="List workflows")
    list_cmd.add_argument("--module")
    list_cmd.set_defaults(func=cmd_list)

    history = sub.add_parser("history", help="Show run history summary")
    history.add_argument("--limit", type=int)
    history.set_defaults(func=cmd_history)

    export = sub.add_parser("export", help="Export run data")
    export.add_argument("run_id")
    export.add_argument("--output")
    export.add_argument(
        "--report", action="store_true", help="Generate summary report with statistics"
    )
    export.set_defaults(func=cmd_export)

    providers = sub.add_parser("providers", help="List providers")
    providers.set_defaults(func=cmd_providers)

    # Interactive mode for step-by-step workflow execution
    interactive = sub.add_parser("interactive", help="Run interactive BMAD workflow session")
    interactive.add_argument("--module", help="BMAD module (e.g., bmm, core)")
    interactive.add_argument("--workflow", help="Workflow name (e.g., prd, brainstorming)")
    interactive.add_argument("--run-id", help="Resume existing run")
    interactive.add_argument("--provider", help="LLM provider to use")
    interactive.set_defaults(func=cmd_interactive)

    # Quick start from brainstorming
    start = sub.add_parser("start", help="Start BMAD workflow from brainstorming")
    start.add_argument("--module", default="core", help="BMAD module (default: core)")
    start.add_argument(
        "--workflow", default="brainstorming", help="Workflow (default: brainstorming)"
    )
    start.add_argument("--provider", help="LLM provider to use")
    start.set_defaults(func=cmd_start)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
