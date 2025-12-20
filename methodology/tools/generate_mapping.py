from __future__ import annotations

from pathlib import Path

from mapping import (
    generate_mapping_records,
    generate_registry_workflows,
    project_root_from_here,
    write_mapping,
    write_registry_workflows,
)


def main() -> int:
    root = project_root_from_here()
    bmad_root = root / "BMAD-METHOD"
    out_dir = root / "methodology"
    out_dir.mkdir(parents=True, exist_ok=True)

    mapping_records = generate_mapping_records(bmad_root)
    write_mapping(mapping_records, out_dir / "integration-mapping.md")

    workflow_records = generate_registry_workflows(bmad_root)
    write_registry_workflows(workflow_records, out_dir / "registry-workflows.md")

    print(f"Mapping records: {len(mapping_records)}")
    print(f"Workflow registry records: {len(workflow_records)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
