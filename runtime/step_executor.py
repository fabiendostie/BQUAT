"""BMAD step file executor for interactive workflow execution.

This module provides the core step execution logic that loads BMAD step files,
parses their instructions, and executes them conversationally with user interaction.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, cast

import yaml

from runtime import storage
from runtime.engine import StepExecutor
from runtime.providers.base import Provider, ProviderRequest
from runtime.time_provider import get_current_time


@dataclass
class StepInstruction:
    """Parsed instruction from a BMAD step file."""

    role: str
    content: str
    wait_for_input: bool = False
    next_step: Optional[str] = None
    template_path: Optional[str] = None
    output_path: Optional[str] = None


@dataclass
class StepFileContent:
    """Parsed content from a BMAD step file."""

    frontmatter: Dict[str, Any]
    title: str
    role: str
    instructions: List[str]
    conversation_flow: List[str]
    outputs: List[str]
    templates: List[str]
    next_step: Optional[str]
    raw_content: str


@dataclass
class ConversationTurn:
    """A single turn in the conversation."""

    role: str  # "user", "assistant", "system"
    content: str
    step_id: str
    timestamp: str


@dataclass
class ConversationState:
    """State of the ongoing conversation for a workflow run."""

    run_id: str
    workflow: str
    current_step_idx: int
    current_step_id: str
    steps_completed: List[str] = field(default_factory=list)
    turns: List[ConversationTurn] = field(default_factory=list)
    documents: Dict[str, str] = field(default_factory=dict)
    waiting_for_input: bool = False
    last_prompt: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for persistence."""
        return {
            "run_id": self.run_id,
            "workflow": self.workflow,
            "current_step_idx": self.current_step_idx,
            "current_step_id": self.current_step_id,
            "steps_completed": self.steps_completed,
            "turns": [
                {
                    "role": t.role,
                    "content": t.content,
                    "step_id": t.step_id,
                    "timestamp": t.timestamp,
                }
                for t in self.turns
            ],
            "documents": self.documents,
            "waiting_for_input": self.waiting_for_input,
            "last_prompt": self.last_prompt,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ConversationState:
        """Create from dictionary."""
        turns = [
            ConversationTurn(
                role=t["role"],
                content=t["content"],
                step_id=t["step_id"],
                timestamp=t["timestamp"],
            )
            for t in data.get("turns", [])
        ]
        return cls(
            run_id=data["run_id"],
            workflow=data["workflow"],
            current_step_idx=data.get("current_step_idx", 0),
            current_step_id=data.get("current_step_id", ""),
            steps_completed=data.get("steps_completed", []),
            turns=turns,
            documents=data.get("documents", {}),
            waiting_for_input=data.get("waiting_for_input", False),
            last_prompt=data.get("last_prompt", ""),
        )


def parse_step_file(path: Path) -> StepFileContent:
    """Parse a BMAD step file into structured content."""
    text = path.read_text(encoding="utf-8")

    # Parse frontmatter
    frontmatter: Dict[str, Any] = {}
    body = text
    if text.startswith("---"):
        lines = text.splitlines()
        end_idx = None
        for idx, line in enumerate(lines[1:], 1):
            if line.strip() == "---":
                end_idx = idx
                break
        if end_idx:
            raw_fm = "\n".join(lines[1:end_idx])
            try:
                frontmatter = yaml.safe_load(raw_fm) or {}
            except Exception:
                frontmatter = {}
            body = "\n".join(lines[end_idx + 1 :])

    # Extract title
    title = ""
    for line in body.splitlines():
        if line.strip().startswith("#"):
            title = line.strip().lstrip("#").strip()
            break

    # Extract role (Your Role section)
    role = ""
    role_match = re.search(
        r"\*\*(?:Your\s+)?Role[:\s]*\*\*\s*(.+?)(?:\n\n|\n\*\*|$)",
        body,
        re.IGNORECASE | re.DOTALL,
    )
    if role_match:
        role = role_match.group(1).strip()

    # Extract conversation flow
    conversation_flow: List[str] = []
    flow_match = re.search(
        r"\*\*Conversation\s+Flow[:\s]*\*\*(.*?)(?:\n\n\*\*|\n##|$)",
        body,
        re.IGNORECASE | re.DOTALL,
    )
    if flow_match:
        flow_text = flow_match.group(1)
        for line in flow_text.splitlines():
            line = line.strip()
            if line and re.match(r"^\d+\.", line):
                conversation_flow.append(re.sub(r"^\d+\.\s*", "", line))

    # Extract instructions (numbered or bulleted items)
    instructions: List[str] = []
    for line in body.splitlines():
        line = line.strip()
        if re.match(r"^(\d+\.|[-*])\s+", line):
            instructions.append(re.sub(r"^(\d+\.|[-*])\s*", "", line))

    # Extract outputs
    outputs: List[str] = []
    output_match = re.search(
        r"(?:output(?:_file|file)?|outputs?)\s*:\s*([^\n]+)",
        body,
        re.IGNORECASE,
    )
    if output_match:
        outputs.append(output_match.group(1).strip())
    # Also check frontmatter
    if frontmatter.get("outputFile"):
        outputs.append(frontmatter["outputFile"])
    if frontmatter.get("output"):
        outputs.append(frontmatter["output"])

    # Extract templates
    templates: List[str] = []
    template_match = re.search(
        r"(?:template(?:_path)?|templates?)\s*:\s*([^\n]+)",
        body,
        re.IGNORECASE,
    )
    if template_match:
        templates.append(template_match.group(1).strip())
    if frontmatter.get("template"):
        templates.append(frontmatter["template"])

    # Extract next step reference
    next_step = None
    next_match = re.search(
        r"(?:continue|next|load)\s*[:\->]+\s*(?:step[-_])?(\d+)",
        body,
        re.IGNORECASE,
    )
    if next_match:
        next_step = f"step-{next_match.group(1).zfill(2)}"

    return StepFileContent(
        frontmatter=frontmatter,
        title=title,
        role=role,
        instructions=instructions,
        conversation_flow=conversation_flow or instructions[:5],
        outputs=outputs,
        templates=templates,
        next_step=next_step,
        raw_content=body,
    )


def find_step_files(workflow_dir: Path) -> List[Path]:
    """Find all step files in a workflow directory."""
    steps_dir = workflow_dir / "steps"
    if steps_dir.exists():
        files = list(steps_dir.glob("step-*.md"))
    else:
        files = list(workflow_dir.glob("step-*.md"))

    # Sort by step number
    def sort_key(p: Path) -> int:
        match = re.match(r"step-(\d+)", p.stem)
        return int(match.group(1)) if match else 999

    return sorted(files, key=sort_key)


def build_step_prompt(
    step_content: StepFileContent,
    conversation_state: ConversationState,
    user_input: Optional[str] = None,
) -> str:
    """Build a prompt for the LLM based on step content and conversation state."""
    parts: List[str] = []

    # System context
    parts.append(f"# {step_content.title}")
    parts.append("")
    if step_content.role:
        parts.append(f"**Your Role:** {step_content.role}")
        parts.append("")

    # Conversation flow instructions
    if step_content.conversation_flow:
        parts.append("**Instructions:**")
        for i, instruction in enumerate(step_content.conversation_flow, 1):
            parts.append(f"{i}. {instruction}")
        parts.append("")

    # Templates to use
    if step_content.templates:
        parts.append("**Templates available:**")
        for template in step_content.templates:
            parts.append(f"- {template}")
        parts.append("")

    # Expected outputs
    if step_content.outputs:
        parts.append("**Expected outputs:**")
        for output in step_content.outputs:
            parts.append(f"- {output}")
        parts.append("")

    # Document context (what's been built so far)
    if conversation_state.documents:
        parts.append("**Documents in progress:**")
        for name, content in conversation_state.documents.items():
            preview = content[:200] + "..." if len(content) > 200 else content
            parts.append(f"- {name}: {preview}")
        parts.append("")

    # Previous conversation turns for this step
    step_turns = [
        t for t in conversation_state.turns if t.step_id == conversation_state.current_step_id
    ]
    if step_turns:
        parts.append("**Previous conversation:**")
        for turn in step_turns[-5:]:  # Last 5 turns
            parts.append(f"[{turn.role}]: {turn.content[:300]}")
        parts.append("")

    # User input
    if user_input:
        parts.append(f"**User says:** {user_input}")

    return "\n".join(parts)


class BmadStepExecutor(StepExecutor):
    """Executor that runs BMAD step files interactively.

    This executor:
    1. Loads the appropriate step file for the current step
    2. Parses its instructions and conversation flow
    3. Builds prompts for the LLM
    4. Manages conversation state
    5. Builds output documents incrementally
    """

    def __init__(
        self,
        provider: Optional[Provider] = None,
        bmad_root: Optional[Path] = None,
    ) -> None:
        self.provider = provider
        self.bmad_root = bmad_root or Path("BMAD-METHOD")

    def _find_workflow_dir(self, module: str, workflow: str) -> Optional[Path]:
        """Find the workflow directory in BMAD-METHOD."""
        # Try various paths
        candidates = [
            self.bmad_root / "src" / module / "workflows" / workflow,
            self.bmad_root / "src" / "modules" / module / "workflows" / workflow,
            self.bmad_root / module / "workflows" / workflow,
        ]
        for path in candidates:
            if path.exists():
                return path
        return None

    def _load_conversation_state(self, run_dir: Path) -> Optional[ConversationState]:
        """Load conversation state from run directory."""
        state_file = run_dir / "conversation_state.json"
        if state_file.exists():
            data = storage.read_json(state_file)
            if data:
                return ConversationState.from_dict(data)
        return None

    def _save_conversation_state(self, run_dir: Path, state: ConversationState) -> None:
        """Save conversation state to run directory."""
        storage.write_json(run_dir / "conversation_state.json", state.to_dict())

    def _invoke_provider(
        self, prompt: str, conversation_history: List[Dict[str, str]]
    ) -> Optional[str]:
        """Invoke the LLM provider with the prompt."""
        if not self.provider:
            return None

        messages = list(conversation_history)
        messages.append({"role": "user", "content": prompt})

        request = ProviderRequest(
            model="",  # Use default
            messages=messages,
        )
        response = self.provider.invoke(request)
        return response.content

    def execute(self, step: Dict[str, Any], context: Dict[str, Any]) -> None:
        """Execute a BMAD step file.

        This method:
        1. Determines the current step file
        2. Loads and parses it
        3. Builds a prompt
        4. Invokes the LLM
        5. Updates conversation state
        6. Appends to output documents
        """
        manifest = cast(Dict[str, Any], context["manifest"])
        run_dir = cast(Path, context["run_dir"])
        user_input = context.get("user_input")

        # Get workflow info
        workflow_info = manifest.get("workflow", {})
        module = workflow_info.get("module", "")
        workflow = workflow_info.get("workflow", "")

        # Load or create conversation state
        state = self._load_conversation_state(run_dir)
        if not state:
            state = ConversationState(
                run_id=manifest.get("run_id", ""),
                workflow=workflow,
                current_step_idx=0,
                current_step_id=step.get("step_id", "step-01"),
            )

        # Find workflow directory and step files
        workflow_dir = self._find_workflow_dir(module, workflow)
        if not workflow_dir:
            # Fallback: use step spec info if available
            step["status"] = "completed"
            step["result"] = {"error": "Workflow directory not found"}
            return

        step_files = find_step_files(workflow_dir)
        if not step_files:
            step["status"] = "completed"
            step["result"] = {"error": "No step files found"}
            return

        # Find current step file
        current_step_id = step.get("step_id", f"step-{state.current_step_idx + 1:02d}")
        current_file = None
        for sf in step_files:
            if sf.stem.startswith(
                current_step_id.split("-")[0] + "-" + current_step_id.split("-")[1]
                if "-" in current_step_id
                else current_step_id
            ):
                current_file = sf
                break

        if not current_file and step_files:
            idx = min(state.current_step_idx, len(step_files) - 1)
            current_file = step_files[idx]

        if not current_file:
            step["status"] = "completed"
            step["result"] = {"error": "Step file not found"}
            return

        # Parse step file
        step_content = parse_step_file(current_file)

        # Update state
        state.current_step_id = current_file.stem

        # Build prompt
        prompt = build_step_prompt(step_content, state, user_input)

        # Record user input if provided
        if user_input:
            state.turns.append(
                ConversationTurn(
                    role="user",
                    content=user_input,
                    step_id=state.current_step_id,
                    timestamp=get_current_time(),
                )
            )

        # Invoke LLM
        conversation_history = [{"role": t.role, "content": t.content} for t in state.turns[-10:]]
        response_text = self._invoke_provider(prompt, conversation_history)

        if response_text:
            # Record assistant response
            state.turns.append(
                ConversationTurn(
                    role="assistant",
                    content=response_text,
                    step_id=state.current_step_id,
                    timestamp=get_current_time(),
                )
            )

            # Check if step asks for user input
            needs_input = any(
                phrase in response_text.lower()
                for phrase in [
                    "what do you think",
                    "tell me about",
                    "please describe",
                    "would you like",
                    "let me know",
                    "your input",
                    "?",
                ]
            )

            if needs_input:
                state.waiting_for_input = True
                state.last_prompt = response_text
                step["status"] = "waiting_for_input"
            else:
                # Step can proceed
                state.steps_completed.append(state.current_step_id)
                state.current_step_idx += 1
                step["status"] = "completed"

            # Update output documents if we have content
            for output in step_content.outputs:
                if output and response_text:
                    existing = state.documents.get(output, "")
                    state.documents[output] = existing + "\n\n" + response_text

        # Save state
        self._save_conversation_state(run_dir, state)

        # Save response to step
        step["result"] = {
            "step_file": str(current_file),
            "step_title": step_content.title,
            "response": response_text,
            "waiting_for_input": state.waiting_for_input,
            "steps_completed": state.steps_completed,
        }

        # Write outputs
        for output_name, content in state.documents.items():
            output_path = run_dir / output_name
            output_path.write_text(content, encoding="utf-8")
            if output_name not in step.get("outputs", []):
                step.setdefault("outputs", []).append(output_name)


class InteractiveStepExecutor(BmadStepExecutor):
    """Interactive executor that prompts user for input.

    Extends BmadStepExecutor to handle interactive CLI sessions.
    """

    def __init__(
        self,
        provider: Optional[Provider] = None,
        bmad_root: Optional[Path] = None,
        input_callback: Optional[Callable[[str], str]] = None,
        output_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        super().__init__(provider, bmad_root)
        self.input_callback = input_callback or input
        self.output_callback = output_callback or print

    def execute_interactive(
        self,
        step: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute a step interactively, prompting for user input as needed.

        Returns the final step result after all conversation turns.
        """
        while True:
            # Execute step
            self.execute(step, context)

            # Check if we need user input
            result = step.get("result", {})
            if not result.get("waiting_for_input"):
                break

            # Display response to user
            if result.get("response"):
                self.output_callback(f"\n{result['response']}\n")

            # Get user input
            try:
                user_input = self.input_callback("\nYour response: ")
            except (EOFError, KeyboardInterrupt):
                step["status"] = "cancelled"
                break

            if user_input.lower() in ("quit", "exit", "q"):
                step["status"] = "cancelled"
                break

            if user_input.lower() in ("continue", "next", "skip"):
                step["status"] = "completed"
                break

            # Continue with user input
            context["user_input"] = user_input
            step["status"] = "running"

        return step
