import sys
import unittest
import trace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "methodology" / "tools" / "mapping.py"
COVERAGE_THRESHOLD = 85.0


def discover_tests() -> unittest.TestSuite:
    loader = unittest.TestLoader()
    return loader.discover(str(ROOT / "tests"))


def run_tests() -> unittest.TestResult:
    runner = unittest.TextTestRunner(verbosity=2)
    return runner.run(discover_tests())


def executable_lines(path: Path) -> set[int]:
    lines = path.read_text(encoding="ascii", errors="ignore").splitlines()
    exec_lines = set()
    for idx, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        if stripped.startswith(("\"", "'")):
            continue
        if stripped in {"]", ")", "}", "]:", "],", "})", "):"}:
            continue
        exec_lines.add(idx)
    return exec_lines


def main() -> int:
    tracer = trace.Trace(count=True, trace=False)
    result = tracer.runfunc(run_tests)

    if not result.wasSuccessful():
        return 1

    results = tracer.results()
    counts = results.counts

    executed = set()
    target_resolved = TARGET.resolve()
    for (filename, lineno), count in counts.items():
        if count <= 0:
            continue
        try:
            if Path(filename).resolve() == target_resolved:
                executed.add(lineno)
        except Exception:
            continue

    total = executable_lines(TARGET)
    if not total:
        print("No executable lines found for coverage")
        return 1

    covered = total.intersection(executed)
    coverage = (len(covered) / len(total)) * 100.0
    print(f"Coverage for {TARGET.name}: {coverage:.2f}%")

    if coverage < COVERAGE_THRESHOLD:
        print(f"Coverage below threshold: {coverage:.2f}% < {COVERAGE_THRESHOLD}%")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
