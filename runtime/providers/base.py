from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ProviderRequest:
    model: str
    messages: List[Dict[str, str]]
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    stream: bool = False
    timeout_seconds: Optional[int] = None


@dataclass(frozen=True)
class ProviderResponse:
    content: str
    raw: Dict[str, Any]
    chunks: Optional[List[str]] = None


class ProviderError(RuntimeError):
    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        retriable: bool = True,
        error_type: str = "",
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retriable = retriable
        self.error_type = error_type


class Provider:
    def invoke(self, request: ProviderRequest) -> ProviderResponse:
        raise NotImplementedError

    def invoke_stream(self, request: ProviderRequest) -> ProviderResponse:
        raise ProviderError("Streaming not supported")
