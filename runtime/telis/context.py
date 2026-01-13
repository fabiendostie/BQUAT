from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from runtime import config as runtime_config
from runtime.telis import shards
from runtime.tools import lsp

LspProvider = Callable[["TelisContextRequest"], Dict[str, Any]]


@dataclass(frozen=True)
class TelisContextRequest:
    query: str
    language: str
    tier: str
    document_path: Optional[Path] = None
    document_text: Optional[str] = None
    line: int = 0
    character: int = 0
    method: str = "hover"
    shard_limit: Optional[int] = None
    min_score: int = 1


@dataclass(frozen=True)
class TelisContextResult:
    source: str
    content: str
    used_fallback: bool
    lsp_payload: Optional[Dict[str, Any]]
    shard_result: Optional[shards.ShardSearchResult]


def resolve_context(
    request: TelisContextRequest,
    registry: shards.ShardRegistry,
    policy: shards.TierBudgetPolicy,
    lsp_provider: Optional[LspProvider] = None,
    root: Optional[Path] = None,
) -> TelisContextResult:
    payload = None
    if lsp_provider:
        payload = _call_lsp_provider(lsp_provider, request)
    else:
        payload = _try_lsp(request, root)

    if payload:
        content = _compress_lsp_payload(request.method, payload)
        if content:
            return TelisContextResult(
                source="lsp",
                content=content,
                used_fallback=False,
                lsp_payload=payload,
                shard_result=None,
            )

    shard_result = registry.select_for_policy(
        request.query,
        request.language,
        request.tier,
        policy,
        limit=request.shard_limit,
        min_score=request.min_score,
    )
    content = "\n".join([shard.content for shard in shard_result.shards])
    return TelisContextResult(
        source="shards",
        content=content,
        used_fallback=True,
        lsp_payload=payload,
        shard_result=shard_result,
    )


def _call_lsp_provider(
    provider: LspProvider, request: TelisContextRequest
) -> Optional[Dict[str, Any]]:
    try:
        return provider(request)
    except Exception:
        return None


def _try_lsp(request: TelisContextRequest, root: Optional[Path]) -> Optional[Dict[str, Any]]:
    document_path = request.document_path
    document_text = request.document_text
    if not document_path and not document_text:
        return None
    try:
        config = lsp.build_server_config(request.language, root=root)
    except ValueError:
        return None
    if document_path:
        text = document_path.read_text(encoding="utf-8", errors="ignore")
        uri = lsp.file_uri(document_path)
        language_id = request.language
    else:
        text = document_text or ""
        uri = lsp.file_uri(_temp_document_path(root, request.language))
        language_id = request.language
    with lsp.LspClient(config) as client:
        client.open_document(uri, language_id, text)
        if request.method == "signatureHelp":
            return client.signature_help(uri, request.line, request.character)
        return client.hover(uri, request.line, request.character)


def _temp_document_path(root: Optional[Path], language: str) -> Path:
    base = (root or runtime_config.project_root_from_here()).resolve()
    suffix = ".txt"
    if language == "python":
        suffix = ".py"
    if language in {"typescript", "javascript"}:
        suffix = ".ts"
    return base / f"_telis_temp{suffix}"


def _compress_lsp_payload(method: str, payload: Dict[str, Any]) -> str:
    result = payload.get("result")
    if result is None:
        return ""
    if method == "signatureHelp":
        return _compress_signature_help(result)
    return _compress_hover(result)


def _compress_hover(result: Dict[str, Any]) -> str:
    if not isinstance(result, dict):
        return ""
    contents = result.get("contents")
    if isinstance(contents, str):
        return contents.strip()
    if isinstance(contents, dict):
        value = contents.get("value")
        if isinstance(value, str):
            return value.strip()
    if isinstance(contents, list):
        parts = []
        for item in contents:
            if isinstance(item, str):
                parts.append(item.strip())
            elif isinstance(item, dict):
                value = item.get("value")
                if isinstance(value, str):
                    parts.append(value.strip())
        return "\n".join([part for part in parts if part])
    return ""


def _compress_signature_help(result: Dict[str, Any]) -> str:
    signatures = result.get("signatures", [])
    if not isinstance(signatures, list) or not signatures:
        return ""
    signature = signatures[0]
    if isinstance(signature, dict):
        label = signature.get("label")
        if isinstance(label, str):
            return label.strip()
    return ""
