from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Set

from runtime import models

_CONGRUENCE_FACTORS = {
    "CL1": 0.5,
    "CL2": 0.8,
    "CL3": 1.0,
}


@dataclass(frozen=True)
class AssuranceResult:
    reliability: float
    formality: str
    scope: List[str]
    weakest_id: Optional[str]


def normalize_congruence(level: str, default: str = "CL1") -> str:
    value = (level or "").strip().upper()
    if not value:
        return default
    if value in _CONGRUENCE_FACTORS:
        return value
    if value == "CL0":
        return "CL1"
    return default


def normalize_formality(level: str, default: str = "F0") -> str:
    value = (level or "").strip().upper()
    if not value or not value.startswith("F"):
        return default
    try:
        int(value[1:])
        return value
    except (ValueError, TypeError):
        return default


def congruence_factor(level: str) -> float:
    return _CONGRUENCE_FACTORS.get(normalize_congruence(level), 0.5)


def apply_congruence_penalty(reliability: float, congruence: str) -> float:
    # Pattern B.1.3: Adjusted reliability = Reliability * Phi(CL)
    adjusted = _clamp_reliability(reliability) * congruence_factor(congruence)
    return round(adjusted, 6)


def wlnk_score(records: Iterable[models.EvidenceLink]) -> AssuranceResult:
    weakest_reliability = None
    weakest_id = None
    min_f_num = None
    min_f_str = "F0"
    common_scope: Optional[Set[str]] = None

    for record in records:
        # Reliability (R) - Weakest link
        score = apply_congruence_penalty(record.reliability, record.congruence)
        if weakest_reliability is None or score < weakest_reliability:
            weakest_reliability = score
            weakest_id = record.id

        # Formality (F) - min(F) weakest link principle
        f_str = normalize_formality(record.formality)
        try:
            f_num = int(f_str[1:])
            if min_f_num is None or f_num < min_f_num:
                min_f_num = f_num
                min_f_str = f_str
        except (ValueError, IndexError):
            if min_f_num is None:
                min_f_num = 0
                min_f_str = "F0"

        # ClaimScope (G) - Intersection for serial dependency chain
        # (Assuming wlnk over a set of dependencies implies serial integration for validity)
        record_scope = set(record.scope)
        if common_scope is None:
            common_scope = record_scope
        else:
            common_scope = common_scope.intersection(record_scope)

    if weakest_reliability is None:
        return AssuranceResult(reliability=0.0, formality="F0", scope=[], weakest_id=None)

    return AssuranceResult(
        reliability=weakest_reliability,
        formality=min_f_str,
        scope=sorted(list(common_scope)) if common_scope is not None else [],
        weakest_id=weakest_id,
    )


def _clamp_reliability(value: float) -> float:
    try:
        raw = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, raw))
