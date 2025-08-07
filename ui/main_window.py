"""
Main application window for the Database Synchronization Application.

This module contains the primary user interface with sync controls,
status display, and live logging.
"""

import logging
from datetime import datetime
from typing import List, Optional

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QLabel, QTableWidget,
    QTableWidgetItem, QGroupBox, QSplitter,
    QHeaderView, QProgressBar, QStatusBar, QMenuBar,
    QMenu, QMessageBox, QFileDialog
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtGui import QFont, QAction, QIcon, QColor

from core.config_manager import ConfigManager
from core.sync_worker import SyncWorker
from core.models import JobStatus, DatabasePair
from .log_handler import LogManager
from .password_dialog import PasswordDialog
from .settings_dialog import SettingsDialog
from utils.constants import (
    WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT, LOG_VIEWER_MAX_HEIGHT,
    REFRESH_INTERVAL, STATUS_MESSAGES, ERROR_MESSAGES,
)


class MainWindow(QMainWindow):
    """Main application window with sync controls and monitoring."""

    def __init__(self):
        """Initialize the main window."""
        super().__init__()

        # Initialize core components
        self.config_manager = ConfigManager()
        self.log_manager = LogManager()
        self.sync_worker = SyncWorker()
        self.sync_thread = QThread()

        # UI state
        self.current_status = JobStatus.STOPPED
        self.is_scheduled_sync_active = False

        # Timers
        self.status_timer = QTimer()
        self.scheduled_sync_timer = QTimer()

        self.setup_ui()
        self.setup_worker()
        self.setup_timers()
        self.load_initial_data()

        # Check for first run
        if self.config_manager.is_first_run():
            self.show_first_run_setup()

    def setup_ui(self):
        """Set up the user interface."""
        self.setWindowTitle("Database Synchronization Tool")
        self.resize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Create menu bar
        self.create_menu_bar()

        # Control panel
        control_group = QGroupBox("Sync Controls")
        control_layout = QHBoxLayout(control_group)

        self.start_sync_btn = QPushButton("Start Sync Schedule")
        self.stop_sync_btn = QPushButton("Stop Sync Schedule")
        self.manual_sync_btn = QPushButton("Run Manual Sync")
        self.setup_infrastructure_btn = QPushButton("Setup Infrastructure")
        self.settings_btn = QPushButton("Settings")

        # Set button properties
        for btn in [self.start_sync_btn, self.stop_sync_btn, self.manual_sync_btn]:
            btn.setMinimumHeight(35)

        self.start_sync_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; }")
        self.stop_sync_btn.setStyleSheet("QPushButton { background-color: #f44336; color: white; font-weight: bold; }")
        self.manual_sync_btn.setStyleSheet(
            "QPushButton { background-color: #2196F3; color: white; font-weight: bold; }")

        # Initially disable stop button
        self.stop_sync_btn.setEnabled(False)

        control_layout.addWidget(self.start_sync_btn)
        control_layout.addWidget(self.stop_sync_btn)
        control_layout.addWidget(self.manual_sync_btn)
        control_layout.addWidget(self.setup_infrastructure_btn)
        control_layout.addStretch()
        control_layout.addWidget(self.settings_btn)

        main_layout.addWidget(control_group)

        # Status panel
        status_group = QGroupBox("Status")
        status_layout = QVBoxLayout(status_group)

        # Status row
        status_row = QHBoxLayout()

        self.status_label = QLabel("Status: Stopped")
        self.status_label.setStyleSheet("font-weight: bold; font-size: 14px;")

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumHeight(20)

        self.stats_label = QLabel("Ready")
        self.stats_label.setAlignment(Qt.AlignRight)

        status_row.addWidget(self.status_label)
        status_row.addStretch()
        status_row.addWidget(self.progress_bar)
        status_row.addWidget(self.stats_label)

        status_layout.addLayout(status_row)

        # Next sync info
        self.next_sync_label = QLabel("No scheduled sync")
        self.next_sync_label.setStyleSheet("color: gray; font-size: 11px;")
        status_layout.addWidget(self.next_sync_label)

        main_layout.addWidget(status_group)

        # Create splitter for main content
        splitter = QSplitter(Qt.Vertical)

        # Database pairs overview
        pairs_group = QGroupBox("Configured Database Pairs")
        pairs_layout = QVBoxLayout(pairs_group)

        # Pairs table
        self.pairs_table = QTableWidget()
        self.pairs_table.setColumnCount(6)
        self.pairs_table.setHorizontalHeaderLabels([
            "Name", "Status", "Last Sync", "Tables", "Interval (sec)", "Actions"
        ])

        # Configure table
        header = self.pairs_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)

        self.pairs_table.setAlternatingRowColors(True)
        self.pairs_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.pairs_table.setMaximumHeight(200)

        pairs_layout.addWidget(self.pairs_table)
        splitter.addWidget(pairs_group)

        # Log viewer
        log_group = QGroupBox("Live Logs")
        log_layout = QVBoxLayout(log_group)

        # Log controls
        log_controls = QHBoxLayout()

        self.clear_logs_btn = QPushButton("Clear Logs")
        self.save_logs_btn = QPushButton("Save Logs")
        log_level_label = QLabel("Show:")

        log_controls.addWidget(self.clear_logs_btn)
        log_controls.addWidget(self.save_logs_btn)
        log_controls.addStretch()
        log_controls.addWidget(log_level_label)

        log_layout.addLayout(log_controls)

        # Log text area
        self.log_viewer = QTextEdit()
        self.log_viewer.setReadOnly(True)
        self.log_viewer.setMaximumHeight(LOG_VIEWER_MAX_HEIGHT)
        self.log_viewer.setFont(QFont("Consolas", 9))
        self.log_viewer.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #444;
            }
        """)

        log_layout.addWidget(self.log_viewer)
        splitter.addWidget(log_group)

        # Set splitter proportions
        splitter.setSizes([300, 200])  # Give more space to pairs table
        main_layout.addWidget(splitter)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Add UI log handler
        self.log_manager.add_ui_handler(self.log_viewer)

        # Connect signals
        self.connect_signals()

    def create_menu_bar(self):
        """Create the application menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        export_config_action = QAction("&Export Configuration...", self)
        export_config_action.triggered.connect(self.export_configuration)
        file_menu.addAction(export_config_action)

        import_config_action = QAction("&Import Configuration...", self)
        import_config_action.triggered.connect(self.import_configuration)
        file_menu.addAction(import_config_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Tools menu
        tools_menu = menubar.addMenu("&Tools")

        validate_config_action = QAction("&Validate Configurations", self)
        validate_config_action.triggered.connect(self.validate_configurations)
        tools_menu.addAction(validate_config_action)

        reset_stats_action = QAction("&Reset Statistics", self)
        reset_stats_action.triggered.connect(self.reset_statistics)
        tools_menu.addAction(reset_stats_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def connect_signals(self):
        """Connect UI signals to handlers."""
        # Button connections
        self.start_sync_btn.clicked.connect(self.start_sync_schedule)
        self.stop_sync_btn.clicked.connect(self.stop_sync_schedule)
        self.manual_sync_btn.clicked.connect(self.run_manual_sync)
        self.setup_infrastructure_btn.clicked.connect(self.setup_infrastructure)
        self.settings_btn.clicked.connect(self.open_settings)

        # Log controls
        self.clear_logs_btn.clicked.connect(self.log_manager.clear_ui_logs)
        self.save_logs_btn.clicked.connect(self.save_logs)

        # Sync worker signals
        self.sync_worker.status_changed.connect(self.update_status)
        self.sync_worker.log_message.connect(self.handle_worker_log)
        self.sync_worker.progress_updated.connect(self.update_progress)
        self.sync_worker.sync_completed.connect(self.handle_sync_completed)
        self.sync_worker.error_occurred.connect(self.handle_worker_error)

    def setup_worker(self):
        """Set up the sync worker thread."""
        # Move worker to separate thread
        self.sync_worker.moveToThread(self.sync_thread)
        self.sync_thread.start()

        # Load database pairs into worker
        self.refresh_sync_worker()

    def setup_timers(self):
        """Set up application timers."""
        # Status update timer
        self.status_timer.timeout.connect(self.update_ui_status)
        self.status_timer.start(REFRESH_INTERVAL)

        # Scheduled sync timer
        self.scheduled_sync_timer.timeout.connect(self.trigger_scheduled_sync)

    def load_initial_data(self):
        """Load initial data and update UI."""
        self.update_pairs_table()
        self.update_statistics()

        # Log startup
        logger = logging.getLogger(__name__)
        logger.info("Database Synchronization Tool started")
        logger.info(f"Loaded {len(self.config_manager.get_database_pairs())} database pairs")

    def show_first_run_setup(self):
        """Show first run password setup dialog."""
        dialog = PasswordDialog(self, is_first_run=True)
        if dialog.exec():
            password = dialog.get_password()
            if password and len(password) >= 4:  # Basic validation
                if self.config_manager.set_password(password):
                    QMessageBox.information(
                        self,
                        "Setup Complete",
                        "Password has been set successfully. You can now access settings."
                    )
                else:
                    QMessageBox.warning(
                        self,
                        "Setup Error",
                        "Failed to set password. Please try again."
                    )
            else:
                QMessageBox.warning(
                    self,
                    "Invalid Password",
                    "Password must be at least 4 characters long."
                )
        else:
            QMessageBox.information(
                self,
                "First Run",
                "Default password 'admin' will be used. You can change it in Settings."
            )

    def start_sync_schedule(self):
        """Start scheduled synchronization."""
        db_pairs = self.config_manager.get_enabled_database_pairs()
        if not db_pairs:
            QMessageBox.warning(
                self,
                "No Configuration",
                ERROR_MESSAGES['no_db_pairs']
            )
            return

        # Start the worker
        self.sync_worker.start_scheduled_sync()

        # Start timer for scheduled syncs
        interval = min(pair.sync_interval for pair in db_pairs) * 1000  # Convert to ms
        self.scheduled_sync_timer.start(interval)

        # Update UI
        self.is_scheduled_sync_active = True
        self.start_sync_btn.setEnabled(False)
        self.stop_sync_btn.setEnabled(True)

        logging.info(f"Scheduled sync started with {interval / 1000}s interval")

    def stop_sync_schedule(self):
        """Stop scheduled synchronization."""
        self.sync_worker.stop_scheduled_sync()
        self.scheduled_sync_timer.stop()

        # Update UI
        self.is_scheduled_sync_active = False
        self.start_sync_btn.setEnabled(True)
        self.stop_sync_btn.setEnabled(False)

        logging.info("Scheduled sync stopped")

    def run_manual_sync(self):
        """Run a one-time manual synchronization."""
        db_pairs = self.config_manager.get_enabled_database_pairs()
        if not db_pairs:
            QMessageBox.warning(
                self,
                "No Configuration",
                ERROR_MESSAGES['no_db_pairs']
            )
            return

        self.sync_worker.run_manual_sync()

    def setup_infrastructure(self):
        """Set up synchronization infrastructure."""
        db_pairs = self.config_manager.get_enabled_database_pairs()
        if not db_pairs:
            QMessageBox.warning(
                self,
                "No Configuration",
                ERROR_MESSAGES['no_db_pairs']
            )
            return

        reply = QMessageBox.question(
            self,
            "Setup Infrastructure",
            "This will create changelog tables and triggers in your databases. Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.sync_worker.setup_sync_infrastructure()

    def trigger_scheduled_sync(self):
        """Trigger a scheduled sync cycle."""
        if self.is_scheduled_sync_active:
            self.sync_worker.run_scheduled_sync_cycle()

    def open_settings(self):
        """Open the settings dialog with password authentication."""
        dialog = PasswordDialog(self)
        if dialog.exec():
            password = dialog.get_password()
            if self.config_manager.verify_password(password):
                settings_dialog = SettingsDialog(self.config_manager, self)
                if settings_dialog.exec():
                    # Reload configuration and update UI
                    self.update_pairs_table()
                    self.refresh_sync_worker()
                    logging.info("Settings updated")
            else:
                QMessageBox.warning(
                    self,
                    "Access Denied",
                    ERROR_MESSAGES['invalid_password']
                )

    def refresh_sync_worker(self):
        """Refresh the sync worker with current configuration."""
        db_pairs = self.config_manager.get_enabled_database_pairs()
        self.sync_worker.set_database_pairs(db_pairs)

    def update_status(self, status: str):
        """
        Update the status display.

        Args:
            status: Status string from JobStatus enum
        """
        self.current_status = JobStatus(status)
        self.status_label.setText(f"Status: {status}")

        # Update status styling
        if status == JobStatus.RUNNING.value:
            self.status_label.setStyleSheet("color: green; font-weight: bold; font-size: 14px;")
            self.progress_bar.setVisible(True)
        elif status == JobStatus.ERROR.value:
            self.status_label.setStyleSheet("color: red; font-weight: bold; font-size: 14px;")
            self.progress_bar.setVisible(False)
        elif status == JobStatus.COMPLETED.value:
            self.status_label.setStyleSheet("color: blue; font-weight: bold; font-size: 14px;")
            self.progress_bar.setVisible(False)
        else:
            self.status_label.setStyleSheet("font-weight: bold; font-size: 14px;")
            self.progress_bar.setVisible(False)

    def update_progress(self, percentage: int):
        """
        Update the progress bar.

        Args:
            percentage: Progress percentage (0-100)
        """
        self.progress_bar.setValue(percentage)
        if percentage >= 100:
            # Hide progress bar after a short delay
            QTimer.singleShot(2000, lambda: self.progress_bar.setVisible(False))

    def handle_worker_log(self, level: str, message: str):
        """
        Handle log messages from the sync worker.

        Args:
            level: Log level
            message: Log message
        """
        logger = logging.getLogger("SyncWorker")
        getattr(logger, level.lower())(message)

    def handle_sync_completed(self, results: List[dict]):
        """
        Handle sync completion.

        Args:
            results: List of sync result dictionaries
        """
        successful = sum(1 for result in results if result.get('success', False))
        total = len(results)
        records = sum(result.get('records_synced', 0) for result in results)

        # Update status bar
        self.status_bar.showMessage(
            f"Last sync: {successful}/{total} tables successful, {records} records synced",
            10000  # Show for 10 seconds
        )

        # Update statistics
        self.update_statistics()

        # Update pairs table with last sync times
        self.update_pairs_table()

    def handle_worker_error(self, error: str):
        """
        Handle worker errors.

        Args:
            error: Error message
        """
        QMessageBox.critical(self, "Sync Error", f"Synchronization error:\n\n{error}")
        logging.error(f"Sync worker error: {error}")

    def update_ui_status(self):
        """Update UI status information periodically."""
        # Update next sync time if scheduled sync is active
        if self.is_scheduled_sync_active:
            remaining = self.scheduled_sync_timer.remainingTime()
            if remaining > 0:
                minutes, seconds = divmod(remaining // 1000, 60)
                self.next_sync_label.setText(f"Next sync in: {minutes:02d}:{seconds:02d}")
            else:
                self.next_sync_label.setText("Sync starting...")
        else:
            self.next_sync_label.setText("No scheduled sync")

        # Update statistics
        self.update_statistics()

    def update_statistics(self):
        """Update statistics display."""
        stats = self.sync_worker.get_sync_statistics()

        stats_text = (
            f"Total: {stats.get('total_syncs', 0)} | "
            f"Success: {stats.get('successful_syncs', 0)} | "
            f"Failed: {stats.get('failed_syncs', 0)} | "
            f"Records: {stats.get('total_records_synced', 0)}"
        )

        self.stats_label.setText(stats_text)

    def update_pairs_table(self):
        """Update the database pairs table."""
        db_pairs = self.config_manager.get_database_pairs()
        self.pairs_table.setRowCount(len(db_pairs))

        for i, pair in enumerate(db_pairs):
            # Name
            name_item = QTableWidgetItem(pair.name)
            if not pair.is_enabled:
                name_item.setForeground(QColor("gray"))
            self.pairs_table.setItem(i, 0, name_item)

            # Status
            status_item = QTableWidgetItem("Enabled" if pair.is_enabled else "Disabled")
            status_item.setForeground(QColor("green") if pair.is_enabled else QColor("gray"))
            self.pairs_table.setItem(i, 1, status_item)

            # Last sync
            last_sync = pair.last_sync if pair.last_sync else "Never"
            if pair.last_sync:
                try:
                    sync_time = datetime.fromisoformat(pair.last_sync)
                    last_sync = sync_time.strftime("%Y-%m-%d %H:%M:%S")
                except:
                    last_sync = "Invalid date"

            self.pairs_table.setItem(i, 2, QTableWidgetItem(last_sync))

            # Tables count
            sync_enabled = sum(1 for table in pair.tables if table.sync_direction.value != "no_sync")
            tables_text = f"{sync_enabled}/{len(pair.tables)}"
            self.pairs_table.setItem(i, 3, QTableWidgetItem(tables_text))

            # Interval
            self.pairs_table.setItem(i, 4, QTableWidgetItem(str(pair.sync_interval)))

            # Actions (placeholder)
            actions_item = QTableWidgetItem("Sync Now")
            self.pairs_table.setItem(i, 5, actions_item)

    def validate_configurations(self):
        """Validate all database configurations."""
        validation_results = self.sync_worker.validate_all_configurations()

        if 'error' in validation_results:
            QMessageBox.warning(self, "Validation Error", validation_results['error'][0])
            return

        total_errors = sum(len(errors) for errors in validation_results.values())

        if total_errors == 0:
            QMessageBox.information(
                self,
                "Validation Complete",
                "All database configurations are valid!"
            )
        else:
            error_details = []
            for pair_id, errors in validation_results.items():
                if errors:
                    # Find pair name
                    pair_name = pair_id
                    for pair in self.config_manager.get_database_pairs():
                        if pair.id == pair_id:
                            pair_name = pair.name
                            break

                    error_details.append(f"{pair_name}:")
                    for error in errors:
                        error_details.append(f"  • {error}")
                    error_details.append("")

            QMessageBox.warning(
                self,
                f"Validation Issues ({total_errors} errors)",
                "\n".join(error_details)
            )

    def reset_statistics(self):
        """Reset synchronization statistics."""
        reply = QMessageBox.question(
            self,
            "Reset Statistics",
            "Are you sure you want to reset all synchronization statistics?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.sync_worker.reset_statistics()
            self.update_statistics()

    def save_logs(self):
        """Save current logs to a file."""
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save Logs",
            f"sync_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "Text Files (*.txt);;All Files (*)"
        )

        if filename:
            if self.log_manager.save_ui_logs(filename):
                QMessageBox.information(self, "Logs Saved", f"Logs saved successfully to:\n{filename}")
            else:
                QMessageBox.warning(self, "Save Error", "Failed to save logs.")

    def export_configuration(self):
        """Export configuration to a file."""
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export Configuration",
            f"db_sync_config_{datetime.now().strftime('%Y%m%d')}.json",
            "JSON Files (*.json);;All Files (*)"
        )

        if filename:
            # Ask about including passwords
            reply = QMessageBox.question(
                self,
                "Include Passwords",
                "Include database passwords in the export?\n\n"
                "Note: Passwords will be stored in plain text.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            include_passwords = reply == QMessageBox.Yes

            if self.config_manager.export_config(filename, include_passwords):
                QMessageBox.information(
                    self,
                    "Export Complete",
                    f"Configuration exported successfully to:\n{filename}"
                )
            else:
                QMessageBox.warning(self, "Export Error", "Failed to export configuration.")

    def import_configuration(self):
        """Import configuration from a file."""
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Import Configuration",
            "",
            "JSON Files (*.json);;All Files (*)"
        )

        if filename:
            # Ask about merge vs replace
            reply = QMessageBox.question(
                self,
                "Import Mode",
                "How would you like to import the configuration?\n\n"
                "Yes: Merge with existing configuration\n"
                "No: Replace existing configuration",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.Yes
            )

            if reply == QMessageBox.Cancel:
                return

            merge = reply == QMessageBox.Yes

            if self.config_manager.import_config(filename, merge):
                QMessageBox.information(
                    self,
                    "Import Complete",
                    "Configuration imported successfully."
                )
                self.update_pairs_table()
                self.refresh_sync_worker()
            else:
                QMessageBox.warning(self, "Import Error", "Failed to import configuration.")

    def show_about(self):
        """Show about dialog."""
        from ..utils.constants import APP_NAME, APP_VERSION

        QMessageBox.about(
            self,
            f"About {APP_NAME}",
            f"""
            <h2>{APP_NAME}</h2>
            <p>Version {APP_VERSION}</p>
            <p>A powerful database synchronization tool for keeping your local and cloud databases in sync.</p>

            <p><b>Features:</b></p>
            <ul>
                <li>Bidirectional database synchronization</li>
                <li>Change tracking with triggers</li>
                <li>Scheduled and manual sync operations</li>
                <li>Support for MySQL, PostgreSQL, and SQLite</li>
                <li>Comprehensive logging and monitoring</li>
            </ul>

            <p><b>Support:</b></p>
            <p>For help and documentation, please refer to the user manual.</p>
            """
        )

    def closeEvent(self, event):
        """Handle application close event."""
        # Stop any running sync operations
        if self.is_scheduled_sync_active:
            self.stop_sync_schedule()

        # Clean up worker
        self.sync_worker.cleanup()

        # Wait for thread to finish
        self.sync_thread.quit()
        self.sync_thread.wait(3000)  # Wait up to 3 seconds

        # Clean up log manager
        self.log_manager.cleanup()

        logging.info("Application closed")
        super().closeEvent(event)