from __future__ import annotations

from typing import Dict, Optional

from runtime import agents, models, storage
from runtime.engine import StepExecutor
from runtime.providers.base import Provider, ProviderRequest


class PlanExecutor(StepExecutor):
    def __init__(self, agent_name: str, provider: Optional[Provider] = None) -> None:
        self.agent_name = agent_name
        self.provider = provider

    def execute(self, step: Dict[str, object], context: Dict[str, object]) -> None:
        manifest = context["manifest"]
        run_dir = context["run_dir"]
        spec = models.WorkflowSpec.from_mapping(manifest["workflow"])
        agent = agents.get_agent(self.agent_name)
        plan = agent.build_plan(spec)

        storage.write_json(
            run_dir / "plan.json",
            {
                "framework": plan.framework,
                "workflow": plan.workflow.to_dict(),
                "prompt": plan.prompt,
                "outputs": plan.outputs,
                "templates": plan.templates,
            },
        )

        if self.provider:
            request = ProviderRequest(
                model="",
                messages=[{"role": "user", "content": plan.prompt}],
            )
            response = self.provider.invoke(request)
            storage.write_json(
                run_dir / "response.json",
                {
                    "content": response.content,
                    "raw": response.raw,
                },
            )
            outputs = list(step.get("outputs", []))
            for name in ["plan.json", "response.json"]:
                if name not in outputs:
                    outputs.append(name)
            step["outputs"] = outputs
