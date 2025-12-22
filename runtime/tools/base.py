from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Literal, Optional, cast

RiskLevel = Literal["low", "medium", "high"]


def normalize_risk(value: Optional[str]) -> RiskLevel:
    if not value:
        return "low"
    normalized = value.strip().lower()
    if normalized in {"low", "medium", "high"}:
        return cast(RiskLevel, normalized)
    raise ValueError(f"Invalid risk level: {value}")


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: Dict[str, Any]
    risk: RiskLevel = "low"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolSpec":
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            parameters=dict(data.get("parameters", {})),
            risk=normalize_risk(data.get("risk")),
        )


@dataclass(frozen=True)
class ToolCall:
    name: str
    args: Dict[str, Any]
    required: bool = False
    risk: RiskLevel = "low"
    gate: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolCall":
        return cls(
            name=data["name"],
            args=dict(data.get("args", {})),
            required=bool(data.get("required", False)),
            risk=normalize_risk(data.get("risk")),
            gate=str(data.get("gate", "")),
        )
