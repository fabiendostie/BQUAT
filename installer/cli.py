"""CLI entry point for BAQT installer."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import BaqtInstaller, InstallConfig
from .verify import verify_installation


def main(argv: list[str] | None = None) -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="baqt",
        description="BAQT unified installer - BMAD + TELIS + QUINT",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Install command
    install_parser = subparsers.add_parser("install", help="Install BAQT to a directory")
    install_parser.add_argument(
        "target",
        nargs="?",
        default=".",
        help="Target directory (default: current directory)",
    )
    install_parser.add_argument(
        "--force", "-f", action="store_true", help="Overwrite existing installation"
    )
    install_parser.add_argument("--no-bmad", action="store_true", help="Skip BMAD installation")
    install_parser.add_argument("--no-quint", action="store_true", help="Skip QUINT installation")
    install_parser.add_argument(
        "--no-runtime", action="store_true", help="Skip runtime installation"
    )
    install_parser.add_argument("--no-docs", action="store_true", help="Skip documentation")
    install_parser.add_argument("--build-quint", action="store_true", help="Build QUINT Go binary")
    install_parser.add_argument("--json", action="store_true", help="Output result as JSON")

    # Update command
    update_parser = subparsers.add_parser("update", help="Update existing installation")
    update_parser.add_argument(
        "target",
        nargs="?",
        default=".",
        help="Target directory (default: current directory)",
    )
    update_parser.add_argument("--json", action="store_true", help="Output result as JSON")

    # Verify command
    verify_parser = subparsers.add_parser("verify", help="Verify installation integrity")
    verify_parser.add_argument(
        "target",
        nargs="?",
        default=".",
        help="Target directory (default: current directory)",
    )
    verify_parser.add_argument("--json", action="store_true", help="Output result as JSON")

    # Status command
    status_parser = subparsers.add_parser("status", help="Show installation status")
    status_parser.add_argument(
        "target",
        nargs="?",
        default=".",
        help="Target directory (default: current directory)",
    )
    status_parser.add_argument("--json", action="store_true", help="Output result as JSON")

    # Version command
    subparsers.add_parser("version", help="Show version information")

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "version":
        return cmd_version()

    if args.command == "install":
        return cmd_install(args)

    if args.command == "update":
        return cmd_update(args)

    if args.command == "verify":
        return cmd_verify(args)

    if args.command == "status":
        return cmd_status(args)

    return 1


def cmd_version() -> int:
    """Show version information."""
    from .manifest import get_baqt_version

    print(f"BAQT version {get_baqt_version()}")
    return 0


def _print_quickstart(target: Path) -> None:
    """Print post-install quickstart guide."""
    print()
    print("=" * 60)
    print("  BAQT Quick Start")
    print("=" * 60)
    print()
    print("  1. VERIFY INSTALLATION")
    print(f"     baqt verify {target}")
    print()
    print("  2. CONFIGURE PROVIDER (choose one)")
    print("     export OLLAMA_HOST=http://localhost:11434  # Local")
    print("     export OPENAI_API_KEY=sk-...              # OpenAI")
    print("     export ANTHROPIC_API_KEY=sk-ant-...       # Claude")
    print()
    print("  3. RUN A WORKFLOW")
    print(f"     cd {target}")
    print("     baqt run brainstorming    # Start ideation")
    print("     baqt run prd              # Create product spec")
    print("     baqt run architecture     # Design system")
    print()
    print("  4. USE WITH CLAUDE CODE / CURSOR")
    print(f"     Open {target} in your IDE")
    print("     BAQT commands available via /_baqt/commands/")
    print()
    print("  DOCS: https://github.com/fabiendostie/BQUAT#readme")
    print("=" * 60)


def cmd_install(args: argparse.Namespace) -> int:
    """Execute install command."""
    target = Path(args.target).resolve()

    config = InstallConfig(
        target_dir=target,
        include_bmad=not args.no_bmad,
        include_quint=not args.no_quint,
        include_runtime=not args.no_runtime,
        include_docs=not args.no_docs,
        build_quint=args.build_quint,
        force=args.force,
    )

    installer = BaqtInstaller()
    result = installer.install(config)

    if args.json:
        output = {
            "success": result.success,
            "message": result.message,
            "errors": result.errors,
            "warnings": result.warnings,
        }
        if result.manifest:
            output["manifest"] = {
                "install_id": result.manifest.install_id,
                "baqt_version": result.manifest.baqt_version,
                "component_count": len(result.manifest.components),
                "file_count": len(result.manifest.files),
            }
        print(json.dumps(output, indent=2))
    else:
        if result.success:
            print(f"[OK] {result.message}")
            if result.manifest:
                print(f"     Install ID: {result.manifest.install_id}")
                print(f"     Components: {len(result.manifest.components)}")
                print(f"     Files: {len(result.manifest.files)}")
            _print_quickstart(target)
        else:
            print(f"[FAIL] {result.message}")
            for error in result.errors:
                print(f"       - {error}")

        if result.warnings:
            print("\nWarnings:")
            for warning in result.warnings:
                print(f"  - {warning}")

    return 0 if result.success else 1


def cmd_update(args: argparse.Namespace) -> int:
    """Execute update command."""
    target = Path(args.target).resolve()

    installer = BaqtInstaller()
    result = installer.update(target)

    if args.json:
        output = {
            "success": result.success,
            "message": result.message,
            "errors": result.errors,
            "warnings": result.warnings,
        }
        print(json.dumps(output, indent=2))
    else:
        if result.success:
            print(f"[OK] {result.message}")
        else:
            print(f"[FAIL] {result.message}")
            for error in result.errors:
                print(f"       - {error}")

        if result.warnings:
            print("\nWarnings:")
            for warning in result.warnings:
                print(f"  - {warning}")

    return 0 if result.success else 1


def cmd_verify(args: argparse.Namespace) -> int:
    """Execute verify command."""
    target = Path(args.target).resolve()

    report = verify_installation(target)

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print("BAQT Installation Verification")
        print("================================")
        print(f"Target: {target}")
        print()

        for check in report.checks:
            status = "[OK]" if check.passed else "[FAIL]"
            print(f"{status} {check.name}: {check.message}")

        print()
        print(f"Summary: {report.summary}")

    return 0 if report.passed else 1


def cmd_status(args: argparse.Namespace) -> int:
    """Execute status command."""
    target = Path(args.target).resolve()

    installer = BaqtInstaller()
    status = installer.status(target)

    if args.json:
        print(json.dumps(status, indent=2))
    else:
        if not status["installed"]:
            print(f"No BAQT installation found at {target}")
            return 1

        print("BAQT Installation Status")
        print("=========================")
        print(f"Install ID: {status['install_id']}")
        print(f"Version: {status['baqt_version']}")
        print(f"Installed: {status['installed_at']}")
        print(f"Updated: {status['updated_at']}")
        print()
        print("Components:")
        for comp in status["components"]:
            print(f"  - {comp['name']}: v{comp['version']} ({comp['commit']})")
        print()
        print(f"Total files: {status['file_count']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
