"""
Configuration management for the Database Synchronization Application.

This module handles all configuration persistence, including database pairs,
application settings, and password management.
"""

import json
import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from .models import DatabasePair, AppConfig
from ..utils.constants import (
    CONFIG_FILE, DEFAULT_PASSWORD, DEFAULT_LOG_LEVEL,
    DEFAULT_SYNC_INTERVAL, ERROR_MESSAGES
)


class ConfigManager:
    """Manages application configuration and persistence."""

    def __init__(self, config_file: str = CONFIG_FILE):
        """
        Initialize the configuration manager.

        Args:
            config_file: Path to the configuration file
        """
        self.config_file = Path(config_file)
        self.logger = logging.getLogger(self.__class__.__name__)

        # Default configuration
        self._config = AppConfig(
            app_password_hash=self._hash_password(DEFAULT_PASSWORD),
            database_pairs=[],
            log_level=DEFAULT_LOG_LEVEL,
            auto_start=False,
            default_sync_interval=DEFAULT_SYNC_INTERVAL
        )

        self.load_config()

    @property
    def config(self) -> AppConfig:
        """Get the current configuration."""
        return self._config

    def _hash_password(self, password: str) -> str:
        """
        Hash a password using SHA-256.

        Args:
            password: Plain text password

        Returns:
            Hashed password as hex string
        """
        return hashlib.sha256(password.encode('utf-8')).hexdigest()

    def verify_password(self, password: str) -> bool:
        """
        Verify a password against the stored hash.

        Args:
            password: Plain text password to verify

        Returns:
            True if password is correct, False otherwise
        """
        return self._hash_password(password) == self._config.app_password_hash

    def set_password(self, password: str) -> bool:
        """
        Set a new password for the application.

        Args:
            password: New plain text password

        Returns:
            True if password was set successfully, False otherwise
        """
        try:
            self._config.app_password_hash = self._hash_password(password)
            self.save_config()
            self.logger.info("Password updated successfully")
            return True
        except Exception as e:
            self.logger.error(f"Failed to set password: {e}")
            return False

    def is_first_run(self) -> bool:
        """
        Check if this is the first run (default password still in use).

        Returns:
            True if default password is still active
        """
        return self.verify_password(DEFAULT_PASSWORD)

    def load_config(self) -> bool:
        """
        Load configuration from file.

        Returns:
            True if loaded successfully, False otherwise
        """
        if not self.config_file.exists():
            self.logger.info("Configuration file doesn't exist, using defaults")
            return True

        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Validate and merge with defaults
            self._config.app_password_hash = data.get(
                'app_password_hash',
                self._config.app_password_hash
            )
            self._config.database_pairs = data.get('database_pairs', [])
            self._config.log_level = data.get('log_level', self._config.log_level)
            self._config.auto_start = data.get('auto_start', self._config.auto_start)
            self._config.default_sync_interval = data.get(
                'default_sync_interval',
                self._config.default_sync_interval
            )
            self._config.max_log_size = data.get(
                'max_log_size',
                self._config.max_log_size
            )
            self._config.backup_enabled = data.get(
                'backup_enabled',
                self._config.backup_enabled
            )

            self.logger.info(f"Configuration loaded from {self.config_file}")
            return True

        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in config file: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Failed to load config: {e}")
            return False

    def save_config(self) -> bool:
        """
        Save current configuration to file.

        Returns:
            True if saved successfully, False otherwise
        """
        try:
            # Create backup of existing config
            if self.config_file.exists() and self._config.backup_enabled:
                backup_file = self.config_file.with_suffix('.json.bak')
                self.config_file.replace(backup_file)
                self.logger.debug(f"Created config backup: {backup_file}")

            # Save current config
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self._config.to_dict(), f, indent=4, ensure_ascii=False)

            self.logger.info(f"Configuration saved to {self.config_file}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to save config: {e}")
            return False

    def add_database_pair(self, db_pair: DatabasePair) -> bool:
        """
        Add a new database pair configuration.

        Args:
            db_pair: Database pair to add

        Returns:
            True if added successfully, False otherwise
        """
        try:
            # Check for duplicate names
            if self.get_database_pair_by_name(db_pair.name):
                self.logger.warning(f"Database pair with name '{db_pair.name}' already exists")
                return False

            self._config.database_pairs.append(db_pair.to_dict())
            self.save_config()
            self.logger.info(f"Added database pair: {db_pair.name}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to add database pair: {e}")
            return False

    def update_database_pair(self, pair_id: str, db_pair: DatabasePair) -> bool:
        """
        Update an existing database pair configuration.

        Args:
            pair_id: ID of the pair to update
            db_pair: Updated database pair configuration

        Returns:
            True if updated successfully, False otherwise
        """
        try:
            for i, pair_data in enumerate(self._config.database_pairs):
                if pair_data.get('id') == pair_id:
                    self._config.database_pairs[i] = db_pair.to_dict()
                    self.save_config()
                    self.logger.info(f"Updated database pair: {db_pair.name}")
                    return True

            self.logger.warning(f"Database pair with ID '{pair_id}' not found")
            return False

        except Exception as e:
            self.logger.error(f"Failed to update database pair: {e}")
            return False

    def remove_database_pair(self, pair_id: str) -> bool:
        """
        Remove a database pair configuration.

        Args:
            pair_id: ID of the pair to remove

        Returns:
            True if removed successfully, False otherwise
        """
        try:
            original_count = len(self._config.database_pairs)
            self._config.database_pairs = [
                pair for pair in self._config.database_pairs
                if pair.get('id') != pair_id
            ]

            if len(self._config.database_pairs) < original_count:
                self.save_config()
                self.logger.info(f"Removed database pair with ID: {pair_id}")
                return True
            else:
                self.logger.warning(f"Database pair with ID '{pair_id}' not found")
                return False

        except Exception as e:
            self.logger.error(f"Failed to remove database pair: {e}")
            return False

    def get_database_pairs(self) -> List[DatabasePair]:
        """
        Get all configured database pairs.

        Returns:
            List of database pair configurations
        """
        pairs = []
        for pair_data in self._config.database_pairs:
            try:
                pair = DatabasePair.from_dict(pair_data)
                pairs.append(pair)
            except Exception as e:
                self.logger.error(f"Failed to load database pair: {e}")
                continue

        return pairs

    def get_database_pair_by_id(self, pair_id: str) -> Optional[DatabasePair]:
        """
        Get a database pair by its ID.

        Args:
            pair_id: ID of the database pair

        Returns:
            Database pair if found, None otherwise
        """
        for pair_data in self._config.database_pairs:
            if pair_data.get('id') == pair_id:
                try:
                    return DatabasePair.from_dict(pair_data)
                except Exception as e:
                    self.logger.error(f"Failed to load database pair: {e}")
                    return None
        return None

    def get_database_pair_by_name(self, name: str) -> Optional[DatabasePair]:
        """
        Get a database pair by its name.

        Args:
            name: Name of the database pair

        Returns:
            Database pair if found, None otherwise
        """
        for pair_data in self._config.database_pairs:
            if pair_data.get('name') == name:
                try:
                    return DatabasePair.from_dict(pair_data)
                except Exception as e:
                    self.logger.error(f"Failed to load database pair: {e}")
                    return None
        return None

    def get_enabled_database_pairs(self) -> List[DatabasePair]:
        """
        Get all enabled database pairs.

        Returns:
            List of enabled database pair configurations
        """
        return [pair for pair in self.get_database_pairs() if pair.is_enabled]

    def update_sync_timestamp(self, pair_id: str, timestamp: str) -> bool:
        """
        Update the last sync timestamp for a database pair.

        Args:
            pair_id: ID of the database pair
            timestamp: ISO format timestamp string

        Returns:
            True if updated successfully, False otherwise
        """
        try:
            for pair_data in self._config.database_pairs:
                if pair_data.get('id') == pair_id:
                    pair_data['last_sync'] = timestamp
                    self.save_config()
                    return True
            return False

        except Exception as e:
            self.logger.error(f"Failed to update sync timestamp: {e}")
            return False

    def export_config(self, export_path: str, include_passwords: bool = False) -> bool:
        """
        Export configuration to a file.

        Args:
            export_path: Path for the export file
            include_passwords: Whether to include passwords in export

        Returns:
            True if exported successfully, False otherwise
        """
        try:
            export_data = self._config.to_dict()

            if not include_passwords:
                # Remove sensitive data
                export_data['app_password_hash'] = ""
                for pair_data in export_data['database_pairs']:
                    if 'local_db' in pair_data:
                        pair_data['local_db']['password'] = ""
                    if 'cloud_db' in pair_data:
                        pair_data['cloud_db']['password'] = ""

            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=4, ensure_ascii=False)

            self.logger.info(f"Configuration exported to {export_path}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to export configuration: {e}")
            return False

    def import_config(self, import_path: str, merge: bool = False) -> bool:
        """
        Import configuration from a file.

        Args:
            import_path: Path to the import file
            merge: If True, merge with existing config; if False, replace

        Returns:
            True if imported successfully, False otherwise
        """
        try:
            with open(import_path, 'r', encoding='utf-8') as f:
                import_data = json.load(f)

            if not merge:
                # Replace existing configuration
                self._config = AppConfig.from_dict(import_data)
            else:
                # Merge with existing configuration
                if 'database_pairs' in import_data:
                    existing_names = {pair.get('name') for pair in self._config.database_pairs}
                    for pair_data in import_data['database_pairs']:
                        if pair_data.get('name') not in existing_names:
                            self._config.database_pairs.append(pair_data)

            self.save_config()
            self.logger.info(f"Configuration imported from {import_path}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to import configuration: {e}")
            return False
        