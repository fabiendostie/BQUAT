"""Full greenfield pipeline test: interactive steps 1-4, autonomous steps 5-7.

This integration test exercises the complete BMAD workflow from ideation to product:
- Steps 1-4 (brainstorming, product-brief, prd, ux-design): Interactive with BMAD
- Steps 5-7 (architecture, epics-and-stories, dev-story): Autonomous execution

Requires environment variables:
- BAQT_LIVE_E2E=1: Enable live E2E testing
- BAQT_LIVE_PROVIDER=gemini: Provider to use (gemini, anthropic, openai, etc.)
- GEMINI_API_KEY (or appropriate key for chosen provider)

Optional:
- BAQT_LIVE_KEEP_RUNS=1: Keep run artifacts for inspection
- BAQT_LIVE_MODEL: Override default model for provider
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cli import interactive as cli_interactive  # noqa: E402
from cli.interactive import InteractiveCLI  # noqa: E402
from runtime import engine, step_executor, storage  # noqa: E402
from runtime.providers.base import Provider, ProviderError, ProviderRequest  # noqa: E402
from runtime.providers.registry import ProviderRegistry  # noqa: E402
from runtime.quint import store as quint_store  # noqa: E402
from runtime.telis import BehavioralCache, TelisPolicyEngine, shards  # noqa: E402

_PROVIDER_CONFIGS = {
    "gemini": {
        "type": "gemini",
        "model": os.environ.get("BAQT_LIVE_MODEL", "gemini-2.0-flash"),
        "api_key_env": "GEMINI_API_KEY",
    },
    "anthropic": {
        "type": "anthropic",
        "model": os.environ.get("BAQT_LIVE_MODEL", "claude-sonnet-4-20250514"),
        "api_key_env": "ANTHROPIC_API_KEY",
    },
    "openai": {
        "type": "openai",
        "model": os.environ.get("BAQT_LIVE_MODEL", "gpt-4o-mini"),
        "api_key_env": "OPENAI_API_KEY",
    },
    "ollama": {
        "type": "ollama",
        "model": os.environ.get("BAQT_LIVE_MODEL", "llama3"),
        "base_url": os.environ.get("BAQT_LIVE_BASE_URL", "http://localhost:11434"),
        "timeout_seconds": 300,  # Local LLMs need more time
    },
    "mock": {
        "type": "mock",
        "model": "mock",
    },
}

SAMPLE_IDEA = "A command-line habit tracker with weekly summaries. Users can add habits, log daily completions, and see weekly progress reports."


def _ascii(text: str) -> str:
    """Convert text to ASCII-safe string."""
    return text.encode("ascii", "ignore").decode("ascii")


def _run_pytest(project_dir: Path) -> subprocess.CompletedProcess[str]:
    """Run pytest in a project directory."""
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


class InteractiveInputProvider:
    """Simulates interactive user input for test automation."""

    def __init__(self, idea: str, responses: Optional[List[str]] = None) -> None:
        self.idea = idea
        self.responses = responses or []
        self.call_count = 0

    def __call__(self, prompt: str) -> str:
        """Return appropriate response based on prompt context."""
        self.call_count += 1

        # First call typically asks for the main idea
        if self.call_count == 1:
            return self.idea

        # Subsequent calls use provided responses or defaults
        if self.responses and self.call_count - 2 < len(self.responses):
            return self.responses[self.call_count - 2]

        # Default: proceed to next step
        lower_prompt = prompt.lower()
        if "continue" in lower_prompt or "another" in lower_prompt:
            return "n"
        if "skip" in lower_prompt or "quit" in lower_prompt:
            return "next"
        return "done"


def _inject_telis_inputs(
    run_dir: Path,
    query: str,
    language: str,
    document_path: Optional[str] = None,
) -> None:
    """Inject TELIS context inputs into manifest."""
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
    """Defines expected artifact for a workflow."""

    template_path: Optional[Path]
    output_name: str


class BmadTemplateExecutor(engine.StepExecutor):
    """Executor that fills BMAD templates using LLM."""

    def __init__(
        self,
        provider: Optional[Provider],
        idea: str,
        artifacts: Dict[str, WorkflowArtifact],
    ) -> None:
        self.provider = provider
        self.idea = idea
        self.artifacts = artifacts
        self.generated: set[str] = set()

    def execute(self, step: Dict[str, Any], context: Dict[str, Any]) -> None:
        """Execute step by filling template with LLM."""
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

        # Record QUINT evidence
        evidence_level = str(workflow.get("evidence", "L0") or "L0")
        store = quint_store.EvidenceStore(run_dir)
        link = quint_store.build_evidence_link(
            claim=f"Generated {key} document",
            level=evidence_level,
            source="greenfield-pipeline",
            carrier_ref=rel_path,
            artifacts=[rel_path],
        )
        store.record(link)


class DevStoryExecutor(engine.StepExecutor):
    """Executor that implements a dev-story with red/green TDD loop."""

    def __init__(
        self,
        provider: Optional[Provider],
        story_path: Path,
        project_dir: Path,
        model_name: str,
    ) -> None:
        self.provider = provider
        self.story_path = story_path
        self.project_dir = project_dir
        self.model_name = model_name
        self.completed = False

    def execute(self, step: Dict[str, Any], context: Dict[str, Any]) -> None:
        """Execute dev-story with red/green TDD."""
        if self.completed:
            return
        self.completed = True

        run_dir = Path(context["run_dir"])
        output_dir = run_dir / "outputs"
        output_dir.mkdir(parents=True, exist_ok=True)

        self.project_dir.mkdir(parents=True, exist_ok=True)
        tests_dir = self.project_dir / "tests"
        tests_dir.mkdir(parents=True, exist_ok=True)

        # Write test file first (red phase)
        # Use tempfile.mkdtemp instead of tmp_path fixture to avoid Windows permission issues
        # when running pytest as a subprocess from within another pytest session
        test_path = tests_dir / "test_habit_tracker.py"
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
                        '    tmp_dir = tempfile.mkdtemp()',
                        "    try:",
                        '        data_path = tmp_dir + "/habits.json"',
                        '        add_habit(data_path, "read")',
                        '        log_completion(data_path, "read", "2026-01-05")',
                        '        log_completion(data_path, "read", "2026-01-07")',
                        '        summary = weekly_summary(data_path, "2026-01-05")',
                        '        assert summary["read"] == 2',
                        "    finally:",
                        "        shutil.rmtree(tmp_dir, ignore_errors=True)",
                        "",
                        "",
                        "def test_summary_empty():",
                        '    tmp_dir = tempfile.mkdtemp()',
                        "    try:",
                        '        data_path = tmp_dir + "/habits.json"',
                        '        add_habit(data_path, "exercise")',
                        '        summary = weekly_summary(data_path, "2026-01-05")',
                        '        assert summary.get("exercise", 0) == 0',
                        "    finally:",
                        "        shutil.rmtree(tmp_dir, ignore_errors=True)",
                    ]
                )
            ),
            encoding="ascii",
        )

        # Verify red phase (tests should fail)
        red_run = _run_pytest(self.project_dir)
        if red_run.returncode == 0:
            raise AssertionError("Expected failing tests before implementation.")

        # Write implementation (green phase)
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
                        '        with open(path, "r", encoding="utf-8") as handle:',
                        "            return json.load(handle)",
                        "    except FileNotFoundError:",
                        '        return {"habits": [], "logs": []}',
                        "",
                        "",
                        "def _save(path, payload):",
                        '    with open(path, "w", encoding="utf-8") as handle:',
                        "        json.dump(payload, handle, indent=2, sort_keys=True)",
                        "",
                        "",
                        "def add_habit(path, name):",
                        "    payload = _load(path)",
                        '    if name not in payload["habits"]:',
                        '        payload["habits"].append(name)',
                        "    _save(path, payload)",
                        "",
                        "",
                        "def log_completion(path, name, date_str):",
                        "    payload = _load(path)",
                        '    if name not in payload["habits"]:',
                        '        payload["habits"].append(name)',
                        '    payload["logs"].append({"habit": name, "date": date_str})',
                        "    _save(path, payload)",
                        "",
                        "",
                        "def weekly_summary(path, week_start):",
                        "    payload = _load(path)",
                        '    start = datetime.strptime(week_start, "%Y-%m-%d").date()',
                        "    end = start + timedelta(days=7)",
                        '    summary = {name: 0 for name in payload["habits"]}',
                        '    for log in payload["logs"]:',
                        '        logged = datetime.strptime(log["date"], "%Y-%m-%d").date()',
                        "        if start <= logged < end:",
                        '            summary[log["habit"]] = summary.get(log["habit"], 0) + 1',
                        "    return summary",
                    ]
                )
            ),
            encoding="ascii",
        )

        # Verify green phase (tests should pass)
        green_run = _run_pytest(self.project_dir)
        if green_run.returncode != 0:
            raise AssertionError(
                f"Tests still failing after implementation:\n{green_run.stdout}\n{green_run.stderr}"
            )

        # Write QA log
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

        # Generate implementation note via LLM
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

        # Write final product summary
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

        # Update story file status
        self._update_story_file(
            qa_log=qa_log,
            files=[
                str(code_path.relative_to(self.project_dir)),
                str(test_path.relative_to(self.project_dir)),
            ],
            completion_note=plan_note,
        )

        # Update step outputs
        rel_summary = str(summary_path.relative_to(run_dir)).replace("\\", "/")
        rel_log = str(qa_log.relative_to(run_dir)).replace("\\", "/")
        outputs = list(step.get("outputs", []))
        for rel in (rel_summary, rel_log):
            if rel not in outputs:
                outputs.append(rel)
        step["outputs"] = outputs

        # Record QUINT evidence (L2 - validated)
        workflow = context["manifest"].get("workflow", {})
        evidence_level = str(workflow.get("evidence", "L2") or "L2")
        store = quint_store.EvidenceStore(run_dir)
        link = quint_store.build_evidence_link(
            claim="Dev-story implemented with passing tests",
            level=evidence_level,
            source="greenfield-pipeline",
            carrier_ref=rel_summary,
            artifacts=[rel_summary, rel_log],
        )
        store.record(link)

    def _update_story_file(
        self,
        qa_log: Path,
        files: List[str],
        completion_note: str,
    ) -> None:
        """Update story file with completion status."""
        text = self.story_path.read_text(encoding="ascii")
        text = text.replace("Status: ready-for-dev", "Status: review")
        text = re.sub(r"^- \[ \]", "- [x]", text, flags=re.MULTILINE)

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
        """Append lines to a markdown section."""
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


class GreenfieldPipelineTests(unittest.TestCase):
    """Full greenfield pipeline: interactive steps 1-4, autonomous steps 5-7."""

    def setUp(self) -> None:
        """Set up test environment with provider and TELIS."""
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

        # Create sandbox
        self.sandbox = ROOT / "runs" / "tmp-tests" / uuid4().hex
        self.sandbox.mkdir(parents=True, exist_ok=True)
        self.workspace = self.sandbox / "workspace"
        self.workspace.mkdir(parents=True, exist_ok=True)

        # Configuration - use longer timeouts for local LLMs
        timeout = provider_cfg.get("timeout_seconds", 120)
        self.config = {
            "runtime": {
                "storage_root": str(self.sandbox),
                "max_retries": 0,
                "step_timeout_seconds": timeout,
            },
            "automation": {"override": True},
            "hitl": {"mode": "disabled"},
            "providers": {
                "default": self.provider_name,
                self.provider_name: provider_cfg,
                "reliability": {
                    "enabled": True,
                    "timeout_seconds": timeout,
                    "max_retries": 1,
                },
            },
        }

        # Initialize provider
        registry = ProviderRegistry(self.config)
        try:
            self.provider = registry.get(self.provider_name)
        except ProviderError as exc:
            self.skipTest(str(exc))

        self.idea = SAMPLE_IDEA

        # Initialize TELIS engine with knowledge shards
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
        telis_engine = TelisPolicyEngine(
            registry=telis_registry, cache=BehavioralCache(ttl_seconds=60)
        )

        # Initialize workflow engine
        mapping = engine.load_mapping_records()
        self.engine = engine.WorkflowEngine(
            self.config,
            mapping,
            storage_root=self.sandbox,
            telis=telis_engine,
        )

        # Set up InteractiveCLI with custom input callback
        self.input_callback = InteractiveInputProvider(self.idea)
        self.cli = InteractiveCLI(
            engine=self.engine,
            provider=self.provider,
            bmad_root=ROOT / "BMAD-METHOD",
            output_callback=lambda _text: None,  # Suppress output in tests
            input_callback=self.input_callback,
        )

    def tearDown(self) -> None:
        """Clean up test artifacts."""
        if os.environ.get("BAQT_LIVE_KEEP_RUNS") == "1":
            return
        if hasattr(self, "sandbox") and self.sandbox.exists():
            shutil.rmtree(self.sandbox, ignore_errors=True)

    def _get_templates(self) -> Dict[str, WorkflowArtifact]:
        """Get workflow artifact templates."""
        return {
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

    def _write_story_file(self) -> Path:
        """Write story file for dev-story execution."""
        story_dir = self.workspace / "_bmad" / "bmm" / "sprint_artifacts"
        story_dir.mkdir(parents=True, exist_ok=True)
        story_path = story_dir / "1-1-habit-tracker.md"

        model = str(_PROVIDER_CONFIGS[self.provider_name].get("model", ""))

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
                        model or "unknown-model",
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

    def _run_workflow_with_executor(
        self,
        module: str,
        workflow: str,
        executor: engine.StepExecutor,
        telis_query: str,
        telis_language: str,
        telis_document_path: Optional[str] = None,
    ) -> Path:
        """Run a workflow with custom executor."""
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

    def _assert_telis_quint_recorded(self, run_dir: Path) -> None:
        """Assert TELIS context and QUINT evidence were recorded."""
        fingerprints = storage.read_json(run_dir / "context-fingerprints.json")
        self.assertTrue(fingerprints.get("fingerprints"), "No TELIS fingerprints recorded")

        snapshots = storage.read_json(run_dir / "context-snapshots.json")
        self.assertTrue(snapshots.get("snapshots"), "No TELIS snapshots recorded")

        evidence = storage.read_evidence_links(run_dir)
        self.assertTrue(evidence.get("evidence"), "No QUINT evidence recorded")

    def test_interactive_steps_1_to_4(self) -> None:
        """Test interactive steps: brainstorming through UX design."""
        interactive_workflows = [
            ("core", "brainstorming"),
            ("bmm", "create-product-brief"),
            ("bmm", "prd"),
            ("bmm", "create-ux-design"),
        ]

        original_parse = step_executor.parse_step_file

        def _parse_without_outputs(path: Path):
            content = original_parse(path)
            content.outputs = []
            return content

        with patch.object(
            step_executor, "parse_step_file", side_effect=_parse_without_outputs
        ), patch.object(cli_interactive, "parse_step_file", side_effect=_parse_without_outputs):
            for module, workflow in interactive_workflows:
                # Reset input callback for each workflow
                self.input_callback = InteractiveInputProvider(self.idea)
                self.cli.input = self.input_callback

                run_id = self.cli.run_workflow(module, workflow)

                self.assertIsNotNone(run_id, f"Workflow {module}/{workflow} returned no run_id")
                run_dir = self.sandbox / str(run_id)
                self.assertTrue(run_dir.exists(), f"Run directory not created: {run_dir}")

                manifest_path = run_dir / "manifest.json"
                self.assertTrue(manifest_path.exists(), "Manifest not created")

                # Check conversation state was saved
                workflow_dir = self.cli._find_workflow_dir(module, workflow)
                if workflow_dir and step_executor.find_step_files(workflow_dir):
                    state_path = run_dir / "conversation_state.json"
                    self.assertTrue(state_path.exists(), "Conversation state not saved")
                    state = storage.read_json(state_path)
                    self.assertTrue(state.get("turns"), "No conversation turns recorded")

    def test_autonomous_steps_5_to_7(self) -> None:
        """Test autonomous steps: architecture through dev-story."""
        templates = self._get_templates()
        doc_executor = BmadTemplateExecutor(self.provider, self.idea, templates)

        autonomous_workflows = [
            ("bmm", "create-architecture"),
            ("bmm", "create-epics-and-stories"),
        ]

        for module, workflow in autonomous_workflows:
            run_dir = self._run_workflow_with_executor(
                module,
                workflow,
                executor=doc_executor,
                telis_query=self.idea,
                telis_language="markdown",
            )
            self._assert_telis_quint_recorded(run_dir)

        # Dev-story with red/green TDD
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

        run_dir = self._run_workflow_with_executor(
            "bmm",
            "dev-story",
            executor=dev_executor,
            telis_query="habit tracker implementation",
            telis_language="python",
            telis_document_path=rel_code_path,
        )

        # Verify final product
        summary_path = run_dir / "outputs" / "final-product.md"
        self.assertTrue(summary_path.exists(), "Final product not generated")
        self.assertIn("Habit Tracker", summary_path.read_text(encoding="ascii"))

        # Verify story status updated
        self.assertIn("Status: review", story_path.read_text(encoding="ascii"))

        self._assert_telis_quint_recorded(run_dir)

    def test_full_greenfield_pipeline(self) -> None:
        """Complete end-to-end greenfield pipeline test."""
        # Phase 1: Interactive steps 1-4
        interactive_workflows = [
            ("core", "brainstorming"),
            ("bmm", "create-product-brief"),
            ("bmm", "prd"),
            ("bmm", "create-ux-design"),
        ]

        original_parse = step_executor.parse_step_file

        def _parse_without_outputs(path: Path):
            content = original_parse(path)
            content.outputs = []
            return content

        interactive_run_ids = []
        with patch.object(
            step_executor, "parse_step_file", side_effect=_parse_without_outputs
        ), patch.object(cli_interactive, "parse_step_file", side_effect=_parse_without_outputs):
            for module, workflow in interactive_workflows:
                self.input_callback = InteractiveInputProvider(self.idea)
                self.cli.input = self.input_callback

                run_id = self.cli.run_workflow(module, workflow)
                self.assertIsNotNone(run_id)
                interactive_run_ids.append(run_id)

        # Phase 2: Autonomous steps 5-7
        templates = self._get_templates()
        doc_executor = BmadTemplateExecutor(self.provider, self.idea, templates)

        autonomous_workflows = [
            ("bmm", "create-architecture"),
            ("bmm", "create-epics-and-stories"),
        ]

        autonomous_run_dirs = []
        for module, workflow in autonomous_workflows:
            run_dir = self._run_workflow_with_executor(
                module,
                workflow,
                executor=doc_executor,
                telis_query=self.idea,
                telis_language="markdown",
            )
            autonomous_run_dirs.append(run_dir)
            self._assert_telis_quint_recorded(run_dir)

        # Phase 3: Dev-story with TDD
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

        final_run_dir = self._run_workflow_with_executor(
            "bmm",
            "dev-story",
            executor=dev_executor,
            telis_query="habit tracker implementation",
            telis_language="python",
            telis_document_path=rel_code_path,
        )

        # Final verification
        summary_path = final_run_dir / "outputs" / "final-product.md"
        self.assertTrue(summary_path.exists(), "Final product not generated")

        summary_content = summary_path.read_text(encoding="ascii")
        self.assertIn("Habit Tracker", summary_content)
        self.assertIn("red", summary_content.lower())
        self.assertIn("green", summary_content.lower())

        story_content = story_path.read_text(encoding="ascii")
        self.assertIn("Status: review", story_content)

        # Verify complete evidence chain
        self._assert_telis_quint_recorded(final_run_dir)

        # Summary
        total_runs = len(interactive_run_ids) + len(autonomous_run_dirs) + 1
        print(f"\nPipeline completed: {total_runs} workflows executed")
        print(f"  Interactive (1-4): {len(interactive_run_ids)} runs")
        print(f"  Autonomous (5-7): {len(autonomous_run_dirs) + 1} runs")
        print(f"  Final product: {summary_path}")


if __name__ == "__main__":
    unittest.main()
