from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from runtime import config as runtime_config
from runtime.telis import cache as telis_cache
from runtime.telis import context as telis_context
from runtime.telis import negotiation as telis_negotiation
from runtime.telis import shards
from runtime.tools import file_io

_POLICY_DEFAULT_TIERS = ["tier_1_nano", "tier_2_micro", "tier_3_full"]
_LANGUAGE_ALIASES = {
    "py": "python",
    "python": "python",
    "js": "javascript",
    "javascript": "javascript",
    "ts": "typescript",
    "typescript": "typescript",
    "json": "json",
    "yaml": "yaml",
    "yml": "yaml",
    "md": "markdown",
    "markdown": "markdown",
}
_EXTENSION_LANGUAGE = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".md": "markdown",
}


@dataclass(frozen=True)
class TelisPolicy:
    policy: str
    tiers: List[str]
    progressive: bool
    use_lsp: bool
    max_phase: int


def parse_policy(policy: str) -> TelisPolicy:
    normalized = (policy or "").strip().lower()
    tiers: List[str] = []
    if "tier 1" in normalized:
        tiers.append("tier_1_nano")
    if "tier 2" in normalized:
        tiers.append("tier_2_micro")
    if "tier 3" in normalized:
        tiers.append("tier_3_full")
    if not tiers:
        tiers = ["tier_1_nano"]
    progressive = (
        "progressive" in normalized or "negotiation" in normalized or "on demand" in normalized
    )
    if progressive and len(tiers) == 1:
        tier = tiers[0]
        if tier in _POLICY_DEFAULT_TIERS:
            start = _POLICY_DEFAULT_TIERS.index(tier)
            tiers = _POLICY_DEFAULT_TIERS[start:]
    use_lsp = "lsp" in normalized
    max_phase = max(1, len(tiers))
    return TelisPolicy(
        policy=policy,
        tiers=tiers,
        progressive=progressive,
        use_lsp=use_lsp,
        max_phase=max_phase,
    )


class TelisPolicyEngine:
    def __init__(
        self,
        registry: Optional[shards.ShardRegistry] = None,
        policy: Optional[shards.TierBudgetPolicy] = None,
        cache: Optional[telis_cache.BehavioralCache] = None,
        lsp_provider: Optional[telis_context.LspProvider] = None,
        root: Optional[Path] = None,
        enabled: bool = True,
        cache_enabled: bool = True,
    ) -> None:
        self.registry = registry or shards.ShardRegistry()
        self.policy = policy or shards.default_tier_budgets()
        self.cache = cache
        self.lsp_provider = lsp_provider
        self.root = (root or runtime_config.project_root_from_here()).resolve()
        self.enabled = enabled
        self.cache_enabled = cache_enabled

    @classmethod
    def from_config(
        cls,
        config: Dict[str, Any],
        registry: Optional[shards.ShardRegistry] = None,
        lsp_provider: Optional[telis_context.LspProvider] = None,
        root: Optional[Path] = None,
    ) -> Optional["TelisPolicyEngine"]:
        telis_cfg = dict(config.get("telis", {}))
        if not telis_cfg.get("enabled", True):
            return None
        cache_enabled = telis_cfg.get("cache_enabled", True)
        cache_ttl = telis_cfg.get("cache_ttl_seconds")
        cache = None
        if cache_enabled:
            cache = telis_cache.BehavioralCache(
                ttl_seconds=int(cache_ttl) if cache_ttl is not None else 60 * 60 * 24 * 7
            )
        registry = registry or _load_registry(telis_cfg)
        policy = _load_budget_policy(telis_cfg)
        return cls(
            registry=registry,
            policy=policy,
            cache=cache,
            lsp_provider=lsp_provider,
            root=root,
            enabled=True,
            cache_enabled=cache_enabled,
        )

    def resolve_for_step(
        self,
        step: Dict[str, Any],
        step_spec: Optional[Any],
        manifest: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        if not self.enabled:
            return None
        policy_text = str(manifest.get("workflow", {}).get("telis", "")).strip()
        if not policy_text or policy_text.lower() in {"none", "n/a", "na"}:
            return None
        inputs = _merge_inputs(step, step_spec)
        if inputs.get("telis_enabled") is False:
            return None
        telis_policy = parse_policy(policy_text)
        query = _first_string(inputs, ["telis_query", "query", "goal", "task"])
        if not query:
            query = _fallback_query(step, step_spec, manifest)
        language = _normalize_language(
            _first_string(inputs, ["telis_language", "language", "lang"])
        )
        if not language:
            language = _infer_language(step, step_spec)
        if not query or not language:
            return None

        method = _first_string(inputs, ["telis_method", "lsp_method"]) or "hover"
        line = int(_first_int(inputs, ["telis_line", "line"], default=0) or 0)
        character = int(_first_int(inputs, ["telis_character", "character"], default=0) or 0)
        shard_limit = _first_int(inputs, ["telis_shard_limit", "shard_limit"], default=None)
        min_score = int(_first_int(inputs, ["telis_min_score", "min_score"], default=1) or 1)
        doc_path = _resolve_document_path(
            _first_string(inputs, ["telis_document_path", "document_path", "file"])
        )
        doc_text = _first_string(inputs, ["telis_document_text", "document_text"])
        cache_key = _cache_key(
            query,
            language,
            telis_policy.tiers,
            method,
            doc_path,
            doc_text,
        )

        if self.cache and self.cache_enabled:
            cached = self.cache.get(cache_key)
            if cached:
                phases_raw = cached.metadata.get("phases", [])
                phases = list(phases_raw) if isinstance(phases_raw, list) else []
                return {
                    "policy": policy_text,
                    "query": query,
                    "language": language,
                    "tiers": telis_policy.tiers,
                    "progressive": telis_policy.progressive,
                    "source": cached.metadata.get("source", "cache"),
                    "used_fallback": bool(cached.metadata.get("used_fallback")),
                    "context": cached.response,
                    "cached": True,
                    "cache_key": cache_key,
                    "metadata": dict(cached.metadata),
                    "phases": phases,
                }

        lsp_provider = self.lsp_provider if telis_policy.use_lsp else None
        if telis_policy.progressive:
            phase_tiers_raw = _first_list(inputs, ["telis_phase_tiers"], default=None)
            phase_tiers = (
                [str(item) for item in phase_tiers_raw]
                if phase_tiers_raw
                else list(telis_policy.tiers)
            )
            max_phase_default = len(phase_tiers) if phase_tiers else telis_policy.max_phase
            max_phase = int(
                _first_int(inputs, ["telis_max_phase"], default=max_phase_default)
                or max_phase_default
            )
            negotiation_request = telis_negotiation.TelisNegotiationRequest(
                query=query,
                language=language,
                document_path=doc_path,
                document_text=doc_text,
                line=line,
                character=character,
                method=method,
                shard_limit=shard_limit,
                min_score=min_score,
                max_phase=max_phase,
                phase_tiers=phase_tiers,
                draft_response=_first_string(inputs, ["telis_draft_response"], default=""),
                uncertainty_markers=_first_list(
                    inputs, ["telis_uncertainty_markers"], default=None
                ),
                signals=_first_list(inputs, ["telis_signals"], default=None),
            )
            negotiation = telis_negotiation.negotiate_context(
                negotiation_request,
                self.registry,
                self.policy,
                lsp_provider=lsp_provider,
                root=self.root,
            )
            result = _result_from_negotiation(policy_text, telis_policy, negotiation)
        else:
            context_request = telis_context.TelisContextRequest(
                query=query,
                language=language,
                tier=telis_policy.tiers[0],
                document_path=doc_path,
                document_text=doc_text,
                line=line,
                character=character,
                method=method,
                shard_limit=shard_limit,
                min_score=min_score,
            )
            ctx = telis_context.resolve_context(
                context_request,
                self.registry,
                self.policy,
                lsp_provider=lsp_provider,
                root=self.root,
            )
            result = _result_from_context(policy_text, telis_policy, ctx)

        if self.cache and self.cache_enabled:
            metadata = dict(result.get("metadata", {}))
            metadata.update(
                {
                    "source": result.get("source"),
                    "used_fallback": result.get("used_fallback"),
                    "phases": result.get("phases", []),
                    "language": language,
                }
            )
            self.cache.set(cache_key, result.get("context", ""), metadata=metadata)
            result["cache_key"] = cache_key

        result.update(
            {
                "policy": policy_text,
                "query": query,
                "language": language,
                "tiers": telis_policy.tiers,
                "progressive": telis_policy.progressive,
                "cached": False,
            }
        )
        return result


def _load_budget_policy(config: Dict[str, Any]) -> shards.TierBudgetPolicy:
    budgets = config.get("tier_budgets")
    if isinstance(budgets, dict):
        parsed = {str(key): int(value) for key, value in budgets.items()}
        return shards.TierBudgetPolicy(budgets=parsed)
    return shards.default_tier_budgets()


def _load_registry(config: Dict[str, Any]) -> shards.ShardRegistry:
    records: Iterable[Dict[str, object]] = []
    if isinstance(config.get("shards"), list):
        records = config.get("shards", [])
    elif isinstance(config.get("shards_path"), str):
        records = _load_shards_path(str(config.get("shards_path")))
    return shards.ShardRegistry.from_records(list(records))


def _load_shards_path(path: str) -> List[Dict[str, object]]:
    target = Path(path)
    if not target.is_absolute():
        target = runtime_config.project_root_from_here() / target
    if not target.exists():
        return []
    try:
        payload = json.loads(target.read_text(encoding="ascii"))
    except json.JSONDecodeError:
        return []
    if isinstance(payload, dict):
        if isinstance(payload.get("shards"), list):
            return payload.get("shards", [])
        if isinstance(payload.get("records"), list):
            return payload.get("records", [])
    if isinstance(payload, list):
        return payload
    return []


def _merge_inputs(step: Dict[str, Any], step_spec: Optional[Any]) -> Dict[str, Any]:
    merged: Dict[str, Any] = {}
    if step_spec is not None and hasattr(step_spec, "inputs"):
        merged.update(getattr(step_spec, "inputs"))
    merged.update(step.get("inputs", {}) or {})
    return merged


def _first_string(inputs: Dict[str, Any], keys: Sequence[str], default: str = "") -> str:
    for key in keys:
        value = inputs.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return default


def _first_int(
    inputs: Dict[str, Any], keys: Sequence[str], default: Optional[int] = None
) -> Optional[int]:
    for key in keys:
        value = inputs.get(key)
        if isinstance(value, (int, float, str)):
            try:
                return int(value)
            except (TypeError, ValueError):
                continue
    return default


def _first_list(
    inputs: Dict[str, Any], keys: Sequence[str], default: Optional[List[Any]]
) -> Optional[List[Any]]:
    for key in keys:
        value = inputs.get(key)
        if isinstance(value, list):
            return list(value)
    return default


def _fallback_query(
    step: Dict[str, Any], step_spec: Optional[Any], manifest: Dict[str, Any]
) -> str:
    if step_spec is not None:
        description = getattr(step_spec, "description", "")
        if description:
            return str(description)
        name = getattr(step_spec, "name", "")
        if name:
            return str(name)
    if step.get("name"):
        return str(step.get("name"))
    workflow = manifest.get("workflow", {})
    return str(workflow.get("workflow", ""))


def _normalize_language(language: str) -> str:
    value = (language or "").strip().lower()
    if not value:
        return ""
    return _LANGUAGE_ALIASES.get(value, value)


def _infer_language(step: Dict[str, Any], step_spec: Optional[Any]) -> str:
    outputs: List[str] = []
    if step_spec is not None and hasattr(step_spec, "outputs"):
        outputs.extend(getattr(step_spec, "outputs"))
    outputs.extend(step.get("outputs", []) or [])
    for output in outputs:
        if not isinstance(output, str) or not output:
            continue
        suffix = Path(output.replace("template:", "")).suffix.lower()
        if suffix in _EXTENSION_LANGUAGE:
            return _EXTENSION_LANGUAGE[suffix]
    return ""


def _resolve_document_path(raw: str) -> Optional[Path]:
    if not raw:
        return None
    try:
        resolved = file_io.resolve_path(raw)
    except ValueError:
        return None
    if not resolved.exists() or not resolved.is_file():
        return None
    return resolved


def _cache_key(
    query: str,
    language: str,
    tiers: Sequence[str],
    method: str,
    document_path: Optional[Path],
    document_text: Optional[str],
) -> str:
    basis = [language, method, ",".join(tiers), query]
    if document_path:
        basis.append(str(document_path))
    if document_text:
        digest = hashlib.sha256(document_text.encode("utf-8")).hexdigest()[:12]
        basis.append(digest)
    return "::".join(basis)


def _result_from_context(
    policy_text: str,
    telis_policy: TelisPolicy,
    ctx: telis_context.TelisContextResult,
) -> Dict[str, Any]:
    metadata = {}
    if ctx.shard_result:
        metadata = {
            "tokens_selected": ctx.shard_result.tokens_selected,
            "budget_tokens": ctx.shard_result.budget_tokens,
            "shard_ids": [shard.shard_id for shard in ctx.shard_result.shards],
        }
    return {
        "policy": policy_text,
        "source": ctx.source,
        "used_fallback": ctx.used_fallback,
        "context": ctx.content,
        "phases": [
            {
                "phase": 1,
                "tier": telis_policy.tiers[0],
                "source": ctx.source,
                "used_fallback": ctx.used_fallback,
                "context": ctx.content,
            }
        ],
        "metadata": metadata,
    }


def _result_from_negotiation(
    policy_text: str,
    telis_policy: TelisPolicy,
    negotiation: telis_negotiation.TelisNegotiationResult,
) -> Dict[str, Any]:
    phases: List[Dict[str, Any]] = []
    shard_ids: List[str] = []
    tokens_selected = 0
    budget_tokens = 0
    for phase in negotiation.phases:
        ctx = phase.context
        phases.append(
            {
                "phase": phase.phase,
                "tier": phase.tier,
                "source": ctx.source,
                "used_fallback": ctx.used_fallback,
                "context": ctx.content,
                "reason": phase.reason,
            }
        )
        if ctx.shard_result:
            budget_tokens = max(budget_tokens, ctx.shard_result.budget_tokens)
            tokens_selected = max(tokens_selected, ctx.shard_result.tokens_selected)
            shard_ids.extend([shard.shard_id for shard in ctx.shard_result.shards])
    metadata = {
        "tokens_selected": tokens_selected,
        "budget_tokens": budget_tokens,
        "shard_ids": shard_ids,
    }
    final_ctx = negotiation.final_context
    return {
        "policy": policy_text,
        "source": final_ctx.source,
        "used_fallback": final_ctx.used_fallback,
        "context": final_ctx.content,
        "phases": phases,
        "metadata": metadata,
    }
