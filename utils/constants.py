"""
Application constants and configuration values.

This module contains all the constant values used throughout the application,
including file names, default values, and configuration parameters.
"""

from pathlib import Path

# Application Information
APP_NAME = "Database Sync Tool"
APP_VERSION = "1.0.0"
ORGANIZATION_NAME = "YourCompany"

# File Names
CONFIG_FILE = "config.json"
LOG_FILE = "sync_app.log"
BACKUP_DIR = "backups"

# Default Values
DEFAULT_PASSWORD = "admin"
DEFAULT_SYNC_INTERVAL = 300  # 5 minutes in seconds
DEFAULT_CONNECTION_TIMEOUT = 30  # seconds
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_MAX_LOG_SIZE = 10  # MB

# Database Configuration
SUPPORTED_DATABASES = ["mysql", "postgresql", "sqlite"]
DEFAULT_MYSQL_PORT = 3306
DEFAULT_POSTGRESQL_PORT = 5432

# Changelog Table Configuration
CHANGELOG_TABLE_SUFFIX = "_changelog"
TRIGGER_SUFFIX = "_trigger"

# SQL Templates for different database types
MYSQL_CHANGELOG_TABLE = """
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
    INDEX idx_timestamp (timestamp),
    INDEX idx_database_id (database_id)
);
"""

POSTGRESQL_CHANGELOG_TABLE = """
CREATE TABLE IF NOT EXISTS {changelog_table} (
    id BIGSERIAL PRIMARY KEY,
    operation VARCHAR(10) NOT NULL,
    table_name VARCHAR(100) NOT NULL,
    primary_key_values JSONB NOT NULL,
    change_data JSONB,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    database_id VARCHAR(36) NOT NULL,
    synced BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_{changelog_table}_table_synced 
ON {changelog_table} (table_name, synced);

CREATE INDEX IF NOT EXISTS idx_{changelog_table}_timestamp 
ON {changelog_table} (timestamp);

CREATE INDEX IF NOT EXISTS idx_{changelog_table}_database_id 
ON {changelog_table} (database_id);
"""

SQLITE_CHANGELOG_TABLE = """
CREATE TABLE IF NOT EXISTS {changelog_table} (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operation TEXT NOT NULL,
    table_name TEXT NOT NULL,
    primary_key_values TEXT NOT NULL,
    change_data TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    database_id TEXT NOT NULL,
    synced BOOLEAN DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_{changelog_table}_table_synced 
ON {changelog_table} (table_name, synced);

CREATE INDEX IF NOT EXISTS idx_{changelog_table}_timestamp 
ON {changelog_table} (timestamp);

CREATE INDEX IF NOT EXISTS idx_{changelog_table}_database_id 
ON {changelog_table} (database_id);
"""

# UI Constants
WINDOW_MIN_WIDTH = 800
WINDOW_MIN_HEIGHT = 600
LOG_VIEWER_MAX_HEIGHT = 200
REFRESH_INTERVAL = 5000  # 5 seconds in milliseconds

# Sync Constants
MAX_BATCH_SIZE = 1000
MAX_RETRY_ATTEMPTS = 3
RETRY_DELAY = 5  # seconds

# Color Schemes for Dark Theme
DARK_THEME_COLORS = {
    'window': (53, 53, 53),
    'window_text': (255, 255, 255),
    'base': (25, 25, 25),
    'alternate_base': (53, 53, 53),
    'tooltip_base': (0, 0, 0),
    'tooltip_text': (255, 255, 255),
    'text': (255, 255, 255),
    'button': (53, 53, 53),
    'button_text': (255, 255, 255),
    'bright_text': (255, 0, 0),
    'link': (42, 130, 218),
    'highlight': (42, 130, 218),
    'highlighted_text': (0, 0, 0)
}

# Status Messages
STATUS_MESSAGES = {
    'connecting': "Connecting to database...",
    'connected': "Database connection established",
    'connection_failed': "Failed to connect to database",
    'sync_started': "Synchronization started",
    'sync_completed': "Synchronization completed successfully",
    'sync_failed': "Synchronization failed",
    'sync_stopped': "Synchronization stopped by user",
    'no_changes': "No changes to synchronize",
    'loading_tables': "Loading database tables...",
    'tables_loaded': "Database tables loaded successfully",
    'setup_complete': "Synchronization infrastructure setup complete"
}

# Error Messages
ERROR_MESSAGES = {
    'invalid_password': "Invalid password. Access denied.",
    'password_mismatch': "Passwords do not match. Please try again.",
    'no_db_pairs': "No database pairs configured. Please add a configuration first.",
    'connection_timeout': "Database connection timed out.",
    'sync_in_progress': "Synchronization already in progress.",
    'config_save_failed': "Failed to save configuration.",
    'config_load_failed': "Failed to load configuration.",
    'invalid_config': "Invalid configuration data.",
    'table_not_found': "Table not found in database.",
    'trigger_creation_failed': "Failed to create database triggers.",
    'changelog_creation_failed': "Failed to create changelog table."
}

# Validation Rules
VALIDATION_RULES = {
    'min_password_length': 4,
    'max_password_length': 50,
    'min_sync_interval': 30,  # seconds
    'max_sync_interval': 86400,  # 24 hours
    'min_port': 1,
    'max_port': 65535,
    'max_table_name_length': 64,
    'max_db_name_length': 64
}