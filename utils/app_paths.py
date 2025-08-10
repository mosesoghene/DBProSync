#!/usr/bin/env python3
"""
Path management utilities for Database Sync Tool
This module ensures all file operations use appropriate user-writable directories
"""

import os
import sys
import tempfile
from pathlib import Path
import logging


class AppPaths:
    """Centralized path management for the application."""

    def __init__(self):
        self._app_data_dir = None
        self._config_dir = None
        self._logs_dir = None
        self._backups_dir = None
        self._temp_dir = None

    @property
    def app_data_dir(self):
        """Get the application data directory (for logs, temp files, etc.)"""
        if self._app_data_dir is None:
            if os.name == 'nt':  # Windows
                base_dir = os.environ.get('LOCALAPPDATA', os.path.expanduser('~\\AppData\\Local'))
                self._app_data_dir = Path(base_dir) / "Database Sync Tool"
            else:  # Linux/Mac
                self._app_data_dir = Path.home() / ".database-sync-tool" / "data"

            # Create directory if it doesn't exist
            try:
                self._app_data_dir.mkdir(parents=True, exist_ok=True)
            except PermissionError:
                # Fallback to temp directory
                self._app_data_dir = Path(tempfile.gettempdir()) / "database_sync_tool"
                self._app_data_dir.mkdir(parents=True, exist_ok=True)

        return self._app_data_dir

    @property
    def config_dir(self):
        """Get the configuration directory"""
        if self._config_dir is None:
            if os.name == 'nt':  # Windows
                base_dir = os.environ.get('APPDATA', os.path.expanduser('~\\AppData\\Roaming'))
                self._config_dir = Path(base_dir) / "Database Sync Tool"
            else:  # Linux/Mac
                self._config_dir = Path.home() / ".database-sync-tool"

            try:
                self._config_dir.mkdir(parents=True, exist_ok=True)
            except PermissionError:
                # Fallback to temp directory
                self._config_dir = Path(tempfile.gettempdir()) / "database_sync_tool_config"
                self._config_dir.mkdir(parents=True, exist_ok=True)

        return self._config_dir

    @property
    def logs_dir(self):
        """Get the logs directory"""
        if self._logs_dir is None:
            self._logs_dir = self.app_data_dir / "logs"
            try:
                self._logs_dir.mkdir(parents=True, exist_ok=True)
            except PermissionError:
                self._logs_dir = Path(tempfile.gettempdir()) / "database_sync_tool_logs"
                self._logs_dir.mkdir(parents=True, exist_ok=True)

        return self._logs_dir

    @property
    def backups_dir(self):
        """Get the backups directory"""
        if self._backups_dir is None:
            self._backups_dir = self.app_data_dir / "backups"
            try:
                self._backups_dir.mkdir(parents=True, exist_ok=True)
            except PermissionError:
                self._backups_dir = Path(tempfile.gettempdir()) / "database_sync_tool_backups"
                self._backups_dir.mkdir(parents=True, exist_ok=True)

        return self._backups_dir

    @property
    def temp_dir(self):
        """Get a temporary directory for the app"""
        if self._temp_dir is None:
            self._temp_dir = self.app_data_dir / "temp"
            try:
                self._temp_dir.mkdir(parents=True, exist_ok=True)
            except PermissionError:
                self._temp_dir = Path(tempfile.gettempdir()) / "database_sync_tool_temp"
                self._temp_dir.mkdir(parents=True, exist_ok=True)

        return self._temp_dir

    @property
    def config_file(self):
        """Get the main config file path"""
        return self.config_dir / "config.json"

    def get_log_file(self, name="app"):
        """Get a log file path"""
        return self.logs_dir / f"{name}.log"

    def migrate_from_install_dir(self):
        """Migrate config and data from installation directory to user directory"""
        migrated = False

        # Try to find installation directory
        install_paths = [
            Path(sys.executable).parent,  # Next to executable
            Path(sys.executable).parent / "_internal",  # PyInstaller internal
            Path.cwd(),  # Current working directory
        ]

        for install_path in install_paths:
            old_config = install_path / "config.json"
            if old_config.exists() and not self.config_file.exists():
                try:
                    import shutil
                    shutil.copy2(old_config, self.config_file)
                    print(f"Migrated config from {old_config} to {self.config_file}")
                    migrated = True
                    break
                except Exception as e:
                    print(f"Could not migrate config from {old_config}: {e}")

        return migrated


# Global instance
app_paths = AppPaths()


def setup_logging():
    """Set up logging configuration with proper user-writable paths."""
    # Ensure we're using user-writable paths
    log_file = app_paths.get_log_file("app")

    # Clear any existing handlers
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    try:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ],
            force=True  # Force reconfiguration
        )
        logging.info(f"Logging initialized. Log file: {log_file}")
        logging.info(f"App data directory: {app_paths.app_data_dir}")
        logging.info(f"Config directory: {app_paths.config_dir}")

    except Exception as e:
        # Ultimate fallback - just use console logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler(sys.stdout)],
            force=True
        )
        logging.error(f"Could not set up file logging: {e}")
        logging.info("Using console logging only")


def get_safe_file_path(filename, subdirectory=None):
    """Get a safe file path in the user data directory"""
    if subdirectory:
        base_dir = app_paths.app_data_dir / subdirectory
        base_dir.mkdir(parents=True, exist_ok=True)
    else:
        base_dir = app_paths.app_data_dir

    return base_dir / filename


# Backwards compatibility functions
def get_app_data_dir():
    return app_paths.app_data_dir


def get_config_dir():
    return app_paths.config_dir


def get_user_config_path():
    return app_paths.config_file


def migrate_config_from_install_dir():
    return app_paths.migrate_from_install_dir()