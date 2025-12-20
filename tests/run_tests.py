import sys
import unittest
import trace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = [
    ROOT / "methodology" / "tools" / "mapping.py",
    ROOT / "runtime" / "agents.py",
    ROOT / "runtime" / "config.py",
    ROOT / "runtime" / "engine.py",
    ROOT / "runtime" / "gates.py",
    ROOT / "runtime" / "models.py",
    ROOT / "runtime" / "prompts.py",
    ROOT / "runtime" / "storage.py",
]
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
    target_resolved = {target.resolve() for target in TARGETS}
    for (filename, lineno), count in counts.items():
        if count <= 0:
            continue
        try:
            resolved = Path(filename).resolve()
            if resolved in target_resolved:
                executed.add((resolved, lineno))
        except Exception:
            continue

    total = set()
    per_file_totals = {}
    for target in TARGETS:
        lines = executable_lines(target)
        per_file_totals[target.resolve()] = lines
        total.update({(target.resolve(), line) for line in lines})

    if not total:
        print("No executable lines found for coverage")
        return 1

    covered = total.intersection(executed)
    coverage = (len(covered) / len(total)) * 100.0
    print(f"Coverage overall: {coverage:.2f}%")

    for target in TARGETS:
        target_lines = per_file_totals.get(target.resolve(), set())
        if not target_lines:
            continue
        target_total = {(target.resolve(), line) for line in target_lines}
        target_covered = target_total.intersection(executed)
        target_coverage = (len(target_covered) / len(target_total)) * 100.0
        print(f"Coverage for {target.name}: {target_coverage:.2f}%")

    if coverage < COVERAGE_THRESHOLD:
        print(f"Coverage below threshold: {coverage:.2f}% < {COVERAGE_THRESHOLD}%")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
