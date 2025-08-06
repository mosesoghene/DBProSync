import sys
import json
import uuid
import hashlib
import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QLabel, QDialog, QFormLayout, QLineEdit,
    QComboBox, QTableWidget, QTableWidgetItem, QCheckBox, QGroupBox,
    QMessageBox, QPasswordEdit, QSpinBox, QHeaderView, QTabWidget,
    QSplitter, QFrame, QProgressBar
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal, QObject
from PySide6.QtGui import QFont, QIcon, QPalette, QColor


class SyncDirection(Enum):
    NO_SYNC = "no_sync"
    LOCAL_TO_CLOUD = "local_to_cloud"
    CLOUD_TO_LOCAL = "cloud_to_local"
    BIDIRECTIONAL = "bidirectional"


class JobStatus(Enum):
    STOPPED = "Stopped"
    RUNNING = "Running"
    ERROR = "Error"
    PAUSED = "Paused"


@dataclass
class DatabaseConfig:
    id: str
    name: str
    db_type: str  # mysql, postgresql, sqlite, etc.
    host: str
    port: int
    database: str
    username: str
    password: str
    is_local: bool = True


@dataclass
class TableSyncConfig:
    table_name: str
    sync_direction: SyncDirection
    last_sync: Optional[str] = None


@dataclass
class DatabasePair:
    id: str
    name: str
    local_db: DatabaseConfig
    cloud_db: DatabaseConfig
    tables: List[TableSyncConfig]
    sync_interval: int = 300  # 5 minutes default


class ConfigManager:
    def __init__(self, config_file: str = "config.json"):
        self.config_file = Path(config_file)
        self.config = {
            "app_password": self._hash_password("admin"),
            "database_pairs": [],
            "log_level": "INFO",
            "auto_start": False,
            "default_sync_interval": 300
        }
        self.load_config()

    def _hash_password(self, password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()

    def verify_password(self, password: str) -> bool:
        return self._hash_password(password) == self.config["app_password"]

    def set_password(self, password: str):
        self.config["app_password"] = self._hash_password(password)
        self.save_config()

    def load_config(self):
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    loaded_config = json.load(f)
                    self.config.update(loaded_config)
            except Exception as e:
                logging.error(f"Failed to load config: {e}")

    def save_config(self):
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            logging.error(f"Failed to save config: {e}")

    def add_database_pair(self, db_pair: DatabasePair):
        pair_dict = asdict(db_pair)
        # Convert enum to string
        for table in pair_dict['tables']:
            table['sync_direction'] = table['sync_direction'].value

        self.config["database_pairs"].append(pair_dict)
        self.save_config()

    def get_database_pairs(self) -> List[DatabasePair]:
        pairs = []
        for pair_data in self.config["database_pairs"]:
            # Convert string back to enum
            tables = []
            for table_data in pair_data['tables']:
                table_data['sync_direction'] = SyncDirection(table_data['sync_direction'])
                tables.append(TableSyncConfig(**table_data))

            pair_data['tables'] = tables
            local_db = DatabaseConfig(**pair_data['local_db'])
            cloud_db = DatabaseConfig(**pair_data['cloud_db'])
            pair_data['local_db'] = local_db
            pair_data['cloud_db'] = cloud_db

            pairs.append(DatabasePair(**pair_data))
        return pairs


class LogHandler(logging.Handler):
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget

    def emit(self, record):
        msg = self.format(record)
        self.text_widget.append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


class SyncWorker(QObject):
    status_changed = Signal(str)
    log_message = Signal(str, str)  # level, message
    progress_updated = Signal(int)

    def __init__(self):
        super().__init__()
        self.is_running = False
        self.db_pairs = []

    def start_sync(self, db_pairs: List[DatabasePair]):
        self.db_pairs = db_pairs
        self.is_running = True
        self.status_changed.emit(JobStatus.RUNNING.value)
        self.log_message.emit("INFO", "Sync job started")

    def stop_sync(self):
        self.is_running = False
        self.status_changed.emit(JobStatus.STOPPED.value)
        self.log_message.emit("INFO", "Sync job stopped")

    def run_manual_sync(self):
        self.log_message.emit("INFO", "Running manual sync...")
        # TODO: Implement actual sync logic
        time.sleep(2)  # Simulate work
        self.log_message.emit("INFO", "Manual sync completed")


class PasswordDialog(QDialog):
    def __init__(self, parent=None, is_first_run=False):
        super().__init__(parent)
        self.is_first_run = is_first_run
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Password Required")
        self.setModal(True)
        self.resize(300, 150)

        layout = QFormLayout()

        if self.is_first_run:
            layout.addRow(QLabel("Set new password for settings access:"))
            self.new_password = QLineEdit()
            self.new_password.setEchoMode(QLineEdit.Password)
            layout.addRow("New Password:", self.new_password)

            self.confirm_password = QLineEdit()
            self.confirm_password.setEchoMode(QLineEdit.Password)
            layout.addRow("Confirm Password:", self.confirm_password)
        else:
            layout.addRow(QLabel("Enter password to access settings:"))
            self.password = QLineEdit()
            self.password.setEchoMode(QLineEdit.Password)
            layout.addRow("Password:", self.password)

        button_layout = QHBoxLayout()
        self.ok_button = QPushButton("OK")
        self.cancel_button = QPushButton("Cancel")

        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)

        layout.addRow(button_layout)
        self.setLayout(layout)

    def get_password(self):
        if self.is_first_run:
            return self.new_password.text() if self.new_password.text() == self.confirm_password.text() else None
        else:
            return self.password.text()


class DatabaseConnectionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.tables = []

    def setup_ui(self):
        self.setWindowTitle("Database Connection Settings")
        self.setModal(True)
        self.resize(800, 600)

        main_layout = QVBoxLayout()

        # Database pair name
        pair_layout = QFormLayout()
        self.pair_name = QLineEdit()
        pair_layout.addRow("Configuration Name:", self.pair_name)
        main_layout.addLayout(pair_layout)

        # Database connections
        db_layout = QHBoxLayout()

        # Local DB
        local_group = QGroupBox("Local Database")
        local_layout = QFormLayout()

        self.local_type = QComboBox()
        self.local_type.addItems(["mysql", "postgresql", "sqlite"])
        local_layout.addRow("Type:", self.local_type)

        self.local_host = QLineEdit("localhost")
        local_layout.addRow("Host:", self.local_host)

        self.local_port = QSpinBox()
        self.local_port.setRange(1, 65535)
        self.local_port.setValue(3306)
        local_layout.addRow("Port:", self.local_port)

        self.local_database = QLineEdit()
        local_layout.addRow("Database:", self.local_database)

        self.local_username = QLineEdit()
        local_layout.addRow("Username:", self.local_username)

        self.local_password = QLineEdit()
        self.local_password.setEchoMode(QLineEdit.Password)
        local_layout.addRow("Password:", self.local_password)

        local_group.setLayout(local_layout)
        db_layout.addWidget(local_group)

        # Cloud DB
        cloud_group = QGroupBox("Cloud Database")
        cloud_layout = QFormLayout()

        self.cloud_type = QComboBox()
        self.cloud_type.addItems(["mysql", "postgresql", "sqlite"])
        cloud_layout.addRow("Type:", self.cloud_type)

        self.cloud_host = QLineEdit()
        cloud_layout.addRow("Host:", self.cloud_host)

        self.cloud_port = QSpinBox()
        self.cloud_port.setRange(1, 65535)
        self.cloud_port.setValue(3306)
        cloud_layout.addRow("Port:", self.cloud_port)

        self.cloud_database = QLineEdit()
        cloud_layout.addRow("Database:", self.cloud_database)

        self.cloud_username = QLineEdit()
        cloud_layout.addRow("Username:", self.cloud_username)

        self.cloud_password = QLineEdit()
        self.cloud_password.setEchoMode(QLineEdit.Password)
        cloud_layout.addRow("Password:", self.cloud_password)

        cloud_group.setLayout(cloud_layout)
        db_layout.addWidget(cloud_group)

        main_layout.addLayout(db_layout)

        # Connection buttons
        conn_layout = QHBoxLayout()
        self.test_connection_btn = QPushButton("Test Connections")
        self.load_tables_btn = QPushButton("Load Tables")
        self.load_tables_btn.setEnabled(False)

        self.test_connection_btn.clicked.connect(self.test_connections)
        self.load_tables_btn.clicked.connect(self.load_tables)

        conn_layout.addWidget(self.test_connection_btn)
        conn_layout.addWidget(self.load_tables_btn)
        conn_layout.addStretch()
        main_layout.addLayout(conn_layout)

        # Tables selection
        tables_group = QGroupBox("Table Synchronization Settings")
        tables_layout = QVBoxLayout()

        self.tables_widget = QTableWidget()
        self.tables_widget.setColumnCount(4)
        self.tables_widget.setHorizontalHeaderLabels([
            "Table Name", "Local to Cloud", "Cloud to Local", "Bidirectional"
        ])

        header = self.tables_widget.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)

        tables_layout.addWidget(self.tables_widget)
        tables_group.setLayout(tables_layout)
        main_layout.addWidget(tables_group)

        # Sync interval
        interval_layout = QFormLayout()
        self.sync_interval = QSpinBox()
        self.sync_interval.setRange(30, 86400)  # 30 seconds to 24 hours
        self.sync_interval.setValue(300)  # 5 minutes default
        self.sync_interval.setSuffix(" seconds")
        interval_layout.addRow("Sync Interval:", self.sync_interval)
        main_layout.addLayout(interval_layout)

        # Dialog buttons
        button_layout = QHBoxLayout()
        self.save_button = QPushButton("Save Configuration")
        self.cancel_button = QPushButton("Cancel")

        self.save_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.cancel_button)
        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)

    def test_connections(self):
        # TODO: Implement actual database connection testing
        QMessageBox.information(self, "Connection Test",
                                "Connection test successful!\n(Note: This is a mock implementation)")
        self.load_tables_btn.setEnabled(True)

    def load_tables(self):
        # TODO: Implement actual table loading from databases
        # For now, add some mock tables
        mock_tables = ["users", "orders", "products", "categories", "inventory"]

        self.tables_widget.setRowCount(len(mock_tables))

        for i, table_name in enumerate(mock_tables):
            self.tables_widget.setItem(i, 0, QTableWidgetItem(table_name))

            # Create radio button group for sync direction
            local_to_cloud = QCheckBox()
            cloud_to_local = QCheckBox()
            bidirectional = QCheckBox()

            # Make them mutually exclusive
            def make_exclusive(current_cb, others):
                def toggle():
                    if current_cb.isChecked():
                        for other in others:
                            other.setChecked(False)

                return toggle

            local_to_cloud.toggled.connect(make_exclusive(local_to_cloud, [cloud_to_local, bidirectional]))
            cloud_to_local.toggled.connect(make_exclusive(cloud_to_local, [local_to_cloud, bidirectional]))
            bidirectional.toggled.connect(make_exclusive(bidirectional, [local_to_cloud, cloud_to_local]))

            self.tables_widget.setCellWidget(i, 1, local_to_cloud)
            self.tables_widget.setCellWidget(i, 2, cloud_to_local)
            self.tables_widget.setCellWidget(i, 3, bidirectional)

    def get_database_pair(self) -> DatabasePair:
        # Create database configurations
        local_db = DatabaseConfig(
            id=str(uuid.uuid4()),
            name=f"{self.pair_name.text()}_local",
            db_type=self.local_type.currentText(),
            host=self.local_host.text(),
            port=self.local_port.value(),
            database=self.local_database.text(),
            username=self.local_username.text(),
            password=self.local_password.text(),
            is_local=True
        )

        cloud_db = DatabaseConfig(
            id=str(uuid.uuid4()),
            name=f"{self.pair_name.text()}_cloud",
            db_type=self.cloud_type.currentText(),
            host=self.cloud_host.text(),
            port=self.cloud_port.value(),
            database=self.cloud_database.text(),
            username=self.cloud_username.text(),
            password=self.cloud_password.text(),
            is_local=False
        )

        # Get table configurations
        tables = []
        for i in range(self.tables_widget.rowCount()):
            table_name = self.tables_widget.item(i, 0).text()

            local_to_cloud = self.tables_widget.cellWidget(i, 1).isChecked()
            cloud_to_local = self.tables_widget.cellWidget(i, 2).isChecked()
            bidirectional = self.tables_widget.cellWidget(i, 3).isChecked()

            sync_direction = SyncDirection.NO_SYNC
            if local_to_cloud:
                sync_direction = SyncDirection.LOCAL_TO_CLOUD
            elif cloud_to_local:
                sync_direction = SyncDirection.CLOUD_TO_LOCAL
            elif bidirectional:
                sync_direction = SyncDirection.BIDIRECTIONAL

            tables.append(TableSyncConfig(table_name, sync_direction))

        return DatabasePair(
            id=str(uuid.uuid4()),
            name=self.pair_name.text(),
            local_db=local_db,
            cloud_db=cloud_db,
            tables=tables,
            sync_interval=self.sync_interval.value()
        )


class SettingsDialog(QDialog):
    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.resize(900, 700)

        layout = QVBoxLayout()

        # Tab widget for different settings sections
        tab_widget = QTabWidget()

        # Database configurations tab
        db_tab = QWidget()
        db_layout = QVBoxLayout()

        # Add database pair button
        add_db_layout = QHBoxLayout()
        self.add_db_button = QPushButton("Add Database Pair")
        self.add_db_button.clicked.connect(self.add_database_pair)
        add_db_layout.addWidget(self.add_db_button)
        add_db_layout.addStretch()
        db_layout.addLayout(add_db_layout)

        # Database pairs list
        self.db_pairs_widget = QTableWidget()
        self.db_pairs_widget.setColumnCount(4)
        self.db_pairs_widget.setHorizontalHeaderLabels([
            "Name", "Local DB", "Cloud DB", "Tables Count"
        ])
        db_layout.addWidget(self.db_pairs_widget)

        db_tab.setLayout(db_layout)
        tab_widget.addTab(db_tab, "Database Pairs")

        # General settings tab
        general_tab = QWidget()
        general_layout = QFormLayout()

        self.auto_start_cb = QCheckBox("Auto-start synchronization on app launch")
        general_layout.addRow(self.auto_start_cb)

        self.default_interval = QSpinBox()
        self.default_interval.setRange(30, 86400)
        self.default_interval.setValue(300)
        self.default_interval.setSuffix(" seconds")
        general_layout.addRow("Default Sync Interval:", self.default_interval)

        self.log_level = QComboBox()
        self.log_level.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self.log_level.setCurrentText("INFO")
        general_layout.addRow("Log Level:", self.log_level)

        general_tab.setLayout(general_layout)
        tab_widget.addTab(general_tab, "General")

        layout.addWidget(tab_widget)

        # Dialog buttons
        button_layout = QHBoxLayout()
        self.save_button = QPushButton("Save")
        self.cancel_button = QPushButton("Cancel")

        self.save_button.clicked.connect(self.save_settings)
        self.cancel_button.clicked.connect(self.reject)

        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        self.setLayout(layout)

        self.load_current_settings()

    def load_current_settings(self):
        # Load database pairs
        db_pairs = self.config_manager.get_database_pairs()
        self.db_pairs_widget.setRowCount(len(db_pairs))

        for i, pair in enumerate(db_pairs):
            self.db_pairs_widget.setItem(i, 0, QTableWidgetItem(pair.name))
            self.db_pairs_widget.setItem(i, 1, QTableWidgetItem(f"{pair.local_db.host}:{pair.local_db.database}"))
            self.db_pairs_widget.setItem(i, 2, QTableWidgetItem(f"{pair.cloud_db.host}:{pair.cloud_db.database}"))
            self.db_pairs_widget.setItem(i, 3, QTableWidgetItem(str(len(pair.tables))))

        # Load general settings
        self.auto_start_cb.setChecked(self.config_manager.config.get("auto_start", False))
        self.default_interval.setValue(self.config_manager.config.get("default_sync_interval", 300))
        self.log_level.setCurrentText(self.config_manager.config.get("log_level", "INFO"))

    def add_database_pair(self):
        dialog = DatabaseConnectionDialog(self)
        if dialog.exec():
            db_pair = dialog.get_database_pair()
            self.config_manager.add_database_pair(db_pair)
            self.load_current_settings()

    def save_settings(self):
        self.config_manager.config["auto_start"] = self.auto_start_cb.isChecked()
        self.config_manager.config["default_sync_interval"] = self.default_interval.value()
        self.config_manager.config["log_level"] = self.log_level.currentText()
        self.config_manager.save_config()
        self.accept()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager()
        self.sync_worker = SyncWorker()
        self.sync_thread = QThread()
        self.sync_timer = QTimer()
        self.current_status = JobStatus.STOPPED

        self.setup_ui()
        self.setup_logging()
        self.setup_worker()

        # Check if this is first run (default password)
        if self.config_manager.verify_password("admin"):
            self.show_first_run_dialog()

    def setup_ui(self):
        self.setWindowTitle("Database Synchronization Tool")
        self.setGeometry(100, 100, 1000, 700)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)

        # Control buttons
        control_layout = QHBoxLayout()

        self.start_sync_btn = QPushButton("Start Sync Schedule")
        self.stop_sync_btn = QPushButton("Stop Sync Schedule")
        self.manual_sync_btn = QPushButton("Run Manual Sync")
        self.settings_btn = QPushButton("Settings")

        self.start_sync_btn.clicked.connect(self.start_sync_schedule)
        self.stop_sync_btn.clicked.connect(self.stop_sync_schedule)
        self.manual_sync_btn.clicked.connect(self.run_manual_sync)
        self.settings_btn.clicked.connect(self.open_settings)

        control_layout.addWidget(self.start_sync_btn)
        control_layout.addWidget(self.stop_sync_btn)
        control_layout.addWidget(self.manual_sync_btn)
        control_layout.addStretch()
        control_layout.addWidget(self.settings_btn)

        layout.addLayout(control_layout)

        # Status bar
        status_layout = QHBoxLayout()

        self.status_label = QLabel("Status: Stopped")
        self.status_label.setStyleSheet("QLabel { font-weight: bold; }")

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)

        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        status_layout.addWidget(self.progress_bar)

        layout.addLayout(status_layout)

        # Log viewer
        log_group = QGroupBox("Live Logs")
        log_layout = QVBoxLayout()

        self.log_viewer = QTextEdit()
        self.log_viewer.setReadOnly(True)
        self.log_viewer.setMaximumHeight(200)
        self.log_viewer.setFont(QFont("Consolas", 9))

        log_layout.addWidget(self.log_viewer)
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)

        # Database pairs overview
        overview_group = QGroupBox("Configured Database Pairs")
        overview_layout = QVBoxLayout()

        self.pairs_table = QTableWidget()
        self.pairs_table.setColumnCount(5)
        self.pairs_table.setHorizontalHeaderLabels([
            "Name", "Status", "Last Sync", "Tables", "Interval (sec)"
        ])

        header = self.pairs_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)

        overview_layout.addWidget(self.pairs_table)
        overview_group.setLayout(overview_layout)
        layout.addWidget(overview_group)

        self.update_pairs_table()

    def setup_logging(self):
        # Setup file logging
        log_file = "sync_app.log"
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                LogHandler(self.log_viewer)
            ]
        )

        self.logger = logging.getLogger(__name__)
        self.logger.info("Application started")

    def setup_worker(self):
        self.sync_worker.moveToThread(self.sync_thread)
        self.sync_worker.status_changed.connect(self.update_status)
        self.sync_worker.log_message.connect(self.handle_log_message)
        self.sync_worker.progress_updated.connect(self.progress_bar.setValue)

        self.sync_thread.start()

        # Setup timer for scheduled sync
        self.sync_timer.timeout.connect(self.run_scheduled_sync)

    def show_first_run_dialog(self):
        dialog = PasswordDialog(self, is_first_run=True)
        if dialog.exec():
            password = dialog.get_password()
            if password:
                self.config_manager.set_password(password)
                QMessageBox.information(self, "Password Set",
                                        "Password has been set successfully.")
            else:
                QMessageBox.warning(self, "Invalid Password",
                                    "Passwords do not match. Using default password 'admin'.")

    def start_sync_schedule(self):
        db_pairs = self.config_manager.get_database_pairs()
        if not db_pairs:
            QMessageBox.warning(self, "No Configuration",
                                "Please configure database pairs in Settings first.")
            return

        self.sync_worker.start_sync(db_pairs)

        # Start timer with the interval from first pair (or default)
        interval = db_pairs[0].sync_interval if db_pairs else 300
        self.sync_timer.start(interval * 1000)  # Convert to milliseconds

        self.start_sync_btn.setEnabled(False)
        self.stop_sync_btn.setEnabled(True)

    def stop_sync_schedule(self):
        self.sync_worker.stop_sync()
        self.sync_timer.stop()

        self.start_sync_btn.setEnabled(True)
        self.stop_sync_btn.setEnabled(False)

    def run_manual_sync(self):
        db_pairs = self.config_manager.get_database_pairs()
        if not db_pairs:
            QMessageBox.warning(self, "No Configuration",
                                "Please configure database pairs in Settings first.")
            return

        self.sync_worker.run_manual_sync()

    def run_scheduled_sync(self):
        self.logger.info("Running scheduled sync...")
        self.run_manual_sync()

    def open_settings(self):
        dialog = PasswordDialog(self)
        if dialog.exec():
            password = dialog.get_password()
            if self.config_manager.verify_password(password):
                settings_dialog = SettingsDialog(self.config_manager, self)
                if settings_dialog.exec():
                    self.update_pairs_table()
                    self.logger.info("Settings updated")
            else:
                QMessageBox.warning(self, "Access Denied", "Invalid password.")

    def update_status(self, status: str):
        self.status_label.setText(f"Status: {status}")

        if status == JobStatus.RUNNING.value:
            self.status_label.setStyleSheet("QLabel { color: green; font-weight: bold; }")
            self.progress_bar.setVisible(True)
        elif status == JobStatus.ERROR.value:
            self.status_label.setStyleSheet("QLabel { color: red; font-weight: bold; }")
            self.progress_bar.setVisible(False)
        else:
            self.status_label.setStyleSheet("QLabel { font-weight: bold; }")
            self.progress_bar.setVisible(False)

    def handle_log_message(self, level: str, message: str):
        if level == "INFO":
            self.logger.info(message)
        elif level == "WARNING":
            self.logger.warning(message)
        elif level == "ERROR":
            self.logger.error(message)
        else:
            self.logger.debug(message)

    def update_pairs_table(self):
        db_pairs = self.config_manager.get_database_pairs()
        self.pairs_table.setRowCount(len(db_pairs))

        for i, pair in enumerate(db_pairs):
            self.pairs_table.setItem(i, 0, QTableWidgetItem(pair.name))
            self.pairs_table.setItem(i, 1, QTableWidgetItem("Ready"))
            self.pairs_table.setItem(i, 2, QTableWidgetItem("Never"))

            # Count tables with sync enabled
            sync_enabled = sum(1 for table in pair.tables
                               if table.sync_direction != SyncDirection.NO_SYNC)
            self.pairs_table.setItem(i, 3, QTableWidgetItem(f"{sync_enabled}/{len(pair.tables)}"))
            self.pairs_table.setItem(i, 4, QTableWidgetItem(str(pair.sync_interval)))

    def closeEvent(self, event):
        if self.sync_timer.isActive():
            self.stop_sync_schedule()

        self.sync_thread.quit()
        self.sync_thread.wait()
        self.logger.info("Application closed")
        super().closeEvent(event)


class DatabaseManager:
    """Handles database connections and operations"""

    def __init__(self, db_config: DatabaseConfig):
        self.config = db_config
        self.connection = None

    def connect(self) -> bool:
        """Establish database connection"""
        try:
            # TODO: Implement actual database connections based on db_type
            # This would use libraries like pymysql, psycopg2, sqlite3, etc.
            self.logger.info(f"Connecting to {self.config.db_type} database at {self.config.host}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to connect to database: {e}")
            return False

    def disconnect(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            self.connection = None

    def test_connection(self) -> bool:
        """Test database connection"""
        if self.connect():
            self.disconnect()
            return True
        return False

    def get_tables(self) -> List[str]:
        """Get list of tables in database"""
        try:
            # TODO: Implement actual table listing based on database type
            # Mock implementation for now
            if self.config.db_type == "mysql":
                query = "SHOW TABLES"
            elif self.config.db_type == "postgresql":
                query = """
                        SELECT table_name \
                        FROM information_schema.tables
                        WHERE table_schema = 'public' \
                        """
            elif self.config.db_type == "sqlite":
                query = """
                        SELECT name \
                        FROM sqlite_master
                        WHERE type = 'table' \
                          AND name NOT LIKE 'sqlite_%' \
                        """

            # Mock return for demonstration
            return ["users", "orders", "products", "categories", "inventory"]
        except Exception as e:
            self.logger.error(f"Failed to get tables: {e}")
            return []

    def create_changelog_table(self, table_name: str) -> bool:
        """Create changelog table for tracking changes"""
        try:
            changelog_table = f"{table_name}_changelog"

            # TODO: Implement actual changelog table creation
            # The changelog table should track:
            # - operation (INSERT, UPDATE, DELETE)
            # - primary key values
            # - timestamp
            # - database identifier (to avoid syncing own changes)
            # - change data (JSON or serialized format)

            create_query = f"""
            CREATE TABLE IF NOT EXISTS {changelog_table} (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                operation VARCHAR(10) NOT NULL,
                table_name VARCHAR(100) NOT NULL,
                primary_key_values JSON NOT NULL,
                change_data JSON,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                database_id VARCHAR(36) NOT NULL,
                synced BOOLEAN DEFAULT FALSE,
                INDEX idx_table_synced (table_name, synced),
                INDEX idx_timestamp (timestamp)
            )
            """

            self.logger.info(f"Created changelog table: {changelog_table}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to create changelog table: {e}")
            return False

    def create_triggers(self, table_name: str, db_id: str) -> bool:
        """Create triggers to populate changelog table"""
        try:
            changelog_table = f"{table_name}_changelog"

            # TODO: Implement actual trigger creation based on database type
            # Triggers should capture INSERT, UPDATE, DELETE operations
            # and insert records into the changelog table

            # Example MySQL triggers:
            insert_trigger = f"""
            CREATE TRIGGER {table_name}_insert_trigger
            AFTER INSERT ON {table_name}
            FOR EACH ROW
            INSERT INTO {changelog_table} 
            (operation, table_name, primary_key_values, change_data, database_id)
            VALUES ('INSERT', '{table_name}', 
                    JSON_OBJECT('id', NEW.id), 
                    JSON_EXTRACT(JSON_OBJECT(NEW.*), '), 
                    '{db_id}')
            """

            update_trigger = f"""
            CREATE TRIGGER {table_name}_update_trigger
            AFTER UPDATE ON {table_name}
            FOR EACH ROW
            INSERT INTO {changelog_table} 
            (operation, table_name, primary_key_values, change_data, database_id)
            VALUES ('UPDATE', '{table_name}', 
                    JSON_OBJECT('id', NEW.id), 
                    JSON_OBJECT('old', JSON_EXTRACT(JSON_OBJECT(OLD.*), '),
                               'new', JSON_EXTRACT(JSON_OBJECT(NEW.*), ')), 
                    '{db_id}')
            """

            delete_trigger = f"""
            CREATE TRIGGER {table_name}_delete_trigger
            AFTER DELETE ON {table_name}
            FOR EACH ROW
            INSERT INTO {changelog_table} 
            (operation, table_name, primary_key_values, change_data, database_id)
            VALUES ('DELETE', '{table_name}', 
                    JSON_OBJECT('id', OLD.id), 
                    JSON_EXTRACT(JSON_OBJECT(OLD.*), '), 
                    '{db_id}')
            """

            self.logger.info(f"Created triggers for table: {table_name}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to create triggers: {e}")
            return False

    def get_pending_changes(self, table_name: str, last_sync_time: str = None) -> List[Dict]:
        """Get pending changes from changelog table"""
        try:
            changelog_table = f"{table_name}_changelog"

            query = f"""
            SELECT * FROM {changelog_table} 
            WHERE synced = FALSE
            """

            if last_sync_time:
                query += f" AND timestamp > '{last_sync_time}'"

            query += " ORDER BY timestamp ASC"

            # TODO: Execute query and return results
            # Mock return for demonstration
            return []
        except Exception as e:
            self.logger.error(f"Failed to get pending changes: {e}")
            return []

    def apply_change(self, change_record: Dict) -> bool:
        """Apply a change record to the database"""
        try:
            operation = change_record['operation']
            table_name = change_record['table_name']
            change_data = change_record['change_data']

            # TODO: Implement actual change application based on operation type
            if operation == 'INSERT':
                # Build and execute INSERT query
                pass
            elif operation == 'UPDATE':
                # Build and execute UPDATE query
                pass
            elif operation == 'DELETE':
                # Build and execute DELETE query
                pass

            self.logger.info(f"Applied {operation} to {table_name}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to apply change: {e}")
            return False

    def mark_changes_synced(self, change_ids: List[int]) -> bool:
        """Mark changes as synced in changelog table"""
        try:
            # TODO: Update synced flag for the given change IDs
            self.logger.info(f"Marked {len(change_ids)} changes as synced")
            return True
        except Exception as e:
            self.logger.error(f"Failed to mark changes as synced: {e}")
            return False


class SyncEngine:
    """Main synchronization logic"""

    def __init__(self, db_pair: DatabasePair):
        self.db_pair = db_pair
        self.local_manager = DatabaseManager(db_pair.local_db)
        self.cloud_manager = DatabaseManager(db_pair.cloud_db)
        self.logger = logging.getLogger(self.__class__.__name__)

    def setup_sync_infrastructure(self) -> bool:
        """Set up changelog tables and triggers for all sync-enabled tables"""
        try:
            # Connect to both databases
            if not self.local_manager.connect() or not self.cloud_manager.connect():
                return False

            for table_config in self.db_pair.tables:
                if table_config.sync_direction == SyncDirection.NO_SYNC:
                    continue

                table_name = table_config.table_name

                # Create changelog tables
                if not self.local_manager.create_changelog_table(table_name):
                    return False
                if not self.cloud_manager.create_changelog_table(table_name):
                    return False

                # Create triggers
                if not self.local_manager.create_triggers(table_name, self.db_pair.local_db.id):
                    return False
                if not self.cloud_manager.create_triggers(table_name, self.db_pair.cloud_db.id):
                    return False

            self.logger.info("Sync infrastructure setup completed")
            return True
        except Exception as e:
            self.logger.error(f"Failed to setup sync infrastructure: {e}")
            return False
        finally:
            self.local_manager.disconnect()
            self.cloud_manager.disconnect()

    def sync_table(self, table_config: TableSyncConfig) -> bool:
        """Synchronize a single table based on its configuration"""
        try:
            table_name = table_config.table_name
            direction = table_config.sync_direction
            last_sync = table_config.last_sync

            if direction == SyncDirection.NO_SYNC:
                return True

            self.logger.info(f"Syncing table {table_name} with direction {direction.value}")

            # Connect to databases
            if not self.local_manager.connect() or not self.cloud_manager.connect():
                return False

            if direction == SyncDirection.LOCAL_TO_CLOUD:
                return self._sync_one_way(table_name, self.local_manager,
                                          self.cloud_manager, last_sync)
            elif direction == SyncDirection.CLOUD_TO_LOCAL:
                return self._sync_one_way(table_name, self.cloud_manager,
                                          self.local_manager, last_sync)
            elif direction == SyncDirection.BIDIRECTIONAL:
                success1 = self._sync_one_way(table_name, self.local_manager,
                                              self.cloud_manager, last_sync)
                success2 = self._sync_one_way(table_name, self.cloud_manager,
                                              self.local_manager, last_sync)
                return success1 and success2

            return True
        except Exception as e:
            self.logger.error(f"Failed to sync table {table_name}: {e}")
            return False
        finally:
            self.local_manager.disconnect()
            self.cloud_manager.disconnect()

    def _sync_one_way(self, table_name: str, source_manager: DatabaseManager,
                      target_manager: DatabaseManager, last_sync: str = None) -> bool:
        """Perform one-way synchronization from source to target"""
        try:
            # Get pending changes from source
            pending_changes = source_manager.get_pending_changes(table_name, last_sync)

            if not pending_changes:
                self.logger.info(f"No pending changes for table {table_name}")
                return True

            applied_ids = []

            for change in pending_changes:
                # Skip changes that originated from the target database
                if change['database_id'] == target_manager.config.id:
                    continue

                if target_manager.apply_change(change):
                    applied_ids.append(change['id'])
                else:
                    self.logger.warning(f"Failed to apply change {change['id']}")

            # Mark successfully applied changes as synced
            if applied_ids:
                source_manager.mark_changes_synced(applied_ids)
                self.logger.info(f"Successfully synced {len(applied_ids)} changes for {table_name}")

            return True
        except Exception as e:
            self.logger.error(f"Failed one-way sync: {e}")
            return False

    def sync_all_tables(self) -> bool:
        """Synchronize all configured tables"""
        success = True

        for table_config in self.db_pair.tables:
            if not self.sync_table(table_config):
                success = False

            # Update last sync time
            table_config.last_sync = datetime.now().isoformat()

        return success


def main():
    app = QApplication(sys.argv)

    # Set application properties
    app.setApplicationName("Database Sync Tool")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("YourCompany")

    # Apply a modern dark theme
    app.setStyle("Fusion")
    dark_palette = QPalette()
    dark_palette.setColor(QPalette.Window, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.WindowText, QColor(255, 255, 255))
    dark_palette.setColor(QPalette.Base, QColor(25, 25, 25))
    dark_palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ToolTipBase, QColor(0, 0, 0))
    dark_palette.setColor(QPalette.ToolTipText, QColor(255, 255, 255))
    dark_palette.setColor(QPalette.Text, QColor(255, 255, 255))
    dark_palette.setColor(QPalette.Button, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ButtonText, QColor(255, 255, 255))
    dark_palette.setColor(QPalette.BrightText, QColor(255, 0, 0))
    dark_palette.setColor(QPalette.Link, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.HighlightedText, QColor(0, 0, 0))
    app.setPalette(dark_palette)

    # Create and show main window
    window = MainWindow()
    window.show()

    # Run the application
    sys.exit(app.exec())


if __name__ == "__main__":
    main()