from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from runtime import config as runtime_config
from runtime.time_provider import get_current_time
from runtime.tools import file_io

DEFAULT_PII_PATTERNS = {
    "email": r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
    "phone": r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b",
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
}

DEFAULT_MODERATION_BLOCKLIST = [
    "self-harm",
    "suicide",
    "bomb",
    "explosive",
    "hate speech",
    "kill",
]

DEFAULT_RULES_BLOCKLIST = [
    "drop table",
    "delete from",
    "truncate table",
    "rm -rf",
]

DEFAULT_RULES_REGEX = [
    r"\b(select|insert|update|delete)\b.+\bfrom\b.+\bwhere\b",
    r"\b(drop|truncate)\b\s+\btable\b",
]


@dataclass(frozen=True)
class GuardrailReport:
    stage: str
    status: str
    checked_at: str
    violations: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage": self.stage,
            "status": self.status,
            "checked_at": self.checked_at,
            "violations": [dict(item) for item in self.violations],
        }


class GuardrailViolation(RuntimeError):
    def __init__(self, report: GuardrailReport) -> None:
        message = f"guardrail failed ({report.stage})"
        if report.violations:
            detail = report.violations[0]
            message = f"{message}: {detail.get('type')} {detail.get('match')}".strip()
        super().__init__(message)
        self.report = report


def evaluate_guardrails(
    stage: str,
    step: Dict[str, Any],
    step_spec: Optional[Any],
    config: Dict[str, Any],
    run_dir: Path,
) -> Optional[GuardrailReport]:
    guardrails_cfg = config.get("guardrails", {})
    if not guardrails_cfg or not guardrails_cfg.get("enabled", True):
        return None
    stages = guardrails_cfg.get("stages", ["inputs", "outputs"])
    if stage not in stages:
        return None

    texts = _collect_texts(stage, step, step_spec, run_dir)
    violations: List[Dict[str, Any]] = []

    pii_cfg = guardrails_cfg.get("pii", {})
    if pii_cfg.get("enabled", True):
        patterns = _normalize_patterns(pii_cfg.get("patterns"), DEFAULT_PII_PATTERNS)
        _apply_regex(
            texts,
            patterns,
            "pii",
            violations,
            _max_hits(pii_cfg),
        )

    moderation_cfg = guardrails_cfg.get("moderation", {})
    if moderation_cfg.get("enabled", True):
        blocklist = _normalize_list(moderation_cfg.get("blocklist"), DEFAULT_MODERATION_BLOCKLIST)
        _apply_blocklist(
            texts,
            blocklist,
            "moderation",
            violations,
            _max_hits(moderation_cfg),
        )

    rules_cfg = guardrails_cfg.get("rules", {})
    if rules_cfg.get("enabled", True):
        blocklist = _normalize_list(rules_cfg.get("blocklist"), DEFAULT_RULES_BLOCKLIST)
        _apply_blocklist(
            texts,
            blocklist,
            "rules_blocklist",
            violations,
            _max_hits(rules_cfg),
        )
        patterns = _normalize_patterns(rules_cfg.get("regex"), DEFAULT_RULES_REGEX)
        _apply_regex(
            texts,
            patterns,
            "rules_regex",
            violations,
            _max_hits(rules_cfg),
        )

    status = "failed" if violations else "passed"
    return GuardrailReport(
        stage=stage,
        status=status,
        checked_at=get_current_time(),
        violations=violations,
    )


def enforce_guardrails(
    stage: str,
    step: Dict[str, Any],
    step_spec: Optional[Any],
    config: Dict[str, Any],
    run_dir: Path,
) -> Optional[GuardrailReport]:
    report = evaluate_guardrails(stage, step, step_spec, config, run_dir)
    if report and report.status == "failed":
        raise GuardrailViolation(report)
    return report


def _max_hits(cfg: Dict[str, Any]) -> int:
    try:
        value = int(cfg.get("max_hits", 3))
    except (TypeError, ValueError):
        value = 3
    return max(1, value)


def _normalize_list(value: Any, default: Sequence[str]) -> List[str]:
    if value is None:
        return list(default)
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str):
        return [value]
    return list(default)


def _normalize_patterns(value: Any, default: Any) -> Dict[str, str]:
    if value is None:
        if isinstance(default, dict):
            return {key: str(pattern) for key, pattern in default.items()}
        return {f"pattern_{idx}": str(item) for idx, item in enumerate(default)}
    if isinstance(value, dict):
        return {str(key): str(pattern) for key, pattern in value.items()}
    if isinstance(value, list):
        return {f"pattern_{idx}": str(pattern) for idx, pattern in enumerate(value)}
    if isinstance(value, str):
        return {"pattern": value}
    return {f"pattern_{idx}": str(item) for idx, item in enumerate(default)}


def _apply_regex(
    texts: List[Tuple[str, str]],
    patterns: Dict[str, str],
    violation_type: str,
    violations: List[Dict[str, Any]],
    max_hits: int,
) -> None:
    for name, pattern in patterns.items():
        try:
            compiled = re.compile(pattern, re.IGNORECASE)
        except re.error:
            continue
        for source, text in texts:
            for match in compiled.finditer(text):
                violations.append(
                    {
                        "type": violation_type,
                        "rule": name,
                        "match": match.group(0),
                        "source": source,
                    }
                )
                if len(violations) >= max_hits:
                    return


def _apply_blocklist(
    texts: List[Tuple[str, str]],
    blocklist: Iterable[str],
    violation_type: str,
    violations: List[Dict[str, Any]],
    max_hits: int,
) -> None:
    lowered_list = [item.lower() for item in blocklist if item]
    for source, text in texts:
        lowered = text.lower()
        for item in lowered_list:
            if item in lowered:
                violations.append(
                    {
                        "type": violation_type,
                        "rule": item,
                        "match": item,
                        "source": source,
                    }
                )
                if len(violations) >= max_hits:
                    return


def _collect_texts(
    stage: str,
    step: Dict[str, Any],
    step_spec: Optional[Any],
    run_dir: Path,
) -> List[Tuple[str, str]]:
    if stage == "inputs":
        payload = step_spec.inputs if step_spec else step.get("inputs", {})
        return _flatten_texts(payload)
    if stage == "outputs":
        outputs = step.get("outputs", [])
        return _read_output_texts(outputs, run_dir)
    return []


def _flatten_texts(value: Any, path: str = "") -> List[Tuple[str, str]]:
    texts: List[Tuple[str, str]] = []
    if isinstance(value, str):
        if value:
            texts.append((path or "value", value))
        return texts
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{path}.{key}" if path else str(key)
            texts.extend(_flatten_texts(item, child))
        return texts
    if isinstance(value, list):
        for idx, item in enumerate(value):
            child = f"{path}[{idx}]" if path else f"[{idx}]"
            texts.extend(_flatten_texts(item, child))
        return texts
    return texts


def _read_output_texts(outputs: Any, run_dir: Path) -> List[Tuple[str, str]]:
    if not isinstance(outputs, list):
        return []
    texts: List[Tuple[str, str]] = []
    root = runtime_config.project_root_from_here()
    for output in outputs:
        if not isinstance(output, str):
            continue
        cleaned = output.strip()
        if not cleaned or "{" in cleaned:
            continue
        if cleaned.startswith("template:") or cleaned.startswith("id:"):
            continue
        resolved = _resolve_output_path(cleaned, root, run_dir)
        if not resolved:
            continue
        try:
            content = resolved.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        texts.append((cleaned, content))
    return texts


def _resolve_output_path(value: str, root: Path, run_dir: Path) -> Optional[Path]:
    for base in (root, run_dir):
        try:
            resolved = file_io.resolve_path(value, root=base)
        except ValueError:
            continue
        if resolved.exists() and resolved.is_file():
            return resolved
    return None
