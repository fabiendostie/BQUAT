from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional

from runtime.guardrails import checks
from runtime.guardrails.checks import GuardrailReport
from runtime.time_provider import get_current_time


def _evaluate_pii(texts: List[tuple[str, str]], cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    violations: List[Dict[str, Any]] = []
    patterns = checks._normalize_patterns(cfg.get("patterns"), checks.DEFAULT_PII_PATTERNS)
    checks._apply_regex(texts, patterns, "pii", violations, checks._max_hits(cfg))
    return violations


def _evaluate_moderation(texts: List[tuple[str, str]], cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    violations: List[Dict[str, Any]] = []
    blocklist = checks._normalize_list(cfg.get("blocklist"), checks.DEFAULT_MODERATION_BLOCKLIST)
    checks._apply_blocklist(texts, blocklist, "moderation", violations, checks._max_hits(cfg))
    return violations


def _evaluate_rules(texts: List[tuple[str, str]], cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    violations: List[Dict[str, Any]] = []
    blocklist = checks._normalize_list(cfg.get("blocklist"), checks.DEFAULT_RULES_BLOCKLIST)
    checks._apply_blocklist(texts, blocklist, "rules_blocklist", violations, checks._max_hits(cfg))
    patterns = checks._normalize_patterns(cfg.get("regex"), checks.DEFAULT_RULES_REGEX)
    checks._apply_regex(texts, patterns, "rules_regex", violations, checks._max_hits(cfg))
    return violations


async def evaluate_guardrails_async(
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

    texts = checks._collect_texts(stage, step, step_spec, run_dir)
    tasks: List[asyncio.Future] = []

    pii_cfg = guardrails_cfg.get("pii", {})
    if pii_cfg.get("enabled", True):
        tasks.append(asyncio.to_thread(_evaluate_pii, texts, pii_cfg))

    moderation_cfg = guardrails_cfg.get("moderation", {})
    if moderation_cfg.get("enabled", True):
        tasks.append(asyncio.to_thread(_evaluate_moderation, texts, moderation_cfg))

    rules_cfg = guardrails_cfg.get("rules", {})
    if rules_cfg.get("enabled", True):
        tasks.append(asyncio.to_thread(_evaluate_rules, texts, rules_cfg))

    violations: List[Dict[str, Any]] = []
    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                continue
            violations.extend(result)

    status = "failed" if violations else "passed"
    return GuardrailReport(
        stage=stage,
        status=status,
        checked_at=get_current_time(),
        violations=violations,
    )


def evaluate_guardrails_concurrent(
    stage: str,
    step: Dict[str, Any],
    step_spec: Optional[Any],
    config: Dict[str, Any],
    run_dir: Path,
) -> Optional[GuardrailReport]:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(evaluate_guardrails_async(stage, step, step_spec, config, run_dir))
    return checks.evaluate_guardrails(stage, step, step_spec, config, run_dir)
