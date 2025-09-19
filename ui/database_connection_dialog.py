"""
Database connection configuration dialog.

This module provides the interface for configuring database connections
and table sync settings.
"""

import logging
from typing import List, Optional
import uuid

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLineEdit, QSpinBox, QComboBox, QPushButton, QTableWidget,
    QTableWidgetItem, QCheckBox, QHeaderView, QMessageBox,
    QProgressDialog, QLabel, QSplitter, QTextEdit, QWidget, QSizePolicy
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont

from core.models import DatabaseConfig, DatabasePair, TableSyncConfig, SyncDirection, DatabaseType
from utils.constants import (
    SUPPORTED_DATABASES, DEFAULT_MYSQL_PORT, DEFAULT_POSTGRESQL_PORT,
    VALIDATION_RULES, WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT
)


class ConnectionTestWorker(QThread):
    """Worker thread for testing database connections."""

    test_completed = Signal(bool, str, list)  # success, message, tables

    def __init__(self, db_config: DatabaseConfig):
        super().__init__()
        self.db_config = db_config

    def run(self):
        """Test database connection and get table list."""
        try:
            from core.database_manager import DatabaseManager

            manager = DatabaseManager(self.db_config)

            # Test connection
            if manager.test_connection():
                # Get tables if connection successful
                tables = manager.get_tables()
                self.test_completed.emit(True, "Connection successful", tables)
            else:
                self.test_completed.emit(False, "Connection failed", [])

        except Exception as e:
            self.test_completed.emit(False, f"Connection error: {str(e)}", [])


class DatabaseConnectionDialog(QDialog):
    """Dialog for configuring database connections and sync settings."""

    def __init__(self, parent=None, existing_pair: Optional[DatabasePair] = None):
        """
        Initialize the database connection dialog.

        Args:
            parent: Parent widget
            existing_pair: Existing database pair to edit (None for new pair)
        """
        super().__init__(parent)
        self.existing_pair = existing_pair
        self.is_editing = existing_pair is not None
        self.logger = logging.getLogger(self.__class__.__name__)

        # Connection test workers
        self.local_test_worker = None
        self.cloud_test_worker = None

        # Available tables
        self.local_tables = []
        self.cloud_tables = []
        self.common_tables = []

        self.setup_ui()

        if self.is_editing:
            self.load_existing_configuration()

    def setup_ui(self):
        """Set up the user interface."""
        title = "Edit Database Pair" if self.is_editing else "Add Database Pair"
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.setMinimumSize(1000, 700)
        self.setMaximumHeight(800)

        # Main layout
        main_layout = QVBoxLayout(self)

        # Configuration name
        name_layout = QFormLayout()
        self.pair_name = QLineEdit()
        self.pair_name.setPlaceholderText("Enter a name for this configuration")
        name_layout.addRow("Configuration Name:", self.pair_name)
        main_layout.addLayout(name_layout)

        # Create splitter for main content
        splitter = QSplitter(Qt.Vertical)

        # Database connection settings
        conn_widget = self.create_connection_settings()
        splitter.addWidget(conn_widget)

        # Table synchronization settings
        tables_widget = self.create_table_settings()
        splitter.addWidget(tables_widget)

        # Set splitter proportions
        splitter.setSizes([200, 350])
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        main_layout.addWidget(splitter)

        # Sync interval and options
        self.create_sync_options(main_layout)

        # Dialog buttons
        self.create_dialog_buttons(main_layout)

    def create_connection_settings(self) -> QGroupBox:
        """Create database connection settings section."""
        conn_group = QGroupBox("Database Connections")
        layout = QHBoxLayout(conn_group)

        # Local database settings
        local_group = QGroupBox("Local Database")
        local_layout = QFormLayout(local_group)

        self.local_type = QComboBox()
        self.local_type.addItems(SUPPORTED_DATABASES)
        self.local_type.currentTextChanged.connect(self.on_local_db_type_changed)
        local_layout.addRow("Database Type:", self.local_type)

        self.local_host = QLineEdit("localhost")
        local_layout.addRow("Host:", self.local_host)

        self.local_port = QSpinBox()
        self.local_port.setRange(VALIDATION_RULES['min_port'], VALIDATION_RULES['max_port'])
        self.local_port.setValue(DEFAULT_MYSQL_PORT)
        local_layout.addRow("Port:", self.local_port)

        self.local_database = QLineEdit()
        self.local_database.setPlaceholderText("Database name")
        local_layout.addRow("Database:", self.local_database)

        self.local_username = QLineEdit()
        local_layout.addRow("Username:", self.local_username)

        self.local_password = QLineEdit()
        self.local_password.setEchoMode(QLineEdit.Password)
        local_layout.addRow("Password:", self.local_password)

        # Local connection buttons
        local_btn_layout = QHBoxLayout()
        self.test_local_btn = QPushButton("Test Connection")
        self.test_local_btn.clicked.connect(self.test_local_connection)
        local_btn_layout.addWidget(self.test_local_btn)
        local_btn_layout.addStretch()
        local_layout.addRow(local_btn_layout)

        layout.addWidget(local_group)

        # Cloud database settings
        cloud_group = QGroupBox("Cloud Database")
        cloud_layout = QFormLayout(cloud_group)

        self.cloud_type = QComboBox()
        self.cloud_type.addItems(SUPPORTED_DATABASES)
        self.cloud_type.currentTextChanged.connect(self.on_cloud_db_type_changed)
        cloud_layout.addRow("Database Type:", self.cloud_type)

        self.cloud_host = QLineEdit()
        self.cloud_host.setPlaceholderText("Remote host address")
        cloud_layout.addRow("Host:", self.cloud_host)

        self.cloud_port = QSpinBox()
        self.cloud_port.setRange(VALIDATION_RULES['min_port'], VALIDATION_RULES['max_port'])
        self.cloud_port.setValue(DEFAULT_MYSQL_PORT)
        cloud_layout.addRow("Port:", self.cloud_port)

        self.cloud_database = QLineEdit()
        self.cloud_database.setPlaceholderText("Database name")
        cloud_layout.addRow("Database:", self.cloud_database)

        self.cloud_username = QLineEdit()
        cloud_layout.addRow("Username:", self.cloud_username)

        self.cloud_password = QLineEdit()
        self.cloud_password.setEchoMode(QLineEdit.Password)
        cloud_layout.addRow("Password:", self.cloud_password)

        # Cloud connection buttons
        cloud_btn_layout = QHBoxLayout()
        self.test_cloud_btn = QPushButton("Test Connection")
        self.test_cloud_btn.clicked.connect(self.test_cloud_connection)
        cloud_btn_layout.addWidget(self.test_cloud_btn)
        cloud_btn_layout.addStretch()
        cloud_layout.addRow(cloud_btn_layout)

        layout.addWidget(cloud_group)

        return conn_group

    def create_table_settings(self) -> QGroupBox:
        """Create table synchronization settings section."""
        tables_group = QGroupBox("Table Synchronization Settings")
        layout = QVBoxLayout(tables_group)

        # Control buttons
        controls_layout = QHBoxLayout()

        self.load_tables_btn = QPushButton("Load Tables")
        self.load_tables_btn.clicked.connect(self.load_tables)
        self.load_tables_btn.setEnabled(False)

        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.clicked.connect(self.select_all_tables)

        self.select_none_btn = QPushButton("Select None")
        self.select_none_btn.clicked.connect(self.select_no_tables)

        controls_layout.addWidget(self.load_tables_btn)
        controls_layout.addWidget(self.select_all_btn)
        controls_layout.addWidget(self.select_none_btn)
        controls_layout.addStretch()

        layout.addLayout(controls_layout)

        # Create horizontal splitter for tables and status
        content_splitter = QSplitter(Qt.Horizontal)

        # Left side - Tables table
        tables_container = QWidget()
        tables_container_layout = QVBoxLayout(tables_container)
        tables_container_layout.setContentsMargins(0, 0, 0, 0)

        self.tables_widget = QTableWidget()
        self.tables_widget.setColumnCount(5)
        self.tables_widget.setHorizontalHeaderLabels([
            "Table Name", "Local → Cloud", "Cloud → Local", "Bidirectional", "No Sync"
        ])

        # Configure table
        header = self.tables_widget.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)

        self.tables_widget.setAlternatingRowColors(True)
        self.tables_widget.setMinimumHeight(200)  # Reduced minimum height
        self.tables_widget.setMaximumHeight(300)  # Add maximum height to prevent overflow
        self.tables_widget.setMinimumWidth(400)   # Keep minimum width

        tables_container_layout.addWidget(self.tables_widget)
        content_splitter.addWidget(tables_container)

        # Right side - Status area
        status_container = QWidget()
        status_container_layout = QVBoxLayout(status_container)
        status_container_layout.setContentsMargins(0, 0, 0, 0)

        status_label = QLabel("Connection Status:")
        status_label.setStyleSheet("font-weight: bold;")
        status_container_layout.addWidget(status_label)

        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setFont(QFont("Consolas", 9))
        self.status_text.setMinimumWidth(300)
        self.status_text.setMaximumWidth(400)
        self.status_text.setMaximumHeight(300)  # Add maximum height
        self.status_text.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

        status_container_layout.addWidget(self.status_text)
        content_splitter.addWidget(status_container)

        # Set splitter proportions - give more space to tables
        content_splitter.setSizes([600, 300])
        content_splitter.setCollapsible(0, False)  # Don't allow tables area to collapse
        content_splitter.setCollapsible(1, True)  # Allow status area to collapse

        layout.addWidget(content_splitter)

        return tables_group

    def create_sync_options(self, layout):
        """Create sync options section."""
        options_group = QGroupBox("Sync Options")
        options_layout = QFormLayout(options_group)

        # Sync interval
        self.sync_interval = QSpinBox()
        self.sync_interval.setRange(VALIDATION_RULES['min_sync_interval'],
                                    VALIDATION_RULES['max_sync_interval'])
        self.sync_interval.setValue(300)
        self.sync_interval.setSuffix(" seconds")
        options_layout.addRow("Sync Interval:", self.sync_interval)

        # Enable/disable pair
        self.pair_enabled = QCheckBox("Enable this database pair")
        self.pair_enabled.setChecked(True)
        options_layout.addRow(self.pair_enabled)

        # Conflict resolution
        self.conflict_resolution = QComboBox()
        self.conflict_resolution.addItems(["newer_wins", "local_wins", "cloud_wins"])
        self.conflict_resolution.setCurrentText("newer_wins")
        options_layout.addRow("Conflict Resolution:", self.conflict_resolution)

        layout.addWidget(options_group)

    def create_dialog_buttons(self, layout):
        """Create dialog action buttons."""
        button_layout = QHBoxLayout()

        self.save_button = QPushButton("Save Configuration")
        self.cancel_button = QPushButton("Cancel")

        self.save_button.clicked.connect(self.validate_and_accept)
        self.cancel_button.clicked.connect(self.reject)

        # Style buttons
        self.save_button.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; }")
        self.save_button.setMinimumHeight(35)
        self.cancel_button.setMinimumHeight(35)

        button_layout.addStretch()
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

    def on_local_db_type_changed(self, db_type: str):
        """Handle local database type change."""
        if db_type == DatabaseType.MYSQL.value:
            self.local_port.setValue(DEFAULT_MYSQL_PORT)
        elif db_type == DatabaseType.POSTGRESQL.value:
            self.local_port.setValue(DEFAULT_POSTGRESQL_PORT)
        elif db_type == DatabaseType.SQLITE.value:
            self.local_port.setValue(0)
            self.local_host.setText("")

    def on_cloud_db_type_changed(self, db_type: str):
        """Handle cloud database type change."""
        if db_type == DatabaseType.MYSQL.value:
            self.cloud_port.setValue(DEFAULT_MYSQL_PORT)
        elif db_type == DatabaseType.POSTGRESQL.value:
            self.cloud_port.setValue(DEFAULT_POSTGRESQL_PORT)
        elif db_type == DatabaseType.SQLITE.value:
            self.cloud_port.setValue(0)

    def test_local_connection(self):
        """Test local database connection."""
        db_config = self.get_local_db_config()
        if not self.validate_db_config(db_config, "Local"):
            return

        self.test_local_btn.setEnabled(False)
        self.test_local_btn.setText("Testing...")

        self.local_test_worker = ConnectionTestWorker(db_config)
        self.local_test_worker.test_completed.connect(self.on_local_test_completed)
        self.local_test_worker.start()

    def test_cloud_connection(self):
        """Test cloud database connection."""
        db_config = self.get_cloud_db_config()
        if not self.validate_db_config(db_config, "Cloud"):
            return

        self.test_cloud_btn.setEnabled(False)
        self.test_cloud_btn.setText("Testing...")

        self.cloud_test_worker = ConnectionTestWorker(db_config)
        self.cloud_test_worker.test_completed.connect(self.on_cloud_test_completed)
        self.cloud_test_worker.start()

    def on_local_test_completed(self, success: bool, message: str, tables: List[str]):
        """Handle local connection test completion."""
        self.test_local_btn.setEnabled(True)
        self.test_local_btn.setText("Test Connection")

        if success:
            self.local_tables = tables
            self.status_text.append(f"Local: {message} - Found {len(tables)} tables")
            self.check_load_tables_readiness()
        else:
            self.status_text.append(f"Local: {message}")
            QMessageBox.warning(self, "Local Connection Failed", message)

    def on_cloud_test_completed(self, success: bool, message: str, tables: List[str]):
        """Handle cloud connection test completion."""
        self.test_cloud_btn.setEnabled(True)
        self.test_cloud_btn.setText("Test Connection")

        if success:
            self.cloud_tables = tables
            self.status_text.append(f"Cloud: {message} - Found {len(tables)} tables")
            self.check_load_tables_readiness()
        else:
            self.status_text.append(f"Cloud: {message}")
            QMessageBox.warning(self, "Cloud Connection Failed", message)

    def check_load_tables_readiness(self):
        """Check if both connections are tested and enable load tables button."""
        if self.local_tables and self.cloud_tables:
            self.load_tables_btn.setEnabled(True)

            # Find common tables
            self.common_tables = list(set(self.local_tables) & set(self.cloud_tables))
            self.status_text.append(f"Found {len(self.common_tables)} common tables ready for sync")

    def load_tables(self):
        """Load tables for synchronization configuration."""
        if not self.common_tables:
            QMessageBox.warning(self, "No Common Tables",
                                "No tables found that exist in both databases.")
            return

        self.tables_widget.setRowCount(len(self.common_tables))

        for i, table_name in enumerate(sorted(self.common_tables)):
            # Table name
            self.tables_widget.setItem(i, 0, QTableWidgetItem(table_name))

            # Create radio button group for sync direction
            local_to_cloud = QCheckBox()
            cloud_to_local = QCheckBox()
            bidirectional = QCheckBox()
            no_sync = QCheckBox()

            # Set no_sync as default
            no_sync.setChecked(True)

            # Make them mutually exclusive
            def make_exclusive(current_cb, others, row=i):
                def toggle():
                    if current_cb.isChecked():
                        for other in others:
                            other.setChecked(False)

                return toggle

            local_to_cloud.toggled.connect(
                make_exclusive(local_to_cloud, [cloud_to_local, bidirectional, no_sync]))
            cloud_to_local.toggled.connect(
                make_exclusive(cloud_to_local, [local_to_cloud, bidirectional, no_sync]))
            bidirectional.toggled.connect(
                make_exclusive(bidirectional, [local_to_cloud, cloud_to_local, no_sync]))
            no_sync.toggled.connect(
                make_exclusive(no_sync, [local_to_cloud, cloud_to_local, bidirectional]))

            self.tables_widget.setCellWidget(i, 1, local_to_cloud)
            self.tables_widget.setCellWidget(i, 2, cloud_to_local)
            self.tables_widget.setCellWidget(i, 3, bidirectional)
            self.tables_widget.setCellWidget(i, 4, no_sync)

        self.status_text.append(f"Loaded {len(self.common_tables)} tables for configuration")

    def select_all_tables(self):
        """Select bidirectional sync for all tables."""
        for i in range(self.tables_widget.rowCount()):
            bidirectional_cb = self.tables_widget.cellWidget(i, 3)
            if bidirectional_cb:
                bidirectional_cb.setChecked(True)

    def select_no_tables(self):
        """Select no sync for all tables."""
        for i in range(self.tables_widget.rowCount()):
            no_sync_cb = self.tables_widget.cellWidget(i, 4)
            if no_sync_cb:
                no_sync_cb.setChecked(True)

    def validate_db_config(self, db_config: DatabaseConfig, prefix: str) -> bool:
        """Validate database configuration."""
        if not db_config.database:
            QMessageBox.warning(self, "Invalid Configuration",
                                f"{prefix} database name is required.")
            return False

        if db_config.db_type != DatabaseType.SQLITE.value:
            if not db_config.host:
                QMessageBox.warning(self, "Invalid Configuration",
                                    f"{prefix} host is required.")
                return False

            if not db_config.username:
                QMessageBox.warning(self, "Invalid Configuration",
                                    f"{prefix} username is required.")
                return False

        return True

    def get_local_db_config(self) -> DatabaseConfig:
        """Get local database configuration from UI."""
        return DatabaseConfig(
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

    def get_cloud_db_config(self) -> DatabaseConfig:
        """Get cloud database configuration from UI."""
        return DatabaseConfig(
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

    def get_table_configurations(self) -> List[TableSyncConfig]:
        """Get table synchronization configurations from UI."""
        tables = []

        for i in range(self.tables_widget.rowCount()):
            table_name_item = self.tables_widget.item(i, 0)
            if not table_name_item:
                continue

            table_name = table_name_item.text()

            # Get sync direction
            sync_direction = SyncDirection.NO_SYNC

            if self.tables_widget.cellWidget(i, 1).isChecked():  # Local to Cloud
                sync_direction = SyncDirection.LOCAL_TO_CLOUD
            elif self.tables_widget.cellWidget(i, 2).isChecked():  # Cloud to Local
                sync_direction = SyncDirection.CLOUD_TO_LOCAL
            elif self.tables_widget.cellWidget(i, 3).isChecked():  # Bidirectional
                sync_direction = SyncDirection.BIDIRECTIONAL

            tables.append(TableSyncConfig(
                table_name=table_name,
                sync_direction=sync_direction,
                conflict_resolution=self.conflict_resolution.currentText()
            ))

        return tables

    def validate_and_accept(self):
        """Validate configuration and accept dialog."""
        try:
            # Basic validation
            if not self.pair_name.text().strip():
                QMessageBox.warning(self, "Invalid Configuration",
                                    "Configuration name is required.")
                return

            local_config = self.get_local_db_config()
            cloud_config = self.get_cloud_db_config()

            if not self.validate_db_config(local_config, "Local"):
                return

            if not self.validate_db_config(cloud_config, "Cloud"):
                return

            # Check if tables are loaded
            if self.tables_widget.rowCount() == 0:
                reply = QMessageBox.question(
                    self,
                    "No Tables Configured",
                    "No tables have been configured for synchronization.\n\n"
                    "Do you want to save this configuration anyway?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )

                if reply != QMessageBox.Yes:
                    return

            self.accept()

        except Exception as e:
            QMessageBox.critical(self, "Validation Error", f"Error validating configuration:\n{e}")

    def get_database_pair(self) -> DatabasePair:
        """Get the complete database pair configuration."""
        local_db = self.get_local_db_config()
        cloud_db = self.get_cloud_db_config()
        tables = self.get_table_configurations()

        return DatabasePair(
            id=self.existing_pair.id if self.existing_pair else str(uuid.uuid4()),
            name=self.pair_name.text().strip(),
            local_db=local_db,
            cloud_db=cloud_db,
            tables=tables,
            sync_interval=self.sync_interval.value(),
            is_enabled=self.pair_enabled.isChecked()
        )

    def load_existing_configuration(self):
        """Load existing database pair configuration into UI."""
        if not self.existing_pair:
            return

        # Load basic info
        self.pair_name.setText(self.existing_pair.name)
        self.sync_interval.setValue(self.existing_pair.sync_interval)
        self.pair_enabled.setChecked(self.existing_pair.is_enabled)

        # Load local database config
        local_db = self.existing_pair.local_db
        self.local_type.setCurrentText(local_db.db_type)
        self.local_host.setText(local_db.host)
        self.local_port.setValue(local_db.port)
        self.local_database.setText(local_db.database)
        self.local_username.setText(local_db.username)
        self.local_password.setText(local_db.password)

        # Load cloud database config
        cloud_db = self.existing_pair.cloud_db
        self.cloud_type.setCurrentText(cloud_db.db_type)
        self.cloud_host.setText(cloud_db.host)
        self.cloud_port.setValue(cloud_db.port)
        self.cloud_database.setText(cloud_db.database)
        self.cloud_username.setText(cloud_db.username)
        self.cloud_password.setText(cloud_db.password)

        # Load table configurations if available
        if self.existing_pair.tables:
            table_names = [table.table_name for table in self.existing_pair.tables]
            self.common_tables = table_names
            self.load_tables()

            # Set sync directions
            for i, table_config in enumerate(self.existing_pair.tables):
                if i < self.tables_widget.rowCount():
                    direction = table_config.sync_direction

                    if direction == SyncDirection.LOCAL_TO_CLOUD:
                        self.tables_widget.cellWidget(i, 1).setChecked(True)
                    elif direction == SyncDirection.CLOUD_TO_LOCAL:
                        self.tables_widget.cellWidget(i, 2).setChecked(True)
                    elif direction == SyncDirection.BIDIRECTIONAL:
                        self.tables_widget.cellWidget(i, 3).setChecked(True)
                    else:  # NO_SYNC
                        self.tables_widget.cellWidget(i, 4).setChecked(True)