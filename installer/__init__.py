"""BQUAT unified installer - BMAD + TELIS + QUINT framework installer."""

from .cli import main
from .core import BquatInstaller, InstallConfig, InstallResult
from .manifest import (
    ComponentVersion,
    FileRecord,
    InstallManifest,
    compute_checksum,
    get_bquat_version,
    read_manifest,
    write_manifest,
)
from .verify import InstallationVerifier, VerificationCheck, VerificationReport, verify_installation

__all__ = [
    "BquatInstaller",
    "ComponentVersion",
    "FileRecord",
    "InstallConfig",
    "InstallManifest",
    "InstallResult",
    "InstallationVerifier",
    "VerificationCheck",
    "VerificationReport",
    "compute_checksum",
    "get_bquat_version",
    "main",
    "read_manifest",
    "verify_installation",
    "write_manifest",
]

__version__ = "1.0.0"
