"""Live full lifecycle E2E test using BMAD assets with TELIS + QUINT (env-gated)."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import unittest
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import engine, storage  # noqa: E402
from runtime.providers.base import Provider, ProviderError, ProviderRequest  # noqa: E402
from runtime.providers.registry import ProviderRegistry  # noqa: E402
from runtime.quint import store as quint_store  # noqa: E402
from runtime.telis import BehavioralCache, TelisPolicyEngine, shards  # noqa: E402

_PROVIDER_CONFIGS = {
    "openai": {
        "type": "openai",
        "model": os.environ.get("BAQT_LIVE_MODEL", "gpt-4o-mini"),
        "api_key_env": "OPENAI_API_KEY",
    },
    "claude": {
        "type": "anthropic",
        "model": os.environ.get("BAQT_LIVE_MODEL", "claude-4"),
        "api_key_env": "ANTHROPIC_API_KEY",
    },
    "anthropic": {
        "type": "anthropic",
        "model": os.environ.get("BAQT_LIVE_MODEL", "claude-4"),
        "api_key_env": "ANTHROPIC_API_KEY",
    },
    "gemini": {
        "type": "gemini",
        "model": os.environ.get("BAQT_LIVE_MODEL", "gemini-3-flash-preview"),
        "api_key_env": "GEMINI_API_KEY",
    },
    "groq": {
        "type": "groq",
        "model": os.environ.get("BAQT_LIVE_MODEL", "llama3-8b-8192"),
        "api_key_env": "GROQ_API_KEY",
    },
    "litellm": {
        "type": "litellm",
        "model": os.environ.get("BAQT_LIVE_MODEL", "gpt-4o-mini"),
        "base_url": os.environ.get("BAQT_LIVE_BASE_URL", "http://localhost:4000"),
    },
    "ollama": {
        "type": "ollama",
        "model": os.environ.get("BAQT_LIVE_MODEL", "llama3"),
        "base_url": os.environ.get("BAQT_LIVE_BASE_URL", "http://localhost:11434"),
    },
    "mock": {
        "type": "mock",
        "model": "mock",
    },
}


def _ascii(text: str) -> str:
    return text.encode("ascii", "ignore").decode("ascii")


def _run_pytest(project_dir: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_dir)
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=project_dir,
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
        check=False,
    )


def _inject_telis_inputs(
    run_dir: Path,
    query: str,
    language: str,
    document_path: str | None = None,
) -> None:
    manifest = storage.read_manifest(run_dir)
    step_specs = manifest.get("step_specs", [])
    steps = manifest.get("steps", [])
    for spec in step_specs:
        inputs = dict(spec.get("inputs", {}) or {})
        inputs["telis_query"] = query
        inputs["telis_language"] = language
        if document_path:
            inputs["telis_document_path"] = document_path
        spec["inputs"] = inputs
    for step in steps:
        inputs = dict(step.get("inputs", {}) or {})
        inputs["telis_query"] = query
        inputs["telis_language"] = language
        if document_path:
            inputs["telis_document_path"] = document_path
        step["inputs"] = inputs
    manifest["step_specs"] = step_specs
    manifest["steps"] = steps
    storage.write_manifest(run_dir, manifest)


@dataclass(frozen=True)
class WorkflowArtifact:
    template_path: Path | None
    output_name: str


class BmadTemplateExecutor(engine.StepExecutor):
    """Executor that fills BMAD templates once per workflow."""

    def __init__(self, provider: Provider | None, idea: str, artifacts: dict[str, WorkflowArtifact]) -> None:
        self.provider = provider
        self.idea = idea
        self.artifacts = artifacts
        self.generated: set[str] = set()

    def execute(self, step: dict, context: dict) -> None:
        manifest = context["manifest"]
        workflow = manifest.get("workflow", {})
        key = f"{workflow.get('module')}/{workflow.get('workflow')}"
        if key in self.generated:
            return
        self.generated.add(key)

        artifact = self.artifacts.get(key)
        if not artifact:
            return
        run_dir = Path(context["run_dir"])
        output_dir = run_dir / "outputs"
        output_path = output_dir / artifact.output_name
        output_path.parent.mkdir(parents=True, exist_ok=True)

        template_text = ""
        if artifact.template_path and artifact.template_path.exists():
            template_text = artifact.template_path.read_text(encoding="utf-8", errors="ignore")
        prompt = (
            "Use ASCII only.\n"
            f"Idea: {self.idea}\n"
            f"Workflow: {key}\n"
            "Fill in the template with concise, actionable content.\n"
            "Return full markdown only.\n\n"
            f"{template_text}"
        )
        response_text = ""
        if self.provider:
            response = self.provider.invoke(
                ProviderRequest(model="", messages=[{"role": "user", "content": prompt}])
            )
            response_text = response.content or ""
        content = _ascii(response_text.strip())
        if not content:
            content = _ascii(f"# {key}\n\nIdea: {self.idea}\n")

        output_path.write_text(content, encoding="ascii")
        rel_path = str(output_path.relative_to(run_dir)).replace("\\", "/")
        outputs = list(step.get("outputs", []))
        if rel_path not in outputs:
            outputs.append(rel_path)
        step["outputs"] = outputs

        evidence_level = str(workflow.get("evidence", "L0") or "L0")
        store = quint_store.EvidenceStore(run_dir)
        link = quint_store.build_evidence_link(
            claim=f"Generated {key} document",
            level=evidence_level,
            source="e2e-lifecycle",
            carrier_ref=rel_path,
            artifacts=[rel_path],
        )
        store.record(link)


class DevStoryExecutor(engine.StepExecutor):
    """Executor that implements a dev-story with a red/green QA loop."""

    def __init__(
        self,
        provider: Provider | None,
        story_path: Path,
        project_dir: Path,
        model_name: str,
    ) -> None:
        self.provider = provider
        self.story_path = story_path
        self.project_dir = project_dir
        self.model_name = model_name
        self.completed = False

    def execute(self, step: dict, context: dict) -> None:
        if self.completed:
            return
        self.completed = True
        run_dir = Path(context["run_dir"])
        output_dir = run_dir / "outputs"
        output_dir.mkdir(parents=True, exist_ok=True)

        self.project_dir.mkdir(parents=True, exist_ok=True)
        tests_dir = self.project_dir / "tests"
        tests_dir.mkdir(parents=True, exist_ok=True)

        test_path = tests_dir / "test_habit_tracker.py"
        # Use tempfile.mkdtemp instead of tmp_path fixture to avoid Windows permission issues
        # when running pytest as a subprocess from within another pytest session
        test_path.write_text(
            _ascii(
                "\n".join(
                    [
                        "import tempfile",
                        "import shutil",
                        "from habit_tracker import add_habit, log_completion, weekly_summary",
                        "",
                        "",
                        "def test_weekly_summary():",
                        "    tmp_dir = tempfile.mkdtemp()",
                        "    try:",
                        "        data_path = tmp_dir + \"/habits.json\"",
                        "        add_habit(data_path, \"read\")",
                        "        log_completion(data_path, \"read\", \"2026-01-05\")",
                        "        log_completion(data_path, \"read\", \"2026-01-07\")",
                        "        summary = weekly_summary(data_path, \"2026-01-05\")",
                        "        assert summary[\"read\"] == 2",
                        "    finally:",
                        "        shutil.rmtree(tmp_dir, ignore_errors=True)",
                        "",
                        "",
                        "def test_summary_empty():",
                        "    tmp_dir = tempfile.mkdtemp()",
                        "    try:",
                        "        data_path = tmp_dir + \"/habits.json\"",
                        "        add_habit(data_path, \"exercise\")",
                        "        summary = weekly_summary(data_path, \"2026-01-05\")",
                        "        assert summary.get(\"exercise\", 0) == 0",
                        "    finally:",
                        "        shutil.rmtree(tmp_dir, ignore_errors=True)",
                    ]
                )
            ),
            encoding="ascii",
        )

        red_run = _run_pytest(self.project_dir)
        if red_run.returncode == 0:
            raise AssertionError("Expected failing tests before implementation.")

        code_path = self.project_dir / "habit_tracker.py"
        code_path.write_text(
            _ascii(
                "\n".join(
                    [
                        "import json",
                        "from datetime import datetime, timedelta",
                        "",
                        "",
                        "def _load(path):",
                        "    try:",
                        "        with open(path, \"r\", encoding=\"utf-8\") as handle:",
                        "            return json.load(handle)",
                        "    except FileNotFoundError:",
                        "        return {\"habits\": [], \"logs\": []}",
                        "",
                        "",
                        "def _save(path, payload):",
                        "    with open(path, \"w\", encoding=\"utf-8\") as handle:",
                        "        json.dump(payload, handle, indent=2, sort_keys=True)",
                        "",
                        "",
                        "def add_habit(path, name):",
                        "    payload = _load(path)",
                        "    if name not in payload[\"habits\"]:",
                        "        payload[\"habits\"].append(name)",
                        "    _save(path, payload)",
                        "",
                        "",
                        "def log_completion(path, name, date_str):",
                        "    payload = _load(path)",
                        "    if name not in payload[\"habits\"]:",
                        "        payload[\"habits\"].append(name)",
                        "    payload[\"logs\"].append({\"habit\": name, \"date\": date_str})",
                        "    _save(path, payload)",
                        "",
                        "",
                        "def weekly_summary(path, week_start):",
                        "    payload = _load(path)",
                        "    start = datetime.strptime(week_start, \"%Y-%m-%d\").date()",
                        "    end = start + timedelta(days=7)",
                        "    summary = {name: 0 for name in payload[\"habits\"]}",
                        "    for log in payload[\"logs\"]:",
                        "        logged = datetime.strptime(log[\"date\"], \"%Y-%m-%d\").date()",
                        "        if start <= logged < end:",
                        "            summary[log[\"habit\"]] = summary.get(log[\"habit\"], 0) + 1",
                        "    return summary",
                    ]
                )
            ),
            encoding="ascii",
        )

        green_run = _run_pytest(self.project_dir)
        if green_run.returncode != 0:
            raise AssertionError(f"Tests still failing after implementation:\n{green_run.stdout}\n{green_run.stderr}")

        qa_log = output_dir / "qa-log.txt"
        qa_log.write_text(
            _ascii(
                "\n".join(
                    [
                        "RED RUN (expected failure)",
                        red_run.stdout.strip(),
                        red_run.stderr.strip(),
                        "",
                        "GREEN RUN (expected pass)",
                        green_run.stdout.strip(),
                        green_run.stderr.strip(),
                    ]
                )
            ),
            encoding="ascii",
        )

        plan_note = ""
        if self.provider:
            prompt = (
                "Use ASCII only.\n"
                "Create a short implementation note for a CLI habit tracker story.\n"
                "Mention red/green testing and weekly summary logic.\n"
            )
            response = self.provider.invoke(
                ProviderRequest(model="", messages=[{"role": "user", "content": prompt}])
            )
            plan_note = _ascii(response.content.strip())

        summary_path = output_dir / "final-product.md"
        summary_path.write_text(
            _ascii(
                "\n".join(
                    [
                        "# Habit Tracker CLI",
                        "",
                        "Implemented a minimal habit tracker with weekly summaries.",
                        "",
                        "## Features",
                        "- Add habits and log completions",
                        "- Weekly summary counts per habit",
                        "- JSON storage using the standard library",
                        "",
                        "## QA Loop",
                        "- Tests written first (red)",
                        "- Implementation added (green)",
                        "",
                        "## Notes",
                        plan_note or "Plan note unavailable.",
                    ]
                )
            ),
            encoding="ascii",
        )

        self._update_story_file(
            qa_log=qa_log,
            files=[
                str(code_path.relative_to(self.project_dir)),
                str(test_path.relative_to(self.project_dir)),
            ],
            completion_note=plan_note,
        )

        rel_summary = str(summary_path.relative_to(run_dir)).replace("\\", "/")
        rel_log = str(qa_log.relative_to(run_dir)).replace("\\", "/")
        outputs = list(step.get("outputs", []))
        for rel in (rel_summary, rel_log):
            if rel not in outputs:
                outputs.append(rel)
        step["outputs"] = outputs

        workflow = context["manifest"].get("workflow", {})
        evidence_level = str(workflow.get("evidence", "L2") or "L2")
        store = quint_store.EvidenceStore(run_dir)
        link = quint_store.build_evidence_link(
            claim="Dev-story implemented with passing tests",
            level=evidence_level,
            source="e2e-lifecycle",
            carrier_ref=rel_summary,
            artifacts=[rel_summary, rel_log],
        )
        store.record(link)

    def _update_story_file(
        self,
        qa_log: Path,
        files: list[str],
        completion_note: str,
    ) -> None:
        text = self.story_path.read_text(encoding="ascii")
        text = text.replace("Status: ready-for-dev", "Status: review")
        text = re.sub(r"^- \\[ \\]", "- [x]", text, flags=re.MULTILINE)

        text = self._append_section(
            text,
            "### Completion Notes List",
            "- Implemented habit tracker with weekly summaries.",
            "- Tests added and passing via pytest.",
            f"- QA log: {qa_log.name}",
            f"- Plan note: {completion_note}" if completion_note else "- Plan note: n/a",
        )
        text = self._append_section(
            text,
            "### File List",
            *[f"- {name}" for name in files],
        )
        text = self._append_section(
            text,
            "### Change Log",
            "- Added habit tracker implementation and tests.",
        )
        self.story_path.write_text(text, encoding="ascii")

    @staticmethod
    def _append_section(text: str, header: str, *lines: str) -> str:
        marker = f"{header}\n"
        if marker not in text:
            return text
        insert = "\n".join(lines).strip()
        if not insert:
            return text
        before, after = text.split(marker, 1)
        if after.startswith("\n"):
            after = after[1:]
        return f"{before}{marker}{insert}\n\n{after}"


class FullLifecycleLiveTests(unittest.TestCase):
    """Exercise analysis -> planning -> solutioning -> implementation end-to-end."""

    def setUp(self) -> None:
        if os.environ.get("BAQT_LIVE_E2E") != "1":
            self.skipTest("BAQT_LIVE_E2E not set")
        self.provider_name = os.environ.get("BAQT_LIVE_PROVIDER", "").strip().lower()
        if not self.provider_name:
            self.skipTest("BAQT_LIVE_PROVIDER not set")
        if self.provider_name not in _PROVIDER_CONFIGS:
            self.skipTest(f"Unsupported provider: {self.provider_name}")

        provider_cfg = dict(_PROVIDER_CONFIGS[self.provider_name])
        required_env = provider_cfg.get("api_key_env")
        if required_env and not os.environ.get(required_env):
            self.skipTest(f"Missing required env var: {required_env}")

        self.sandbox = ROOT / "runs" / "tmp-tests" / uuid4().hex
        self.sandbox.mkdir(parents=True, exist_ok=True)
        self.workspace = self.sandbox / "workspace"
        self.workspace.mkdir(parents=True, exist_ok=True)

        self.config = {
            "runtime": {
                "storage_root": str(self.sandbox),
                "max_retries": 0,
                "step_timeout_seconds": 120,
            },
            "automation": {"override": True},
            "hitl": {"mode": "disabled"},
            "providers": {
                "default": self.provider_name,
                self.provider_name: provider_cfg,
            },
        }

        registry = ProviderRegistry(self.config)
        try:
            self.provider = registry.get(self.provider_name)
        except ProviderError as exc:
            self.skipTest(str(exc))

        self.idea = "A command-line habit tracker with weekly summaries."

        telis_registry = shards.ShardRegistry()
        telis_registry.add(
            shards.Shard(
                shard_id="md.lifecycle",
                language="markdown",
                version="1.0",
                tier="tier_1_nano",
                topics=["requirements", "templates"],
                tokens=40,
                content="Use clear headings, bullet lists, and concise acceptance criteria.",
            )
        )
        telis_registry.add(
            shards.Shard(
                shard_id="py.testing",
                language="python",
                version="3.11",
                tier="tier_2_micro",
                topics=["pytest", "testing"],
                tokens=80,
                content="Write pytest tests first, then implement minimal code to pass.",
            )
        )
        telis_engine = TelisPolicyEngine(registry=telis_registry, cache=BehavioralCache(ttl_seconds=60))

        mapping = engine.load_mapping_records()
        self.engine = engine.WorkflowEngine(
            self.config,
            mapping,
            storage_root=self.sandbox,
            telis=telis_engine,
        )

    def tearDown(self) -> None:
        if os.environ.get("BAQT_LIVE_KEEP_RUNS") == "1":
            return
        if hasattr(self, "sandbox") and self.sandbox.exists():
            shutil.rmtree(self.sandbox, ignore_errors=True)

    def test_full_lifecycle(self) -> None:
        templates = {
            "core/brainstorming": WorkflowArtifact(
                ROOT / "BMAD-METHOD" / "src" / "core" / "workflows" / "brainstorming" / "template.md",
                "analysis/brainstorming.md",
            ),
            "bmm/create-product-brief": WorkflowArtifact(
                ROOT
                / "BMAD-METHOD"
                / "src"
                / "modules"
                / "bmm"
                / "workflows"
                / "1-analysis"
                / "create-product-brief"
                / "product-brief.template.md",
                "analysis/product-brief.md",
            ),
            "bmm/prd": WorkflowArtifact(
                ROOT
                / "BMAD-METHOD"
                / "src"
                / "modules"
                / "bmm"
                / "workflows"
                / "2-plan-workflows"
                / "prd"
                / "prd-template.md",
                "planning/prd.md",
            ),
            "bmm/create-ux-design": WorkflowArtifact(
                ROOT
                / "BMAD-METHOD"
                / "src"
                / "modules"
                / "bmm"
                / "workflows"
                / "2-plan-workflows"
                / "create-ux-design"
                / "ux-design-template.md",
                "planning/ux-design.md",
            ),
            "bmm/create-architecture": WorkflowArtifact(
                ROOT
                / "BMAD-METHOD"
                / "src"
                / "modules"
                / "bmm"
                / "workflows"
                / "3-solutioning"
                / "create-architecture"
                / "architecture-decision-template.md",
                "solutioning/architecture.md",
            ),
            "bmm/create-epics-and-stories": WorkflowArtifact(
                ROOT
                / "BMAD-METHOD"
                / "src"
                / "modules"
                / "bmm"
                / "workflows"
                / "3-solutioning"
                / "create-epics-and-stories"
                / "templates"
                / "epics-template.md",
                "solutioning/epics.md",
            ),
        }

        doc_executor = BmadTemplateExecutor(self.provider, self.idea, templates)

        analysis_runs = [
            ("core", "brainstorming"),
            ("bmm", "create-product-brief"),
        ]
        planning_runs = [
            ("bmm", "prd"),
            ("bmm", "create-ux-design"),
        ]
        solutioning_runs = [
            ("bmm", "create-architecture"),
            ("bmm", "create-epics-and-stories"),
        ]

        for module, workflow in analysis_runs + planning_runs + solutioning_runs:
            run_dir = self._run_workflow(
                module,
                workflow,
                executor=doc_executor,
                telis_query=self.idea,
                telis_language="markdown",
            )
            self._assert_telis_quint(run_dir)

        story_path = self._write_story_file()
        project_dir = self.workspace / "habit-tracker"
        code_path = project_dir / "habit_tracker.py"
        code_path.parent.mkdir(parents=True, exist_ok=True)
        code_path.write_text("# stub for TELIS\n", encoding="ascii")

        rel_code_path = str(code_path.relative_to(ROOT)).replace("\\", "/")
        dev_executor = DevStoryExecutor(
            self.provider,
            story_path=story_path,
            project_dir=project_dir,
            model_name=str(_PROVIDER_CONFIGS[self.provider_name].get("model", "")),
        )
        run_dir = self._run_workflow(
            "bmm",
            "dev-story",
            executor=dev_executor,
            telis_query="habit tracker implementation",
            telis_language="python",
            telis_document_path=rel_code_path,
        )

        summary_path = run_dir / "outputs" / "final-product.md"
        self.assertTrue(summary_path.exists())
        self.assertIn("Habit Tracker", summary_path.read_text(encoding="ascii"))
        self.assertIn("Status: review", story_path.read_text(encoding="ascii"))
        self._assert_telis_quint(run_dir)

    def _run_workflow(
        self,
        module: str,
        workflow: str,
        executor: engine.StepExecutor,
        telis_query: str,
        telis_language: str,
        telis_document_path: str | None = None,
    ) -> Path:
        manifest = self.engine.create_run(module, workflow)
        run_dir = self.sandbox / manifest["run_id"]
        _inject_telis_inputs(
            run_dir,
            query=telis_query,
            language=telis_language,
            document_path=telis_document_path,
        )
        result = self.engine.run(
            module,
            workflow,
            run_id=manifest["run_id"],
            executor=executor,
            agent_name="bmad",
        )
        if result.get("status") != "completed":
            raise AssertionError(f"Workflow {module}/{workflow} failed: {result}")
        return run_dir

    def _assert_telis_quint(self, run_dir: Path) -> None:
        fingerprints = storage.read_json(run_dir / "context-fingerprints.json")
        self.assertTrue(fingerprints.get("fingerprints"))
        snapshots = storage.read_json(run_dir / "context-snapshots.json")
        self.assertTrue(snapshots.get("snapshots"))
        evidence = storage.read_evidence_links(run_dir)
        self.assertTrue(evidence.get("evidence"))

    def _write_story_file(self) -> Path:
        story_dir = self.workspace / "_bmad" / "bmm" / "sprint_artifacts"
        story_dir.mkdir(parents=True, exist_ok=True)
        story_path = story_dir / "1-1-habit-tracker.md"
        story_path.write_text(
            _ascii(
                "\n".join(
                    [
                        "# Story 1.1: Habit Tracker CLI",
                        "",
                        "Status: ready-for-dev",
                        "",
                        "## Story",
                        "",
                        "As a user,",
                        "I want to track habits from the command line,",
                        "so that I can see weekly progress summaries.",
                        "",
                        "## Acceptance Criteria",
                        "",
                        "1. Add habits and log completions.",
                        "2. Generate weekly summaries per habit.",
                        "",
                        "## Tasks / Subtasks",
                        "",
                        "- [ ] Implement habit storage and CLI entry points (AC: 1)",
                        "  - [ ] Add habits to JSON store",
                        "  - [ ] Log habit completions",
                        "- [ ] Implement weekly summary logic (AC: 2)",
                        "  - [ ] Count completions by week",
                        "- [ ] Add pytest coverage for summary behavior (AC: 1, 2)",
                        "",
                        "## Dev Notes",
                        "",
                        "- Use standard library only.",
                        "- Keep data in a JSON file.",
                        "- Tests should use pytest and tmp_path.",
                        "",
                        "## Dev Agent Record",
                        "",
                        "### Agent Model Used",
                        "",
                        self._model_line(),
                        "",
                        "### Debug Log References",
                        "",
                        "### Completion Notes List",
                        "",
                        "### File List",
                        "",
                        "### Change Log",
                        "",
                    ]
                )
            ),
            encoding="ascii",
        )
        return story_path

    def _model_line(self) -> str:
        model = str(_PROVIDER_CONFIGS[self.provider_name].get("model", ""))
        return model or "unknown-model"


if __name__ == "__main__":
    unittest.main()
