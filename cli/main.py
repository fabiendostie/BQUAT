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


# =============================================================================
# TELIS Commands
# =============================================================================


def cmd_telis_status(args: argparse.Namespace) -> int:
    """Show TELIS configuration status."""
    config = _load_config(args.config)
    telis_cfg = config.get("telis", {})

    print("TELIS Configuration Status")
    print("=" * 40)
    print(f"Policy: {telis_cfg.get('policy', 'default')}")
    print(f"Use LSP: {telis_cfg.get('use_lsp', True)}")
    print(f"Progressive: {telis_cfg.get('progressive', True)}")

    # Show tier budgets
    budgets = telis_cfg.get("tier_budgets", {})
    if budgets:
        print("\nTier Budgets:")
        for tier, budget in budgets.items():
            print(f"  {tier}: {budget} tokens")
    else:
        print("\nTier Budgets: (defaults)")
        print("  tier_1_nano: 50 tokens")
        print("  tier_2_micro: 500 tokens")
        print("  tier_3_full: 2000 tokens")

    # Show shards config
    shards_path = telis_cfg.get("shards_path")
    shards_list = telis_cfg.get("shards", [])
    print(f"\nShards Path: {shards_path or '(not configured)'}")
    print(f"Inline Shards: {len(shards_list)} defined")

    return 0


def cmd_telis_list(args: argparse.Namespace) -> int:
    """List loaded shards."""
    from runtime.telis.manager import TelisPolicyEngine

    config = _load_config(args.config)
    telis = TelisPolicyEngine.from_config(config)

    if telis is None:
        print("TELIS is disabled in configuration.")
        return 1

    shard_list = telis.registry.list(language=args.language, tier=args.tier)

    if not shard_list:
        print("No shards loaded.")
        print("\nTo add shards, either:")
        print("  1. Run: baqt telis init")
        print("  2. Add 'shards_path' to your config")
        return 0

    print(f"Loaded Shards: {len(shard_list)}")
    print("=" * 60)

    for shard in shard_list:
        print(f"\n[{shard.shard_id}]")
        print(f"  Language: {shard.language}")
        print(f"  Tier: {shard.tier}")
        print(f"  Topics: {', '.join(shard.topics)}")
        print(f"  Tokens: {shard.tokens}")

    return 0


def cmd_telis_add(args: argparse.Namespace) -> int:
    """Add shards from a YAML/JSON file."""
    file_path = Path(args.file)
    if not file_path.exists():
        print(f"Error: File not found: {file_path}")
        return 1

    content = file_path.read_text(encoding="utf-8")

    if file_path.suffix in (".yaml", ".yml"):
        if yaml is None:
            print("Error: PyYAML not installed. Run: pip install pyyaml")
            return 1
        data = yaml.safe_load(content)
    else:
        data = json.loads(content)

    shards = data.get("shards", [])
    if not shards:
        print("No shards found in file.")
        return 1

    # Update config to include shards_path
    config_path = Path("config/runtime.yaml")
    if config_path.exists():
        print(f"Found {len(shards)} shards in {file_path}")
        print("\nTo use these shards, add to your config/runtime.yaml:")
        print("\n  telis:")
        print(f'    shards_path: "{file_path}"')
    else:
        print(f"Found {len(shards)} shards in {file_path}")

    print("\nShards summary:")
    for shard in shards:
        print(f"  - {shard.get('id')}: {shard.get('language')} ({shard.get('tier')})")

    return 0


def cmd_telis_init(args: argparse.Namespace) -> int:
    """Initialize sample shards configuration."""
    output_path = Path(args.output)

    sample_shards = """# TELIS Knowledge Shards Configuration
# See docs/Token-Efficient_Language_Intelligence_System_TELIS.md for details

shards:
  # Python shards
  - id: "python.async"
    language: "python"
    version: "3.11+"
    tier: "tier_2_micro"
    topics: [async, await, asyncio, coroutines]
    tokens: 180
    content: |
      ## Python Async Patterns
      - async def: define coroutine function
      - await expr: suspend until result ready
      - asyncio.gather(*coros): run concurrently
      - asyncio.create_task(coro): schedule execution
      - async for: iterate async iterator
      - async with: async context manager
      ## Gotchas
      - Can't use await outside async function
      - asyncio.run() creates new event loop

  - id: "python.typing"
    language: "python"
    version: "3.11+"
    tier: "tier_1_nano"
    topics: [types, annotations, generics]
    tokens: 80
    content: |
      def f(x: int) -> str: ...
      list[int], dict[str, Any], tuple[int, ...]
      T = TypeVar('T'); Generic[T]
      Optional[X] = X | None
      Callable[[Args], Return]

  # JavaScript/TypeScript shards
  - id: "js.async"
    language: "javascript"
    version: "ES2024"
    tier: "tier_2_micro"
    topics: [promises, async, await, fetch]
    tokens: 200
    content: |
      ## JS Async Patterns
      - Promise.all([]): parallel, fail-fast
      - Promise.allSettled([]): parallel, all results
      - Promise.race([]): first to settle wins
      - for await (x of asyncIter): sequential
      ## Gotchas
      - forEach doesn't await
      - map returns Promise[], use Promise.all(arr.map(...))
      - Unhandled rejection crashes Node.js

  - id: "js.array"
    language: "javascript"
    version: "ES2024"
    tier: "tier_1_nano"
    topics: [array, map, filter, reduce]
    tokens: 60
    content: |
      arr.map(x => f(x))
      arr.filter(x => bool)
      arr.reduce((acc, x) => acc + x, init)
      arr.flatMap(x => [x, x])
      arr.find(x => bool) // first match or undefined

  # JSON shards
  - id: "json.schema"
    language: "json"
    version: "draft-07"
    tier: "tier_2_micro"
    topics: [schema, validation, types]
    tokens: 150
    content: |
      ## JSON Schema Basics
      - type: string|number|boolean|object|array|null
      - properties: {name: {type: "string"}}
      - required: ["field1", "field2"]
      - additionalProperties: false
      - $ref: "#/definitions/Name"
      - oneOf/anyOf/allOf: schema composition
"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(sample_shards, encoding="utf-8")

    print(f"Created sample shards config: {output_path}")
    print("\nTo activate, add to config/runtime.yaml:")
    print("\n  telis:")
    print(f'    shards_path: "{output_path}"')
    print("\nSample includes shards for:")
    print("  - Python: async patterns, typing")
    print("  - JavaScript: async patterns, array methods")
    print("  - JSON: schema basics")

    return 0


# =============================================================================
# QUINT Commands
# =============================================================================


def cmd_quint_status(args: argparse.Namespace) -> int:
    """Show QUINT evidence status for a run."""
    config = _load_config(args.config)
    root = runtime_config.storage_root(config)
    run_dir = root / args.run_id

    if not run_dir.exists():
        print(f"Error: Run not found: {args.run_id}")
        return 1

    evidence_data = storage.read_evidence_links(run_dir)
    drr_data = storage.read_drrs(run_dir)
    fingerprints_path = run_dir / "fingerprints.json"

    evidence_list: list[Dict[str, Any]] = evidence_data.get("evidence", [])
    drr_list: list[Dict[str, Any]] = drr_data.get("drrs", [])

    print(f"QUINT Evidence Status: {args.run_id}")
    print("=" * 50)
    print(f"Evidence Records: {len(evidence_list)}")
    print(f"Decision Records (DRRs): {len(drr_list)}")
    print(f"Fingerprints: {'Yes' if fingerprints_path.exists() else 'No'}")

    # Count by level
    if evidence_list:
        levels: Dict[str, int] = {}
        for e in evidence_list:
            lvl = str(e.get("level", "unknown"))
            levels[lvl] = levels.get(lvl, 0) + 1
        print("\nEvidence by Level:")
        for lvl, count in sorted(levels.items()):
            print(f"  {lvl}: {count}")

    # Show drift status
    drift_path = run_dir / "drift.json"
    if drift_path.exists():
        drift_data = json.loads(drift_path.read_text(encoding="utf-8"))
        drifts = drift_data.get("drifts", [])
        print(f"\nContext Drift Detected: {len(drifts)} indicator(s)")

    return 0


def cmd_quint_evidence(args: argparse.Namespace) -> int:
    """List evidence records for a run."""
    config = _load_config(args.config)
    root = runtime_config.storage_root(config)
    run_dir = root / args.run_id

    if not run_dir.exists():
        print(f"Error: Run not found: {args.run_id}")
        return 1

    evidence_data = storage.read_evidence_links(run_dir)
    evidence_list: list[Dict[str, Any]] = evidence_data.get("evidence", [])

    if args.level:
        evidence_list = [e for e in evidence_list if e.get("level") == args.level]

    if not evidence_list:
        print("No evidence records found.")
        return 0

    print(f"Evidence Records: {len(evidence_list)}")
    print("=" * 60)

    for e in evidence_list:
        print(f"\n[{e.get('evidence_id', 'unknown')}]")
        print(f"  Level: {e.get('level')}")
        print(f"  Type: {e.get('evidence_type')}")
        print(f"  Source: {e.get('source_step')}")
        print(f"  WLNK Score: {e.get('wlnk_score', 'N/A')}")
        claim = e.get("claim")
        if claim:
            print(f"  Claim: {str(claim)[:60]}...")

    return 0


def cmd_quint_drr(args: argparse.Namespace) -> int:
    """Show Decision Review Records for a run."""
    config = _load_config(args.config)
    root = runtime_config.storage_root(config)
    run_dir = root / args.run_id

    if not run_dir.exists():
        print(f"Error: Run not found: {args.run_id}")
        return 1

    drr_data = storage.read_drrs(run_dir)
    drr_list: list[Dict[str, Any]] = drr_data.get("drrs", [])

    if not drr_list:
        print("No Decision Review Records found.")
        return 0

    print(f"Decision Review Records: {len(drr_list)}")
    print("=" * 60)

    for drr in drr_list:
        print(f"\n[{drr.get('drr_id', 'unknown')}]")
        print(f"  Title: {drr.get('title')}")
        print(f"  Status: {drr.get('status')}")
        decision = drr.get("decision", {})
        if isinstance(decision, dict):
            print(f"  Decision: {decision.get('choice', 'pending')}")
        else:
            print(f"  Decision: {decision}")
        options = drr.get("options")
        if options:
            print(f"  Options: {len(options)} evaluated")
        evidence = drr.get("evidence")
        if evidence:
            print(f"  Evidence: {len(evidence)} linked")

    return 0


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

    # TELIS shard management
    telis = sub.add_parser("telis", help="TELIS context shard management")
    telis_sub = telis.add_subparsers(dest="telis_command", required=True)

    telis_status = telis_sub.add_parser("status", help="Show TELIS configuration status")
    telis_status.set_defaults(func=cmd_telis_status)

    telis_list = telis_sub.add_parser("list", help="List loaded shards")
    telis_list.add_argument("--language", help="Filter by language")
    telis_list.add_argument("--tier", help="Filter by tier")
    telis_list.set_defaults(func=cmd_telis_list)

    telis_add = telis_sub.add_parser("add", help="Add shards from YAML/JSON file")
    telis_add.add_argument("file", help="Path to shards file")
    telis_add.set_defaults(func=cmd_telis_add)

    telis_init = telis_sub.add_parser("init", help="Initialize sample shards config")
    telis_init.add_argument("--output", default="config/telis-shards.yaml", help="Output path")
    telis_init.set_defaults(func=cmd_telis_init)

    # QUINT evidence management
    quint = sub.add_parser("quint", help="QUINT evidence store management")
    quint_sub = quint.add_subparsers(dest="quint_command", required=True)

    quint_status = quint_sub.add_parser("status", help="Show QUINT evidence status for a run")
    quint_status.add_argument("run_id", help="Run ID to check")
    quint_status.set_defaults(func=cmd_quint_status)

    quint_evidence = quint_sub.add_parser("evidence", help="List evidence records for a run")
    quint_evidence.add_argument("run_id", help="Run ID")
    quint_evidence.add_argument("--level", help="Filter by level (L1, L2, L3)")
    quint_evidence.set_defaults(func=cmd_quint_evidence)

    quint_drr = quint_sub.add_parser("drr", help="Show Decision Review Records for a run")
    quint_drr.add_argument("run_id", help="Run ID")
    quint_drr.set_defaults(func=cmd_quint_drr)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
