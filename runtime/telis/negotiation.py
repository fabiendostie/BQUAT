from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

from runtime.telis import shards
from runtime.telis.context import (
    LspProvider,
    TelisContextRequest,
    TelisContextResult,
    resolve_context,
)

_DEFAULT_PHASE_TIERS = ["tier_1_nano", "tier_2_micro", "tier_3_full"]
_DEFAULT_UNCERTAINTY_MARKERS = (
    "not sure",
    "uncertain",
    "unclear",
    "need more",
    "need details",
    "missing context",
    "insufficient",
    "not enough",
    "ambiguous",
)


@dataclass(frozen=True)
class TelisNegotiationRequest:
    query: str
    language: str
    document_path: Optional[Path] = None
    document_text: Optional[str] = None
    line: int = 0
    character: int = 0
    method: str = "hover"
    shard_limit: Optional[int] = None
    min_score: int = 1
    max_phase: int = 3
    phase_tiers: Optional[List[str]] = None
    draft_response: str = ""
    uncertainty_markers: Optional[List[str]] = None
    signals: Optional[List[bool]] = None


@dataclass(frozen=True)
class TelisNegotiationPhase:
    phase: int
    tier: str
    reason: str
    context: TelisContextResult


@dataclass(frozen=True)
class TelisNegotiationResult:
    phases: List[TelisNegotiationPhase]
    final_context: TelisContextResult


ShouldEscalate = Callable[[int, TelisContextResult], bool]


def negotiate_context(
    request: TelisNegotiationRequest,
    registry: shards.ShardRegistry,
    policy: shards.TierBudgetPolicy,
    lsp_provider: Optional[LspProvider] = None,
    root: Optional[Path] = None,
    should_escalate: Optional[ShouldEscalate] = None,
) -> TelisNegotiationResult:
    tiers = list(request.phase_tiers or _DEFAULT_PHASE_TIERS)
    if not tiers:
        tiers = list(_DEFAULT_PHASE_TIERS)
    max_phase = max(1, min(request.max_phase, len(tiers)))
    phases: List[TelisNegotiationPhase] = []

    for idx in range(max_phase):
        phase = idx + 1
        tier = tiers[idx]
        ctx_request = TelisContextRequest(
            query=request.query,
            language=request.language,
            tier=tier,
            document_path=request.document_path,
            document_text=request.document_text,
            line=request.line,
            character=request.character,
            method=request.method,
            shard_limit=request.shard_limit,
            min_score=request.min_score,
        )
        ctx = resolve_context(ctx_request, registry, policy, lsp_provider=lsp_provider, root=root)
        reason = "initial" if phase == 1 else "escalated"
        phases.append(TelisNegotiationPhase(phase=phase, tier=tier, reason=reason, context=ctx))

        if phase == max_phase:
            break
        if should_escalate:
            escalate = should_escalate(phase, ctx)
        else:
            escalate = _should_escalate(request, phase)
        if not escalate:
            break

    return TelisNegotiationResult(phases=phases, final_context=phases[-1].context)


def _should_escalate(request: TelisNegotiationRequest, phase: int) -> bool:
    if request.signals and phase - 1 < len(request.signals):
        return bool(request.signals[phase - 1])
    text = request.draft_response or request.query
    markers = request.uncertainty_markers or list(_DEFAULT_UNCERTAINTY_MARKERS)
    return detect_uncertainty(text, markers)


def detect_uncertainty(text: str, markers: List[str]) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in markers)
