import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from runtime.providers import http as http_mod
from runtime.providers.base import ProviderError


class DummyResponse:
    def __init__(self, payload: dict) -> None:
        self._data = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._data

    def __enter__(self) -> "DummyResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class DummyStreamResponse(DummyResponse):
    def __init__(self, lines: list[bytes]) -> None:
        self._lines = lines

    def __iter__(self):
        return iter(self._lines)


class RuntimeHttpTests(unittest.TestCase):
    @patch("runtime.providers.http.request.urlopen")
    def test_post_json_with_headers(self, urlopen_mock) -> None:
        urlopen_mock.return_value = DummyResponse({"ok": True})
        data = http_mod.post_json("http://example", {"a": 1}, {"X-Test": "1"})
        self.assertEqual(data, {"ok": True})
        req = urlopen_mock.call_args[0][0]
        headers = {key.lower(): value for key, value in req.header_items()}
        self.assertEqual(headers.get("x-test"), "1")

    @patch("runtime.providers.http.request.urlopen")
    def test_post_json_no_headers(self, urlopen_mock) -> None:
        urlopen_mock.return_value = DummyResponse({"ok": True})
        data = http_mod.post_json("http://example", {"a": 1})
        self.assertEqual(data, {"ok": True})
        req = urlopen_mock.call_args[0][0]
        headers = {key.lower(): value for key, value in req.header_items()}
        self.assertEqual(headers.get("content-type"), "application/json")

    @patch("runtime.providers.http.request.urlopen")
    def test_post_json_stream_parses_lines(self, urlopen_mock) -> None:
        urlopen_mock.return_value = DummyStreamResponse(
            [
                b'data: {"chunk": 1}\n',
                b"\n",
                b'data: {"chunk": 2}\n',
                b"data: [DONE]\n",
            ]
        )
        chunks = list(http_mod.post_json_stream("http://example", {"a": 1}))
        self.assertEqual(chunks, [{"chunk": 1}, {"chunk": 2}])

    @patch("runtime.providers.http.request.urlopen")
    def test_post_json_http_error_rate_limit(self, urlopen_mock) -> None:
        payload = {"error": {"message": "Rate limited", "type": "rate_limit_error"}}
        body = io.BytesIO(json.dumps(payload).encode("utf-8"))
        urlopen_mock.side_effect = HTTPError("http://example", 429, "Too Many", {}, body)
        with self.assertRaises(ProviderError) as ctx:
            http_mod.post_json("http://example", {"a": 1})
        self.assertEqual(ctx.exception.status_code, 429)
        self.assertTrue(ctx.exception.retriable)
        self.assertEqual(ctx.exception.error_type, "rate_limit_error")

    @patch("runtime.providers.http.request.urlopen")
    def test_post_json_http_error_non_retriable(self, urlopen_mock) -> None:
        payload = {"error": {"message": "Bad request", "type": "invalid_request_error"}}
        body = io.BytesIO(json.dumps(payload).encode("utf-8"))
        urlopen_mock.side_effect = HTTPError("http://example", 400, "Bad Request", {}, body)
        with self.assertRaises(ProviderError) as ctx:
            http_mod.post_json("http://example", {"a": 1})
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertFalse(ctx.exception.retriable)


if __name__ == "__main__":
    unittest.main()
