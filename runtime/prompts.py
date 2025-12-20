from __future__ import annotations

from typing import Any, Dict

DEFAULT_TEMPLATES = {
    "bmad": "BMAD workflow {workflow} in {phase}. Outputs: {outputs}.",
    "telis": "TELIS policy {telis} for {workflow} ({phase}).",
    "quint": "QUINT checkpoint {quint} for {workflow} ({phase}).",
}


class _SafeDict(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def get_template(framework: str) -> str:
    return DEFAULT_TEMPLATES.get(framework, "Workflow {workflow} in {phase}.")


def render_prompt(template: str, context: Dict[str, Any]) -> str:
    return template.format_map(_SafeDict(context))
