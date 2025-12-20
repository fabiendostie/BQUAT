from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from runtime import models
from runtime import prompts


def split_artifacts(artifacts: List[str]) -> Tuple[List[str], List[str]]:
    outputs: List[str] = []
    templates: List[str] = []
    for artifact in artifacts:
        if artifact.startswith("template:"):
            templates.append(artifact.split("template:", 1)[1])
        else:
            outputs.append(artifact)
    return outputs, templates


@dataclass(frozen=True)
class AgentPlan:
    workflow: models.WorkflowSpec
    prompt: str
    outputs: List[str]
    templates: List[str]
    framework: str


class BaseAgent:
    framework: str

    def __init__(self, framework: str) -> None:
        self.framework = framework

    def build_plan(self, spec: models.WorkflowSpec) -> AgentPlan:
        outputs, templates = split_artifacts(spec.artifacts)
        context = {
            "workflow": spec.workflow,
            "phase": spec.phase,
            "outputs": ", ".join(outputs) if outputs else "none",
            "quint": spec.quint,
            "telis": spec.telis,
        }
        template = prompts.get_template(self.framework)
        prompt = prompts.render_prompt(template, context)
        return AgentPlan(
            workflow=spec,
            prompt=prompt,
            outputs=outputs,
            templates=templates,
            framework=self.framework,
        )


class BMADAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__("bmad")


class TELISAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__("telis")


class QUINTAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__("quint")


AGENTS: Dict[str, BaseAgent] = {
    "bmad": BMADAgent(),
    "telis": TELISAgent(),
    "quint": QUINTAgent(),
}


def get_agent(name: str) -> BaseAgent:
    if name not in AGENTS:
        raise KeyError(f"Unknown agent: {name}")
    return AGENTS[name]
