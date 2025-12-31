import json
import sys
import time
import unittest
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import (
    config as runtime_config,  # noqa: E402
)
from runtime import (
    engine,  # noqa: E402
    models,  # noqa: E402
    storage,  # noqa: E402
)
from runtime.plugins.base import Plugin  # noqa: E402


def _sandbox_root() -> Path:
    root = ROOT / "runs" / "tmp-tests" / uuid4().hex
    root.mkdir(parents=True, exist_ok=True)
    return root


class FlakyExecutor(engine.StepExecutor):
    def __init__(self) -> None:
        self.calls = 0

    def execute(self, step: dict, context: dict) -> None:
        self.calls += 1
        if self.calls == 1:
            raise ValueError("boom")


class FailingExecutor(engine.StepExecutor):
    def execute(self, step: dict, context: dict) -> None:
        raise RuntimeError("nope")


class RecordingPlugin(Plugin):
    def __init__(self) -> None:
        self.events = []

    def before_run(self, manifest: dict) -> None:
        self.events.append("before_run")

    def after_run(self, manifest: dict) -> None:
        self.events.append("after_run")

    def before_step(self, step: dict, manifest: dict) -> None:
        self.events.append("before_step")

    def after_step(self, step: dict, manifest: dict) -> None:
        self.events.append("after_step")

    def on_error(self, step: dict, manifest: dict, error: str) -> None:
        self.events.append("on_error")

    def on_validation(self, manifest: dict, status: str) -> None:
        self.events.append(f"validation:{status}")


class PersistingPlugin(Plugin):
    def __init__(self, storage_root: Path) -> None:
        self.storage_root = storage_root
        self.snapshot = None

    def on_error(self, step: dict, manifest: dict, error: str) -> None:
        self.snapshot = storage.read_manifest(self.storage_root / manifest["run_id"])


class TimeoutExecutor(engine.StepExecutor):
    def execute(self, step: dict, context: dict) -> None:
        time.sleep(0.01)


class RecordingExecutor(engine.StepExecutor):
    def __init__(self) -> None:
        self.steps = []

    def execute(self, step: dict, context: dict) -> None:
        self.steps.append(step.get("name"))


class GuardrailExecutor(engine.StepExecutor):
    def execute(self, step: dict, context: dict) -> None:
        run_dir = Path(context["run_dir"])
        (run_dir / "guardrail.txt").write_text("Contact me at test@example.com", encoding="ascii")
        step["outputs"] = ["guardrail.txt"]


class RuntimeEngineTests(unittest.TestCase):
    def _config(self, max_retries: int = 0, require_conditional: bool = False) -> dict:
        return {
            "runtime": {
                "storage_root": "runs",
                "max_retries": max_retries,
                "step_timeout_seconds": 5,
            },
            "hitl": {"mode": "blocking", "require_conditional": require_conditional},
        }

    def _spec(self, human_gate: str = "required") -> models.WorkflowSpec:
        return models.WorkflowSpec(
            module="bmm",
            workflow="prd",
            phase="Phase 2 Planning",
            quint="Deduction (L1)",
            telis="Tier 2 shards + progressive negotiation",
            validation="Template/schema validation",
            human=human_gate,
            evidence="L1",
            artifacts=["{output_folder}/prd.md"],
            scope="production",
            path="src/modules/bmm/workflows/2-plan-workflows/prd/workflow.md",
        )

    def test_blocking_gate_and_resume(self) -> None:
        tmp = _sandbox_root()
        spec = self._spec(human_gate="required")
        eng = engine.WorkflowEngine(self._config(), [spec], storage_root=tmp)
        manifest = eng.run("bmm", "prd")
        self.assertEqual(manifest["status"], "blocked")
        self.assertEqual(manifest.get("blocked_reason"), "human_gate")

        gates_payload = storage.read_human_gates(tmp / manifest["run_id"])
        self.assertEqual(len(gates_payload.get("gates", [])), 1)
        gate_entry = gates_payload["gates"][0]
        self.assertEqual(gate_entry.get("status"), "blocked")
        self.assertEqual(gate_entry.get("reason"), "explicit human gate")

        run_id = manifest["run_id"]
        eng.approve_gate(run_id, approved_by="tester")
        gates_payload = storage.read_human_gates(tmp / run_id)
        gate_entry = gates_payload["gates"][0]
        self.assertEqual(gate_entry.get("status"), "approved")
        self.assertEqual(gate_entry.get("approved_by"), "tester")
        resumed = eng.resume(run_id)
        self.assertEqual(resumed["status"], "completed")

    def test_retries_then_success(self) -> None:
        tmp = _sandbox_root()
        spec = self._spec(human_gate="optional")
        eng = engine.WorkflowEngine(self._config(max_retries=1), [spec], storage_root=tmp)
        manifest = eng.run("bmm", "prd", executor=FlakyExecutor())
        self.assertEqual(manifest["status"], "completed")
        self.assertEqual(manifest["steps"][0]["attempts"], 2)

    def test_step_retries_override_config(self) -> None:
        tmp = _sandbox_root()
        spec = self._spec(human_gate="optional")
        eng = engine.WorkflowEngine(self._config(max_retries=2), [spec], storage_root=tmp)
        created = eng.create_run("bmm", "prd")
        run_dir = tmp / created["run_id"]
        step_spec = models.StepSpec(
            id="step-1",
            name="retry",
            description="",
            phase=spec.phase,
            inputs={},
            outputs=["{output_folder}/prd.md"],
            templates=[],
            tools=[],
            validation=spec.validation,
            evidence=spec.evidence,
            human_gate=spec.human,
            retries={"max": 0, "backoff_seconds": 0},
        )
        manifest = storage.read_manifest(run_dir)
        manifest["step_specs"] = [step_spec.to_dict()]
        manifest["steps"] = []
        storage.write_manifest(run_dir, manifest)
        result = eng.run("bmm", "prd", run_id=created["run_id"], executor=FailingExecutor())
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["steps"][0]["attempts"], 1)

    def test_step_retry_backoff_applied(self) -> None:
        tmp = _sandbox_root()
        spec = self._spec(human_gate="optional")
        eng = engine.WorkflowEngine(self._config(max_retries=0), [spec], storage_root=tmp)
        created = eng.create_run("bmm", "prd")
        run_dir = tmp / created["run_id"]
        step_spec = models.StepSpec(
            id="step-1",
            name="backoff",
            description="",
            phase=spec.phase,
            inputs={},
            outputs=["{output_folder}/prd.md"],
            templates=[],
            tools=[],
            validation=spec.validation,
            evidence=spec.evidence,
            human_gate=spec.human,
            retries={"max": 1, "backoff_seconds": 5},
        )
        manifest = storage.read_manifest(run_dir)
        manifest["step_specs"] = [step_spec.to_dict()]
        manifest["steps"] = []
        storage.write_manifest(run_dir, manifest)
        calls = []
        original_sleep = engine.time.sleep
        engine.time.sleep = lambda seconds: calls.append(seconds)
        try:
            result = eng.run("bmm", "prd", run_id=created["run_id"], executor=FailingExecutor())
        finally:
            engine.time.sleep = original_sleep
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["steps"][0]["attempts"], 2)
        self.assertEqual(calls, [5])

    def test_automation_phase_blocks_manual(self) -> None:
        tmp = _sandbox_root()
        spec = self._spec(human_gate="optional")
        config = self._config()
        config["automation"] = {"phases": ["Phase 4 Implementation"]}
        eng = engine.WorkflowEngine(config, [spec], storage_root=tmp)
        manifest = eng.run("bmm", "prd")
        self.assertEqual(manifest["status"], "blocked")
        self.assertEqual(manifest.get("blocked_reason"), "manual_phase")

    def test_automation_phase_allows_configured(self) -> None:
        tmp = _sandbox_root()
        spec = self._spec(human_gate="optional")
        config = self._config()
        config["automation"] = {"phases": ["Phase 2 Planning"]}
        eng = engine.WorkflowEngine(config, [spec], storage_root=tmp)
        manifest = eng.run("bmm", "prd")
        self.assertEqual(manifest["status"], "completed")

    def test_guardrail_blocks_output_pii(self) -> None:
        tmp = _sandbox_root()
        spec = self._spec(human_gate="optional")
        config = self._config()
        config["guardrails"] = {
            "enabled": True,
            "stages": ["outputs"],
            "pii": {"enabled": True},
            "moderation": {"enabled": False},
            "rules": {"enabled": False},
        }
        eng = engine.WorkflowEngine(config, [spec], storage_root=tmp)
        created = eng.create_run("bmm", "prd")
        run_dir = tmp / created["run_id"]
        step_spec = models.StepSpec(
            id="step-1",
            name="guardrails",
            description="",
            phase=spec.phase,
            inputs={},
            outputs=["{output_folder}/prd.md"],
            templates=[],
            tools=[],
            validation=spec.validation,
            evidence=spec.evidence,
            human_gate=spec.human,
            retries={"max": 0, "backoff_seconds": 0},
        )
        manifest = storage.read_manifest(run_dir)
        manifest["step_specs"] = [step_spec.to_dict()]
        manifest["steps"] = []
        storage.write_manifest(run_dir, manifest)
        result = eng.run("bmm", "prd", run_id=created["run_id"], executor=GuardrailExecutor())
        self.assertEqual(result["status"], "failed")
        self.assertIn("guardrail failed", result["steps"][0]["error"])

    def test_load_mapping_records(self) -> None:
        tmp = _sandbox_root()
        mapping_path = tmp / "integration-mapping.json"
        payload = {
            "records": [
                {
                    "module": "bmm",
                    "workflow": "prd",
                    "phase": "Phase 2 Planning",
                    "quint": "Deduction (L1)",
                    "telis": "Tier 2 shards + progressive negotiation",
                    "validation": "Template/schema validation",
                    "human": "required",
                    "evidence": "L1",
                    "artifacts": ["{output_folder}/prd.md"],
                    "scope": "production",
                    "path": "src/modules/bmm/workflows/2-plan-workflows/prd/workflow.md",
                }
            ]
        }
        mapping_path.write_text(json.dumps(payload), encoding="ascii")
        records = engine.load_mapping_records(mapping_path)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].workflow, "prd")

    def test_failure_when_retries_exhausted(self) -> None:
        tmp = _sandbox_root()
        spec = self._spec(human_gate="optional")
        eng = engine.WorkflowEngine(self._config(max_retries=0), [spec], storage_root=tmp)
        manifest = eng.run("bmm", "prd", executor=FailingExecutor())
        self.assertEqual(manifest["status"], "failed")

    def test_create_run_and_resume_blocked(self) -> None:
        tmp = _sandbox_root()
        spec = self._spec(human_gate="required")
        eng = engine.WorkflowEngine(self._config(), [spec], storage_root=tmp)
        created = eng.create_run("bmm", "prd")
        run_id = created["run_id"]
        resumed = eng.resume(run_id)
        self.assertEqual(resumed["status"], "blocked")

    def test_default_mapping_path_loads(self) -> None:
        path = engine.default_mapping_path()
        self.assertTrue(path.name == "integration-mapping.json")
        records = engine.load_mapping_records(path)
        self.assertTrue(len(records) >= 1)

    def test_workflow_spec_missing(self) -> None:
        spec = self._spec(human_gate="optional")
        eng = engine.WorkflowEngine(self._config(), [spec])
        with self.assertRaises(KeyError):
            eng.get_workflow_spec("bmm", "missing")

    def test_run_with_existing_manifest(self) -> None:
        tmp = _sandbox_root()
        spec = self._spec(human_gate="optional")
        eng = engine.WorkflowEngine(self._config(), [spec], storage_root=tmp)
        created = eng.create_run("bmm", "prd")
        run_dir = tmp / created["run_id"]
        manifest = storage.read_manifest(run_dir)
        manifest["steps"] = []
        storage.write_manifest(run_dir, manifest)
        result = eng.run("bmm", "prd", run_id=created["run_id"])
        self.assertEqual(result["status"], "completed")
        self.assertTrue(result["steps"])

    def test_tool_pipeline_records_results(self) -> None:
        tmp = _sandbox_root()
        spec = self._spec(human_gate="optional")
        config = self._config()
        config["tools"] = {"allowlist": ["getCurrentTime"]}
        eng = engine.WorkflowEngine(config, [spec], storage_root=tmp)
        created = eng.create_run("bmm", "prd")
        run_dir = tmp / created["run_id"]
        manifest = storage.read_manifest(run_dir)
        step_spec = models.StepSpec(
            id="step-1",
            name="tool-step",
            description="",
            phase=spec.phase,
            inputs={},
            outputs=[],
            templates=[],
            tools=[{"name": "getCurrentTime", "args": {}, "required": True}],
            validation=spec.validation,
            evidence=spec.evidence,
            human_gate=spec.human,
            retries={"max": 0, "backoff_seconds": 0},
        )
        manifest["step_specs"] = [step_spec.to_dict()]
        manifest["steps"] = []
        storage.write_manifest(run_dir, manifest)
        result = eng.run("bmm", "prd", run_id=created["run_id"])
        self.assertEqual(result["status"], "completed")
        tool_results = storage.read_tool_results(run_dir)
        self.assertEqual(tool_results["results"][0]["name"], "getCurrentTime")

    def test_tool_pipeline_blocks_without_approval(self) -> None:
        tmp = _sandbox_root()
        spec = self._spec(human_gate="optional")
        config = self._config()
        config["tools"] = {
            "allowlist": ["writeTextFile"],
            "risk_policy": {"high_requires_approval": True},
        }
        eng = engine.WorkflowEngine(config, [spec], storage_root=tmp)
        created = eng.create_run("bmm", "prd")
        run_dir = tmp / created["run_id"]
        manifest = storage.read_manifest(run_dir)
        step_spec = models.StepSpec(
            id="step-1",
            name="tool-step",
            description="",
            phase=spec.phase,
            inputs={},
            outputs=[],
            templates=[],
            tools=[
                {
                    "name": "writeTextFile",
                    "args": {"path": "notes.txt", "content": "hi"},
                    "required": True,
                    "risk": "high",
                }
            ],
            validation=spec.validation,
            evidence=spec.evidence,
            human_gate=spec.human,
            retries={"max": 0, "backoff_seconds": 0},
        )
        manifest["step_specs"] = [step_spec.to_dict()]
        manifest["steps"] = []
        storage.write_manifest(run_dir, manifest)
        result = eng.run("bmm", "prd", run_id=created["run_id"])
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result.get("blocked_reason"), "tool_gate")

    def test_validation_gate_fails_on_invalid_target(self) -> None:
        tmp = _sandbox_root()
        bad_path = tmp / "bad.py"
        bad_path.write_text("def add(:\n    pass\n", encoding="utf-8")
        spec = self._spec(human_gate="optional")
        eng = engine.WorkflowEngine(self._config(max_retries=0), [spec], storage_root=tmp)
        created = eng.create_run("bmm", "prd")
        run_dir = tmp / created["run_id"]
        step_spec = models.StepSpec(
            id="step-1",
            name="validate",
            description="",
            phase=spec.phase,
            inputs={"validation_targets": [str(bad_path.relative_to(ROOT))]},
            outputs=["{output_folder}/prd.md"],
            templates=[],
            tools=[],
            validation="AST + type + lint (as applicable)",
            evidence=spec.evidence,
            human_gate=spec.human,
            retries={"max": 0, "backoff_seconds": 0},
        )
        manifest = storage.read_manifest(run_dir)
        manifest["step_specs"] = [step_spec.to_dict()]
        manifest["steps"] = []
        storage.write_manifest(run_dir, manifest)
        result = eng.run("bmm", "prd", run_id=created["run_id"])
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["steps"][0]["validation"]["status"], "failed")
        self.assertIn("validation failed", result["steps"][0]["error"])

    def test_output_layout_requires_placeholder(self) -> None:
        tmp = _sandbox_root()
        spec = self._spec(human_gate="optional")
        eng = engine.WorkflowEngine(self._config(max_retries=0), [spec], storage_root=tmp)
        created = eng.create_run("bmm", "prd")
        run_dir = tmp / created["run_id"]
        step_spec = models.StepSpec(
            id="step-1",
            name="layout",
            description="",
            phase=spec.phase,
            inputs={},
            outputs=["docs/prd.md"],
            templates=[],
            tools=[],
            validation="Format validation",
            evidence=spec.evidence,
            human_gate=spec.human,
            retries={"max": 0, "backoff_seconds": 0},
        )
        manifest = storage.read_manifest(run_dir)
        manifest["step_specs"] = [step_spec.to_dict()]
        manifest["steps"] = []
        storage.write_manifest(run_dir, manifest)
        result = eng.run("bmm", "prd", run_id=created["run_id"])
        self.assertEqual(result["status"], "failed")
        issues = result["steps"][0]["validation"]["issues"]
        self.assertTrue(any("output folder placeholder" in item for item in issues))

    def test_plugin_hooks_success(self) -> None:
        tmp = _sandbox_root()
        spec = self._spec(human_gate="optional")
        plugin = RecordingPlugin()
        manager = engine.PluginManager([plugin])
        eng = engine.WorkflowEngine(self._config(), [spec], storage_root=tmp, plugins=manager)
        manifest = eng.run("bmm", "prd")
        self.assertEqual(manifest["status"], "completed")
        self.assertEqual(plugin.events[0], "before_run")
        self.assertEqual(plugin.events[-1], "after_run")
        self.assertIn("validation:completed", plugin.events)
        self.assertGreaterEqual(plugin.events.count("before_step"), 1)
        self.assertEqual(
            plugin.events.count("before_step"),
            plugin.events.count("after_step"),
        )

    def test_plugin_hooks_failure(self) -> None:
        tmp = _sandbox_root()
        spec = self._spec(human_gate="optional")
        plugin = RecordingPlugin()
        manager = engine.PluginManager([plugin])
        eng = engine.WorkflowEngine(
            self._config(max_retries=0), [spec], storage_root=tmp, plugins=manager
        )
        manifest = eng.run("bmm", "prd", executor=FailingExecutor())
        self.assertEqual(manifest["status"], "failed")
        self.assertIn("on_error", plugin.events)
        self.assertIn("validation:failed", plugin.events)
        self.assertIn("after_run", plugin.events)

    def test_manifest_persisted_on_error(self) -> None:
        tmp = _sandbox_root()
        spec = self._spec(human_gate="optional")
        plugin = PersistingPlugin(tmp)
        manager = engine.PluginManager([plugin])
        eng = engine.WorkflowEngine(
            self._config(max_retries=1), [spec], storage_root=tmp, plugins=manager
        )
        manifest = eng.run("bmm", "prd", executor=FlakyExecutor())
        self.assertEqual(manifest["status"], "completed")
        self.assertIsNotNone(plugin.snapshot)
        self.assertEqual(plugin.snapshot["steps"][0]["status"], "failed")
        self.assertEqual(plugin.snapshot["steps"][0]["error"], "boom")

    def test_resume_starts_from_last_incomplete_step(self) -> None:
        tmp = _sandbox_root()
        spec = self._spec(human_gate="optional")
        eng = engine.WorkflowEngine(self._config(), [spec], storage_root=tmp)
        created = eng.create_run("bmm", "prd")
        run_dir = tmp / created["run_id"]
        step_specs = [
            models.StepSpec(
                id="step-1",
                name="one",
                description="",
                phase=spec.phase,
                inputs={},
                outputs=["{output_folder}/one.md"],
                templates=[],
                tools=[],
                validation=spec.validation,
                evidence=spec.evidence,
                human_gate=spec.human,
                retries={"max": 0, "backoff_seconds": 0},
            ),
            models.StepSpec(
                id="step-2",
                name="two",
                description="",
                phase=spec.phase,
                inputs={},
                outputs=["{output_folder}/two.md"],
                templates=[],
                tools=[],
                validation=spec.validation,
                evidence=spec.evidence,
                human_gate=spec.human,
                retries={"max": 0, "backoff_seconds": 0},
            ),
        ]
        manifest = storage.read_manifest(run_dir)
        manifest["step_specs"] = [spec_item.to_dict() for spec_item in step_specs]
        manifest["steps"] = [
            models.RunStep(name="one", status="completed", step_id="step-1").to_dict(),
            models.RunStep(name="two", step_id="step-2").to_dict(),
        ]
        storage.write_manifest(run_dir, manifest)
        executor = RecordingExecutor()
        resumed = eng.resume(created["run_id"], executor=executor)
        self.assertEqual(resumed["status"], "completed")
        self.assertEqual(executor.steps, ["two"])

    def test_step_state_machine_rejects_invalid_transition(self) -> None:
        step = {"name": "demo", "status": "pending"}
        with self.assertRaises(ValueError):
            engine._transition_step(step, "completed")

    def test_step_state_machine_allows_retry_or_resume(self) -> None:
        for status in ("failed", "blocked"):
            step = {"name": "demo", "status": status}
            engine._transition_step(step, "running")
            self.assertEqual(step["status"], "running")

    def test_timeout_failure(self) -> None:
        tmp = _sandbox_root()
        spec = self._spec(human_gate="optional")
        config = self._config(max_retries=0)
        config["runtime"]["step_timeout_seconds"] = 0
        eng = engine.WorkflowEngine(config, [spec], storage_root=tmp)
        manifest = eng.run("bmm", "prd", executor=TimeoutExecutor())
        self.assertEqual(manifest["status"], "failed")
        self.assertEqual(manifest["steps"][0]["error"], "step timeout")

    def test_step_specs_fallback_outputs(self) -> None:
        root = _sandbox_root()
        wf_dir = root / "BMAD-METHOD" / "src" / "modules" / "sample" / "workflows" / "demo"
        wf_dir.mkdir(parents=True, exist_ok=True)
        workflow_path = wf_dir / "workflow.md"
        workflow_path.write_text('<step n="1" goal="One"></step>', encoding="ascii")
        spec = models.WorkflowSpec(
            module="sample",
            workflow="demo",
            phase="Phase 1 Analysis",
            quint="Deduction (L1)",
            telis="Tier 2 shards + progressive negotiation",
            validation="Template/schema validation",
            human="optional",
            evidence="L1",
            artifacts=["{output_folder}/demo.md"],
            scope="production",
            path="src/modules/sample/workflows/demo/workflow.md",
        )
        original = runtime_config.project_root_from_here
        runtime_config.project_root_from_here = lambda: root
        try:
            steps = engine._step_specs_for_workflow(spec, self._config())
        finally:
            runtime_config.project_root_from_here = original
        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0].outputs, ["{output_folder}/demo.md"])

    def test_step_specs_preserve_step_outputs(self) -> None:
        root = _sandbox_root()
        wf_dir = root / "BMAD-METHOD" / "src" / "modules" / "sample" / "workflows" / "demo"
        steps_dir = wf_dir / "steps"
        steps_dir.mkdir(parents=True, exist_ok=True)
        (steps_dir / "step-01-init.md").write_text(
            "output_file: {output_folder}/step.md",
            encoding="ascii",
        )
        workflow_path = wf_dir / "workflow.md"
        workflow_path.write_text("# Demo", encoding="ascii")
        spec = models.WorkflowSpec(
            module="sample",
            workflow="demo",
            phase="Phase 1 Analysis",
            quint="Deduction (L1)",
            telis="Tier 2 shards + progressive negotiation",
            validation="Template/schema validation",
            human="optional",
            evidence="L1",
            artifacts=["{output_folder}/workflow.md"],
            scope="production",
            path="src/modules/sample/workflows/demo/workflow.md",
        )
        original = runtime_config.project_root_from_here
        runtime_config.project_root_from_here = lambda: root
        try:
            steps = engine._step_specs_for_workflow(spec, self._config())
        finally:
            runtime_config.project_root_from_here = original
        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0].outputs, ["{output_folder}/step.md"])


if __name__ == "__main__":
    unittest.main()
