from __future__ import annotations

from typing import Any, Dict, List

SCHEMA_VERSION = "1.0"


WORKFLOW_SPEC_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": [
        "module",
        "workflow",
        "phase",
        "quint",
        "telis",
        "validation",
        "human",
        "evidence",
        "artifacts",
        "scope",
        "path",
    ],
    "properties": {
        "module": {"type": "string"},
        "workflow": {"type": "string"},
        "phase": {"type": "string"},
        "quint": {"type": "string"},
        "telis": {"type": "string"},
        "validation": {"type": "string"},
        "human": {"type": "string"},
        "evidence": {"type": "string"},
        "artifacts": {"type": "array", "items": {"type": "string"}},
        "scope": {"type": "string"},
        "path": {"type": "string"},
    },
}

STEP_SPEC_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": [
        "id",
        "name",
        "description",
        "phase",
        "inputs",
        "outputs",
        "templates",
        "tools",
        "validation",
        "evidence",
        "human_gate",
        "retries",
    ],
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "description": {"type": "string"},
        "phase": {"type": "string"},
        "inputs": {"type": "object"},
        "outputs": {"type": "array", "items": {"type": "string"}},
        "templates": {"type": "array", "items": {"type": "string"}},
        "tools": {"type": "array"},
        "validation": {"type": "string"},
        "evidence": {"type": "string"},
        "human_gate": {"type": "string"},
        "retries": {"type": "object"},
    },
}

RUN_STEP_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": [
        "name",
        "status",
        "attempts",
        "inputs",
        "outputs",
        "tools",
        "validation",
    ],
    "properties": {
        "name": {"type": "string"},
        "status": {"type": "string"},
        "attempts": {"type": "integer"},
        "started_at": {"type": ["string", "null"]},
        "ended_at": {"type": ["string", "null"]},
        "error": {"type": ["string", "null"]},
        "step_id": {"type": ["string", "null"]},
        "inputs": {"type": "object"},
        "outputs": {"type": "array", "items": {"type": "string"}},
        "tools": {"type": "array", "items": {"type": "string"}},
        "validation": {"type": "object"},
    },
}

ARTIFACT_RECORD_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": [
        "artifact_id",
        "path",
        "artifact_type",
        "checksum",
        "workflow",
        "created_at",
        "metadata",
    ],
    "properties": {
        "artifact_id": {"type": "string"},
        "path": {"type": "string"},
        "artifact_type": {"type": "string"},
        "checksum": {"type": "string"},
        "workflow": {"type": "string"},
        "created_at": {"type": "string"},
        "step": {"type": ["string", "null"]},
        "metadata": {"type": "object"},
    },
}

ARTIFACT_INDEX_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["run_id", "artifacts", "updated_at"],
    "properties": {
        "run_id": {"type": "string"},
        "artifacts": {"type": "array", "items": ARTIFACT_RECORD_SCHEMA},
        "updated_at": {"type": "string"},
    },
}

EVIDENCE_LINK_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": [
        "id",
        "claim",
        "level",
        "source",
        "date",
        "valid_until",
        "congruence",
        "reliability",
        "wlnk",
        "carrier_ref",
        "artifacts",
        "notes",
    ],
    "properties": {
        "id": {"type": "string"},
        "claim": {"type": "string"},
        "level": {"type": "string"},
        "source": {"type": "string"},
        "date": {"type": "string"},
        "valid_until": {"type": "string"},
        "congruence": {"type": "string"},
        "reliability": {"type": "number"},
        "wlnk": {"type": "number"},
        "carrier_ref": {"type": "string"},
        "artifacts": {"type": "array", "items": {"type": "string"}},
        "notes": {"type": "string"},
    },
}

HUMAN_GATE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["gate_id", "status", "required", "notes"],
    "properties": {
        "gate_id": {"type": "string"},
        "status": {"type": "string"},
        "required": {"type": "boolean"},
        "approved_by": {"type": ["string", "null"]},
        "approved_at": {"type": ["string", "null"]},
        "notes": {"type": "string"},
    },
}

EVENT_RECORD_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["event_type", "run_id", "timestamp", "payload"],
    "properties": {
        "event_type": {"type": "string"},
        "run_id": {"type": "string"},
        "timestamp": {"type": "string"},
        "payload": {"type": "object"},
        "step_id": {"type": ["string", "null"]},
    },
}

RUN_MANIFEST_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": [
        "run_id",
        "workflow",
        "status",
        "step_specs",
        "steps",
        "current_step",
        "created_at",
        "updated_at",
    ],
    "properties": {
        "run_id": {"type": "string"},
        "workflow": WORKFLOW_SPEC_SCHEMA,
        "status": {"type": "string"},
        "step_specs": {"type": "array", "items": STEP_SPEC_SCHEMA},
        "steps": {"type": "array", "items": RUN_STEP_SCHEMA},
        "current_step": {"type": "integer"},
        "created_at": {"type": "string"},
        "updated_at": {"type": "string"},
    },
}

SCHEMAS: Dict[str, Dict[str, Any]] = {
    "workflow_spec": WORKFLOW_SPEC_SCHEMA,
    "step_spec": STEP_SPEC_SCHEMA,
    "run_step": RUN_STEP_SCHEMA,
    "run_manifest": RUN_MANIFEST_SCHEMA,
    "artifact_record": ARTIFACT_RECORD_SCHEMA,
    "artifact_index": ARTIFACT_INDEX_SCHEMA,
    "evidence_link": EVIDENCE_LINK_SCHEMA,
    "human_gate": HUMAN_GATE_SCHEMA,
    "event_record": EVENT_RECORD_SCHEMA,
}


def schema_registry() -> Dict[str, Any]:
    return {"version": SCHEMA_VERSION, "schemas": SCHEMAS}


def _is_type(value: Any, type_name: str) -> bool:
    if type_name == "null":
        return value is None
    if type_name == "string":
        return isinstance(value, str)
    if type_name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if type_name == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if type_name == "boolean":
        return isinstance(value, bool)
    if type_name == "object":
        return isinstance(value, dict)
    if type_name == "array":
        return isinstance(value, list)
    return False


def _type_matches(value: Any, expected: Any) -> bool:
    if isinstance(expected, list):
        return any(_is_type(value, item) for item in expected)
    if isinstance(expected, str):
        return _is_type(value, expected)
    return True


def validate_schema(schema: Dict[str, Any], data: Any, path: str = "") -> List[str]:
    errors: List[str] = []
    expected_type = schema.get("type")
    if expected_type and not _type_matches(data, expected_type):
        errors.append(f"{path or 'root'}: expected {expected_type}")
        return errors

    if data is None:
        return errors

    if schema.get("enum") and data not in schema["enum"]:
        errors.append(f"{path or 'root'}: value not in enum")
        return errors

    if schema.get("type") == "object":
        if not isinstance(data, dict):
            errors.append(f"{path or 'root'}: expected object")
            return errors
        required = schema.get("required", [])
        for key in required:
            if key not in data:
                errors.append(f"{path or 'root'}: missing required field '{key}'")
        properties = schema.get("properties", {})
        additional = schema.get("additionalProperties", True)
        for key, value in data.items():
            child_path = f"{path}.{key}" if path else key
            if key in properties:
                errors.extend(validate_schema(properties[key], value, child_path))
            elif additional is False:
                errors.append(f"{child_path}: unexpected field")
            elif isinstance(additional, dict):
                errors.extend(validate_schema(additional, value, child_path))

    if schema.get("type") == "array":
        if not isinstance(data, list):
            errors.append(f"{path or 'root'}: expected array")
            return errors
        items_schema = schema.get("items")
        if items_schema:
            for idx, item in enumerate(data):
                item_path = f"{path}[{idx}]" if path else f"[{idx}]"
                errors.extend(validate_schema(items_schema, item, item_path))

    return errors
