import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CHECK_PATHS = [
    ROOT / ".github" / "workflows" / "ci.yml",
    ROOT / ".husky" / "commit-msg",
    ROOT / ".husky" / "pre-push",
    ROOT / ".husky" / "pre-commit",
    ROOT / "VERSION",
    ROOT / "docs" / "versioning.md",
    ROOT / "docs" / "v1-plan.md",
    ROOT / "docs" / "traceability-audit.md",
    ROOT / "package.json",
    ROOT / "pytest.ini",
    ROOT / "requirements-dev.txt",
    ROOT / "config" / "runtime.yaml",
    ROOT / "methodology" / "tools" / "mapping.py",
    ROOT / "methodology" / "tools" / "generate_mapping.py",
    ROOT / "runtime" / "__init__.py",
    ROOT / "runtime" / "agents.py",
    ROOT / "runtime" / "config.py",
    ROOT / "runtime" / "engine.py",
    ROOT / "runtime" / "execution.py",
    ROOT / "runtime" / "gates.py",
    ROOT / "runtime" / "models.py",
    ROOT / "runtime" / "prompts.py",
    ROOT / "runtime" / "storage.py",
    ROOT / "runtime" / "time_provider.py",
    ROOT / "runtime" / "providers" / "__init__.py",
    ROOT / "runtime" / "providers" / "base.py",
    ROOT / "runtime" / "providers" / "http.py",
    ROOT / "runtime" / "providers" / "registry.py",
    ROOT / "runtime" / "plugins" / "__init__.py",
    ROOT / "runtime" / "tools" / "__init__.py",
    ROOT / "runtime" / "tools" / "time_tool.py",
    ROOT / "runtime" / "plugins" / "base.py",
    ROOT / "runtime" / "plugins" / "manager.py",
    ROOT / "cli" / "main.py",
    ROOT / "tests" / "test_mapping.py",
    ROOT / "tests" / "test_style.py",
    ROOT / "tests" / "test_cli.py",
    ROOT / "tests" / "test_runtime_execution.py",
    ROOT / "tests" / "test_runtime_agents.py",
    ROOT / "tests" / "test_runtime_config.py",
    ROOT / "tests" / "test_runtime_engine.py",
    ROOT / "tests" / "test_runtime_gates.py",
    ROOT / "tests" / "test_runtime_http.py",
    ROOT / "tests" / "test_runtime_models.py",
    ROOT / "tests" / "test_time_tool.py",
    ROOT / "tests" / "test_runtime_plugins.py",
    ROOT / "tests" / "test_runtime_providers.py",
    ROOT / "tests" / "test_runtime_storage.py",
    ROOT / "tests" / "test_versioning.py",
    ROOT / "tests" / "run_tests.py",
]


class StyleTests(unittest.TestCase):
    def test_no_tabs_or_trailing_whitespace(self) -> None:
        for path in CHECK_PATHS:
            text = path.read_text(encoding="ascii", errors="ignore")
            for idx, line in enumerate(text.splitlines(), 1):
                self.assertNotIn("\t", line, f"Tab found in {path}:{idx}")
                self.assertEqual(line, line.rstrip(), f"Trailing whitespace in {path}:{idx}")


if __name__ == "__main__":
    unittest.main()
