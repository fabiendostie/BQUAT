from __future__ import annotations

from typing import Dict, List, Optional


class ResourceScheduler:
    """Manages execution resources and concurrency limits."""

    def __init__(self, config: Dict[str, object]) -> None:
        orchestrator_cfg = config.get("orchestrator", {}) if isinstance(config, dict) else {}
        if isinstance(orchestrator_cfg, dict):
            limits = orchestrator_cfg.get("provider_limits", {})
        else:
            limits = {}
        self._limits = (
            {str(key): int(value) for key, value in dict(limits).items()} if limits else {}
        )
        self._in_use: Dict[str, int] = {}
        self._assignments: Dict[str, str] = {}

    def acquire(self, workflow_id: str, provider: str) -> bool:
        if not provider:
            return True
        limit = self._limits.get(provider)
        in_use = self._in_use.get(provider, 0)
        if limit is not None and in_use >= limit:
            return False
        self._in_use[provider] = in_use + 1
        self._assignments[workflow_id] = provider
        return True

    def release(self, workflow_id: str, provider: Optional[str] = None) -> None:
        assigned = provider or self._assignments.pop(workflow_id, None)
        if not assigned:
            return
        current = self._in_use.get(assigned, 0)
        self._in_use[assigned] = max(0, current - 1)

    def get_available_providers(self) -> List[str]:
        if not self._limits:
            return []
        available = []
        for provider, limit in self._limits.items():
            if self._in_use.get(provider, 0) < limit:
                available.append(provider)
        return available
