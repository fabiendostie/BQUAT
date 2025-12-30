from __future__ import annotations

import json
from typing import Any, Dict, Iterable, Optional, Tuple
from urllib import error as url_error
from urllib import request

from runtime.providers.base import ProviderError


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
    try:
        with request.urlopen(req, timeout=timeout_seconds) as resp:
            data = resp.read().decode("utf-8")
        return json.loads(data)
    except url_error.HTTPError as exc:
        payload_data, raw_text = _read_error_body(exc)
        message, error_type = parse_error_payload(payload_data, raw_text)
        retriable = _is_retriable_status(exc.code, error_type)
        raise ProviderError(
            message,
            status_code=exc.code,
            retriable=retriable,
            error_type=error_type,
        ) from exc
    except url_error.URLError as exc:
        raise ProviderError(str(exc), retriable=True) from exc


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
    try:
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
    except url_error.HTTPError as exc:
        payload_data, raw_text = _read_error_body(exc)
        message, error_type = parse_error_payload(payload_data, raw_text)
        retriable = _is_retriable_status(exc.code, error_type)
        raise ProviderError(
            message,
            status_code=exc.code,
            retriable=retriable,
            error_type=error_type,
        ) from exc
    except url_error.URLError as exc:
        raise ProviderError(str(exc), retriable=True) from exc


def parse_error_payload(payload: Optional[Dict[str, Any]], fallback: str = "") -> Tuple[str, str]:
    if not payload:
        message = fallback or "Provider request failed"
        return message, ""
    if "error" in payload:
        error = payload.get("error")
        if isinstance(error, dict):
            message = (
                error.get("message")
                or error.get("detail")
                or error.get("error")
                or fallback
                or "Provider request failed"
            )
            error_type = str(error.get("type") or error.get("code") or error.get("status") or "")
            return message, error_type
        if isinstance(error, str):
            return error, ""
        return str(error), ""
    if "errors" in payload and isinstance(payload["errors"], list) and payload["errors"]:
        first = payload["errors"][0]
        if isinstance(first, dict):
            message = (
                first.get("message") or first.get("detail") or fallback or "Provider request failed"
            )
            error_type = str(first.get("type") or first.get("code") or first.get("status") or "")
            return message, error_type
    if "message" in payload and isinstance(payload["message"], str):
        return payload["message"], ""
    return "", ""


def _is_retriable_status(status_code: Optional[int], error_type: str) -> bool:
    if status_code in {408, 425, 429, 500, 502, 503, 504}:
        return True
    lowered = error_type.lower()
    if not lowered:
        return False
    tokens = ("rate_limit", "resource_exhausted", "quota", "overloaded")
    return any(token in lowered for token in tokens)


def _read_error_body(exc: url_error.HTTPError) -> Tuple[Optional[Dict[str, Any]], str]:
    raw = ""
    try:
        raw_bytes = exc.read()
        if raw_bytes:
            raw = raw_bytes.decode("utf-8", errors="ignore")
    except Exception:  # pragma: no cover - defensive
        raw = ""
    finally:
        try:
            exc.close()
        except Exception:
            pass
    if not raw:
        return None, ""
    try:
        return json.loads(raw), raw
    except json.JSONDecodeError:
        return None, raw
