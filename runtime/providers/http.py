from __future__ import annotations

import json
from typing import Any, Dict, Iterable, Optional
from urllib import request


def post_json(
    url: str,
    payload: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None,
    timeout_seconds: int = 60,
) -> Dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    if headers:
        for key, value in headers.items():
            req.add_header(key, value)
    with request.urlopen(req, timeout=timeout_seconds) as resp:
        data = resp.read().decode("utf-8")
    return json.loads(data)


def post_json_stream(
    url: str,
    payload: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None,
    timeout_seconds: int = 60,
) -> Iterable[Dict[str, Any]]:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    if headers:
        for key, value in headers.items():
            req.add_header(key, value)
    with request.urlopen(req, timeout=timeout_seconds) as resp:
        for raw_line in resp:
            line = raw_line.decode("utf-8").strip()
            if not line:
                continue
            if line.startswith("event:"):
                continue
            if line.startswith("data:"):
                line = line[len("data:") :].strip()
            if line == "[DONE]":
                continue
            if not line.startswith("{") and not line.startswith("["):
                continue
            yield json.loads(line)
