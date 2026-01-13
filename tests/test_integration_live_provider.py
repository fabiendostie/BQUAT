"""Live provider smoke test (env-gated)."""

from __future__ import annotations

import os
import shutil
import sys
import unittest
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import engine, execution, models, storage  # noqa: E402
from runtime.providers.base import ProviderError  # noqa: E402
from runtime.providers.registry import ProviderRegistry  # noqa: E402

_PROVIDER_CONFIGS = {
    "openai": {
        "type": "openai",
        "model": os.environ.get("BAQT_LIVE_MODEL", "gpt-4o-mini"),
        "api_key_env": "OPENAI_API_KEY",
    },
    "claude": {
        "type": "anthropic",
        "model": os.environ.get("BAQT_LIVE_MODEL", "claude-4"),
        "api_key_env": "ANTHROPIC_API_KEY",
    },
    "anthropic": {
        "type": "anthropic",
        "model": os.environ.get("BAQT_LIVE_MODEL", "claude-4"),
        "api_key_env": "ANTHROPIC_API_KEY",
    },
    "gemini": {
        "type": "gemini",
        "model": os.environ.get("BAQT_LIVE_MODEL", "gemini-1.5-flash"),
        "api_key_env": "GEMINI_API_KEY",
    },
    "groq": {
        "type": "groq",
        "model": os.environ.get("BAQT_LIVE_MODEL", "llama3-8b-8192"),
        "api_key_env": "GROQ_API_KEY",
    },
    "litellm": {
        "type": "litellm",
        "model": os.environ.get("BAQT_LIVE_MODEL", "gpt-4o-mini"),
        "base_url": os.environ.get("BAQT_LIVE_BASE_URL", "http://localhost:4000"),
    },
    "ollama": {
        "type": "ollama",
        "model": os.environ.get("BAQT_LIVE_MODEL", "llama3"),
        "base_url": os.environ.get("BAQT_LIVE_BASE_URL", "http://localhost:11434"),
    },
}


class LiveProviderIntegrationTests(unittest.TestCase):
    """Run a single-step workflow with a real provider."""

    def setUp(self) -> None:
        self.provider_name = os.environ.get("BAQT_LIVE_PROVIDER", "").strip().lower()
        if not self.provider_name:
            self.skipTest("BAQT_LIVE_PROVIDER not set")
        if self.provider_name not in _PROVIDER_CONFIGS:
            self.skipTest(f"Unsupported provider: {self.provider_name}")

        provider_cfg = dict(_PROVIDER_CONFIGS[self.provider_name])
        required_env = provider_cfg.get("api_key_env")
        if required_env and not os.environ.get(required_env):
            self.skipTest(f"Missing required env var: {required_env}")

        self.sandbox = ROOT / "runs" / "tmp-tests" / uuid4().hex
        self.sandbox.mkdir(parents=True, exist_ok=True)

        self.config = {
            "runtime": {
                "storage_root": str(self.sandbox),
                "max_retries": 0,
                "step_timeout_seconds": 60,
            },
            "automation": {"override": True},
            "hitl": {"mode": "disabled"},
            "providers": {
                "default": self.provider_name,
                self.provider_name: provider_cfg,
            },
        }

        self.mapping = [
            models.WorkflowSpec(
                module="live",
                workflow="smoke",
                phase="Live Provider Smoke",
                quint="",
                telis="",
                validation="",
                human="none",
                evidence="",
                artifacts=[],
                scope="test",
                path="",
            )
        ]

    def tearDown(self) -> None:
        keep_runs = os.environ.get("BAQT_LIVE_KEEP_RUNS") == "1"
        if keep_runs:
            return
        if hasattr(self, "sandbox") and self.sandbox.exists():
            shutil.rmtree(self.sandbox, ignore_errors=True)

    def test_live_provider_single_step(self) -> None:
        registry = ProviderRegistry(self.config)
        try:
            provider = registry.get(self.provider_name)
        except ProviderError as exc:
            self.skipTest(str(exc))

        eng = engine.WorkflowEngine(self.config, self.mapping, storage_root=self.sandbox)
        executor = execution.PlanExecutor("bmad", provider)
        manifest = eng.run("live", "smoke", executor=executor, agent_name="bmad")
        status = manifest.get("status")
        if status != "completed":
            details = {
                "status": status,
                "blocked_reason": manifest.get("blocked_reason"),
                "blocked_phase": manifest.get("blocked_phase"),
                "blocked_gate": manifest.get("blocked_gate"),
                "blocked_policy": manifest.get("blocked_policy"),
                "error": manifest.get("error"),
                "steps": [
                    {
                        "step_id": step.get("step_id"),
                        "name": step.get("name"),
                        "status": step.get("status"),
                        "error": step.get("error"),
                    }
                    for step in manifest.get("steps", [])
                ],
            }
            self.fail(f"Live provider run did not complete: {details}")
        self.assertEqual(status, "completed")

        run_dir = self.sandbox / manifest["run_id"]
        response_path = run_dir / "response.json"
        self.assertTrue(response_path.exists())
        response = storage.read_json(response_path)
        content = response.get("content", "")
        if not content:
            self.fail(f"Live provider returned empty content: {response.get('raw')}")
        self.assertTrue(content)


if __name__ == "__main__":
    unittest.main()
