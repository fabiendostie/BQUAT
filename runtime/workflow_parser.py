from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import yaml

from runtime import models

STEP_FILE_RE = re.compile(r"^step-(\d+)([a-z]?)?(?:-(.*))?$", re.IGNORECASE)
STEP_TAG_RE = re.compile(r"<step\b([^>]*)>", re.IGNORECASE)
STEP_BLOCK_RE = re.compile(r"<step\b([^>]*)>(.*?)</step>", re.IGNORECASE | re.DOTALL)
TEMPLATE_OUTPUT_BLOCK_RE = re.compile(
    r"<template-output\b([^>]*)>(.*?)</template-output>", re.IGNORECASE | re.DOTALL
)
ATTR_RE = re.compile(r"(\w+)\s*=\s*\"([^\"]*)\"")


def safe_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return path.read_text(encoding="utf-8", errors="ignore")


def clean_artifact_value(value: str) -> str:
    cleaned = value.strip()
    if "#" in cleaned:
        cleaned = cleaned.split("#", 1)[0].strip()
    cleaned = cleaned.strip().strip("`").strip('"').strip("'").strip()
    return cleaned


def is_explicit_artifact(value: str) -> bool:
    if not value:
        return False
    if value.startswith("[") and value.endswith("]"):
        return False
    return True


def extract_outputs(text: str) -> List[str]:
    outputs: List[str] = []
    for match in re.finditer(
        r"(?im)^\s*(?:default_)?output(?:file|_file|_path)\s*:\s*(.+)$",
        text,
    ):
        val = clean_artifact_value(match.group(1))
        if is_explicit_artifact(val):
            outputs.append(val)

    for match in re.finditer(
        r"(?im)[`']?(?:default_)?output(?:file|_file|_path)[`']?\s*=\s*`?([^\r\n`]+)`?",
        text,
    ):
        val = clean_artifact_value(match.group(1))
        if is_explicit_artifact(val):
            outputs.append(val)

    for match in re.finditer(r"(?im)^\s*outputs\s*:\s*$", text):
        start = match.end()
        tail = text[start:]
        for line in tail.splitlines():
            if not line.strip():
                continue
            if re.match(r"^\s*-\s+", line):
                val = clean_artifact_value(re.sub(r"^\s*-\s+", "", line))
                if is_explicit_artifact(val):
                    outputs.append(val)
                continue
            if re.match(r"^\S", line):
                break
            if not line.startswith(" ") and not line.startswith("\t"):
                break

    return outputs


def parse_template_output_names(text: str) -> List[str]:
    names: List[str] = []
    for chunk in re.split(r"[,\n]+", text):
        item = chunk.strip()
        if not item:
            continue
        if "=" in item:
            item = item.split("=", 1)[0].strip()
        item = clean_artifact_value(item)
        if item:
            names.append(item)
    return names


def parse_template_output_tags(text: str) -> Tuple[List[str], Dict[str, object]]:
    outputs: List[str] = []
    files: Dict[str, object] = {}
    for match in TEMPLATE_OUTPUT_BLOCK_RE.finditer(text):
        attrs = {k.lower(): v for k, v in ATTR_RE.findall(match.group(1))}
        file_ref = clean_artifact_value(attrs.get("file", "")) if attrs.get("file") else ""
        names = parse_template_output_names(match.group(2))
        if not names:
            continue
        outputs.extend(names)
        if not file_ref:
            continue
        for name in names:
            existing = files.get(name)
            if not existing:
                files[name] = file_ref
            elif existing == file_ref:
                continue
            elif isinstance(existing, list):
                if file_ref not in existing:
                    existing.append(file_ref)
            else:
                if file_ref != existing:
                    files[name] = [existing, file_ref]
    return outputs, files


def parse_template_outputs(text: str) -> List[str]:
    outputs, _files = parse_template_output_tags(text)
    return outputs


def is_explicit_template_output_file(value: str) -> bool:
    if not value:
        return False
    cleaned = value.strip()
    if cleaned in {"{default_output_file}", "{{default_output_file}}", "default_output_file"}:
        return False
    return True


def parse_frontmatter(text: str) -> Tuple[Dict[str, str], str]:
    if not text.startswith("---"):
        return {}, text
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    end_idx = None
    for idx, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            end_idx = idx
            break
    if end_idx is None:
        return {}, text
    raw = "\n".join(lines[1:end_idx])
    try:
        data = yaml.safe_load(raw) or {}
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    body = "\n".join(lines[end_idx + 1 :])
    return {str(k): str(v) for k, v in data.items() if v is not None}, body


def first_heading(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
    return ""


def step_name_from_filename(stem: str) -> str:
    match = STEP_FILE_RE.match(stem)
    if not match:
        return stem
    name = (match.group(3) or "").strip()
    if not name:
        return stem
    return name.replace("-", " ")


def step_file_sort_key(path: Path) -> Tuple[int, int, str]:
    match = STEP_FILE_RE.match(path.stem)
    if not match:
        return (10**9, 0, path.stem)
    num = int(match.group(1))
    suffix = (match.group(2) or "").lower()
    suffix_idx = 0
    if suffix:
        suffix_idx = 1 + (ord(suffix) - ord("a"))
    return (num, suffix_idx, path.stem)


def build_step_spec(
    step_id: str,
    name: str,
    description: str,
    inputs: Optional[Dict[str, object]] = None,
    outputs: Optional[List[str]] = None,
) -> models.StepSpec:
    return models.StepSpec(
        id=step_id,
        name=name,
        description=description,
        phase="",
        inputs=dict(inputs or {}),
        outputs=list(outputs or []),
        templates=[],
        tools=[],
        validation="",
        evidence="",
        human_gate="",
        retries={"max": 0, "backoff_seconds": 0},
    )


def template_output_file_refs(files: Dict[str, object]) -> List[str]:
    refs: List[str] = []
    seen = set()
    for value in files.values():
        if isinstance(value, list):
            candidates = value
        else:
            candidates = [value]
        for ref in candidates:
            if isinstance(ref, str) and is_explicit_template_output_file(ref):
                if ref not in seen:
                    refs.append(ref)
                    seen.add(ref)
    return refs


def parse_step_files(step_files: Iterable[Path]) -> List[models.StepSpec]:
    steps: List[models.StepSpec] = []
    for path in step_files:
        text = safe_text(path)
        frontmatter, body = parse_frontmatter(text)
        name = frontmatter.get("name") or step_name_from_filename(path.stem)
        description = frontmatter.get("description") or first_heading(body)
        outputs = extract_outputs(text)
        template_outputs, template_output_files = parse_template_output_tags(body)
        inputs: Dict[str, object] = {}
        if template_outputs:
            inputs["template_outputs"] = template_outputs
        if template_output_files:
            inputs["template_output_files"] = template_output_files
            outputs.extend(template_output_file_refs(template_output_files))
        steps.append(build_step_spec(path.stem, name, description, inputs, outputs))
    return steps


def parse_steps_from_xml_like(text: str) -> List[models.StepSpec]:
    steps: List[models.StepSpec] = []
    seen_ids: Dict[str, int] = {}
    matches = list(STEP_BLOCK_RE.finditer(text))
    if not matches:
        matches = [match for match in STEP_TAG_RE.finditer(text)]
    for idx, match in enumerate(matches, 1):
        raw_attrs = match.group(1)
        body = match.group(2) if match.lastindex and match.lastindex >= 2 else ""
        attrs = {k: v for k, v in ATTR_RE.findall(raw_attrs)}
        if attrs.get("substep"):
            continue
        step_id = attrs.get("id")
        number = attrs.get("n")
        if not step_id:
            if number:
                step_id = f"step-{number}"
            else:
                step_id = f"step-{idx}"
        count = seen_ids.get(step_id, 0) + 1
        seen_ids[step_id] = count
        if count > 1:
            step_id = f"{step_id}-{count}"
        name = attrs.get("goal") or attrs.get("title") or step_id
        description = attrs.get("goal") or attrs.get("title") or ""
        template_outputs, template_output_files = parse_template_output_tags(body)
        inputs: Dict[str, object] = {}
        outputs: List[str] = []
        if template_outputs:
            inputs["template_outputs"] = template_outputs
        if template_output_files:
            inputs["template_output_files"] = template_output_files
            outputs.extend(template_output_file_refs(template_output_files))
        steps.append(build_step_spec(step_id, name, description, inputs, outputs))
    return steps


def parse_steps_from_instructions(path: Path) -> List[models.StepSpec]:
    text = safe_text(path)
    return parse_steps_from_xml_like(text)


def resolve_instruction_path(workflow_dir: Path, value: str) -> Path:
    return workflow_dir / Path(value).name


def instruction_path_from_workflow(path: Path) -> Optional[Path]:
    if path.suffix.lower() not in {".yaml", ".yml"}:
        return None
    try:
        data = yaml.safe_load(safe_text(path)) or {}
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    value = data.get("instructions")
    if not isinstance(value, str) or not value:
        return None
    return resolve_instruction_path(path.parent, value)


def parse_workflow_steps(workflow_path: Path) -> List[models.StepSpec]:
    workflow_dir = workflow_path.parent
    step_dir = workflow_dir / "steps"
    if step_dir.exists():
        step_files = sorted(step_dir.glob("step-*.md"), key=step_file_sort_key)
        return parse_step_files(step_files)

    instruction_path = instruction_path_from_workflow(workflow_path)
    if instruction_path and instruction_path.exists():
        steps = parse_steps_from_instructions(instruction_path)
        if steps:
            return steps

    if workflow_path.suffix.lower() in {".md", ".xml"}:
        return parse_steps_from_instructions(workflow_path)

    return []
