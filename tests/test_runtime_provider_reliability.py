import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.providers.base import (  # noqa: E402
    Provider,
    ProviderError,
    ProviderRequest,
    ProviderResponse,
)
from runtime.providers.reliability import (  # noqa: E402
    CircuitBreaker,
    ReliableProvider,
    RetryPolicy,
)


class FlakyProvider(Provider):
    def __init__(self, fail_times: int) -> None:
        self.fail_times = fail_times
        self.calls = 0

    def invoke(self, request: ProviderRequest) -> ProviderResponse:
        self.calls += 1
        if self.calls <= self.fail_times:
            raise ProviderError("transient failure")
        return ProviderResponse(content="ok", raw={"calls": self.calls})


class RecordingProvider(Provider):
    def __init__(self) -> None:
        self.last_request: ProviderRequest | None = None

    def invoke(self, request: ProviderRequest) -> ProviderResponse:
        self.last_request = request
        return ProviderResponse(content="ok", raw={})


class RuntimeProviderReliabilityTests(unittest.TestCase):
    def test_retries_then_success(self) -> None:
        provider = FlakyProvider(fail_times=1)
        retry_policy = RetryPolicy(max_attempts=2, backoff_seconds=0.0, jitter_seconds=0.0)
        reliable = ReliableProvider(provider, retry_policy=retry_policy)
        response = reliable.invoke(ProviderRequest(model="", messages=[]))
        self.assertEqual(response.content, "ok")
        self.assertEqual(provider.calls, 2)

    def test_circuit_breaker_opens(self) -> None:
        clock = [0.0]

        def _now() -> float:
            return clock[0]

        provider = FlakyProvider(fail_times=10)
        retry_policy = RetryPolicy(max_attempts=1, backoff_seconds=0.0, jitter_seconds=0.0)
        breaker = CircuitBreaker(failure_threshold=2, reset_seconds=30.0, time_provider=_now)
        reliable = ReliableProvider(provider, retry_policy=retry_policy, circuit_breaker=breaker)

        with self.assertRaises(ProviderError):
            reliable.invoke(ProviderRequest(model="", messages=[]))
        with self.assertRaises(ProviderError):
            reliable.invoke(ProviderRequest(model="", messages=[]))

        with self.assertRaises(ProviderError) as ctx:
            reliable.invoke(ProviderRequest(model="", messages=[]))
        self.assertIn("Circuit breaker open", str(ctx.exception))
        self.assertEqual(provider.calls, 2)

    def test_stream_fallback(self) -> None:
        provider = RecordingProvider()
        retry_policy = RetryPolicy(max_attempts=1)
        reliable = ReliableProvider(provider, retry_policy=retry_policy)
        response = reliable.invoke_stream(ProviderRequest(model="", messages=[], stream=True))
        self.assertEqual(response.chunks, ["ok"])
        self.assertTrue(response.raw.get("stream_fallback"))

    def test_timeout_injection(self) -> None:
        provider = RecordingProvider()
        retry_policy = RetryPolicy(max_attempts=1)
        reliable = ReliableProvider(provider, retry_policy=retry_policy, timeout_seconds=12)
        reliable.invoke(ProviderRequest(model="", messages=[]))
        self.assertIsNotNone(provider.last_request)
        self.assertEqual(provider.last_request.timeout_seconds, 12)


if __name__ == "__main__":
    unittest.main()
