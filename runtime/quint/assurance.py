from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from runtime import models

_CONGRUENCE_FACTORS = {
    "CL1": 0.5,
    "CL2": 0.8,
    "CL3": 1.0,
}


@dataclass(frozen=True)
class AssuranceResult:
    score: float
    weakest_id: Optional[str]


def normalize_congruence(level: str, default: str = "CL1") -> str:
    value = (level or "").strip().upper()
    if not value:
        return default
    if value in _CONGRUENCE_FACTORS:
        return value
    raise ValueError(f"unsupported congruence level: {level}")


def congruence_factor(level: str) -> float:
    return _CONGRUENCE_FACTORS[normalize_congruence(level)]


def apply_congruence_penalty(reliability: float, congruence: str) -> float:
    adjusted = _clamp_reliability(reliability) * congruence_factor(congruence)
    return round(adjusted, 6)


def wlnk_score(records: Iterable[models.EvidenceLink]) -> AssuranceResult:
    weakest_score = None
    weakest_id = None
    for record in records:
        score = apply_congruence_penalty(record.reliability, record.congruence)
        if weakest_score is None or score < weakest_score:
            weakest_score = score
            weakest_id = record.id
    if weakest_score is None:
        return AssuranceResult(score=0.0, weakest_id=None)
    return AssuranceResult(score=weakest_score, weakest_id=weakest_id)


def _clamp_reliability(value: float) -> float:
    try:
        raw = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, raw))
