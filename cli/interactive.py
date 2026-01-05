"""Interactive CLI for BMAD workflow execution.

This module provides an interactive command-line interface for running
BMAD workflows step-by-step with user input and document building.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, cast

from runtime import storage
from runtime.document_builder import DocumentBuilder
from runtime.engine import WorkflowEngine, load_mapping_records
from runtime.providers.base import Provider
from runtime.providers.registry import ProviderRegistry
from runtime.step_executor import (
    BmadStepExecutor,
    find_step_files,
    parse_step_file,
)


class InteractiveCLI:
    """Interactive CLI for BMAD workflow execution.

    Provides a user-friendly interface for:
    - Starting workflows from brainstorming
    - Progressing through BMAD phases
    - Building documents incrementally
    - Reviewing and approving outputs
    """

    def __init__(
        self,
        engine: WorkflowEngine,
        provider: Optional[Provider] = None,
        bmad_root: Optional[Path] = None,
        output_callback: Optional[Callable[[str], None]] = None,
        input_callback: Optional[Callable[[str], str]] = None,
    ) -> None:
        self.engine = engine
        self.provider = provider
        self.bmad_root = bmad_root or Path("BMAD-METHOD")
        self.output = output_callback or self._default_output
        self.input = input_callback or self._default_input

    def _default_output(self, text: str) -> None:
        """Default output function."""
        print(text)

    def _default_input(self, prompt: str) -> str:
        """Default input function."""
        return input(prompt)

    def _print_header(self, text: str) -> None:
        """Print a formatted header."""
        width = max(len(text) + 4, 60)
        self.output("")
        self.output("=" * width)
        self.output(f"  {text}")
        self.output("=" * width)

    def _print_section(self, title: str, content: str = "") -> None:
        """Print a section with title."""
        self.output("")
        self.output(f"--- {title} ---")
        if content:
            self.output(content)

    def _print_menu(self, options: List[str]) -> None:
        """Print a numbered menu."""
        self.output("")
        for i, option in enumerate(options, 1):
            self.output(f"  {i}. {option}")
        self.output("")

    def _get_choice(self, prompt: str, valid: List[str]) -> str:
        """Get a validated choice from user."""
        while True:
            choice = self.input(prompt).strip().lower()
            if choice in valid:
                return choice
            self.output(f"Invalid choice. Please enter one of: {', '.join(valid)}")

    def show_welcome(self) -> None:
        """Show welcome message and available workflows."""
        self._print_header("BAQT - BMAD Workflow Execution")
        self.output("")
        self.output("Welcome to BAQT interactive workflow execution.")
        self.output("This tool will guide you through BMAD workflows to create")
        self.output("your project documentation from brainstorming to architecture.")
        self.output("")
        self.output("Available workflow phases:")
        self.output("  1. Brainstorming - Explore and refine your idea")
        self.output("  2. Product Brief - Define vision, users, and scope")
        self.output("  3. PRD - Create detailed product requirements")
        self.output("  4. UX Design - Define user experience and design system")
        self.output("  5. Architecture - Design technical architecture")
        self.output("  6. Epics & Stories - Break down into development tasks")
        self.output("")
        self.output("After step 4, autonomous development can begin.")

    def select_workflow(self) -> Optional[Dict[str, str]]:
        """Let user select a workflow to run."""
        self._print_section("Select Starting Point")

        workflows = [
            {"module": "core", "workflow": "brainstorming", "name": "Start with Brainstorming"},
            {"module": "bmm", "workflow": "create-product-brief", "name": "Create Product Brief"},
            {"module": "bmm", "workflow": "prd", "name": "Create PRD"},
            {"module": "bmm", "workflow": "create-ux-design", "name": "Create UX Design"},
            {"module": "bmm", "workflow": "create-architecture", "name": "Create Architecture"},
            {
                "module": "bmm",
                "workflow": "create-epics-and-stories",
                "name": "Create Epics & Stories",
            },
        ]

        self._print_menu([w["name"] for w in workflows] + ["Exit"])

        choice = self.input("Select workflow (1-7): ").strip()
        try:
            idx = int(choice) - 1
            if idx == len(workflows):
                return None
            if 0 <= idx < len(workflows):
                return workflows[idx]
        except ValueError:
            pass

        self.output("Invalid choice.")
        return None

    def run_workflow(
        self,
        module: str,
        workflow: str,
        run_id: Optional[str] = None,
    ) -> Optional[str]:
        """Run a workflow interactively.

        Returns the run_id if successful, None if cancelled.
        """
        self._print_header(f"Starting: {workflow}")

        # Create or resume run
        resolved_run_id: str
        if run_id:
            resolved_run_id = run_id
            run_dir = self.engine.storage_root / resolved_run_id
            if not run_dir.exists():
                self.output(f"Run {resolved_run_id} not found.")
                return None
            manifest = storage.read_manifest(run_dir)
        else:
            manifest = self.engine.create_run(module, workflow)
            resolved_run_id = str(manifest["run_id"])
            run_dir = self.engine.storage_root / resolved_run_id

        self.output(f"Run ID: {resolved_run_id}")
        self.output(f"Run directory: {run_dir}")

        # Find step files
        workflow_dir = self._find_workflow_dir(module, workflow)
        if not workflow_dir:
            self.output("Warning: Workflow directory not found in BMAD-METHOD")
            self.output("Using generic step execution...")

        step_files = find_step_files(workflow_dir) if workflow_dir else []
        total_steps = len(step_files) or len(manifest.get("steps", []))

        self.output(f"Total steps: {total_steps}")
        self.output("")

        # Initialize document builder
        doc_builder = DocumentBuilder(run_dir)

        # Create executor
        executor = BmadStepExecutor(
            provider=self.provider,
            bmad_root=self.bmad_root,
        )

        # Execute steps interactively
        current_step = 0
        while current_step < total_steps:
            # Get step info
            if step_files and current_step < len(step_files):
                step_file = step_files[current_step]
                step_content = parse_step_file(step_file)
                step_title = step_content.title
            else:
                step_title = f"Step {current_step + 1}"

            self._print_section(f"Step {current_step + 1}/{total_steps}: {step_title}")

            # Show step instructions if available
            if step_files and current_step < len(step_files):
                step_content = parse_step_file(step_files[current_step])
                if step_content.role:
                    self.output(f"Role: {step_content.role}")
                if step_content.conversation_flow:
                    self.output("")
                    self.output("This step will:")
                    for i, item in enumerate(step_content.conversation_flow[:3], 1):
                        self.output(f"  {i}. {item}")
                if step_content.outputs:
                    self.output("")
                    self.output(f"Outputs: {', '.join(step_content.outputs)}")

            self.output("")

            # Get user input for this step
            self.output("Enter your input for this step (or 'skip' to skip, 'quit' to exit):")
            user_input = self.input("> ").strip()

            if user_input.lower() in ("quit", "exit", "q"):
                self.output("Workflow paused. You can resume later.")
                return run_id

            if user_input.lower() in ("skip", "s", "next", "n"):
                current_step += 1
                continue

            # Execute step with user input
            step_data = {
                "step_id": f"step-{current_step + 1:02d}",
                "name": step_title,
                "status": "pending",
            }

            context = {
                "manifest": manifest,
                "run_dir": run_dir,
                "user_input": user_input,
            }

            executor.execute(step_data, context)

            # Show response
            raw_result: object = step_data.get("result", {})
            if isinstance(raw_result, dict):
                result = cast(Dict[str, Any], raw_result)
            else:
                result = {}
            response = result.get("response")
            if response:
                self.output("")
                self.output("--- Response ---")
                self.output(response[:1000])  # Limit output
                if len(response) > 1000:
                    self.output("... (truncated)")

            # Check if we need more input
            if result.get("waiting_for_input"):
                self.output("")
                while True:
                    follow_up = self.input(
                        "Continue the conversation (or 'done' to proceed): "
                    ).strip()
                    if follow_up.lower() in ("done", "next", "continue"):
                        break
                    context["user_input"] = follow_up
                    executor.execute(step_data, context)
                    raw_latest: object = step_data.get("result", {})
                    latest_result: Dict[str, Any]
                    if isinstance(raw_latest, dict):
                        latest_result = cast(Dict[str, Any], raw_latest)
                    else:
                        latest_result = {}
                    new_response = latest_result.get("response")
                    if new_response:
                        self.output("")
                        self.output(new_response[:1000])

            # Save progress
            storage.write_manifest(run_dir, manifest)

            # Move to next step
            current_step += 1
            self.output("")
            self.output(f"Step {current_step} completed.")

        # Workflow complete
        self._print_header("Workflow Complete!")

        # Save all documents
        doc_paths = doc_builder.save_all()
        if doc_paths:
            self.output("")
            self.output("Documents created:")
            for path in doc_paths:
                self.output(f"  - {path}")

        # Show progress summary
        progress = doc_builder.get_progress()
        if progress:
            self.output("")
            self.output("Document progress:")
            for name, info in progress.items():
                self.output(
                    f"  {name}: {info['completed_sections']}/{info['total_sections']} sections"
                )

        return resolved_run_id

    def _find_workflow_dir(self, module: str, workflow: str) -> Optional[Path]:
        """Find workflow directory in BMAD-METHOD."""
        candidates = [
            self.bmad_root / "src" / module / "workflows" / workflow,
            self.bmad_root / "src" / "modules" / module / "workflows" / workflow,
            self.bmad_root / module / "workflows" / workflow,
        ]
        for path in candidates:
            if path.exists():
                return path
        return None

    def run_interactive_session(self) -> None:
        """Run a full interactive session."""
        self.show_welcome()

        while True:
            workflow = self.select_workflow()
            if not workflow:
                self.output("Goodbye!")
                break

            run_id = self.run_workflow(
                module=workflow["module"],
                workflow=workflow["workflow"],
            )

            if run_id:
                self.output("")
                choice = self._get_choice(
                    "Continue with another workflow? (y/n): ",
                    ["y", "n", "yes", "no"],
                )
                if choice in ("n", "no"):
                    break


def run_interactive(
    module: str,
    workflow: str,
    provider_name: Optional[str] = None,
    config_path: Optional[Path] = None,
    run_id: Optional[str] = None,
) -> Optional[str]:
    """Convenience function to run a workflow interactively.

    Args:
        module: BMAD module name (e.g., "bmm", "core")
        workflow: Workflow name (e.g., "prd", "brainstorming")
        provider_name: Optional LLM provider name
        config_path: Optional path to config file
        run_id: Optional run ID to resume

    Returns:
        The run_id if successful, None if cancelled.
    """
    from runtime.config import load_config

    config = load_config(config_path)
    mapping = load_mapping_records()
    engine = WorkflowEngine(config=config, mapping_records=mapping)

    provider = None
    if provider_name:
        registry = ProviderRegistry(config)
        provider = registry.get(provider_name)

    cli = InteractiveCLI(
        engine=engine,
        provider=provider,
        bmad_root=Path("BMAD-METHOD"),
    )

    return cli.run_workflow(module, workflow, run_id)


def main() -> int:
    """Main entry point for interactive CLI."""
    from runtime.config import load_config

    config = load_config()
    mapping = load_mapping_records()
    engine = WorkflowEngine(config=config, mapping_records=mapping)

    cli = InteractiveCLI(engine=engine)
    cli.run_interactive_session()
    return 0


if __name__ == "__main__":
    sys.exit(main())
