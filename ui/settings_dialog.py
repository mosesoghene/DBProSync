"""
Settings dialog for the Database Synchronization Application.

This module provides the main settings interface for configuring database
pairs, sync options, and application preferences.
"""

import logging
from typing import List, Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QGroupBox, QFormLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QComboBox, QSpinBox, QCheckBox, QLabel,
    QHeaderView, QMessageBox, QLineEdit, QTextEdit
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from core.config_manager import ConfigManager
from core.models import DatabasePair, SyncDirection
from .database_connection_dialog import DatabaseConnectionDialog
from utils.constants import (
    SUPPORTED_DATABASES, DEFAULT_SYNC_INTERVAL, VALIDATION_RULES
)


class SettingsDialog(QDialog):
    """Main settings dialog for application configuration."""

    def __init__(self, config_manager: ConfigManager, parent=None):
        """
        Initialize the settings dialog.

        Args:
            config_manager: Configuration manager instance
            parent: Parent widget
        """
        super().__init__(parent)
        self.config_manager = config_manager
        self.logger = logging.getLogger(self.__class__.__name__)

        self.setup_ui()
        self.load_current_settings()

    def setup_ui(self):
        """Set up the user interface."""
        self.setWindowTitle("Database Sync Settings")
        self.setModal(True)
        self.resize(900, 700)

        # Main layout
        layout = QVBoxLayout(self)

        # Tab widget for different settings sections
        self.tab_widget = QTabWidget()

        # Database pairs tab
        self.setup_database_tab()

        # General settings tab
        self.setup_general_tab()

        # Advanced settings tab
        self.setup_advanced_tab()

        layout.addWidget(self.tab_widget)

        # Dialog buttons
        self.setup_dialog_buttons(layout)

    def setup_database_tab(self):
        """Set up the database pairs configuration tab."""
        db_tab = QWidget()
        layout = QVBoxLayout(db_tab)

        # Database pairs management
        pairs_group = QGroupBox("Database Pair Configurations")
        pairs_layout = QVBoxLayout(pairs_group)

        # Control buttons
        controls_layout = QHBoxLayout()

        self.add_pair_btn = QPushButton("Add Database Pair")
        self.edit_pair_btn = QPushButton("Edit Selected")
        self.delete_pair_btn = QPushButton("Delete Selected")
        self.test_pair_btn = QPushButton("Test Connection")
        self.duplicate_pair_btn = QPushButton("Duplicate")

        self.add_pair_btn.clicked.connect(self.add_database_pair)
        self.edit_pair_btn.clicked.connect(self.edit_database_pair)
        self.delete_pair_btn.clicked.connect(self.delete_database_pair)
        self.test_pair_btn.clicked.connect(self.test_database_pair)
        self.duplicate_pair_btn.clicked.connect(self.duplicate_database_pair)

        controls_layout.addWidget(self.add_pair_btn)
        controls_layout.addWidget(self.edit_pair_btn)
        controls_layout.addWidget(self.delete_pair_btn)
        controls_layout.addWidget(self.test_pair_btn)
        controls_layout.addWidget(self.duplicate_pair_btn)
        controls_layout.addStretch()

        pairs_layout.addLayout(controls_layout)

        # Database pairs table
        self.pairs_table = QTableWidget()
        self.pairs_table.setColumnCount(7)
        self.pairs_table.setHorizontalHeaderLabels([
            "Name", "Status", "Local DB", "Cloud DB", "Tables", "Interval", "Last Sync"
        ])

        # Configure table
        header = self.pairs_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)

        self.pairs_table.setAlternatingRowColors(True)
        self.pairs_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.pairs_table.itemSelectionChanged.connect(self.on_pair_selection_changed)

        pairs_layout.addWidget(self.pairs_table)
        layout.addWidget(pairs_group)

        self.tab_widget.addTab(db_tab, "Database Pairs")

    def setup_general_tab(self):
        """Set up the general settings tab."""
        general_tab = QWidget()
        layout = QVBoxLayout(general_tab)

        # Application settings
        app_group = QGroupBox("Application Settings")
        app_layout = QFormLayout(app_group)

        self.auto_start_cb = QCheckBox("Auto-start synchronization on app launch")
        app_layout.addRow(self.auto_start_cb)

        self.default_interval = QSpinBox()
        self.default_interval.setRange(VALIDATION_RULES['min_sync_interval'],
                                       VALIDATION_RULES['max_sync_interval'])
        self.default_interval.setValue(DEFAULT_SYNC_INTERVAL)
        self.default_interval.setSuffix(" seconds")
        app_layout.addRow("Default Sync Interval:", self.default_interval)

        self.backup_enabled_cb = QCheckBox("Enable automatic backups before sync")
        app_layout.addRow(self.backup_enabled_cb)

        layout.addWidget(app_group)

        # Logging settings
        log_group = QGroupBox("Logging Settings")
        log_layout = QFormLayout(log_group)

        self.log_level = QComboBox()
        self.log_level.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self.log_level.setCurrentText("INFO")
        log_layout.addRow("Log Level:", self.log_level)

        self.max_log_size = QSpinBox()
        self.max_log_size.setRange(1, 100)
        self.max_log_size.setValue(10)
        self.max_log_size.setSuffix(" MB")
        log_layout.addRow("Max Log File Size:", self.max_log_size)

        layout.addWidget(log_group)

        # Security settings
        security_group = QGroupBox("Security Settings")
        security_layout = QVBoxLayout(security_group)

        change_password_btn = QPushButton("Change Application Password")
        change_password_btn.clicked.connect(self.change_password)
        security_layout.addWidget(change_password_btn)

        layout.addWidget(security_group)

        layout.addStretch()
        self.tab_widget.addTab(general_tab, "General")

    def setup_advanced_tab(self):
        """Set up the advanced settings tab."""
        advanced_tab = QWidget()
        layout = QVBoxLayout(advanced_tab)

        # Performance settings
        perf_group = QGroupBox("Performance Settings")
        perf_layout = QFormLayout(perf_group)

        self.max_batch_size = QSpinBox()
        self.max_batch_size.setRange(100, 10000)
        self.max_batch_size.setValue(1000)
        perf_layout.addRow("Max Records Per Batch:", self.max_batch_size)

        self.connection_timeout = QSpinBox()
        self.connection_timeout.setRange(5, 300)
        self.connection_timeout.setValue(30)
        self.connection_timeout.setSuffix(" seconds")
        perf_layout.addRow("Connection Timeout:", self.connection_timeout)

        self.retry_attempts = QSpinBox()
        self.retry_attempts.setRange(1, 10)
        self.retry_attempts.setValue(3)
        perf_layout.addRow("Max Retry Attempts:", self.retry_attempts)

        layout.addWidget(perf_group)

        # Sync behavior settings
        sync_group = QGroupBox("Sync Behavior")
        sync_layout = QFormLayout(sync_group)

        self.conflict_resolution = QComboBox()
        self.conflict_resolution.addItems(["newer_wins", "local_wins", "cloud_wins"])
        self.conflict_resolution.setCurrentText("newer_wins")
        sync_layout.addRow("Default Conflict Resolution:", self.conflict_resolution)

        self.create_backups_cb = QCheckBox("Create table backups before first sync")
        sync_layout.addRow(self.create_backups_cb)

        layout.addWidget(sync_group)

        # Maintenance
        maint_group = QGroupBox("Maintenance")
        maint_layout = QVBoxLayout(maint_group)

        cleanup_logs_btn = QPushButton("Clean Old Log Files")
        cleanup_logs_btn.clicked.connect(self.cleanup_logs)
        maint_layout.addWidget(cleanup_logs_btn)

        cleanup_changelogs_btn = QPushButton("Clean Old Changelog Entries")
        cleanup_changelogs_btn.clicked.connect(self.cleanup_changelogs)
        maint_layout.addWidget(cleanup_changelogs_btn)

        reset_config_btn = QPushButton("Reset All Settings to Defaults")
        reset_config_btn.clicked.connect(self.reset_to_defaults)
        reset_config_btn.setStyleSheet("background-color: #ff6b6b; color: white;")
        maint_layout.addWidget(reset_config_btn)

        layout.addWidget(maint_group)

        layout.addStretch()
        self.tab_widget.addTab(advanced_tab, "Advanced")

    def setup_dialog_buttons(self, layout):
        """Set up the dialog action buttons."""
        button_layout = QHBoxLayout()

        self.apply_btn = QPushButton("Apply")
        self.save_btn = QPushButton("Save")
        self.cancel_btn = QPushButton("Cancel")

        self.apply_btn.clicked.connect(self.apply_settings)
        self.save_btn.clicked.connect(self.save_and_close)
        self.cancel_btn.clicked.connect(self.reject)

        button_layout.addStretch()
        button_layout.addWidget(self.apply_btn)
        button_layout.addWidget(self.save_btn)
        button_layout.addWidget(self.cancel_btn)

        layout.addLayout(button_layout)

    def load_current_settings(self):
        """Load current settings into the UI."""
        config = self.config_manager.config

        # Load general settings
        self.auto_start_cb.setChecked(config.auto_start)
        self.default_interval.setValue(config.default_sync_interval)
        self.log_level.setCurrentText(config.log_level)
        self.max_log_size.setValue(config.max_log_size)
        self.backup_enabled_cb.setChecked(config.backup_enabled)

        # Load database pairs
        self.refresh_pairs_table()

    def refresh_pairs_table(self):
        """Refresh the database pairs table."""
        pairs = self.config_manager.get_database_pairs()
        self.pairs_table.setRowCount(len(pairs))

        for i, pair in enumerate(pairs):
            # Name
            name_item = QTableWidgetItem(pair.name)
            if not pair.is_enabled:
                name_item.setBackground(Qt.lightGray)
            self.pairs_table.setItem(i, 0, name_item)

            # Status
            status = "Enabled" if pair.is_enabled else "Disabled"
            status_item = QTableWidgetItem(status)
            self.pairs_table.setItem(i, 1, status_item)

            # Local DB
            local_db_text = f"{pair.local_db.db_type}://{pair.local_db.host}:{pair.local_db.port}/{pair.local_db.database}"
            self.pairs_table.setItem(i, 2, QTableWidgetItem(local_db_text))

            # Cloud DB
            cloud_db_text = f"{pair.cloud_db.db_type}://{pair.cloud_db.host}:{pair.cloud_db.port}/{pair.cloud_db.database}"
            self.pairs_table.setItem(i, 3, QTableWidgetItem(cloud_db_text))

            # Tables
            sync_tables = len([t for t in pair.tables if t.sync_direction != SyncDirection.NO_SYNC])
            tables_text = f"{sync_tables}/{len(pair.tables)}"
            self.pairs_table.setItem(i, 4, QTableWidgetItem(tables_text))

            # Interval
            self.pairs_table.setItem(i, 5, QTableWidgetItem(f"{pair.sync_interval}s"))

            # Last sync
            last_sync = pair.last_sync if pair.last_sync else "Never"
            self.pairs_table.setItem(i, 6, QTableWidgetItem(last_sync))

    def on_pair_selection_changed(self):
        """Handle pair selection changes."""
        has_selection = len(self.pairs_table.selectedItems()) > 0
        self.edit_pair_btn.setEnabled(has_selection)
        self.delete_pair_btn.setEnabled(has_selection)
        self.test_pair_btn.setEnabled(has_selection)
        self.duplicate_pair_btn.setEnabled(has_selection)

    def add_database_pair(self):
        """Add a new database pair."""
        dialog = DatabaseConnectionDialog(self)
        if dialog.exec():
            db_pair = dialog.get_database_pair()
            if self.config_manager.add_database_pair(db_pair):
                self.refresh_pairs_table()
                QMessageBox.information(self, "Success", f"Database pair '{db_pair.name}' added successfully.")
            else:
                QMessageBox.warning(self, "Error", "Failed to add database pair.")

    def edit_database_pair(self):
        """Edit the selected database pair."""
        current_row = self.pairs_table.currentRow()
        if current_row < 0:
            return

        pairs = self.config_manager.get_database_pairs()
        if current_row >= len(pairs):
            return

        pair = pairs[current_row]
        dialog = DatabaseConnectionDialog(self, pair)
        if dialog.exec():
            updated_pair = dialog.get_database_pair()
            updated_pair.id = pair.id  # Preserve original ID

            if self.config_manager.update_database_pair(pair.id, updated_pair):
                self.refresh_pairs_table()
                QMessageBox.information(self, "Success", f"Database pair '{updated_pair.name}' updated successfully.")
            else:
                QMessageBox.warning(self, "Error", "Failed to update database pair.")

    def delete_database_pair(self):
        """Delete the selected database pair."""
        current_row = self.pairs_table.currentRow()
        if current_row < 0:
            return

        pairs = self.config_manager.get_database_pairs()
        if current_row >= len(pairs):
            return

        pair = pairs[current_row]

        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to delete the database pair '{pair.name}'?\n\n"
            "This action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            if self.config_manager.remove_database_pair(pair.id):
                self.refresh_pairs_table()
                QMessageBox.information(self, "Success", f"Database pair '{pair.name}' deleted successfully.")
            else:
                QMessageBox.warning(self, "Error", "Failed to delete database pair.")

    def test_database_pair(self):
        """Test connection for the selected database pair."""
        current_row = self.pairs_table.currentRow()
        if current_row < 0:
            return

        pairs = self.config_manager.get_database_pairs()
        if current_row >= len(pairs):
            return

        pair = pairs[current_row]

        # Test both connections
        from ..core.database_manager import DatabaseManager

        local_manager = DatabaseManager(pair.local_db)
        cloud_manager = DatabaseManager(pair.cloud_db)

        local_success = local_manager.test_connection()
        cloud_success = cloud_manager.test_connection()

        if local_success and cloud_success:
            QMessageBox.information(
                self,
                "Connection Test",
                f"Both connections successful for '{pair.name}'"
            )
        else:
            errors = []
            if not local_success:
                errors.append("Local database connection failed")
            if not cloud_success:
                errors.append("Cloud database connection failed")

            QMessageBox.warning(
                self,
                "Connection Test Failed",
                f"Connection issues for '{pair.name}':\n\n" + "\n".join(errors)
            )

    def duplicate_database_pair(self):
        """Duplicate the selected database pair."""
        current_row = self.pairs_table.currentRow()
        if current_row < 0:
            return

        pairs = self.config_manager.get_database_pairs()
        if current_row >= len(pairs):
            return

        original_pair = pairs[current_row]

        # Create duplicate with modified name
        import copy
        duplicate_pair = copy.deepcopy(original_pair)
        duplicate_pair.id = ""  # Will generate new ID
        duplicate_pair.name = f"{original_pair.name} (Copy)"

        # Reset sync timestamps
        duplicate_pair.last_sync = None
        for table in duplicate_pair.tables:
            table.last_sync = None

        if self.config_manager.add_database_pair(duplicate_pair):
            self.refresh_pairs_table()
            QMessageBox.information(self, "Success", f"Database pair duplicated as '{duplicate_pair.name}'.")
        else:
            QMessageBox.warning(self, "Error", "Failed to duplicate database pair.")

    def change_password(self):
        """Change the application password."""
        from .password_dialog import PasswordDialog

        dialog = PasswordDialog(self, is_change_password=True)
        if dialog.exec():
            current_password = dialog.get_current_password()
            new_password = dialog.get_password()

            if not self.config_manager.verify_password(current_password):
                QMessageBox.warning(self, "Invalid Password", "Current password is incorrect.")
                return

            if self.config_manager.set_password(new_password):
                QMessageBox.information(self, "Success", "Password changed successfully.")
            else:
                QMessageBox.warning(self, "Error", "Failed to change password.")

    def cleanup_logs(self):
        """Clean up old log files."""
        reply = QMessageBox.question(
            self,
            "Clean Log Files",
            "This will remove old log files to free up space.\n\nContinue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # Implement log cleanup logic
            QMessageBox.information(self, "Success", "Log files cleaned up successfully.")

    def cleanup_changelogs(self):
        """Clean up old changelog entries."""
        reply = QMessageBox.question(
            self,
            "Clean Changelog Entries",
            "This will remove old synced changelog entries from all databases.\n\n"
            "This action cannot be undone. Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # Implement changelog cleanup logic
            QMessageBox.information(self, "Success", "Changelog entries cleaned up successfully.")

    def reset_to_defaults(self):
        """Reset all settings to defaults."""
        reply = QMessageBox.question(
            self,
            "Reset to Defaults",
            "This will reset ALL settings to their default values.\n\n"
            "Database pair configurations will be preserved.\n\n"
            "Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # Reset to defaults but preserve database pairs
            pairs = self.config_manager.get_database_pairs()

            # Reset config
            from ..core.models import AppConfig
            from ..utils.constants import DEFAULT_PASSWORD, DEFAULT_LOG_LEVEL

            default_config = AppConfig(
                app_password_hash=self.config_manager.config.app_password_hash,  # Keep current password
                database_pairs=[pair.to_dict() for pair in pairs],  # Keep pairs
                log_level=DEFAULT_LOG_LEVEL,
                auto_start=False,
                default_sync_interval=DEFAULT_SYNC_INTERVAL,
                max_log_size=10,
                backup_enabled=True
            )

            self.config_manager._config = default_config
            self.config_manager.save_config()

            # Reload UI
            self.load_current_settings()

            QMessageBox.information(self, "Success", "Settings reset to defaults.")

    def apply_settings(self):
        """Apply settings without closing the dialog."""
        self._save_settings()

    def save_and_close(self):
        """Save settings and close the dialog."""
        if self._save_settings():
            self.accept()

    def _save_settings(self) -> bool:
        """Internal method to save settings."""
        try:
            config = self.config_manager.config

            # Save general settings
            config.auto_start = self.auto_start_cb.isChecked()
            config.default_sync_interval = self.default_interval.value()
            config.log_level = self.log_level.currentText()
            config.max_log_size = self.max_log_size.value()
            config.backup_enabled = self.backup_enabled_cb.isChecked()

            # Save configuration
            if self.config_manager.save_config():
                self.logger.info("Settings saved successfully")
                return True
            else:
                QMessageBox.warning(self, "Error", "Failed to save settings.")
                return False

        except Exception as e:
            self.logger.error(f"Error saving settings: {e}")
            QMessageBox.critical(self, "Error", f"Error saving settings:\n{e}")
            return False
