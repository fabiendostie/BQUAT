from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ProviderRequest:
    model: str
    messages: List[Dict[str, str]]
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


@dataclass(frozen=True)
class ProviderResponse:
    content: str
    raw: Dict[str, Any]


class ProviderError(RuntimeError):
    pass


class Provider:
    def invoke(self, request: ProviderRequest) -> ProviderResponse:
        raise NotImplementedError
