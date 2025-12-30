from __future__ import annotations

import random
import time
from dataclasses import dataclass, replace
from typing import Callable, Optional

from runtime.providers.base import Provider, ProviderError, ProviderRequest, ProviderResponse


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 1
    backoff_seconds: float = 0.5
    backoff_factor: float = 2.0
    backoff_max_seconds: float = 8.0
    jitter_seconds: float = 0.1

    def delay_for(self, attempt: int) -> float:
        if attempt <= 0:
            return 0.0
        base = self.backoff_seconds * (self.backoff_factor ** (attempt - 1))
        delay = min(self.backoff_max_seconds, base)
        if self.jitter_seconds <= 0:
            return delay
        return delay + random.uniform(0, self.jitter_seconds)


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 3,
        reset_seconds: float = 30.0,
        time_provider: Callable[[], float] = time.monotonic,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.reset_seconds = reset_seconds
        self._time = time_provider
        self._state = "closed"
        self._failures = 0
        self._opened_at = 0.0

    def allow(self) -> None:
        if self._state != "open":
            return
        now = self._time()
        if now - self._opened_at >= self.reset_seconds:
            self._state = "half-open"
            return
        raise ProviderError("Circuit breaker open")

    def record_success(self) -> None:
        self._state = "closed"
        self._failures = 0
        self._opened_at = 0.0

    def record_failure(self) -> None:
        if self._state == "half-open":
            self._state = "open"
            self._opened_at = self._time()
            return
        self._failures += 1
        if self._failures >= self.failure_threshold:
            self._state = "open"
            self._opened_at = self._time()


class ReliableProvider(Provider):
    def __init__(
        self,
        provider: Provider,
        retry_policy: RetryPolicy,
        timeout_seconds: Optional[int] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
    ) -> None:
        self.provider = provider
        self.retry_policy = retry_policy
        self.timeout_seconds = timeout_seconds
        self.circuit_breaker = circuit_breaker

    def invoke(self, request: ProviderRequest) -> ProviderResponse:
        return self._invoke_with_retry(request, stream=request.stream)

    def invoke_stream(self, request: ProviderRequest) -> ProviderResponse:
        return self._invoke_with_retry(request, stream=True)

    def _invoke_with_retry(self, request: ProviderRequest, stream: bool) -> ProviderResponse:
        attempts = max(1, self.retry_policy.max_attempts)
        last_error: Optional[BaseException] = None
        for attempt in range(1, attempts + 1):
            if self.circuit_breaker:
                self.circuit_breaker.allow()
            try:
                call_request = self._apply_timeout(request)
                if stream:
                    response = self._invoke_stream(call_request)
                else:
                    response = self.provider.invoke(call_request)
                if self.circuit_breaker:
                    self.circuit_breaker.record_success()
                return response
            except Exception as exc:  # pragma: no cover - defensive
                last_error = exc
                if self.circuit_breaker:
                    self.circuit_breaker.record_failure()
                if attempt >= attempts or not _should_retry(exc):
                    if isinstance(exc, ProviderError):
                        raise
                    raise ProviderError(str(exc)) from exc
                delay = self.retry_policy.delay_for(attempt)
                if delay > 0:
                    time.sleep(delay)
        if isinstance(last_error, ProviderError):
            raise last_error
        raise ProviderError("Provider invocation failed") from last_error

    def _apply_timeout(self, request: ProviderRequest) -> ProviderRequest:
        timeout_seconds = request.timeout_seconds or self.timeout_seconds
        if timeout_seconds == request.timeout_seconds:
            return request
        return replace(request, timeout_seconds=timeout_seconds)

    def _invoke_stream(self, request: ProviderRequest) -> ProviderResponse:
        try:
            return self.provider.invoke_stream(request)
        except ProviderError as exc:
            if "Streaming not supported" not in str(exc):
                raise
        return self._fallback_stream(request)

    def _fallback_stream(self, request: ProviderRequest) -> ProviderResponse:
        fallback_request = replace(request, stream=False)
        response = self.provider.invoke(fallback_request)
        raw = dict(response.raw)
        raw["stream_fallback"] = True
        return ProviderResponse(content=response.content, raw=raw, chunks=[response.content])


def _should_retry(exc: BaseException) -> bool:
    return isinstance(exc, (ProviderError, TimeoutError, OSError))
