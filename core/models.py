"""
Data models and enums for the Database Synchronization Application.

This module contains all the data structures used throughout the application,
including database configurations, sync settings, and status enums.
"""

from dataclasses import dataclass, asdict
from enum import Enum
from typing import List, Optional, Dict, Any
import uuid


class SyncDirection(Enum):
    """Enum for table synchronization directions."""
    NO_SYNC = "no_sync"
    LOCAL_TO_CLOUD = "local_to_cloud"
    CLOUD_TO_LOCAL = "cloud_to_local"
    BIDIRECTIONAL = "bidirectional"


class JobStatus(Enum):
    """Enum for synchronization job status."""
    STOPPED = "Stopped"
    RUNNING = "Running"
    ERROR = "Error"
    PAUSED = "Paused"
    COMPLETED = "Completed"


class DatabaseType(Enum):
    """Enum for supported database types."""
    MYSQL = "mysql"
    POSTGRESQL = "postgresql"
    SQLITE = "sqlite"


class LogLevel(Enum):
    """Enum for logging levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


@dataclass
class DatabaseConfig:
    """Configuration for a database connection."""
    id: str
    name: str
    db_type: str
    host: str
    port: int
    database: str
    username: str
    password: str
    is_local: bool = True
    connection_timeout: int = 30

    def __post_init__(self):
        """Generate ID if not provided."""
        if not self.id:
            self.id = str(uuid.uuid4())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DatabaseConfig':
        """Create instance from dictionary."""
        return cls(**data)

    def get_connection_string(self) -> str:
        """Generate connection string based on database type."""
        if self.db_type == DatabaseType.MYSQL.value:
            return f"mysql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
        elif self.db_type == DatabaseType.POSTGRESQL.value:
            return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
        elif self.db_type == DatabaseType.SQLITE.value:
            return f"sqlite:///{self.database}"
        else:
            raise ValueError(f"Unsupported database type: {self.db_type}")


@dataclass
class TableSyncConfig:
    """Configuration for table synchronization."""
    table_name: str
    sync_direction: SyncDirection
    last_sync: Optional[str] = None
    is_enabled: bool = True
    conflict_resolution: str = "newer_wins"  # newer_wins, local_wins, cloud_wins

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'table_name': self.table_name,
            'sync_direction': self.sync_direction.value,  # Convert enum to string
            'last_sync': self.last_sync,
            'is_enabled': self.is_enabled,
            'conflict_resolution': self.conflict_resolution
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TableSyncConfig':
        """Create instance from dictionary."""
        # Convert string back to enum
        sync_direction = data['sync_direction']
        if isinstance(sync_direction, str):
            sync_direction = SyncDirection(sync_direction)

        return cls(
            table_name=data['table_name'],
            sync_direction=sync_direction,
            last_sync=data.get('last_sync'),
            is_enabled=data.get('is_enabled', True),
            conflict_resolution=data.get('conflict_resolution', 'newer_wins')
        )


@dataclass
class DatabasePair:
    """Configuration for a pair of databases to sync."""
    id: str
    name: str
    local_db: DatabaseConfig
    cloud_db: DatabaseConfig
    tables: List[TableSyncConfig]
    sync_interval: int = 300  # 5 minutes default
    is_enabled: bool = True
    last_sync: Optional[str] = None

    def __post_init__(self):
        """Generate ID if not provided."""
        if not self.id:
            self.id = str(uuid.uuid4())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'id': self.id,
            'name': self.name,
            'local_db': self.local_db.to_dict(),
            'cloud_db': self.cloud_db.to_dict(),
            'tables': [table.to_dict() for table in self.tables],  # This calls TableSyncConfig.to_dict()
            'sync_interval': self.sync_interval,
            'is_enabled': self.is_enabled,
            'last_sync': self.last_sync
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DatabasePair':
        """Create instance from dictionary."""
        local_db = DatabaseConfig.from_dict(data['local_db'])
        cloud_db = DatabaseConfig.from_dict(data['cloud_db'])
        tables = [TableSyncConfig.from_dict(table_data) for table_data in data['tables']]

        return cls(
            id=data['id'],
            name=data['name'],
            local_db=local_db,
            cloud_db=cloud_db,
            tables=tables,
            sync_interval=data.get('sync_interval', 300),
            is_enabled=data.get('is_enabled', True),
            last_sync=data.get('last_sync')
        )

    def get_sync_enabled_tables(self) -> List[TableSyncConfig]:
        """Get list of tables with sync enabled."""
        return [table for table in self.tables
                if table.sync_direction != SyncDirection.NO_SYNC and table.is_enabled]


@dataclass
class ChangeRecord:
    """Represents a database change record."""
    id: int
    operation: str  # INSERT, UPDATE, DELETE
    table_name: str
    primary_key_values: Dict[str, Any]
    change_data: Dict[str, Any]
    timestamp: str
    database_id: str
    synced: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ChangeRecord':
        """Create instance from dictionary."""
        return cls(**data)


@dataclass
class SyncResult:
    """Result of a synchronization operation."""
    success: bool
    table_name: str
    records_synced: int = 0
    errors: List[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None

    def __post_init__(self):
        """Initialize errors list if None."""
        if self.errors is None:
            self.errors = []

    def add_error(self, error: str):
        """Add an error to the result."""
        self.errors.append(error)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)


@dataclass
class AppConfig:
    """Main application configuration."""
    app_password_hash: str
    database_pairs: List[Dict[str, Any]]
    log_level: str = LogLevel.INFO.value
    auto_start: bool = False
    default_sync_interval: int = 300
    max_log_size: int = 10  # MB
    backup_enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AppConfig':
        """Create instance from dictionary."""
        return cls(**data)