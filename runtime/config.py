from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "runtime.yaml"


def project_root_from_here() -> Path:
    return Path(__file__).resolve().parents[1]


def load_config(path: Optional[Path] = None) -> Dict[str, Any]:
    target = path or DEFAULT_CONFIG_PATH
    raw = target.read_text(encoding="ascii")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        try:
            import yaml
        except ImportError as exc:  # pragma: no cover - only if PyYAML missing
            raise ValueError(
                f"Config file '{target}' is not valid JSON and PyYAML is not installed."
            ) from exc
        data = yaml.safe_load(raw)
        if data is None:
            return {}
        if not isinstance(data, dict):
            raise ValueError(f"Config file '{target}' must define a mapping at the root.")
        return data


def storage_root(config: Dict[str, Any], root: Optional[Path] = None) -> Path:
    runtime_cfg = config.get("runtime", {})
    storage = runtime_cfg.get("storage_root", "runs")
    base = root or project_root_from_here()
    return (base / storage).resolve()
