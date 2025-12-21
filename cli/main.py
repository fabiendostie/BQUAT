from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Optional

from runtime import config as runtime_config
from runtime import engine, execution, storage
from runtime.providers.registry import ProviderRegistry


def _load_config(path: Optional[str]) -> Dict[str, Any]:
    target = Path(path) if path else None
    return runtime_config.load_config(target)


def _engine(config: Dict[str, Any]) -> engine.WorkflowEngine:
    mapping = engine.load_mapping_records()
    return engine.WorkflowEngine(config, mapping)


def cmd_validate(args: argparse.Namespace) -> int:
    records = engine.load_mapping_records()
    print(json.dumps({"records": len(records)}))
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    config = _load_config(args.config)
    eng = _engine(config)
    executor = None
    if args.agent:
        provider = None
        if args.provider:
            registry = ProviderRegistry(config)
            provider = registry.get(args.provider)
        executor = execution.PlanExecutor(args.agent, provider)
    manifest = eng.run(args.module, args.workflow, run_id=args.run_id, executor=executor)
    print(json.dumps({"run_id": manifest["run_id"], "status": manifest["status"]}))
    return 0


def cmd_resume(args: argparse.Namespace) -> int:
    config = _load_config(args.config)
    eng = _engine(config)
    executor = None
    if args.agent:
        provider = None
        if args.provider:
            registry = ProviderRegistry(config)
            provider = registry.get(args.provider)
        executor = execution.PlanExecutor(args.agent, provider)
    manifest = eng.resume(args.run_id, executor=executor)
    print(json.dumps({"run_id": manifest["run_id"], "status": manifest["status"]}))
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


def cmd_providers(args: argparse.Namespace) -> int:
    config = _load_config(args.config)
    providers = list(config.get("providers", {}).keys())
    print(json.dumps({"providers": providers}))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bquat")
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
    run.set_defaults(func=cmd_run)

    resume = sub.add_parser("resume", help="Resume a run")
    resume.add_argument("run_id")
    resume.add_argument("--agent", choices=["bmad", "telis", "quint"])
    resume.add_argument("--provider")
    resume.set_defaults(func=cmd_resume)

    approve = sub.add_parser("approve", help="Approve a human gate")
    approve.add_argument("run_id")
    approve.add_argument("--by", required=True)
    approve.add_argument("--notes")
    approve.set_defaults(func=cmd_approve)

    status = sub.add_parser("status", help="Show run status")
    status.add_argument("run_id")
    status.set_defaults(func=cmd_status)

    providers = sub.add_parser("providers", help="List providers")
    providers.set_defaults(func=cmd_providers)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
