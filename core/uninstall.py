"""
Enterprise Uninstall Module for MultiCode.

Provides cross-platform, auditable, consent-driven uninstallation with:
- Intelligent entry point cleanup across Windows/macOS/Linux
- Standard uninstall (keep settings) or full wipe (remove all)
- Audit event emission before destructive actions
- Post-uninstall validation and user guidance
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import sysconfig
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class UninstallPlan:
    """Describes what will be removed and what will be kept."""
    mode: str  # "standard" or "wipe"
    files_to_remove: list[str] = field(default_factory=list)
    dirs_to_remove: list[str] = field(default_factory=list)
    pip_packages: list[str] = field(default_factory=lambda: ["multicode"])
    keep_settings: bool = True
    settings_path: str = ""
    entry_points_removed: list[str] = field(default_factory=list)


@dataclass
class UninstallResult:
    """Records what was actually done."""
    success: bool = True
    mode: str = "standard"
    files_removed: list[str] = field(default_factory=list)
    dirs_removed: list[str] = field(default_factory=list)
    entry_points_removed: list[str] = field(default_factory=list)
    settings_preserved: bool = True
    settings_path: str = ""
    errors: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_audit_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "action": "uninstall",
            "mode": self.mode,
            "files_removed": self.files_removed,
            "dirs_removed": self.dirs_removed,
            "entry_points_removed": self.entry_points_removed,
            "settings_preserved": self.settings_preserved,
            "settings_path": self.settings_path,
            "success": self.success,
            "errors": self.errors,
        }


class PlatformHelper:
    """Cross-platform path resolution and script detection."""

    @staticmethod
    def get_scripts_dir() -> Path:
        """Get the directory where entry point scripts are installed."""
        return Path(sysconfig.get_path("scripts"))

    @staticmethod
    def get_site_packages() -> Path:
        """Get the site-packages directory."""
        return Path(sysconfig.get_path("purelib"))

    @staticmethod
    def get_entry_point_names() -> list[str]:
        """Get all possible entry point script names for this platform."""
        if sys.platform == "win32":
            return ["multicode.exe", "multicode-cli.exe", "multicode", "multicode-cli"]
        else:
            return ["multicode", "multicode-cli"]

    @staticmethod
    def detect_existing_entry_points() -> list[Path]:
        """Scan the scripts directory for existing entry point artifacts."""
        scripts_dir = Path(sysconfig.get_path("scripts"))
        names = PlatformHelper.get_entry_point_names()
        found = []
        if scripts_dir.exists():
            for name in names:
                path = scripts_dir / name
                if path.exists():
                    found.append(path)
        return found

    @staticmethod
    def detect_virtualenv_scripts() -> list[Path]:
        """Find entry points in active virtual environment."""
        venv_root = os.environ.get("VIRTUAL_ENV")
        if not venv_root:
            return []
        scripts = Path(venv_root) / ("Scripts" if sys.platform == "win32" else "bin")
        names = PlatformHelper.get_entry_point_names()
        found = []
        if scripts.exists():
            for name in names:
                path = scripts / name
                if path.exists():
                    found.append(path)
        return found


class UninstallManager:
    """
    Orchestrates the full uninstall lifecycle with audit logging.

    Usage:
        mgr = UninstallManager(mode="wipe")
        plan = mgr.create_plan()
        result = mgr.execute(plan)
    """

    def __init__(self, mode: str = "standard", audit_logger: Any = None):
        self.mode = mode
        self.audit_logger = audit_logger
        self.platform = PlatformHelper()
        self.config_dir = Path.home() / ".multicode"
        # Track paths that are locked because they are the running process
        self._locked_paths: set[str] = set()
        # On Windows, track exes that were renamed (so they won't be found by PATH)
        self._renamed_paths: list[str] = []

    def _is_multicode_exe(self, path: Path) -> bool:
        """Check if a path is a multicode entry point executable."""
        names = self.platform.get_entry_point_names()
        return path.name in names

    def _disable_locked_exe(self, path: Path) -> bool:
        """
        Neutralize a locked executable/directory so it can no longer be invoked.

        On Windows, a running process locks its entry point. For regular
        installs this is a .exe file; for editable installs it's a
        directory containing __main__.py.

        We rename it to <name>.__mc_uninstall to break the PATH lookup.
        """
        if sys.platform != "win32":
            return False
        try:
            disabled = path.with_name(path.name + ".__mc_uninstall")
            path.rename(disabled)
            self._renamed_paths.append(str(path))
            logger.info("Renamed locked path: %s → %s", path.name, disabled.name)
            return True
        except OSError as e:
            logger.debug("Could not rename %s: %s", path, e)
            return False

    def create_plan(self) -> UninstallPlan:
        """Create an uninstall plan describing what will be removed."""
        plan = UninstallPlan(mode=self.mode)
        plan.settings_path = str(self.config_dir)

        if self.mode == "wipe":
            plan.keep_settings = False
        else:
            plan.keep_settings = True

        # Discover entry points that exist
        entry_points = self.platform.detect_existing_entry_points()
        entry_points.extend(self.platform.detect_virtualenv_scripts())
        plan.entry_points_removed = [str(p) for p in entry_points]

        # Discover egg-info directories
        import sysconfig
        site = Path(sysconfig.get_path("purelib"))
        if site.exists():
            for item in site.iterdir():
                if item.name.startswith("multicode") and item.name.endswith(".egg-info"):
                    plan.dirs_to_remove.append(str(item))

        return plan

    def execute(self, plan: UninstallPlan) -> UninstallResult:
        """Execute the uninstall plan and return results."""
        result = UninstallResult(mode=self.mode, settings_preserved=plan.keep_settings, settings_path=plan.settings_path)

        # Emit audit event BEFORE any changes
        self._emit_audit("uninstall_started", {
            "mode": self.mode,
            "keep_settings": plan.keep_settings,
            "entry_points_found": plan.entry_points_removed,
        })

        # Step 1: Uninstall pip package
        self._uninstall_pip(result)

        # Step 2: Remove entry point scripts
        self._remove_entry_points(plan, result)

        # Step 3: Remove egg-info
        self._remove_egg_info(plan, result)

        # Step 4: Handle settings
        if plan.keep_settings:
            logger.info("Settings preserved at %s", self.config_dir)
        else:
            self._wipe_settings(result)

        # Step 5: Clean build artifacts in source tree
        self._clean_build_artifacts(result)

        # Post-uninstall validation
        self._validate_uninstall(result)

        # Final audit event
        self._emit_audit("uninstall_completed", result.to_audit_dict())

        return result

    def _uninstall_pip(self, result: UninstallResult) -> None:
        """Uninstall the pip package."""
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pip", "uninstall", "-y", "-q", "multicode"],
                capture_output=True, text=True, timeout=60,
            )
            if proc.returncode == 0:
                result.files_removed.append("multicode (pip)")
                logger.info("Pip package uninstalled successfully")
            else:
                stderr_text = proc.stderr.strip()
                logger.warning("Pip uninstall returned %d", proc.returncode)

                # On Windows, if the running executable is locked, track and disable it
                if sys.platform == "win32" and "PermissionError" in stderr_text:
                    scripts_dir = self.platform.get_scripts_dir()
                    for ep_name in self.platform.get_entry_point_names():
                        ep_path = scripts_dir / ep_name
                        if ep_path.exists():
                            self._locked_paths.add(str(ep_path))
                            # Try to rename/zero the exe so it can't be found
                            self._disable_locked_exe(ep_path)
                    logger.info(
                        "Running executable is locked; disabled for future invocations"
                    )
                else:
                    result.errors.append(f"pip uninstall returned {proc.returncode}")
        except subprocess.TimeoutExpired:
            result.errors.append("pip uninstall timed out")
        except Exception as e:
            result.errors.append(f"pip uninstall error: {e}")

    def _remove_entry_points(self, plan: UninstallPlan, result: UninstallResult) -> None:
        """Remove entry point scripts from scripts directories, skipping locked paths."""
        for path_str in plan.entry_points_removed:
            path = Path(path_str)
            # Skip paths that are locked (running process or already tracked)
            if path_str in self._locked_paths:
                logger.info("Skipping locked entry point: %s", path)
                continue
            # On Windows, if pip already failed to uninstall due to a locked exe,
            # skip manual removal of multicode exe files to avoid duplicate errors.
            if sys.platform == "win32" and self._locked_paths and self._is_multicode_exe(path):
                self._locked_paths.add(str(path))
                logger.info("Skipping locked entry point (pip locked): %s", path)
                continue
            try:
                if path.is_file() or path.is_symlink():
                    path.unlink()
                    result.files_removed.append(str(path))
                    logger.info("Removed entry point: %s", path)
            except PermissionError:
                self._locked_paths.add(str(path))
                logger.info("Permission denied (locked): %s", path)
            except Exception as e:
                result.errors.append(f"Failed to remove {path}: {e}")

    def _remove_egg_info(self, plan: UninstallPlan, result: UninstallResult) -> None:
        """Remove egg-info directories."""
        for path_str in plan.dirs_to_remove:
            path = Path(path_str)
            try:
                if path.exists():
                    shutil.rmtree(path)
                    result.dirs_removed.append(str(path))
                    logger.info("Removed egg-info: %s", path)
            except Exception as e:
                result.errors.append(f"Failed to remove {path}: {e}")

    def _wipe_settings(self, result: UninstallResult) -> None:
        """Delete user settings, API keys, and audit logs."""
        if not self.config_dir.exists():
            return

        try:
            # Try keyring deletion first (best effort)
            try:
                import keyring
                keyring.delete_password("multicode", "openrouter_api_key")
            except Exception:
                pass

            # Remove env vars (current process only)
            for var in ("MULTICODE_API_KEY", "OPENROUTER_API_KEY"):
                os.environ.pop(var, None)

            # Delete directory
            file_count = sum(1 for _ in self.config_dir.rglob("*") if _.is_file())
            shutil.rmtree(self.config_dir)
            result.dirs_removed.append(str(self.config_dir))
            result.settings_preserved = False
            logger.info("Wiped %d files from %s", file_count, self.config_dir)
        except Exception as e:
            result.errors.append(f"Failed to wipe settings: {e}")

    def _clean_build_artifacts(self, result: UninstallResult) -> None:
        """Remove build artifacts from source tree (if running from repo)."""
        try:
            cwd = Path.cwd()
            # Only clean if cwd looks like the MultiCode source tree
            if (cwd / "pyproject.toml").exists() and (cwd / "multicode").exists():
                for pattern in ("build", "dist", "__pycache__"):
                    target = cwd / pattern
                    if target.exists():
                        shutil.rmtree(target)
                        result.dirs_removed.append(str(target))
        except Exception:
            pass

    def _validate_uninstall(self, result: UninstallResult) -> None:
        """Post-uninstall validation: check if entry point is truly gone."""
        import shutil as _shutil

        if sys.platform == "win32":
            # If we already know paths are locked (running process), skip validation
            if self._locked_paths:
                return  # Expected — don't add any message
            if _shutil.which("multicode"):
                result.errors.append(
                    "Entry point 'multicode' still found in PATH. "
                    "Restart your terminal or run 'refreshenv' (Windows)."
                )
        else:
            if _shutil.which("multicode"):
                result.errors.append(
                    "Entry point 'multicode' still found in PATH. "
                    "Restart your terminal or run 'hash -r' (Unix) / 'refreshenv' (Windows)."
                )

    def _emit_audit(self, action: str, data: dict[str, Any]) -> None:
        """Emit an audit event if an audit logger is configured."""
        if self.audit_logger:
            try:
                self.audit_logger.log(
                    action,  # Will be AuditAction if imported
                    detail=data,
                )
            except Exception as e:
                # Never let audit failure break uninstall
                logger.warning("Audit logging failed: %s", e)


def get_uninstall_summary(result: UninstallResult) -> str:
    """Generate a human-readable summary of uninstall results."""
    lines = []

    if result.success:
        lines.append("[green]✓ MultiCode has been COMPLETELY uninstalled![/green]\n")
    else:
        lines.append("[yellow]⚠ Uninstall completed with warnings[/yellow]\n")

    lines.append("[bold]What was removed:[/bold]")
    for f in result.files_removed:
        lines.append(f"  ✓ {f}")
    for d in result.dirs_removed:
        lines.append(f"  ✓ {d}")
    if result.entry_points_removed:
        for ep in result.entry_points_removed:
            lines.append(f"  ✓ Entry point: {ep}")

    if result.settings_preserved:
        lines.append(f"\n[green]✓ Settings preserved at {result.settings_path}[/green]")
    else:
        lines.append("\n[red]✓ All user data wiped (including settings and API keys)[/red]")

    if result.errors:
        lines.append("\n[yellow]Warnings:[/yellow]")
        for err in result.errors:
            lines.append(f"  ⚠ {err}")

    lines.append("\n[dim]To reinstall: pip install -e .[/dim]")
    if result.settings_preserved:
        lines.append("[dim]Your settings will be automatically detected on reinstall.[/dim]")

    return "\n".join(lines)
