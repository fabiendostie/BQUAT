from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from runtime import storage
from runtime.logging.models import LogRecord
from runtime.time_provider import get_current_time

LOG_LEVELS = {"debug": 0, "info": 1, "warn": 2, "error": 3}


class StructuredLogger:
    """Structured logger that writes JSON log records to run directory."""

    def __init__(
        self,
        run_dir: Path,
        run_id: str,
        min_level: str = "info",
    ) -> None:
        self._run_dir = run_dir
        self._run_id = run_id
        self._min_level = LOG_LEVELS.get(min_level.lower(), 1)

    def _should_log(self, level: str) -> bool:
        return LOG_LEVELS.get(level.lower(), 0) >= self._min_level

    def _append_log(self, record: LogRecord) -> None:
        logs = storage.read_logs(self._run_dir)
        entries: List[Dict[str, Any]] = logs.get("logs", [])
        entries.append(record.to_dict())
        logs["logs"] = entries
        logs["updated_at"] = get_current_time()
        storage.write_logs(self._run_dir, logs)

    def log(
        self,
        level: str,
        category: str,
        message: str,
        step_id: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not self._should_log(level):
            return
        record = LogRecord(
            level=level,
            category=category,
            message=message,
            timestamp=get_current_time(),
            run_id=self._run_id,
            step_id=step_id,
            payload=dict(payload or {}),
        )
        self._append_log(record)

    def run(self, level: str, message: str, **kwargs: Any) -> None:
        self.log(level, "run", message, **kwargs)

    def step(self, level: str, message: str, step_id: str, **kwargs: Any) -> None:
        self.log(level, "step", message, step_id=step_id, **kwargs)

    def gate(self, level: str, message: str, **kwargs: Any) -> None:
        self.log(level, "gate", message, **kwargs)

    def evidence(self, level: str, message: str, **kwargs: Any) -> None:
        self.log(level, "evidence", message, **kwargs)

    def validation(
        self, level: str, message: str, step_id: Optional[str] = None, **kwargs: Any
    ) -> None:
        self.log(level, "validation", message, step_id=step_id, **kwargs)

    def guardrail(
        self, level: str, message: str, step_id: Optional[str] = None, **kwargs: Any
    ) -> None:
        self.log(level, "guardrail", message, step_id=step_id, **kwargs)

    def debug(self, category: str, message: str, **kwargs: Any) -> None:
        self.log("debug", category, message, **kwargs)

    def info(self, category: str, message: str, **kwargs: Any) -> None:
        self.log("info", category, message, **kwargs)

    def warn(self, category: str, message: str, **kwargs: Any) -> None:
        self.log("warn", category, message, **kwargs)

    def error(self, category: str, message: str, **kwargs: Any) -> None:
        self.log("error", category, message, **kwargs)
