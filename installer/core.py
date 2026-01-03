"""Core installation orchestrator for BQUAT unified installer."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .manifest import (
    ComponentVersion,
    InstallManifest,
    create_file_record,
    get_bquat_version,
    get_git_commit,
    read_manifest,
    write_manifest,
)


@dataclass
class InstallResult:
    """Result of an installation operation."""

    success: bool
    message: str
    manifest: InstallManifest | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class InstallConfig:
    """Configuration for installation."""

    target_dir: Path
    include_bmad: bool = True
    include_quint: bool = True
    include_runtime: bool = True
    include_docs: bool = True
    build_quint: bool = False
    force: bool = False


class BquatInstaller:
    """Unified installer for BQUAT framework."""

    BQUAT_DIR = "_bquat"
    MANIFEST_FILE = "manifest.json"

    def __init__(self, source_root: Path | None = None) -> None:
        """Initialize installer with source root."""
        if source_root is None:
            source_root = Path(__file__).resolve().parents[1]
        self.source_root = source_root
        self.bmad_root = source_root / "BMAD-METHOD"
        self.quint_root = source_root / "quint-code"
        self.runtime_root = source_root / "runtime"
        self.config_root = source_root / "config"
        self.docs_root = source_root / "docs"

    def install(self, config: InstallConfig) -> InstallResult:
        """Perform full installation to target directory."""
        errors: list[str] = []
        warnings: list[str] = []

        target = config.target_dir / self.BQUAT_DIR
        manifest_path = target / self.MANIFEST_FILE

        # Check for existing installation
        existing = read_manifest(manifest_path)
        if existing and not config.force:
            return InstallResult(
                success=False,
                message=f"Installation already exists at {target}. Use --force to overwrite.",
                errors=["Existing installation found"],
            )

        # Create target directory
        target.mkdir(parents=True, exist_ok=True)

        # Create manifest
        now = datetime.now(timezone.utc).isoformat()
        manifest = InstallManifest(
            install_id=uuid4().hex[:12],
            installed_at=now,
            updated_at=now,
            target_dir=str(config.target_dir),
            bquat_version=get_bquat_version(),
            config={
                "include_bmad": config.include_bmad,
                "include_quint": config.include_quint,
                "include_runtime": config.include_runtime,
                "include_docs": config.include_docs,
            },
        )

        # Install components
        if config.include_bmad:
            result = self._install_bmad(target, manifest)
            if not result["success"]:
                errors.extend(result.get("errors", []))
            warnings.extend(result.get("warnings", []))

        if config.include_quint:
            result = self._install_quint(target, manifest, build=config.build_quint)
            if not result["success"]:
                errors.extend(result.get("errors", []))
            warnings.extend(result.get("warnings", []))

        if config.include_runtime:
            result = self._install_runtime(target, manifest)
            if not result["success"]:
                errors.extend(result.get("errors", []))
            warnings.extend(result.get("warnings", []))

        if config.include_docs:
            result = self._install_docs(target, manifest)
            if not result["success"]:
                errors.extend(result.get("errors", []))
            warnings.extend(result.get("warnings", []))

        # Install configuration
        result = self._install_config(target, manifest)
        if not result["success"]:
            errors.extend(result.get("errors", []))
        warnings.extend(result.get("warnings", []))

        # Install IDE commands
        result = self._install_ide_commands(config.target_dir, manifest)
        if not result["success"]:
            errors.extend(result.get("errors", []))
        warnings.extend(result.get("warnings", []))

        # Write manifest
        write_manifest(manifest_path, manifest)

        if errors:
            return InstallResult(
                success=False,
                message="Installation completed with errors",
                manifest=manifest,
                errors=errors,
                warnings=warnings,
            )

        return InstallResult(
            success=True,
            message=f"BQUAT installed successfully to {target}",
            manifest=manifest,
            warnings=warnings,
        )

    def _install_bmad(self, target: Path, manifest: InstallManifest) -> dict[str, Any]:
        """Install BMAD assets."""
        errors: list[str] = []
        warnings: list[str] = []

        bmad_src = self.bmad_root / "src"
        if not bmad_src.exists():
            errors.append(f"BMAD source not found at {bmad_src}")
            return {"success": False, "errors": errors, "warnings": warnings}

        bmad_target = target / "bmad"
        try:
            if bmad_target.exists():
                shutil.rmtree(bmad_target)
            shutil.copytree(bmad_src, bmad_target)

            # Record component
            manifest.add_component(
                ComponentVersion(
                    name="bmad",
                    version="1.0.0",
                    commit=get_git_commit(self.bmad_root),
                    installed_at=datetime.now(timezone.utc).isoformat(),
                    source_path=str(bmad_src),
                )
            )

            # Record files
            for file_path in bmad_target.rglob("*"):
                if file_path.is_file():
                    manifest.add_file(create_file_record(file_path, target))

        except (OSError, shutil.Error) as e:
            errors.append(f"Failed to copy BMAD assets: {e}")
            return {"success": False, "errors": errors, "warnings": warnings}

        return {"success": True, "errors": errors, "warnings": warnings}

    def _install_quint(
        self, target: Path, manifest: InstallManifest, build: bool = False
    ) -> dict[str, Any]:
        """Install QUINT assets."""
        errors: list[str] = []
        warnings: list[str] = []

        quint_src = self.quint_root / "src"
        if not quint_src.exists():
            # Fall back to copying the whole quint-code directory
            if not self.quint_root.exists():
                warnings.append("QUINT source not found, skipping")
                return {"success": True, "errors": errors, "warnings": warnings}
            quint_src = self.quint_root

        quint_target = target / "quint"
        quint_target.mkdir(parents=True, exist_ok=True)

        try:
            # Copy source files
            src_target = quint_target / "src"
            if src_target.exists():
                shutil.rmtree(src_target)

            if (self.quint_root / "src").exists():
                shutil.copytree(self.quint_root / "src", src_target)
            else:
                # Copy essential files from quint-code root
                for item in ["go.mod", "go.sum", "main.go"]:
                    src_file = self.quint_root / item
                    if src_file.exists():
                        shutil.copy2(src_file, quint_target / item)

            # Try to build if requested
            if build:
                build_result = self._build_quint(quint_target)
                if not build_result["success"]:
                    warnings.append("QUINT binary build failed, source installed instead")
                    warnings.extend(build_result.get("warnings", []))

            # Record component
            manifest.add_component(
                ComponentVersion(
                    name="quint",
                    version="1.0.0",
                    commit=get_git_commit(self.quint_root),
                    installed_at=datetime.now(timezone.utc).isoformat(),
                    source_path=str(self.quint_root),
                )
            )

            # Record files
            for file_path in quint_target.rglob("*"):
                if file_path.is_file():
                    manifest.add_file(create_file_record(file_path, target))

        except (OSError, shutil.Error) as e:
            errors.append(f"Failed to copy QUINT assets: {e}")
            return {"success": False, "errors": errors, "warnings": warnings}

        return {"success": True, "errors": errors, "warnings": warnings}

    def _build_quint(self, quint_dir: Path) -> dict[str, Any]:
        """Attempt to build QUINT Go binary."""
        warnings: list[str] = []

        bin_dir = quint_dir / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)

        try:
            result = subprocess.run(
                ["go", "build", "-o", str(bin_dir / "quint"), "."],
                cwd=quint_dir,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                warnings.append(f"Go build failed: {result.stderr}")
                return {"success": False, "warnings": warnings}
            return {"success": True, "warnings": warnings}
        except FileNotFoundError:
            warnings.append("Go compiler not found")
            return {"success": False, "warnings": warnings}
        except subprocess.TimeoutExpired:
            warnings.append("Go build timed out")
            return {"success": False, "warnings": warnings}

    def _install_runtime(self, target: Path, manifest: InstallManifest) -> dict[str, Any]:
        """Install BQUAT runtime."""
        errors: list[str] = []
        warnings: list[str] = []

        if not self.runtime_root.exists():
            errors.append(f"Runtime not found at {self.runtime_root}")
            return {"success": False, "errors": errors, "warnings": warnings}

        runtime_target = target / "runtime"
        try:
            if runtime_target.exists():
                shutil.rmtree(runtime_target)
            shutil.copytree(
                self.runtime_root,
                runtime_target,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"),
            )

            # Record component
            manifest.add_component(
                ComponentVersion(
                    name="runtime",
                    version=get_bquat_version(),
                    commit=get_git_commit(self.source_root),
                    installed_at=datetime.now(timezone.utc).isoformat(),
                    source_path=str(self.runtime_root),
                )
            )

            # Record files
            for file_path in runtime_target.rglob("*"):
                if file_path.is_file():
                    manifest.add_file(create_file_record(file_path, target))

        except (OSError, shutil.Error) as e:
            errors.append(f"Failed to copy runtime: {e}")
            return {"success": False, "errors": errors, "warnings": warnings}

        return {"success": True, "errors": errors, "warnings": warnings}

    def _install_docs(self, target: Path, manifest: InstallManifest) -> dict[str, Any]:
        """Install documentation."""
        errors: list[str] = []
        warnings: list[str] = []

        if not self.docs_root.exists():
            warnings.append("Documentation not found, skipping")
            return {"success": True, "errors": errors, "warnings": warnings}

        docs_target = target / "docs"
        try:
            if docs_target.exists():
                shutil.rmtree(docs_target)
            shutil.copytree(self.docs_root, docs_target)

            # Record files
            for file_path in docs_target.rglob("*"):
                if file_path.is_file():
                    manifest.add_file(create_file_record(file_path, target))

        except (OSError, shutil.Error) as e:
            warnings.append(f"Failed to copy docs: {e}")

        return {"success": True, "errors": errors, "warnings": warnings}

    def _install_config(self, target: Path, manifest: InstallManifest) -> dict[str, Any]:
        """Install configuration files."""
        errors: list[str] = []
        warnings: list[str] = []

        config_target = target / "config"
        config_target.mkdir(parents=True, exist_ok=True)

        # Copy runtime.yaml if it exists
        runtime_yaml = self.config_root / "runtime.yaml"
        if runtime_yaml.exists():
            try:
                shutil.copy2(runtime_yaml, config_target / "runtime.yaml")
                manifest.add_file(create_file_record(config_target / "runtime.yaml", target))
            except (OSError, shutil.Error) as e:
                warnings.append(f"Failed to copy runtime.yaml: {e}")

        return {"success": True, "errors": errors, "warnings": warnings}

    def _install_ide_commands(
        self, project_root: Path, manifest: InstallManifest
    ) -> dict[str, Any]:
        """Install IDE slash commands."""
        errors: list[str] = []
        warnings: list[str] = []

        # Install Claude Code commands
        claude_commands = project_root / ".claude" / "commands"
        claude_commands.mkdir(parents=True, exist_ok=True)

        # Copy BMAD commands if available
        bmad_commands = self.bmad_root / "tools" / "cli" / "installers" / "claude-code" / "commands"
        if bmad_commands.exists():
            try:
                for cmd_file in bmad_commands.glob("*.md"):
                    shutil.copy2(cmd_file, claude_commands / cmd_file.name)
            except (OSError, shutil.Error) as e:
                warnings.append(f"Failed to copy BMAD commands: {e}")

        # Create BQUAT-specific commands
        bquat_commands = [
            ("bquat-status.md", self._generate_status_command()),
            ("bquat-run.md", self._generate_run_command()),
            ("bquat-evidence.md", self._generate_evidence_command()),
        ]

        for filename, content in bquat_commands:
            cmd_path = claude_commands / filename
            try:
                with open(cmd_path, "w", encoding="utf-8") as f:
                    f.write(content)
            except OSError as e:
                warnings.append(f"Failed to write {filename}: {e}")

        return {"success": True, "errors": errors, "warnings": warnings}

    def _generate_status_command(self) -> str:
        """Generate BQUAT status slash command."""
        return """---
description: Show BQUAT installation status and run summary
---

Show the current BQUAT installation status including:
1. Installed component versions (BMAD, QUINT, Runtime)
2. Active workflow runs and their status
3. Evidence chain summary
4. Recent activity log

Use the BQUAT runtime to query this information from _bquat/manifest.json and the runs directory.
"""

    def _generate_run_command(self) -> str:
        """Generate BQUAT run slash command."""
        return """---
description: Execute a BQUAT workflow
arguments:
  - name: workflow
    description: The workflow to execute (e.g., bmm/prd, core/adr)
    required: true
---

Execute the specified BQUAT workflow using the runtime engine.

Workflow: $ARGUMENTS.workflow

1. Parse the workflow specification from BMAD assets
2. Create a new run in the runs directory
3. Execute steps according to the workflow definition
4. Record evidence and artifacts
5. Report completion status
"""

    def _generate_evidence_command(self) -> str:
        """Generate BQUAT evidence slash command."""
        return """---
description: Query QUINT evidence chain
arguments:
  - name: run_id
    description: The run ID to query evidence for
    required: false
---

Query the QUINT evidence chain for the specified run or the most recent run.

$ARGUMENTS.run_id

1. Load evidence records from the run directory
2. Calculate WLNK assurance scores
3. Display evidence chain with confidence levels
4. Highlight any gaps or weaknesses in the chain
"""

    def update(self, target_dir: Path) -> InstallResult:
        """Update an existing installation."""
        manifest_path = target_dir / self.BQUAT_DIR / self.MANIFEST_FILE
        existing = read_manifest(manifest_path)

        if not existing:
            return InstallResult(
                success=False,
                message="No existing installation found",
                errors=["Manifest not found"],
            )

        # Re-install with force
        config = InstallConfig(
            target_dir=target_dir,
            include_bmad=existing.config.get("include_bmad", True),
            include_quint=existing.config.get("include_quint", True),
            include_runtime=existing.config.get("include_runtime", True),
            include_docs=existing.config.get("include_docs", True),
            force=True,
        )

        result = self.install(config)
        if result.success:
            result.message = f"BQUAT updated successfully at {target_dir / self.BQUAT_DIR}"

        return result

    def status(self, target_dir: Path) -> dict[str, Any]:
        """Get installation status."""
        manifest_path = target_dir / self.BQUAT_DIR / self.MANIFEST_FILE
        manifest = read_manifest(manifest_path)

        if not manifest:
            return {
                "installed": False,
                "message": "No BQUAT installation found",
            }

        return {
            "installed": True,
            "install_id": manifest.install_id,
            "installed_at": manifest.installed_at,
            "updated_at": manifest.updated_at,
            "bquat_version": manifest.bquat_version,
            "components": [
                {
                    "name": c.name,
                    "version": c.version,
                    "commit": c.commit,
                }
                for c in manifest.components
            ],
            "file_count": len(manifest.files),
            "config": manifest.config,
        }
