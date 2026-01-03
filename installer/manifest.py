"""Installation manifest tracking for BQUAT unified installer."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class ComponentVersion:
    """Version information for an installed component."""

    name: str
    version: str
    commit: str
    installed_at: str
    source_path: str


@dataclass
class FileRecord:
    """Record of an installed file with checksum."""

    path: str
    checksum: str
    size: int
    installed_at: str


@dataclass
class InstallManifest:
    """Tracks the state of a BQUAT installation."""

    install_id: str
    installed_at: str
    updated_at: str
    target_dir: str
    bquat_version: str
    components: list[ComponentVersion] = field(default_factory=list)
    files: list[FileRecord] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert manifest to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> InstallManifest:
        """Create manifest from dictionary."""
        components = [ComponentVersion(**c) for c in data.get("components", [])]
        files = [FileRecord(**f) for f in data.get("files", [])]
        return cls(
            install_id=data["install_id"],
            installed_at=data["installed_at"],
            updated_at=data["updated_at"],
            target_dir=data["target_dir"],
            bquat_version=data["bquat_version"],
            components=components,
            files=files,
            config=data.get("config", {}),
        )

    def add_component(self, component: ComponentVersion) -> None:
        """Add or update a component in the manifest."""
        for i, existing in enumerate(self.components):
            if existing.name == component.name:
                self.components[i] = component
                return
        self.components.append(component)

    def add_file(self, file_record: FileRecord) -> None:
        """Add or update a file record in the manifest."""
        for i, existing in enumerate(self.files):
            if existing.path == file_record.path:
                self.files[i] = file_record
                return
        self.files.append(file_record)

    def get_component(self, name: str) -> ComponentVersion | None:
        """Get a component by name."""
        for component in self.components:
            if component.name == name:
                return component
        return None

    def touch(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now(timezone.utc).isoformat()


def compute_checksum(file_path: Path) -> str:
    """Compute SHA256 checksum of a file."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def create_file_record(file_path: Path, relative_to: Path) -> FileRecord:
    """Create a file record from a file path."""
    rel_path = file_path.relative_to(relative_to)
    return FileRecord(
        path=str(rel_path).replace("\\", "/"),
        checksum=compute_checksum(file_path),
        size=file_path.stat().st_size,
        installed_at=datetime.now(timezone.utc).isoformat(),
    )


def read_manifest(manifest_path: Path) -> InstallManifest | None:
    """Read manifest from file."""
    if not manifest_path.exists():
        return None
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return InstallManifest.from_dict(data)
    except (json.JSONDecodeError, KeyError):
        return None


def write_manifest(manifest_path: Path, manifest: InstallManifest) -> None:
    """Write manifest to file."""
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest.to_dict(), f, indent=2)


def get_bquat_version() -> str:
    """Get the current BQUAT version."""
    return "1.0.0"


def get_git_commit(repo_path: Path) -> str:
    """Get the current git commit hash for a repository."""
    import subprocess

    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()[:12]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"
