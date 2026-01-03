"""Verification checks for BQUAT installation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .manifest import compute_checksum, read_manifest


@dataclass
class VerificationCheck:
    """Result of a single verification check."""

    name: str
    passed: bool
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class VerificationReport:
    """Complete verification report."""

    passed: bool
    checks: list[VerificationCheck]
    summary: str

    def to_dict(self) -> dict[str, Any]:
        """Convert report to dictionary."""
        return {
            "passed": self.passed,
            "summary": self.summary,
            "checks": [
                {
                    "name": c.name,
                    "passed": c.passed,
                    "message": c.message,
                    "details": c.details,
                }
                for c in self.checks
            ],
        }


class InstallationVerifier:
    """Verifies BQUAT installation integrity."""

    BQUAT_DIR = "_bquat"

    def __init__(self, target_dir: Path) -> None:
        """Initialize verifier with target directory."""
        self.target_dir = target_dir
        self.bquat_dir = target_dir / self.BQUAT_DIR

    def verify(self) -> VerificationReport:
        """Run all verification checks."""
        checks: list[VerificationCheck] = []

        # Run all checks
        checks.append(self._check_manifest_exists())
        checks.append(self._check_bmad_assets())
        checks.append(self._check_quint_available())
        checks.append(self._check_runtime_importable())
        checks.append(self._check_telis_registry())
        checks.append(self._check_config_valid())
        checks.append(self._check_ide_commands())
        checks.append(self._check_file_integrity())
        checks.append(self._check_component_versions())
        checks.append(self._check_python_deps())

        # Calculate overall result
        passed = all(c.passed for c in checks)
        passed_count = sum(1 for c in checks if c.passed)
        total_count = len(checks)

        summary = f"{passed_count}/{total_count} checks passed"
        if not passed:
            failed = [c.name for c in checks if not c.passed]
            summary += f". Failed: {', '.join(failed)}"

        return VerificationReport(passed=passed, checks=checks, summary=summary)

    def _check_manifest_exists(self) -> VerificationCheck:
        """Check that manifest file exists and is valid."""
        manifest_path = self.bquat_dir / "manifest.json"
        manifest = read_manifest(manifest_path)

        if manifest is None:
            return VerificationCheck(
                name="manifest_exists",
                passed=False,
                message="Manifest file not found or invalid",
            )

        return VerificationCheck(
            name="manifest_exists",
            passed=True,
            message="Manifest file is valid",
            details={
                "install_id": manifest.install_id,
                "version": manifest.bquat_version,
            },
        )

    def _check_bmad_assets(self) -> VerificationCheck:
        """Check that BMAD core assets are present."""
        bmad_dir = self.bquat_dir / "bmad"

        if not bmad_dir.exists():
            return VerificationCheck(
                name="bmad_assets",
                passed=False,
                message="BMAD assets directory not found",
            )

        # Check for core directories
        required_dirs = ["core", "modules", "utility"]
        missing = [d for d in required_dirs if not (bmad_dir / d).exists()]

        if missing:
            return VerificationCheck(
                name="bmad_assets",
                passed=False,
                message=f"Missing BMAD directories: {', '.join(missing)}",
                details={"missing": missing},
            )

        # Count files
        file_count = sum(1 for _ in bmad_dir.rglob("*") if _.is_file())

        return VerificationCheck(
            name="bmad_assets",
            passed=True,
            message=f"BMAD assets present ({file_count} files)",
            details={"file_count": file_count},
        )

    def _check_quint_available(self) -> VerificationCheck:
        """Check that QUINT binary or source is available."""
        quint_dir = self.bquat_dir / "quint"

        if not quint_dir.exists():
            return VerificationCheck(
                name="quint_available",
                passed=False,
                message="QUINT directory not found",
            )

        # Check for binary
        bin_path = quint_dir / "bin" / "quint"
        if bin_path.exists() or (quint_dir / "bin" / "quint.exe").exists():
            return VerificationCheck(
                name="quint_available",
                passed=True,
                message="QUINT binary available",
                details={"type": "binary"},
            )

        # Check for source
        src_dir = quint_dir / "src"
        go_mod = quint_dir / "go.mod"

        if src_dir.exists() or go_mod.exists():
            return VerificationCheck(
                name="quint_available",
                passed=True,
                message="QUINT source available (binary not built)",
                details={"type": "source"},
            )

        return VerificationCheck(
            name="quint_available",
            passed=False,
            message="QUINT binary or source not found",
        )

    def _check_runtime_importable(self) -> VerificationCheck:
        """Check that runtime modules can be imported."""
        runtime_dir = self.bquat_dir / "runtime"

        if not runtime_dir.exists():
            return VerificationCheck(
                name="runtime_importable",
                passed=False,
                message="Runtime directory not found",
            )

        # Check for key modules
        required_modules = ["engine.py", "models.py", "storage.py"]
        missing = [m for m in required_modules if not (runtime_dir / m).exists()]

        if missing:
            return VerificationCheck(
                name="runtime_importable",
                passed=False,
                message=f"Missing runtime modules: {', '.join(missing)}",
                details={"missing": missing},
            )

        # Check for TELIS and QUINT submodules
        telis_dir = runtime_dir / "telis"
        quint_dir = runtime_dir / "quint"

        submodules = {
            "telis": telis_dir.exists(),
            "quint": quint_dir.exists(),
        }

        return VerificationCheck(
            name="runtime_importable",
            passed=True,
            message="Runtime modules available",
            details={"submodules": submodules},
        )

    def _check_telis_registry(self) -> VerificationCheck:
        """Check that TELIS shard registry is valid."""
        telis_dir = self.bquat_dir / "runtime" / "telis"

        if not telis_dir.exists():
            return VerificationCheck(
                name="telis_registry",
                passed=False,
                message="TELIS directory not found",
            )

        # Check for shards module
        shards_file = telis_dir / "shards.py"
        if not shards_file.exists():
            return VerificationCheck(
                name="telis_registry",
                passed=False,
                message="TELIS shards module not found",
            )

        return VerificationCheck(
            name="telis_registry",
            passed=True,
            message="TELIS shard registry available",
        )

    def _check_config_valid(self) -> VerificationCheck:
        """Check that configuration file is present and valid."""
        config_dir = self.bquat_dir / "config"
        runtime_yaml = config_dir / "runtime.yaml"

        if not config_dir.exists():
            return VerificationCheck(
                name="config_valid",
                passed=False,
                message="Config directory not found",
            )

        if not runtime_yaml.exists():
            return VerificationCheck(
                name="config_valid",
                passed=False,
                message="runtime.yaml not found",
            )

        # Try to parse YAML
        try:
            import yaml

            with open(runtime_yaml, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)

            if not isinstance(config, dict):
                return VerificationCheck(
                    name="config_valid",
                    passed=False,
                    message="runtime.yaml is not valid YAML",
                )

            return VerificationCheck(
                name="config_valid",
                passed=True,
                message="Configuration file is valid",
                details={"sections": list(config.keys())},
            )
        except ImportError:
            # PyYAML not available, just check file exists
            return VerificationCheck(
                name="config_valid",
                passed=True,
                message="Configuration file present (YAML parsing skipped)",
            )
        except Exception as e:
            return VerificationCheck(
                name="config_valid",
                passed=False,
                message=f"Failed to parse runtime.yaml: {e}",
            )

    def _check_ide_commands(self) -> VerificationCheck:
        """Check that IDE commands are registered."""
        claude_commands = self.target_dir / ".claude" / "commands"

        if not claude_commands.exists():
            return VerificationCheck(
                name="ide_commands",
                passed=False,
                message="Claude commands directory not found",
            )

        # Check for BQUAT commands
        bquat_commands = ["bquat-status.md", "bquat-run.md", "bquat-evidence.md"]
        found = [c for c in bquat_commands if (claude_commands / c).exists()]
        missing = [c for c in bquat_commands if c not in found]

        if missing:
            return VerificationCheck(
                name="ide_commands",
                passed=False,
                message=f"Missing IDE commands: {', '.join(missing)}",
                details={"found": found, "missing": missing},
            )

        # Count total commands
        total_commands = list(claude_commands.glob("*.md"))

        return VerificationCheck(
            name="ide_commands",
            passed=True,
            message=f"IDE commands registered ({len(total_commands)} total)",
            details={"bquat_commands": found, "total": len(total_commands)},
        )

    def _check_file_integrity(self) -> VerificationCheck:
        """Check file integrity using checksums from manifest."""
        manifest_path = self.bquat_dir / "manifest.json"
        manifest = read_manifest(manifest_path)

        if manifest is None:
            return VerificationCheck(
                name="file_integrity",
                passed=False,
                message="Cannot verify integrity without manifest",
            )

        corrupted: list[str] = []
        missing: list[str] = []
        checked = 0

        # Sample check (check first 50 files to avoid long verification)
        for file_record in manifest.files[:50]:
            file_path = self.bquat_dir / file_record.path
            if not file_path.exists():
                missing.append(file_record.path)
                continue

            actual_checksum = compute_checksum(file_path)
            if actual_checksum != file_record.checksum:
                corrupted.append(file_record.path)

            checked += 1

        if corrupted or missing:
            return VerificationCheck(
                name="file_integrity",
                passed=False,
                message=f"Integrity issues: {len(corrupted)} corrupted, {len(missing)} missing",
                details={"corrupted": corrupted, "missing": missing},
            )

        return VerificationCheck(
            name="file_integrity",
            passed=True,
            message=f"File integrity verified ({checked} files checked)",
            details={"checked": checked, "total": len(manifest.files)},
        )

    def _check_component_versions(self) -> VerificationCheck:
        """Check that component versions match manifest."""
        manifest_path = self.bquat_dir / "manifest.json"
        manifest = read_manifest(manifest_path)

        if manifest is None:
            return VerificationCheck(
                name="component_versions",
                passed=False,
                message="Cannot verify versions without manifest",
            )

        components = {c.name: c.version for c in manifest.components}
        expected = ["bmad", "quint", "runtime"]
        missing = [c for c in expected if c not in components]

        if missing:
            return VerificationCheck(
                name="component_versions",
                passed=False,
                message=f"Missing component records: {', '.join(missing)}",
                details={"found": components, "missing": missing},
            )

        return VerificationCheck(
            name="component_versions",
            passed=True,
            message="All component versions recorded",
            details={"versions": components},
        )

    def _check_python_deps(self) -> VerificationCheck:
        """Check that Python dependencies are satisfied."""
        # Check for required packages
        required = ["yaml"]  # PyYAML
        missing: list[str] = []

        for pkg in required:
            try:
                __import__(pkg)
            except ImportError:
                missing.append(pkg)

        if missing:
            return VerificationCheck(
                name="python_deps",
                passed=False,
                message=f"Missing Python packages: {', '.join(missing)}",
                details={"missing": missing},
            )

        return VerificationCheck(
            name="python_deps",
            passed=True,
            message="Python dependencies satisfied",
        )


def verify_installation(target_dir: Path) -> VerificationReport:
    """Convenience function to verify an installation."""
    verifier = InstallationVerifier(target_dir)
    return verifier.verify()
