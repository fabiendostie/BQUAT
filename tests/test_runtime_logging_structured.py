from __future__ import annotations

import unittest
from pathlib import Path
from uuid import uuid4

from runtime import storage
from runtime.logging.structured import LOG_LEVELS, StructuredLogger


class StructuredLoggerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sandbox = Path(__file__).resolve().parent / f"sandbox_{uuid4().hex}"
        self.sandbox.mkdir(parents=True, exist_ok=True)
        self.run_id = f"run-{uuid4().hex[:8]}"
        self.run_dir = self.sandbox / self.run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        import shutil

        if self.sandbox.exists():
            shutil.rmtree(self.sandbox)

    def test_log_levels_defined(self) -> None:
        self.assertEqual(LOG_LEVELS["debug"], 0)
        self.assertEqual(LOG_LEVELS["info"], 1)
        self.assertEqual(LOG_LEVELS["warn"], 2)
        self.assertEqual(LOG_LEVELS["error"], 3)

    def test_log_writes_to_file(self) -> None:
        logger = StructuredLogger(self.run_dir, self.run_id)
        logger.log("info", "run", "test message")

        logs = storage.read_logs(self.run_dir)
        self.assertEqual(len(logs["logs"]), 1)
        entry = logs["logs"][0]
        self.assertEqual(entry["level"], "info")
        self.assertEqual(entry["category"], "run")
        self.assertEqual(entry["message"], "test message")
        self.assertEqual(entry["run_id"], self.run_id)

    def test_log_with_payload(self) -> None:
        logger = StructuredLogger(self.run_dir, self.run_id)
        logger.log("info", "step", "step started", payload={"step_name": "execute"})

        logs = storage.read_logs(self.run_dir)
        entry = logs["logs"][0]
        self.assertEqual(entry["payload"], {"step_name": "execute"})

    def test_log_with_step_id(self) -> None:
        logger = StructuredLogger(self.run_dir, self.run_id)
        logger.log("info", "step", "step completed", step_id="step-01")

        logs = storage.read_logs(self.run_dir)
        entry = logs["logs"][0]
        self.assertEqual(entry["step_id"], "step-01")

    def test_level_filtering_suppresses_debug(self) -> None:
        logger = StructuredLogger(self.run_dir, self.run_id, min_level="info")
        logger.log("debug", "run", "debug message")

        logs = storage.read_logs(self.run_dir)
        self.assertEqual(len(logs["logs"]), 0)

    def test_level_filtering_allows_higher(self) -> None:
        logger = StructuredLogger(self.run_dir, self.run_id, min_level="info")
        logger.log("warn", "run", "warning message")

        logs = storage.read_logs(self.run_dir)
        self.assertEqual(len(logs["logs"]), 1)

    def test_level_filtering_debug_level(self) -> None:
        logger = StructuredLogger(self.run_dir, self.run_id, min_level="debug")
        logger.log("debug", "run", "debug message")

        logs = storage.read_logs(self.run_dir)
        self.assertEqual(len(logs["logs"]), 1)

    def test_level_filtering_error_only(self) -> None:
        logger = StructuredLogger(self.run_dir, self.run_id, min_level="error")
        logger.log("info", "run", "info message")
        logger.log("warn", "run", "warn message")
        logger.log("error", "run", "error message")

        logs = storage.read_logs(self.run_dir)
        self.assertEqual(len(logs["logs"]), 1)
        self.assertEqual(logs["logs"][0]["level"], "error")

    def test_multiple_logs_append(self) -> None:
        logger = StructuredLogger(self.run_dir, self.run_id)
        logger.log("info", "run", "first")
        logger.log("info", "run", "second")
        logger.log("info", "run", "third")

        logs = storage.read_logs(self.run_dir)
        self.assertEqual(len(logs["logs"]), 3)
        self.assertEqual(logs["logs"][0]["message"], "first")
        self.assertEqual(logs["logs"][2]["message"], "third")

    def test_category_method_run(self) -> None:
        logger = StructuredLogger(self.run_dir, self.run_id)
        logger.run("info", "workflow started")

        logs = storage.read_logs(self.run_dir)
        self.assertEqual(logs["logs"][0]["category"], "run")

    def test_category_method_step(self) -> None:
        logger = StructuredLogger(self.run_dir, self.run_id)
        logger.step("info", "step started", "step-01")

        logs = storage.read_logs(self.run_dir)
        self.assertEqual(logs["logs"][0]["category"], "step")
        self.assertEqual(logs["logs"][0]["step_id"], "step-01")

    def test_category_method_gate(self) -> None:
        logger = StructuredLogger(self.run_dir, self.run_id)
        logger.gate("warn", "gate blocked")

        logs = storage.read_logs(self.run_dir)
        self.assertEqual(logs["logs"][0]["category"], "gate")

    def test_category_method_evidence(self) -> None:
        logger = StructuredLogger(self.run_dir, self.run_id)
        logger.evidence("info", "evidence recorded")

        logs = storage.read_logs(self.run_dir)
        self.assertEqual(logs["logs"][0]["category"], "evidence")

    def test_category_method_validation(self) -> None:
        logger = StructuredLogger(self.run_dir, self.run_id)
        logger.validation("info", "validation passed", step_id="step-02")

        logs = storage.read_logs(self.run_dir)
        self.assertEqual(logs["logs"][0]["category"], "validation")
        self.assertEqual(logs["logs"][0]["step_id"], "step-02")

    def test_category_method_guardrail(self) -> None:
        logger = StructuredLogger(self.run_dir, self.run_id)
        logger.guardrail("error", "guardrail violation", step_id="step-03")

        logs = storage.read_logs(self.run_dir)
        self.assertEqual(logs["logs"][0]["category"], "guardrail")
        self.assertEqual(logs["logs"][0]["step_id"], "step-03")

    def test_level_shortcuts(self) -> None:
        logger = StructuredLogger(self.run_dir, self.run_id, min_level="debug")
        logger.debug("run", "debug msg")
        logger.info("run", "info msg")
        logger.warn("run", "warn msg")
        logger.error("run", "error msg")

        logs = storage.read_logs(self.run_dir)
        self.assertEqual(len(logs["logs"]), 4)
        levels = [entry["level"] for entry in logs["logs"]]
        self.assertEqual(levels, ["debug", "info", "warn", "error"])

    def test_timestamp_populated(self) -> None:
        logger = StructuredLogger(self.run_dir, self.run_id)
        logger.log("info", "run", "test")

        logs = storage.read_logs(self.run_dir)
        timestamp = logs["logs"][0]["timestamp"]
        self.assertIsNotNone(timestamp)
        self.assertIn("T", timestamp)

    def test_updated_at_set(self) -> None:
        logger = StructuredLogger(self.run_dir, self.run_id)
        logger.log("info", "run", "test")

        logs = storage.read_logs(self.run_dir)
        self.assertIsNotNone(logs["updated_at"])
        self.assertIn("T", logs["updated_at"])

    def test_case_insensitive_level(self) -> None:
        logger = StructuredLogger(self.run_dir, self.run_id, min_level="INFO")
        logger.log("INFO", "run", "uppercase level")

        logs = storage.read_logs(self.run_dir)
        self.assertEqual(len(logs["logs"]), 1)


if __name__ == "__main__":
    unittest.main()
