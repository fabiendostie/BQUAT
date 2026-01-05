"""Context fingerprint tracking for QUINT evidence (REQ-SPEC-009).

A context fingerprint captures the state of context resolution at a point in time,
enabling traceability of what information was available when decisions were made.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from runtime import storage
from runtime.time_provider import get_current_time


@dataclass(frozen=True)
class LspCall:
    """Record of an LSP method invocation during context resolution."""

    method: str
    language: str
    line: int
    character: int
    document_path: Optional[str] = None
    result_type: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "method": self.method,
            "language": self.language,
            "line": self.line,
            "character": self.character,
            "document_path": self.document_path,
            "result_type": self.result_type,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> LspCall:
        return cls(
            method=data.get("method", ""),
            language=data.get("language", ""),
            line=int(data.get("line", 0)),
            character=int(data.get("character", 0)),
            document_path=data.get("document_path"),
            result_type=data.get("result_type", ""),
        )


@dataclass(frozen=True)
class ContextFingerprint:
    """Fingerprint of context state at a point in time.

    Captures which shards, LSP calls, and cache keys were involved
    in resolving context for a step.
    """

    fingerprint_id: str
    step_id: str
    shard_ids: tuple[str, ...] = field(default_factory=tuple)
    lsp_calls: tuple[LspCall, ...] = field(default_factory=tuple)
    token_budget_used: int = 0
    token_budget_total: int = 0
    cache_keys: tuple[str, ...] = field(default_factory=tuple)
    policy_hash: str = ""
    query: str = ""
    language: str = ""
    created_at: str = ""

    def __post_init__(self) -> None:
        if isinstance(self.shard_ids, list):
            object.__setattr__(self, "shard_ids", tuple(self.shard_ids))
        if isinstance(self.lsp_calls, list):
            object.__setattr__(self, "lsp_calls", tuple(self.lsp_calls))
        if isinstance(self.cache_keys, list):
            object.__setattr__(self, "cache_keys", tuple(self.cache_keys))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fingerprint_id": self.fingerprint_id,
            "step_id": self.step_id,
            "shard_ids": list(self.shard_ids),
            "lsp_calls": [call.to_dict() for call in self.lsp_calls],
            "token_budget_used": self.token_budget_used,
            "token_budget_total": self.token_budget_total,
            "cache_keys": list(self.cache_keys),
            "policy_hash": self.policy_hash,
            "query": self.query,
            "language": self.language,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ContextFingerprint:
        lsp_calls_raw = data.get("lsp_calls", [])
        lsp_calls = tuple(LspCall.from_dict(item) for item in lsp_calls_raw)
        return cls(
            fingerprint_id=data.get("fingerprint_id", ""),
            step_id=data.get("step_id", ""),
            shard_ids=tuple(data.get("shard_ids", [])),
            lsp_calls=lsp_calls,
            token_budget_used=int(data.get("token_budget_used", 0)),
            token_budget_total=int(data.get("token_budget_total", 0)),
            cache_keys=tuple(data.get("cache_keys", [])),
            policy_hash=data.get("policy_hash", ""),
            query=data.get("query", ""),
            language=data.get("language", ""),
            created_at=data.get("created_at", ""),
        )

    def compute_hash(self) -> str:
        """Compute a deterministic hash of the fingerprint content."""
        basis = [
            self.step_id,
            ",".join(sorted(self.shard_ids)),
            ",".join(sorted(self.cache_keys)),
            self.policy_hash,
            self.query,
            self.language,
        ]
        content = "::".join(basis)
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def build_fingerprint(
    step_id: str,
    shard_ids: Optional[List[str]] = None,
    lsp_calls: Optional[List[LspCall]] = None,
    token_budget_used: int = 0,
    token_budget_total: int = 0,
    cache_keys: Optional[List[str]] = None,
    policy_hash: str = "",
    query: str = "",
    language: str = "",
) -> ContextFingerprint:
    """Build a context fingerprint with auto-generated ID and timestamp."""
    timestamp = get_current_time()
    fingerprint_id = f"fp-{uuid4().hex[:8]}"
    return ContextFingerprint(
        fingerprint_id=fingerprint_id,
        step_id=step_id,
        shard_ids=tuple(shard_ids or []),
        lsp_calls=tuple(lsp_calls or []),
        token_budget_used=token_budget_used,
        token_budget_total=token_budget_total,
        cache_keys=tuple(cache_keys or []),
        policy_hash=policy_hash,
        query=query,
        language=language,
        created_at=timestamp,
    )


def fingerprint_from_telis_result(
    step_id: str,
    telis_result: Dict[str, Any],
    lsp_calls: Optional[List[LspCall]] = None,
) -> ContextFingerprint:
    """Build a context fingerprint from a TELIS resolution result."""
    metadata = telis_result.get("metadata", {})
    shard_ids = metadata.get("shard_ids", [])
    tokens_used = metadata.get("tokens_selected", 0)
    tokens_total = metadata.get("budget_tokens", 0)
    cache_key = telis_result.get("cache_key", "")
    cache_keys = [cache_key] if cache_key else []
    policy = telis_result.get("policy", "")
    policy_hash = hashlib.sha256(policy.encode("utf-8")).hexdigest()[:12] if policy else ""
    query = telis_result.get("query", "")
    language = telis_result.get("language", "")
    if lsp_calls is None:
        raw_calls = telis_result.get("lsp_calls") or metadata.get("lsp_calls", [])
        if isinstance(raw_calls, list):
            lsp_calls = [LspCall.from_dict(item) for item in raw_calls if isinstance(item, dict)]
        else:
            lsp_calls = []

    return build_fingerprint(
        step_id=step_id,
        shard_ids=shard_ids,
        lsp_calls=lsp_calls,
        token_budget_used=tokens_used,
        token_budget_total=tokens_total,
        cache_keys=cache_keys,
        policy_hash=policy_hash,
        query=query,
        language=language,
    )


class FingerprintStore:
    """Store for context fingerprints within a run directory."""

    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir

    def _read_fingerprints(self) -> Dict[str, Any]:
        """Read fingerprints from storage."""
        path = self.run_dir / "context-fingerprints.json"
        if not path.exists():
            return {"fingerprints": [], "updated_at": ""}
        return storage.read_json(path)

    def _write_fingerprints(self, payload: Dict[str, Any]) -> None:
        """Write fingerprints to storage."""
        path = self.run_dir / "context-fingerprints.json"
        payload["updated_at"] = get_current_time()
        storage.write_json(path, payload)

    def list(self) -> List[Dict[str, Any]]:
        """List all fingerprints in this run."""
        payload = self._read_fingerprints()
        fingerprints = payload.get("fingerprints", [])
        if isinstance(fingerprints, list):
            return [dict(item) for item in fingerprints]
        return []

    def record(self, fingerprint: ContextFingerprint) -> Dict[str, Any]:
        """Record a new fingerprint."""
        payload = self._read_fingerprints()
        fingerprints = payload.get("fingerprints", [])
        if not isinstance(fingerprints, list):
            fingerprints = []
        rendered = fingerprint.to_dict()
        fingerprints.append(rendered)
        payload["fingerprints"] = fingerprints
        self._write_fingerprints(payload)
        storage.update_timeline(self.run_dir)
        return rendered

    def get(self, fingerprint_id: str) -> Optional[Dict[str, Any]]:
        """Get a fingerprint by ID."""
        for fp in self.list():
            if fp.get("fingerprint_id") == fingerprint_id:
                return fp
        return None

    def get_by_step(self, step_id: str) -> List[Dict[str, Any]]:
        """Get all fingerprints for a specific step."""
        return [fp for fp in self.list() if fp.get("step_id") == step_id]

    def get_latest_for_step(self, step_id: str) -> Optional[Dict[str, Any]]:
        """Get the most recent fingerprint for a step."""
        fingerprints = self.get_by_step(step_id)
        if not fingerprints:
            return None
        return max(fingerprints, key=lambda fp: fp.get("created_at", ""))
