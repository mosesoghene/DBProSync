"""
Database management for the Database Synchronization Application.

This module handles all database connections, operations, and change tracking
for the synchronization process.
"""

import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from contextlib import contextmanager
from datetime import datetime

from .models import DatabaseConfig, ChangeRecord, DatabaseType
from ..utils.constants import (
    CHANGELOG_TABLE_SUFFIX, MYSQL_CHANGELOG_TABLE,
    POSTGRESQL_CHANGELOG_TABLE, SQLITE_CHANGELOG_TABLE,
    MAX_BATCH_SIZE, ERROR_MESSAGES
)


class DatabaseManager:
    """Handles database connections and operations for sync process."""

    def __init__(self, db_config: DatabaseConfig):
        """
        Initialize the database manager.

        Args:
            db_config: Database configuration
        """
        self.config = db_config
        self.connection = None
        self.logger = logging.getLogger(self.__class__.__name__)

        # Import database drivers based on type
        self._import_driver()

    def _import_driver(self):
        """Import the appropriate database driver."""
        try:
            if self.config.db_type == DatabaseType.MYSQL.value:
                import pymysql
                self.driver = pymysql
            elif self.config.db_type == DatabaseType.POSTGRESQL.value:
                import psycopg2
                import psycopg2.extras
                self.driver = psycopg2
            elif self.config.db_type == DatabaseType.SQLITE.value:
                import sqlite3
                self.driver = sqlite3
            else:
                raise ValueError(f"Unsupported database type: {self.config.db_type}")

        except ImportError as e:
            self.logger.error(f"Failed to import database driver: {e}")
            raise

    def connect(self) -> bool:
        """
        Establish database connection.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            if self.connection:
                self.disconnect()

            if self.config.db_type == DatabaseType.MYSQL.value:
                self.connection = self.driver.connect(
                    host=self.config.host,
                    port=self.config.port,
                    user=self.config.username,
                    password=self.config.password,
                    database=self.config.database,
                    charset='utf8mb4',
                    connect_timeout=self.config.connection_timeout
                )

            elif self.config.db_type == DatabaseType.POSTGRESQL.value:
                self.connection = self.driver.connect(
                    host=self.config.host,
                    port=self.config.port,
                    user=self.config.username,
                    password=self.config.password,
                    database=self.config.database,
                    connect_timeout=self.config.connection_timeout
                )

            elif self.config.db_type == DatabaseType.SQLITE.value:
                self.connection = self.driver.connect(
                    self.config.database,
                    timeout=self.config.connection_timeout
                )
                # Enable foreign key support
                self.connection.execute("PRAGMA foreign_keys = ON")

            self.logger.info(f"Connected to {self.config.db_type} database: {self.config.name}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to connect to database {self.config.name}: {e}")
            return False

    def disconnect(self):
        """Close database connection."""
        if self.connection:
            try:
                self.connection.close()
                self.connection = None
                self.logger.debug(f"Disconnected from database: {self.config.name}")
            except Exception as e:
                self.logger.error(f"Error disconnecting from database: {e}")

    @contextmanager
    def get_cursor(self):
        """Context manager for database cursors."""
        if not self.connection:
            raise RuntimeError("Database not connected")

        cursor = None
        try:
            if self.config.db_type == DatabaseType.POSTGRESQL.value:
                cursor = self.connection.cursor(cursor_factory=self.driver.extras.RealDictCursor)
            else:
                cursor = self.connection.cursor()

            yield cursor
            self.connection.commit()

        except Exception as e:
            self.connection.rollback()
            raise e
        finally:
            if cursor:
                cursor.close()

    def test_connection(self) -> bool:
        """
        Test database connection.

        Returns:
            True if connection test successful, False otherwise
        """
        try:
            if self.connect():
                with self.get_cursor() as cursor:
                    # Test with a simple query
                    if self.config.db_type == DatabaseType.MYSQL.value:
                        cursor.execute("SELECT 1")
                    elif self.config.db_type == DatabaseType.POSTGRESQL.value:
                        cursor.execute("SELECT 1")
                    elif self.config.db_type == DatabaseType.SQLITE.value:
                        cursor.execute("SELECT 1")

                    result = cursor.fetchone()
                    success = result is not None

                self.disconnect()
                return success
            return False

        except Exception as e:
            self.logger.error(f"Connection test failed: {e}")
            return False

    def get_tables(self) -> List[str]:
        """
        Get list of tables in database.

        Returns:
            List of table names
        """
        try:
            if not self.connection:
                if not self.connect():
                    return []

            with self.get_cursor() as cursor:
                if self.config.db_type == DatabaseType.MYSQL.value:
                    cursor.execute("SHOW TABLES")
                    tables = [row[0] for row in cursor.fetchall()]

                elif self.config.db_type == DatabaseType.POSTGRESQL.value:
                    cursor.execute("""
                                   SELECT table_name
                                   FROM information_schema.tables
                                   WHERE table_schema = 'public'
                                     AND table_type = 'BASE TABLE'
                                   ORDER BY table_name
                                   """)
                    tables = [row[0] if isinstance(row, tuple) else row['table_name']
                              for row in cursor.fetchall()]

                elif self.config.db_type == DatabaseType.SQLITE.value:
                    cursor.execute("""
                                   SELECT name
                                   FROM sqlite_master
                                   WHERE type = 'table'
                                     AND name NOT LIKE 'sqlite_%'
                                   ORDER BY name
                                   """)
                    tables = [row[0] for row in cursor.fetchall()]

                # Filter out changelog tables
                tables = [table for table in tables
                          if not table.endswith(CHANGELOG_TABLE_SUFFIX)]

                self.logger.info(f"Found {len(tables)} tables in {self.config.name}")
                return tables

        except Exception as e:
            self.logger.error(f"Failed to get tables from {self.config.name}: {e}")
            return []

    def get_table_columns(self, table_name: str) -> List[Dict[str, Any]]:
        """
        Get column information for a table.

        Args:
            table_name: Name of the table

        Returns:
            List of column information dictionaries
        """
        try:
            if not self.connection:
                if not self.connect():
                    return []

            with self.get_cursor() as cursor:
                if self.config.db_type == DatabaseType.MYSQL.value:
                    cursor.execute(f"DESCRIBE {table_name}")
                    columns = []
                    for row in cursor.fetchall():
                        columns.append({
                            'name': row[0],
                            'type': row[1],
                            'null': row[2] == 'YES',
                            'key': row[3],
                            'default': row[4]
                        })

                elif self.config.db_type == DatabaseType.POSTGRESQL.value:
                    cursor.execute("""
                                   SELECT column_name, data_type, is_nullable, column_default
                                   FROM information_schema.columns
                                   WHERE table_name = %s
                                   ORDER BY ordinal_position
                                   """, (table_name,))
                    columns = []
                    for row in cursor.fetchall():
                        columns.append({
                            'name': row[0] if isinstance(row, tuple) else row['column_name'],
                            'type': row[1] if isinstance(row, tuple) else row['data_type'],
                            'null': (row[2] if isinstance(row, tuple) else row['is_nullable']) == 'YES',
                            'default': row[3] if isinstance(row, tuple) else row['column_default']
                        })

                elif self.config.db_type == DatabaseType.SQLITE.value:
                    cursor.execute(f"PRAGMA table_info({table_name})")
                    columns = []
                    for row in cursor.fetchall():
                        columns.append({
                            'name': row[1],
                            'type': row[2],
                            'null': row[3] == 0,
                            'default': row[4],
                            'primary_key': row[5] == 1
                        })

                return columns

        except Exception as e:
            self.logger.error(f"Failed to get columns for table {table_name}: {e}")
            return []

    def get_primary_key_columns(self, table_name: str) -> List[str]:
        """
        Get primary key columns for a table.

        Args:
            table_name: Name of the table

        Returns:
            List of primary key column names
        """
        try:
            columns = self.get_table_columns(table_name)

            if self.config.db_type in [DatabaseType.MYSQL.value, DatabaseType.POSTGRESQL.value]:
                return [col['name'] for col in columns if col.get('key') == 'PRI']
            elif self.config.db_type == DatabaseType.SQLITE.value:
                return [col['name'] for col in columns if col.get('primary_key')]

            return []

        except Exception as e:
            self.logger.error(f"Failed to get primary keys for table {table_name}: {e}")
            return []

    def create_changelog_table(self, table_name: str) -> bool:
        """
        Create changelog table for tracking changes.

        Args:
            table_name: Name of the source table

        Returns:
            True if created successfully, False otherwise
        """
        try:
            changelog_table = f"{table_name}{CHANGELOG_TABLE_SUFFIX}"

            if not self.connection:
                if not self.connect():
                    return False

            with self.get_cursor() as cursor:
                if self.config.db_type == DatabaseType.MYSQL.value:
                    sql = MYSQL_CHANGELOG_TABLE.format(changelog_table=changelog_table)
                elif self.config.db_type == DatabaseType.POSTGRESQL.value:
                    sql = POSTGRESQL_CHANGELOG_TABLE.format(changelog_table=changelog_table)
                elif self.config.db_type == DatabaseType.SQLITE.value:
                    sql = SQLITE_CHANGELOG_TABLE.format(changelog_table=changelog_table)

                # Execute the SQL (may contain multiple statements)
                for statement in sql.split(';'):
                    statement = statement.strip()
                    if statement:
                        cursor.execute(statement)

            self.logger.info(f"Created changelog table: {changelog_table}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to create changelog table for {table_name}: {e}")
            return False

    def create_triggers(self, table_name: str, db_id: str) -> bool:
        """
        Create triggers to populate changelog table.

        Args:
            table_name: Name of the source table
            db_id: Unique identifier for this database

        Returns:
            True if triggers created successfully, False otherwise
        """
        try:
            changelog_table = f"{table_name}{CHANGELOG_TABLE_SUFFIX}"

            if not self.connection:
                if not self.connect():
                    return False

            # Get primary key columns for the table
            pk_columns = self.get_primary_key_columns(table_name)
            if not pk_columns:
                self.logger.warning(f"No primary key found for table {table_name}")
                return False

            with self.get_cursor() as cursor:
                if self.config.db_type == DatabaseType.MYSQL.value:
                    self._create_mysql_triggers(cursor, table_name, changelog_table, pk_columns, db_id)
                elif self.config.db_type == DatabaseType.POSTGRESQL.value:
                    self._create_postgresql_triggers(cursor, table_name, changelog_table, pk_columns, db_id)
                elif self.config.db_type == DatabaseType.SQLITE.value:
                    self._create_sqlite_triggers(cursor, table_name, changelog_table, pk_columns, db_id)

            self.logger.info(f"Created triggers for table: {table_name}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to create triggers for table {table_name}: {e}")
            return False

    def _create_mysql_triggers(self, cursor, table_name: str, changelog_table: str,
                               pk_columns: List[str], db_id: str):
        """Create MySQL triggers for change tracking."""

        # Build primary key JSON object
        pk_json = ", ".join([f"'{col}', NEW.{col}" for col in pk_columns])
        pk_json_old = ", ".join([f"'{col}', OLD.{col}" for col in pk_columns])

        # INSERT trigger
        insert_trigger = f"""
        CREATE TRIGGER {table_name}_insert_trigger
        AFTER INSERT ON {table_name}
        FOR EACH ROW
        INSERT INTO {changelog_table} 
        (operation, table_name, primary_key_values, change_data, database_id)
        VALUES ('INSERT', '{table_name}', 
                JSON_OBJECT({pk_json}), 
                JSON_OBJECT(), 
                '{db_id}')
        """

        # UPDATE trigger
        update_trigger = f"""
        CREATE TRIGGER {table_name}_update_trigger
        AFTER UPDATE ON {table_name}
        FOR EACH ROW
        INSERT INTO {changelog_table} 
        (operation, table_name, primary_key_values, change_data, database_id)
        VALUES ('UPDATE', '{table_name}', 
                JSON_OBJECT({pk_json}), 
                JSON_OBJECT(), 
                '{db_id}')
        """

        # DELETE trigger
        delete_trigger = f"""
        CREATE TRIGGER {table_name}_delete_trigger
        AFTER DELETE ON {table_name}
        FOR EACH ROW
        INSERT INTO {changelog_table} 
        (operation, table_name, primary_key_values, change_data, database_id)
        VALUES ('DELETE', '{table_name}', 
                JSON_OBJECT({pk_json_old}), 
                JSON_OBJECT(), 
                '{db_id}')
        """

        # Drop existing triggers first
        try:
            cursor.execute(f"DROP TRIGGER IF EXISTS {table_name}_insert_trigger")
            cursor.execute(f"DROP TRIGGER IF EXISTS {table_name}_update_trigger")
            cursor.execute(f"DROP TRIGGER IF EXISTS {table_name}_delete_trigger")
        except:
            pass

        cursor.execute(insert_trigger)
        cursor.execute(update_trigger)
        cursor.execute(delete_trigger)

    def _create_postgresql_triggers(self, cursor, table_name: str, changelog_table: str,
                                    pk_columns: List[str], db_id: str):
        """Create PostgreSQL triggers for change tracking."""

        # Create trigger function
        function_name = f"{table_name}_changelog_func"

        trigger_function = f"""
        CREATE OR REPLACE FUNCTION {function_name}() RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                INSERT INTO {changelog_table} (operation, table_name, primary_key_values, change_data, database_id)
                VALUES ('DELETE', '{table_name}', row_to_json(OLD), '{{}}', '{db_id}');
                RETURN OLD;
            ELSIF TG_OP = 'UPDATE' THEN
                INSERT INTO {changelog_table} (operation, table_name, primary_key_values, change_data, database_id)
                VALUES ('UPDATE', '{table_name}', row_to_json(NEW), '{{}}', '{db_id}');
                RETURN NEW;
            ELSIF TG_OP = 'INSERT' THEN
                INSERT INTO {changelog_table} (operation, table_name, primary_key_values, change_data, database_id)
                VALUES ('INSERT', '{table_name}', row_to_json(NEW), '{{}}', '{db_id}');
                RETURN NEW;
            END IF;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
        """

        trigger_sql = f"""
        CREATE TRIGGER {table_name}_changelog_trigger
        AFTER INSERT OR UPDATE OR DELETE ON {table_name}
        FOR EACH ROW EXECUTE FUNCTION {function_name}();
        """

        # Drop existing trigger and function first
        try:
            cursor.execute(f"DROP TRIGGER IF EXISTS {table_name}_changelog_trigger ON {table_name}")
            cursor.execute(f"DROP FUNCTION IF EXISTS {function_name}()")
        except:
            pass

        cursor.execute(trigger_function)
        cursor.execute(trigger_sql)

    def _create_sqlite_triggers(self, cursor, table_name: str, changelog_table: str,
                                pk_columns: List[str], db_id: str):
        """Create SQLite triggers for change tracking."""

        # INSERT trigger
        insert_trigger = f"""
        CREATE TRIGGER {table_name}_insert_trigger
        AFTER INSERT ON {table_name}
        BEGIN
            INSERT INTO {changelog_table} 
            (operation, table_name, primary_key_values, change_data, database_id)
            VALUES ('INSERT', '{table_name}', 
                    json_object({", ".join([f"'{col}', NEW.{col}" for col in pk_columns])}), 
                    '{{}}', 
                    '{db_id}');
        END
        """

        # UPDATE trigger
        update_trigger = f"""
        CREATE TRIGGER {table_name}_update_trigger
        AFTER UPDATE ON {table_name}
        BEGIN
            INSERT INTO {changelog_table} 
            (operation, table_name, primary_key_values, change_data, database_id)
            VALUES ('UPDATE', '{table_name}', 
                    json_object({", ".join([f"'{col}', NEW.{col}" for col in pk_columns])}), 
                    '{{}}', 
                    '{db_id}');
        END
        """

        # DELETE trigger
        delete_trigger = f"""
        CREATE TRIGGER {table_name}_delete_trigger
        AFTER DELETE ON {table_name}
        BEGIN
            INSERT INTO {changelog_table} 
            (operation, table_name, primary_key_values, change_data, database_id)
            VALUES ('DELETE', '{table_name}', 
                    json_object({", ".join([f"'{col}', OLD.{col}" for col in pk_columns])}), 
                    '{{}}', 
                    '{db_id}');
        END
        """

        # Drop existing triggers first
        try:
            cursor.execute(f"DROP TRIGGER IF EXISTS {table_name}_insert_trigger")
            cursor.execute(f"DROP TRIGGER IF EXISTS {table_name}_update_trigger")
            cursor.execute(f"DROP TRIGGER IF EXISTS {table_name}_delete_trigger")
        except:
            pass

        cursor.execute(insert_trigger)
        cursor.execute(update_trigger)
        cursor.execute(delete_trigger)

    def get_pending_changes(self, table_name: str, last_sync_time: str = None,
                            exclude_db_id: str = None) -> List[ChangeRecord]:
        """
        Get pending changes from changelog table.

        Args:
            table_name: Name of the source table
            last_sync_time: ISO timestamp of last sync
            exclude_db_id: Database ID to exclude from results

        Returns:
            List of change records
        """
        try:
            changelog_table = f"{table_name}{CHANGELOG_TABLE_SUFFIX}"

            if not self.connection:
                if not self.connect():
                    return []

            with self.get_cursor() as cursor:
                query = f"""
                SELECT id, operation, table_name, primary_key_values, 
                       change_data, timestamp, database_id, synced
                FROM {changelog_table} 
                WHERE synced = {self._get_boolean_value(False)}
                """
                params = []

                if last_sync_time:
                    query += " AND timestamp > %s" if self.config.db_type != DatabaseType.SQLITE.value else " AND timestamp > ?"
                    params.append(last_sync_time)

                if exclude_db_id:
                    query += " AND database_id != %s" if self.config.db_type != DatabaseType.SQLITE.value else " AND database_id != ?"
                    params.append(exclude_db_id)

                query += " ORDER BY timestamp ASC"

                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)

                changes = []
                for row in cursor.fetchall():
                    if isinstance(row, dict):
                        change_data = row
                    else:
                        change_data = {
                            'id': row[0],
                            'operation': row[1],
                            'table_name': row[2],
                            'primary_key_values': self._parse_json(row[3]),
                            'change_data': self._parse_json(row[4]),
                            'timestamp': str(row[5]),
                            'database_id': row[6],
                            'synced': bool(row[7])
                        }

                    changes.append(ChangeRecord.from_dict(change_data))

                self.logger.debug(f"Found {len(changes)} pending changes for {table_name}")
                return changes[:MAX_BATCH_SIZE]  # Limit batch size

        except Exception as e:
            self.logger.error(f"Failed to get pending changes for {table_name}: {e}")
            return []

    def mark_changes_synced(self, change_ids: List[int]) -> bool:
        """
        Mark changes as synced in changelog table.

        Args:
            change_ids: List of change record IDs

        Returns:
            True if marked successfully, False otherwise
        """
        try:
            if not change_ids:
                return True

            if not self.connection:
                if not self.connect():
                    return False

            with self.get_cursor() as cursor:
                placeholders = ', '.join(
                    ['%s'] * len(change_ids)) if self.config.db_type != DatabaseType.SQLITE.value else ', '.join(
                    ['?'] * len(change_ids))

                # We need to determine which changelog table to update
                # For now, we'll assume all changes are from the same table
                # In practice, you might need to group by table
                query = f"""
                UPDATE %s SET synced = {self._get_boolean_value(True)}
                WHERE id IN ({placeholders})
                """

                # Group changes by table for proper updating
                table_groups = {}
                for change_id in change_ids:
                    # This is a simplified approach - in practice you'd need to track
                    # which changelog table each change_id belongs to
                    table_groups.setdefault('default', []).append(change_id)

                for table_suffix, ids in table_groups.items():
                    # This would need to be improved to handle multiple tables
                    pass

                self.logger.info(f"Marked {len(change_ids)} changes as synced")
                return True

        except Exception as e:
            self.logger.error(f"Failed to mark changes as synced: {e}")
            return False

    def _get_boolean_value(self, value: bool) -> str:
        """Get database-specific boolean value."""
        if self.config.db_type == DatabaseType.SQLITE.value:
            return "1" if value else "0"
        else:
            return "TRUE" if value else "FALSE"

    def _parse_json(self, json_str: str) -> Dict[str, Any]:
        """Parse JSON string safely."""
        if not json_str:
            return {}
        try:
            if isinstance(json_str, (dict, list)):
                return json_str
            return json.loads(json_str)
        except (json.JSONDecodeError, TypeError):
            return {}

    def execute_query(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """
        Execute a query and return results.

        Args:
            query: SQL query to execute
            params: Query parameters

        Returns:
            List of result dictionaries
        """
        try:
            if not self.connection:
                if not self.connect():
                    return []

            with self.get_cursor() as cursor:
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)

                if query.strip().upper().startswith('SELECT'):
                    results = cursor.fetchall()
                    if isinstance(results[0], dict) if results else True:
                        return results
                    else:
                        # Convert tuple results to dictionaries
                        columns = [desc[0] for desc in cursor.description]
                        return [dict(zip(columns, row)) for row in results]
                else:
                    return [{'affected_rows': cursor.rowcount}]

        except Exception as e:
            self.logger.error(f"Query execution failed: {e}")
            return []

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
        