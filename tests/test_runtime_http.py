import json
import unittest
from unittest.mock import patch

from runtime.providers import http as http_mod


class DummyResponse:
    def __init__(self, payload: dict) -> None:
        self._data = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._data

    def __enter__(self) -> "DummyResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


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


if __name__ == "__main__":
    unittest.main()
