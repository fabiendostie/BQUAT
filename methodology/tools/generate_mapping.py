from __future__ import annotations

from mapping import (
    generate_mapping_records,
    generate_registry_workflows,
    project_root_from_here,
    write_mapping,
    write_mapping_json,
    write_registry_workflows,
    write_registry_workflows_json,
)


def main() -> int:
    root = project_root_from_here()
    bmad_root = root / "BMAD-METHOD"
    out_dir = root / "methodology"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_dir = out_dir / "mapping"
    json_dir.mkdir(parents=True, exist_ok=True)

    mapping_records = generate_mapping_records(bmad_root)
    write_mapping(mapping_records, out_dir / "integration-mapping.md")
    write_mapping_json(mapping_records, json_dir / "integration-mapping.json")

    workflow_records = generate_registry_workflows(bmad_root)
    write_registry_workflows(workflow_records, out_dir / "registry-workflows.md")
    write_registry_workflows_json(workflow_records, json_dir / "registry-workflows.json")

    print(f"Mapping records: {len(mapping_records)}")
    print(f"Workflow registry records: {len(workflow_records)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
