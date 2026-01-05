"""Packaging module for generated code artifacts.

Provides functionality to package generated code into distributable formats:
- Python packages (wheel, sdist)
- Node.js packages (npm)
- Docker containers
- ZIP archives

This module enables the complete E2E user journey from idea to deployable artifact.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from runtime.time_provider import get_current_time

PackageType = Literal["python", "node", "docker", "zip"]
PackageStatus = Literal["pending", "building", "completed", "failed"]


@dataclass
class PackageConfig:
    """Configuration for package generation."""

    name: str
    version: str = "0.1.0"
    description: str = ""
    author: str = ""
    license: str = "MIT"
    entry_point: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    dev_dependencies: List[str] = field(default_factory=list)
    scripts: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "license": self.license,
            "entry_point": self.entry_point,
            "dependencies": list(self.dependencies),
            "dev_dependencies": list(self.dev_dependencies),
            "scripts": dict(self.scripts),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PackageConfig:
        return cls(
            name=data.get("name", "unnamed"),
            version=data.get("version", "0.1.0"),
            description=data.get("description", ""),
            author=data.get("author", ""),
            license=data.get("license", "MIT"),
            entry_point=data.get("entry_point"),
            dependencies=list(data.get("dependencies", [])),
            dev_dependencies=list(data.get("dev_dependencies", [])),
            scripts=dict(data.get("scripts", {})),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class PackageResult:
    """Result of a packaging operation."""

    status: PackageStatus
    package_type: PackageType
    output_path: Optional[str] = None
    artifacts: List[str] = field(default_factory=list)
    error: Optional[str] = None
    duration_ms: int = 0
    created_at: str = field(default_factory=get_current_time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "package_type": self.package_type,
            "output_path": self.output_path,
            "artifacts": list(self.artifacts),
            "error": self.error,
            "duration_ms": self.duration_ms,
            "created_at": self.created_at,
        }


class PackageBuilder:
    """Builder for creating distributable packages."""

    def __init__(self, source_dir: Path, output_dir: Path) -> None:
        self.source_dir = Path(source_dir).resolve()
        self.output_dir = Path(output_dir).resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def build_python_package(self, config: PackageConfig) -> PackageResult:
        """Build a Python package (wheel and sdist).

        Creates pyproject.toml and builds using pip.
        """
        import time

        start = time.perf_counter()

        try:
            # Create pyproject.toml
            pyproject = self._generate_pyproject_toml(config)
            pyproject_path = self.source_dir / "pyproject.toml"
            pyproject_path.write_text(pyproject, encoding="utf-8")

            # Create __init__.py if missing
            pkg_dir = self.source_dir / config.name.replace("-", "_")
            pkg_dir.mkdir(exist_ok=True)
            init_file = pkg_dir / "__init__.py"
            if not init_file.exists():
                init_file.write_text(
                    f'"""Package {config.name}."""\n\n__version__ = "{config.version}"\n',
                    encoding="utf-8",
                )

            # Build the package
            dist_dir = self.source_dir / "dist"
            result = subprocess.run(
                [sys.executable, "-m", "pip", "wheel", ".", "-w", str(dist_dir)],
                cwd=self.source_dir,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )

            duration_ms = int((time.perf_counter() - start) * 1000)

            if result.returncode != 0:
                return PackageResult(
                    status="failed",
                    package_type="python",
                    error=result.stderr or result.stdout,
                    duration_ms=duration_ms,
                )

            # Collect artifacts
            artifacts = [str(p.name) for p in dist_dir.glob("*.whl")]

            # Copy to output dir
            for artifact in dist_dir.glob("*.whl"):
                shutil.copy(artifact, self.output_dir / artifact.name)

            return PackageResult(
                status="completed",
                package_type="python",
                output_path=str(self.output_dir),
                artifacts=artifacts,
                duration_ms=duration_ms,
            )

        except subprocess.TimeoutExpired:
            duration_ms = int((time.perf_counter() - start) * 1000)
            return PackageResult(
                status="failed",
                package_type="python",
                error="Build timeout",
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = int((time.perf_counter() - start) * 1000)
            return PackageResult(
                status="failed",
                package_type="python",
                error=str(e),
                duration_ms=duration_ms,
            )

    def build_node_package(self, config: PackageConfig) -> PackageResult:
        """Build a Node.js package (npm pack).

        Creates package.json and runs npm pack.
        """
        import time

        start = time.perf_counter()

        try:
            # Create package.json
            package_json = self._generate_package_json(config)
            package_path = self.source_dir / "package.json"
            package_path.write_text(
                json.dumps(package_json, indent=2, sort_keys=True),
                encoding="utf-8",
            )

            # Create index.js if missing and entry_point specified
            if config.entry_point:
                entry_path = self.source_dir / config.entry_point
                if not entry_path.exists():
                    entry_path.write_text(
                        f"// {config.name}\nmodule.exports = {{}};\n",
                        encoding="utf-8",
                    )

            # Run npm pack
            npm_cmd = shutil.which("npm")
            if not npm_cmd:
                duration_ms = int((time.perf_counter() - start) * 1000)
                return PackageResult(
                    status="failed",
                    package_type="node",
                    error="npm not found in PATH",
                    duration_ms=duration_ms,
                )

            result = subprocess.run(
                [npm_cmd, "pack"],
                cwd=self.source_dir,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )

            duration_ms = int((time.perf_counter() - start) * 1000)

            if result.returncode != 0:
                return PackageResult(
                    status="failed",
                    package_type="node",
                    error=result.stderr or result.stdout,
                    duration_ms=duration_ms,
                )

            # Find the generated tarball
            tarballs = list(self.source_dir.glob("*.tgz"))
            artifacts = [t.name for t in tarballs]

            # Copy to output dir
            for tarball in tarballs:
                shutil.copy(tarball, self.output_dir / tarball.name)

            return PackageResult(
                status="completed",
                package_type="node",
                output_path=str(self.output_dir),
                artifacts=artifacts,
                duration_ms=duration_ms,
            )

        except subprocess.TimeoutExpired:
            duration_ms = int((time.perf_counter() - start) * 1000)
            return PackageResult(
                status="failed",
                package_type="node",
                error="Build timeout",
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = int((time.perf_counter() - start) * 1000)
            return PackageResult(
                status="failed",
                package_type="node",
                error=str(e),
                duration_ms=duration_ms,
            )

    def build_zip_archive(self, config: PackageConfig) -> PackageResult:
        """Build a ZIP archive of the source directory."""
        import time

        start = time.perf_counter()

        try:
            archive_name = f"{config.name}-{config.version}"
            archive_path = self.output_dir / archive_name

            # Create the archive
            shutil.make_archive(
                str(archive_path),
                "zip",
                self.source_dir,
            )

            duration_ms = int((time.perf_counter() - start) * 1000)

            return PackageResult(
                status="completed",
                package_type="zip",
                output_path=str(self.output_dir),
                artifacts=[f"{archive_name}.zip"],
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = int((time.perf_counter() - start) * 1000)
            return PackageResult(
                status="failed",
                package_type="zip",
                error=str(e),
                duration_ms=duration_ms,
            )

    def build_docker_image(self, config: PackageConfig) -> PackageResult:
        """Build a Docker image.

        Creates a Dockerfile if not present and builds the image.
        """
        import time

        start = time.perf_counter()

        try:
            # Check for docker
            docker_cmd = shutil.which("docker")
            if not docker_cmd:
                duration_ms = int((time.perf_counter() - start) * 1000)
                return PackageResult(
                    status="failed",
                    package_type="docker",
                    error="docker not found in PATH",
                    duration_ms=duration_ms,
                )

            # Create Dockerfile if missing
            dockerfile_path = self.source_dir / "Dockerfile"
            if not dockerfile_path.exists():
                dockerfile = self._generate_dockerfile(config)
                dockerfile_path.write_text(dockerfile, encoding="utf-8")

            # Build the image
            image_tag = f"{config.name}:{config.version}"
            result = subprocess.run(
                [docker_cmd, "build", "-t", image_tag, "."],
                cwd=self.source_dir,
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )

            duration_ms = int((time.perf_counter() - start) * 1000)

            if result.returncode != 0:
                return PackageResult(
                    status="failed",
                    package_type="docker",
                    error=result.stderr or result.stdout,
                    duration_ms=duration_ms,
                )

            return PackageResult(
                status="completed",
                package_type="docker",
                output_path=image_tag,
                artifacts=[image_tag],
                duration_ms=duration_ms,
            )

        except subprocess.TimeoutExpired:
            duration_ms = int((time.perf_counter() - start) * 1000)
            return PackageResult(
                status="failed",
                package_type="docker",
                error="Build timeout",
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = int((time.perf_counter() - start) * 1000)
            return PackageResult(
                status="failed",
                package_type="docker",
                error=str(e),
                duration_ms=duration_ms,
            )

    def build(
        self,
        config: PackageConfig,
        package_type: PackageType,
    ) -> PackageResult:
        """Build a package of the specified type."""
        builders = {
            "python": self.build_python_package,
            "node": self.build_node_package,
            "zip": self.build_zip_archive,
            "docker": self.build_docker_image,
        }
        builder = builders.get(package_type)
        if not builder:
            return PackageResult(
                status="failed",
                package_type=package_type,
                error=f"Unknown package type: {package_type}",
            )
        return builder(config)

    def _generate_pyproject_toml(self, config: PackageConfig) -> str:
        """Generate pyproject.toml content."""
        deps_str = ", ".join(f'"{d}"' for d in config.dependencies)
        return f'''[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "{config.name}"
version = "{config.version}"
description = "{config.description}"
authors = [{{name = "{config.author}"}}]
license = {{text = "{config.license}"}}
requires-python = ">=3.11"
dependencies = [{deps_str}]

[project.optional-dependencies]
dev = []

[tool.setuptools.packages.find]
where = ["."]
'''

    def _generate_package_json(self, config: PackageConfig) -> Dict[str, Any]:
        """Generate package.json content."""
        return {
            "name": config.name,
            "version": config.version,
            "description": config.description,
            "author": config.author,
            "license": config.license,
            "main": config.entry_point or "index.js",
            "scripts": config.scripts or {"test": "echo 'no tests'"},
            "dependencies": {d: "*" for d in config.dependencies},
            "devDependencies": {d: "*" for d in config.dev_dependencies},
        }

    def _generate_dockerfile(self, config: PackageConfig) -> str:
        """Generate Dockerfile content."""
        return f'''FROM python:3.11-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -e .

CMD ["python", "-m", "{config.name.replace("-", "_")}"]
'''


def package_run_artifacts(
    run_dir: Path,
    output_dir: Optional[Path] = None,
    package_type: PackageType = "zip",
    config: Optional[PackageConfig] = None,
) -> PackageResult:
    """Package artifacts from a completed run.

    Args:
        run_dir: Directory containing run outputs.
        output_dir: Where to write packages (defaults to run_dir/packages).
        package_type: Type of package to create.
        config: Package configuration (auto-generated if not provided).

    Returns:
        PackageResult with status and artifacts.
    """
    run_dir = Path(run_dir).resolve()
    output_dir = output_dir or run_dir / "packages"

    # Read manifest for metadata
    manifest_path = run_dir / "manifest.json"
    manifest = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    # Auto-generate config if not provided
    if config is None:
        workflow = manifest.get("workflow", {})
        config = PackageConfig(
            name=workflow.get("workflow", "unnamed-package"),
            version="0.1.0",
            description=f"Generated from {workflow.get('module', 'unknown')}/{workflow.get('workflow', 'unknown')}",
        )

    # Locate outputs directory
    outputs_dir = run_dir / "outputs"
    if not outputs_dir.exists():
        outputs_dir = run_dir

    builder = PackageBuilder(outputs_dir, output_dir)
    return builder.build(config, package_type)
