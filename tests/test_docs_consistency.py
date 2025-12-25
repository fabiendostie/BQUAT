import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "docs" / "v1-plan.md"
AUDIT_PATH = ROOT / "docs" / "traceability-audit.md"
SPEC_PATH = ROOT / "methodology" / "unified_method_specification.md"
INDEX_PATH = ROOT / "docs" / "unified-framework-documentation-index.md"

PLAN_ID_RE = re.compile(r"^REQ-[A-Z]+-\d+$")
AUDIT_ID_RE = re.compile(r"^[A-Z]+-\d+$")

PREFIX_MAP = {
    "BMAD": "BMAD",
    "INSTALL": "INSTALL",
    "TELIS": "TELIS",
    "QUINT": "QUINT",
    "AGENT": "GUIDE",
    "SPEC": "SPEC",
}


def parse_plan_statuses(text: str) -> dict[str, str]:
    statuses: dict[str, str] = {}
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not cells or not PLAN_ID_RE.match(cells[0]):
            continue
        if len(cells) < 6:
            continue
        statuses[cells[0]] = cells[4].lower()
    return statuses


def parse_audit_statuses(text: str) -> dict[str, str]:
    statuses: dict[str, str] = {}
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not cells or not AUDIT_ID_RE.match(cells[0]):
            continue
        if len(cells) < 3:
            continue
        statuses[cells[0]] = cells[2].lower()
    return statuses


def map_plan_id(plan_id: str) -> str | None:
    match = re.match(r"^REQ-([A-Z]+)-(\d+)$", plan_id)
    if not match:
        return None
    prefix, number = match.groups()
    mapped = PREFIX_MAP.get(prefix)
    if not mapped:
        return None
    return f"{mapped}-{number}"


class DocsConsistencyTests(unittest.TestCase):
    def test_plan_and_audit_statuses_match(self) -> None:
        plan_statuses = parse_plan_statuses(PLAN_PATH.read_text(encoding="ascii"))
        audit_statuses = parse_audit_statuses(AUDIT_PATH.read_text(encoding="ascii"))
        for plan_id, plan_status in plan_statuses.items():
            audit_id = map_plan_id(plan_id)
            if not audit_id:
                continue
            self.assertIn(audit_id, audit_statuses, f"Missing {audit_id} in traceability audit")
            self.assertEqual(
                plan_status,
                audit_statuses[audit_id],
                f"Status mismatch for {plan_id} vs {audit_id}",
            )

    def test_unified_spec_uses_bmad_method_canonical(self) -> None:
        text = SPEC_PATH.read_text(encoding="ascii").lower()
        self.assertIn("bmad-method remains the canonical source", text)

    def test_documentation_index_lists_core_docs(self) -> None:
        index = INDEX_PATH.read_text(encoding="ascii")
        for path in (
            "methodology/unified_method_specification.md",
            "docs/v1-plan.md",
            "docs/traceability-audit.md",
        ):
            self.assertIn(path, index)


if __name__ == "__main__":
    unittest.main()
