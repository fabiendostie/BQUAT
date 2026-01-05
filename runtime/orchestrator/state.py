from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set


@dataclass
class OrchestratorState:
    completed: Set[str] = field(default_factory=set)
    running: Set[str] = field(default_factory=set)
    failed: Set[str] = field(default_factory=set)
    manifests: Dict[str, Dict[str, object]] = field(default_factory=dict)
    history: List[str] = field(default_factory=list)

    def mark_completed(self, workflow_id: str, manifest: Dict[str, object]) -> None:
        self.completed.add(workflow_id)
        self.running.discard(workflow_id)
        self.manifests[workflow_id] = manifest
        self.history.append(workflow_id)

    def mark_failed(self, workflow_id: str, manifest: Dict[str, object]) -> None:
        self.failed.add(workflow_id)
        self.running.discard(workflow_id)
        self.manifests[workflow_id] = manifest
        self.history.append(workflow_id)

    def mark_running(self, workflow_id: str) -> None:
        self.running.add(workflow_id)
