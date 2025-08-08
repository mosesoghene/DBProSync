"""
Windows startup manager for the Database Synchronization Application.

This module handles Windows startup registry operations and auto-start functionality.
"""

import sys
import logging
from typing import Optional
from pathlib import Path

# Only import winreg on Windows
if sys.platform.startswith('win'):
    import winreg
else:
    winreg = None


class WindowsStartupManager:
    """Manages Windows startup functionality."""

    def __init__(self):
        """Initialize the startup manager."""
        self.logger = logging.getLogger(self.__class__.__name__)
        self.app_name = "DatabaseSyncTool"
        self.registry_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"

        # Check if we're on Windows
        if not sys.platform.startswith('win'):
            self.logger.warning("Windows startup manager only works on Windows")

    def is_startup_enabled(self) -> bool:
        """
        Check if application is configured to start with Windows.

        Returns:
            True if startup is enabled, False otherwise
        """
        if not winreg:
            return False

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.registry_path) as key:
                try:
                    winreg.QueryValueEx(key, self.app_name)
                    return True
                except FileNotFoundError:
                    return False
        except Exception as e:
            self.logger.error(f"Error checking startup status: {e}")
            return False

    def enable_startup(self, executable_path: Optional[str] = None) -> bool:
        """
        Enable application to start with Windows.

        Args:
            executable_path: Path to the executable (uses sys.executable if None)

        Returns:
            True if successful, False otherwise
        """
        if not winreg:
            self.logger.error("Windows registry not available")
            return False

        try:
            if executable_path is None:
                if getattr(sys, 'frozen', False):
                    # Running as compiled executable
                    executable_path = sys.executable
                else:
                    # Running as script - create a batch file or use python
                    executable_path = f'"{sys.executable}" "{Path(__file__).parent.parent / "main.py"}"'

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.registry_path, 0, winreg.KEY_SET_VALUE) as key:
                # Add --minimized flag for startup
                startup_command = f'"{executable_path}" --minimized --auto-sync'
                winreg.SetValueEx(key, self.app_name, 0, winreg.REG_SZ, startup_command)

            self.logger.info(f"Startup enabled: {startup_command}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to enable startup: {e}")
            return False

    def disable_startup(self) -> bool:
        """
        Disable application from starting with Windows.

        Returns:
            True if successful, False otherwise
        """
        if not winreg:
            self.logger.error("Windows registry not available")
            return False

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.registry_path, 0, winreg.KEY_SET_VALUE) as key:
                try:
                    winreg.DeleteValue(key, self.app_name)
                    self.logger.info("Startup disabled")
                    return True
                except FileNotFoundError:
                    # Value doesn't exist, consider it success
                    return True

        except Exception as e:
            self.logger.error(f"Failed to disable startup: {e}")
            return False

    def get_startup_command(self) -> Optional[str]:
        """
        Get the current startup command.

        Returns:
            Startup command string, or None if not set
        """
        if not winreg:
            return None

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.registry_path) as key:
                try:
                    value, _ = winreg.QueryValueEx(key, self.app_name)
                    return value
                except FileNotFoundError:
                    return None
        except Exception as e:
            self.logger.error(f"Error getting startup command: {e}")
            return None


def parse_command_line_args():
    """Parse command line arguments for startup options."""
    import argparse

    parser = argparse.ArgumentParser(description="Database Sync Tool")
    parser.add_argument("--minimized", action="store_true",
                       help="Start minimized to system tray")
    parser.add_argument("--auto-sync", action="store_true",
                       help="Start sync automatically (requires valid config)")

    return parser.parse_args()


def is_started_minimized() -> bool:
    """Check if application was started with --minimized flag."""
    return "--minimized" in sys.argv


def is_auto_sync_enabled() -> bool:
    """Check if application should auto-start sync."""
    return "--auto-sync" in sys.argv or is_started_minimized()