import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.plugins.base import Plugin  # noqa: E402
from runtime.plugins.manager import PluginManager  # noqa: E402


class Recorder(Plugin):
    def __init__(self, log: list[str]) -> None:
        self.log = log

    def before_run(self, manifest: dict) -> None:
        self.log.append("before_run")

    def after_run(self, manifest: dict) -> None:
        self.log.append("after_run")

    def before_step(self, step: dict, manifest: dict) -> None:
        self.log.append("before_step")

    def after_step(self, step: dict, manifest: dict) -> None:
        self.log.append("after_step")

    def on_error(self, step: dict, manifest: dict, error: str) -> None:
        self.log.append("on_error")

    def on_validation(self, manifest: dict, status: str) -> None:
        self.log.append(f"validation:{status}")


class RuntimePluginTests(unittest.TestCase):
    def test_plugin_manager_calls(self) -> None:
        log: list[str] = []
        manager = PluginManager([Recorder(log)])
        manager.before_run({})
        manager.before_step({}, {})
        manager.after_step({}, {})
        manager.on_error({}, {}, "boom")
        manager.on_validation({}, "ok")
        manager.after_run({})
        self.assertEqual(
            log,
            [
                "before_run",
                "before_step",
                "after_step",
                "on_error",
                "validation:ok",
                "after_run",
            ],
        )

    def test_base_plugin_noops(self) -> None:
        plugin = Plugin()
        plugin.before_run({})
        plugin.after_run({})
        plugin.before_step({}, {})
        plugin.after_step({}, {})
        plugin.on_error({}, {}, "boom")
        plugin.on_validation({}, "ok")


if __name__ == "__main__":
    unittest.main()
