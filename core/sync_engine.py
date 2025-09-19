"""
Synchronization engine for the Database Synchronization Application.

This module contains the core logic for synchronizing data between
local and cloud databases based on change records.
"""

import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from contextlib import contextmanager

from .models import DatabasePair, TableSyncConfig, SyncDirection, SyncResult, ChangeRecord
from .database_manager import DatabaseManager
from utils.constants import MAX_RETRY_ATTEMPTS, RETRY_DELAY


class SyncEngine:
    """Main synchronization logic and coordination."""

    def __init__(self, db_pair: DatabasePair):
        """
        Initialize the sync engine.

        Args:
            db_pair: Database pair configuration
        """
        self.db_pair = db_pair
        self.local_manager = DatabaseManager(db_pair.local_db)
        self.cloud_manager = DatabaseManager(db_pair.cloud_db)
        self.logger = logging.getLogger(self.__class__.__name__)

        self.sync_results = []
        self.is_running = False

    def setup_sync_infrastructure(self) -> bool:
        """
        Set up changelog tables and triggers for all sync-enabled tables.

        Returns:
            True if setup successful, False otherwise
        """
        self.logger.info(f"Setting up sync infrastructure for {self.db_pair.name}")

        try:
            # Connect to both databases
            if not self.local_manager.connect():
                self.logger.error("Failed to connect to local database")
                return False

            if not self.cloud_manager.connect():
                self.logger.error("Failed to connect to cloud database")
                return False

            success = True
            sync_tables = self.db_pair.get_sync_enabled_tables()

            for table_config in sync_tables:
                table_name = table_config.table_name
                self.logger.info(f"Setting up infrastructure for table: {table_name}")

                # Create changelog tables in both databases
                if not self.local_manager.create_changelog_table(table_name):
                    self.logger.error(f"Failed to create local changelog table for {table_name}")
                    success = False
                    continue

                if not self.cloud_manager.create_changelog_table(table_name):
                    self.logger.error(f"Failed to create cloud changelog table for {table_name}")
                    success = False
                    continue

                # Create triggers in both databases
                if not self.local_manager.create_triggers(table_name, self.db_pair.local_db.id):
                    self.logger.error(f"Failed to create local triggers for {table_name}")
                    success = False
                    continue

                if not self.cloud_manager.create_triggers(table_name, self.db_pair.cloud_db.id):
                    self.logger.error(f"Failed to create cloud triggers for {table_name}")
                    success = False
                    continue

                self.logger.info(f"Successfully set up infrastructure for {table_name}")

            if success:
                self.logger.info("Sync infrastructure setup completed successfully")
            else:
                self.logger.warning("Sync infrastructure setup completed with errors")

            return success

        except Exception as e:
            self.logger.error(f"Failed to setup sync infrastructure: {e}")
            return False
        finally:
            self.local_manager.disconnect()
            self.cloud_manager.disconnect()

    def sync_all_tables(self) -> List[SyncResult]:
        """
        Synchronize all configured tables.

        Returns:
            List of sync results for each table
        """
        self.logger.info(f"Starting sync for database pair: {self.db_pair.name}")
        self.is_running = True
        self.sync_results = []

        try:
            # Connect to both databases
            if not self.local_manager.connect():
                error_result = SyncResult(success=False, table_name="connection")
                error_result.add_error("Failed to connect to local database")
                return [error_result]

            if not self.cloud_manager.connect():
                error_result = SyncResult(success=False, table_name="connection")
                error_result.add_error("Failed to connect to cloud database")
                return [error_result]

            sync_tables = self.db_pair.get_sync_enabled_tables()

            if not sync_tables:
                self.logger.info("No tables configured for synchronization")
                return []

            for table_config in sync_tables:
                if not self.is_running:
                    self.logger.info("Sync stopped by user")
                    break

                result = self.sync_table(table_config)
                self.sync_results.append(result)

                # Update last sync time if successful
                if result.success:
                    table_config.last_sync = datetime.now().isoformat()

            # Update database pair last sync time
            self.db_pair.last_sync = datetime.now().isoformat()

            successful_syncs = sum(1 for result in self.sync_results if result.success)
            total_records = sum(result.records_synced for result in self.sync_results)

            self.logger.info(f"Sync completed: {successful_syncs}/{len(sync_tables)} tables, "
                             f"{total_records} records synchronized")

            return self.sync_results

        except Exception as e:
            self.logger.error(f"Error during sync: {e}")
            error_result = SyncResult(success=False, table_name="general")
            error_result.add_error(str(e))
            return [error_result]
        finally:
            self.is_running = False
            self.local_manager.disconnect()
            self.cloud_manager.disconnect()

    def sync_table(self, table_config: TableSyncConfig) -> SyncResult:
        """
        Synchronize a single table based on its configuration.

        Args:
            table_config: Table synchronization configuration

        Returns:
            Sync result for the table
        """
        table_name = table_config.table_name
        direction = table_config.sync_direction

        self.logger.info(f"Syncing table {table_name} with direction {direction.value}")

        result = SyncResult(
            success=True,
            table_name=table_name,
            start_time=datetime.now().isoformat()
        )

        try:
            if direction == SyncDirection.NO_SYNC:
                self.logger.debug(f"Table {table_name} is set to NO_SYNC, skipping")
                return result

            total_synced = 0

            if direction == SyncDirection.LOCAL_TO_CLOUD:
                synced = self._sync_one_way(
                    table_name, self.local_manager, self.cloud_manager,
                    table_config.last_sync, self.db_pair.cloud_db.id
                )
                total_synced += synced

            elif direction == SyncDirection.CLOUD_TO_LOCAL:
                synced = self._sync_one_way(
                    table_name, self.cloud_manager, self.local_manager,
                    table_config.last_sync, self.db_pair.local_db.id
                )
                total_synced += synced

            elif direction == SyncDirection.BIDIRECTIONAL:
                # Sync local to cloud
                synced1 = self._sync_one_way(
                    table_name, self.local_manager, self.cloud_manager,
                    table_config.last_sync, self.db_pair.cloud_db.id
                )

                # Sync cloud to local
                synced2 = self._sync_one_way(
                    table_name, self.cloud_manager, self.local_manager,
                    table_config.last_sync, self.db_pair.local_db.id
                )

                total_synced = synced1 + synced2

            result.records_synced = total_synced
            result.end_time = datetime.now().isoformat()

            if total_synced > 0:
                self.logger.info(f"Successfully synced {total_synced} records for table {table_name}")
            else:
                self.logger.debug(f"No changes to sync for table {table_name}")

            return result

        except Exception as e:
            self.logger.error(f"Failed to sync table {table_name}: {e}")
            result.success = False
            result.add_error(str(e))
            result.end_time = datetime.now().isoformat()
            return result

    def _sync_one_way(self, table_name: str, source_manager: DatabaseManager,
                      target_manager: DatabaseManager, last_sync: str = None,
                      exclude_db_id: str = None) -> int:
        """
        Perform one-way synchronization from source to target.
        Now includes intelligent data comparison based on timestamps and record counts.
        """
        try:
            # First, try changelog-based sync for real-time changes
            pending_changes = source_manager.get_pending_changes(
                table_name, last_sync, exclude_db_id
            )

            changelog_synced = 0
            if pending_changes:
                self.logger.info(f"Processing {len(pending_changes)} changelog entries for {table_name}")

                applied_ids = []
                for change in pending_changes:
                    if not self.is_running:
                        break

                    if self._apply_change_with_retry(change, target_manager):
                        applied_ids.append(change.id)
                    else:
                        self.logger.warning(f"Failed to apply change {change.id} for table {table_name}")

                # Mark successfully applied changes as synced
                if applied_ids:
                    source_manager.mark_changes_synced(table_name, applied_ids)
                    changelog_synced = len(applied_ids)

            # Then, perform full table comparison sync
            self.logger.info(f"Performing full table comparison sync for {table_name}")
            comparison_synced = self._compare_and_sync_table_data(
                table_name, source_manager, target_manager
            )

            total_synced = changelog_synced + comparison_synced

            if total_synced > 0:
                self.logger.info(f"Synced {total_synced} records for {table_name} "
                                 f"({changelog_synced} from changelog, {comparison_synced} from comparison)")
            else:
                self.logger.debug(f"No changes to sync for table {table_name}")

            return total_synced

        except Exception as e:
            self.logger.error(f"Failed one-way sync for {table_name}: {e}")
            return 0

    def _apply_change_with_retry(self, change: ChangeRecord, target_manager: DatabaseManager) -> bool:
        """
        Apply a change record with retry logic.

        Args:
            change: Change record to apply
            target_manager: Target database manager

        Returns:
            True if change applied successfully, False otherwise
        """
        for attempt in range(MAX_RETRY_ATTEMPTS):
            try:
                if self._apply_change(change, target_manager):
                    return True

                if attempt < MAX_RETRY_ATTEMPTS - 1:
                    self.logger.warning(f"Retrying change application (attempt {attempt + 1})")
                    import time
                    time.sleep(RETRY_DELAY)

            except Exception as e:
                self.logger.error(f"Error applying change (attempt {attempt + 1}): {e}")
                if attempt < MAX_RETRY_ATTEMPTS - 1:
                    import time
                    time.sleep(RETRY_DELAY)

        return False

    def _apply_change(self, change: ChangeRecord, target_manager: DatabaseManager) -> bool:
        """
        Apply a single change record to the target database.

        Args:
            change: Change record to apply
            target_manager: Target database manager

        Returns:
            True if applied successfully, False otherwise
        """
        try:
            operation = change.operation
            table_name = change.table_name
            pk_values = change.primary_key_values

            if operation == 'INSERT':
                return self._apply_insert(table_name, change, target_manager)
            elif operation == 'UPDATE':
                return self._apply_update(table_name, change, target_manager)
            elif operation == 'DELETE':
                return self._apply_delete(table_name, pk_values, target_manager)
            else:
                self.logger.error(f"Unknown operation type: {operation}")
                return False

        except Exception as e:
            self.logger.error(f"Failed to apply change: {e}")
            return False

    def _apply_insert(self, table_name: str, change: ChangeRecord, target_manager: DatabaseManager) -> bool:
        """Apply an INSERT operation."""
        try:
            # Get the complete record data from source database using primary key
            source_manager = self.local_manager if target_manager == self.cloud_manager else self.cloud_manager

            # Build query to get full record
            pk_conditions = []
            pk_params = []

            for col, val in change.primary_key_values.items():
                if source_manager.config.db_type == 'sqlite':
                    pk_conditions.append(f"{col} = ?")
                else:
                    pk_conditions.append(f"{col} = %s")
                pk_params.append(val)

            # Get the complete record from source
            select_query = f"SELECT * FROM {table_name} WHERE {' AND '.join(pk_conditions)}"
            records = source_manager.execute_query(select_query, tuple(pk_params))

            if not records:
                self.logger.warning(f"Source record not found for insert: {change.primary_key_values}")
                return False

            record = records[0]

            # Check if record already exists in target
            check_query = f"SELECT COUNT(*) as count FROM {table_name} WHERE {' AND '.join(pk_conditions)}"
            results = target_manager.execute_query(check_query, tuple(pk_params))

            if results and results[0].get('count', 0) > 0:
                self.logger.debug(f"Record already exists in {table_name}, skipping insert")
                return True

            # Build INSERT statement
            columns = list(record.keys())
            values = [record[col] for col in columns]

            if target_manager.config.db_type == 'sqlite':
                placeholders = ', '.join(['?' for _ in columns])
            else:
                placeholders = ', '.join(['%s' for _ in columns])

            insert_query = f"""
            INSERT INTO {table_name} ({', '.join(columns)}) 
            VALUES ({placeholders})
            """

            result = target_manager.execute_query(insert_query, tuple(values))

            if result and result[0].get('affected_rows', 0) > 0:
                self.logger.info(f"Inserted record into {table_name}: {change.primary_key_values}")
                return True
            else:
                self.logger.error(f"Failed to insert record into {table_name}")
                return False

        except Exception as e:
            self.logger.error(f"Failed to apply INSERT: {e}")
            return False

    def _apply_update(self, table_name: str, change: ChangeRecord, target_manager: DatabaseManager) -> bool:
        """Apply an UPDATE operation."""
        try:
            # Get the complete updated record from source
            source_manager = self.local_manager if target_manager == self.cloud_manager else self.cloud_manager

            pk_conditions = []
            pk_params = []

            for col, val in change.primary_key_values.items():
                if source_manager.config.db_type == 'sqlite':
                    pk_conditions.append(f"{col} = ?")
                else:
                    pk_conditions.append(f"{col} = %s")
                pk_params.append(val)

            # Get current record from source
            select_query = f"SELECT * FROM {table_name} WHERE {' AND '.join(pk_conditions)}"
            records = source_manager.execute_query(select_query, tuple(pk_params))

            if not records:
                self.logger.warning(f"Source record not found for update: {change.primary_key_values}")
                return False

            record = records[0]

            # Check if target record exists
            check_query = f"SELECT COUNT(*) as count FROM {table_name} WHERE {' AND '.join(pk_conditions)}"
            results = target_manager.execute_query(check_query, tuple(pk_params))

            if not results or results[0].get('count', 0) == 0:
                # Record doesn't exist, treat as insert
                self.logger.info(f"Target record not found, inserting instead of updating: {table_name}")
                return self._apply_insert(table_name, change, target_manager)

            # Build UPDATE statement
            pk_columns = set(change.primary_key_values.keys())
            update_columns = [col for col in record.keys() if col not in pk_columns]

            if not update_columns:
                self.logger.debug(f"No non-primary key columns to update for {table_name}")
                return True

            if target_manager.config.db_type == 'sqlite':
                set_clauses = [f"{col} = ?" for col in update_columns]
            else:
                set_clauses = [f"{col} = %s" for col in update_columns]

            update_values = [record[col] for col in update_columns]
            update_values.extend(pk_params)  # Add PK values for WHERE clause

            update_query = f"""
            UPDATE {table_name} 
            SET {', '.join(set_clauses)}
            WHERE {' AND '.join(pk_conditions)}
            """

            result = target_manager.execute_query(update_query, tuple(update_values))

            if result and result[0].get('affected_rows', 0) > 0:
                self.logger.info(f"Updated record in {table_name}: {change.primary_key_values}")
                return True
            else:
                self.logger.warning(f"No rows updated in {table_name}: {change.primary_key_values}")
                return True  # Consider successful if no rows affected (idempotent)

        except Exception as e:
            self.logger.error(f"Failed to apply UPDATE: {e}")
            return False

    def _apply_delete(self, table_name: str, pk_values: Dict[str, Any], target_manager: DatabaseManager) -> bool:
        """Apply a DELETE operation."""
        try:
            # Build WHERE clause for primary key
            pk_conditions = []
            pk_params = []

            for col, val in pk_values.items():
                if target_manager.config.db_type == 'sqlite':
                    pk_conditions.append(f"{col} = ?")
                else:
                    pk_conditions.append(f"{col} = %s")
                pk_params.append(val)

            # Execute delete
            delete_query = f"DELETE FROM {table_name} WHERE {' AND '.join(pk_conditions)}"
            results = target_manager.execute_query(delete_query, tuple(pk_params))

            if results and results[0].get('affected_rows', 0) > 0:
                self.logger.info(f"Deleted record from {table_name} with PK: {pk_values}")
                return True
            else:
                self.logger.debug(f"No record found to delete in {table_name} with PK: {pk_values}")
                return True  # Consider this successful since the end result is the same

        except Exception as e:
            self.logger.error(f"Failed to apply DELETE: {e}")
            return False

    def _compare_and_sync_table_data(self, table_name: str, source_manager: DatabaseManager,
                                     target_manager: DatabaseManager) -> int:
        """
        Compare table data between source and target and sync based on timestamps and record count.

        Args:
            table_name: Name of the table to sync
            source_manager: Source database manager
            target_manager: Target database manager

        Returns:
            Number of records synchronized
        """
        try:
            # Get table structure to identify timestamp columns
            source_structure = source_manager.get_table_structure(table_name)
            target_structure = target_manager.get_table_structure(table_name)

            if not source_structure or not target_structure:
                self.logger.error(f"Could not get table structure for {table_name}")
                return 0

            # Get primary key columns
            pk_columns = source_structure.get('primary_keys', [])
            if not pk_columns:
                self.logger.error(f"No primary key found for table {table_name}")
                return 0

            # Find timestamp/updated_at columns
            timestamp_columns = self._find_timestamp_columns(source_structure)

            # Get record counts
            source_count = self._get_table_count(source_manager, table_name)
            target_count = self._get_table_count(target_manager, table_name)

            self.logger.info(f"Table {table_name}: Source={source_count}, Target={target_count} records")

            # If source has no data, nothing to sync
            if source_count == 0:
                return 0

            # Get all records from source
            source_records = self._get_all_records(source_manager, table_name, timestamp_columns)

            if not source_records:
                return 0

            # Get existing records from target for comparison
            target_records_map = self._get_records_map(target_manager, table_name, pk_columns, timestamp_columns)

            synced_count = 0

            for record in source_records:
                # Build primary key for this record
                pk_value = tuple(record.get(col) for col in pk_columns)

                target_record = target_records_map.get(pk_value)

                should_sync = False

                if target_record is None:
                    # Record doesn't exist in target - insert it
                    should_sync = True
                    self.logger.debug(f"New record for PK {pk_value}")
                else:
                    # Record exists - compare timestamps
                    should_sync = self._should_update_based_on_timestamp(
                        record, target_record, timestamp_columns
                    )

                    if should_sync:
                        self.logger.debug(f"Source record newer for PK {pk_value}")

                if should_sync:
                    if self._sync_single_record(record, table_name, target_manager, pk_columns,
                                                target_record is not None):
                        synced_count += 1

            return synced_count

        except Exception as e:
            self.logger.error(f"Failed to compare and sync table data for {table_name}: {e}")
            return 0

    def _find_timestamp_columns(self, table_structure: dict) -> list:
        """Find columns that likely contain timestamps."""
        columns = table_structure.get('columns', {})
        timestamp_columns = []

        # Common timestamp column names and types
        timestamp_names = ['updated_at', 'modified_at', 'timestamp', 'last_modified', 'created_at']
        timestamp_types = ['timestamp', 'datetime', 'date']

        for col_name, col_info in columns.items():
            col_type = col_info.get('type', '').lower()

            # Check by name or type
            if (col_name.lower() in timestamp_names or
                    any(ts_type in col_type for ts_type in timestamp_types)):
                timestamp_columns.append(col_name)

        return timestamp_columns

    def _get_table_count(self, manager: DatabaseManager, table_name: str) -> int:
        """Get total record count for a table."""
        try:
            results = manager.execute_query(f"SELECT COUNT(*) as count FROM {table_name}")
            return results[0]['count'] if results else 0
        except Exception as e:
            self.logger.error(f"Failed to get count for {table_name}: {e}")
            return 0

    def _get_all_records(self, manager: DatabaseManager, table_name: str, timestamp_columns: list) -> list:
        """Get all records from a table, ordered by timestamp if available."""
        try:
            query = f"SELECT * FROM {table_name}"

            # Order by timestamp columns if available
            if timestamp_columns:
                order_cols = ', '.join([f"{col} DESC" for col in timestamp_columns[:1]])  # Use first timestamp column
                query += f" ORDER BY {order_cols}"

            return manager.execute_query(query)
        except Exception as e:
            self.logger.error(f"Failed to get records from {table_name}: {e}")
            return []

    def _get_records_map(self, manager: DatabaseManager, table_name: str, pk_columns: list,
                         timestamp_columns: list) -> dict:
        """Get existing records as a map keyed by primary key values."""
        try:
            records = manager.execute_query(f"SELECT * FROM {table_name}")
            records_map = {}

            for record in records:
                pk_value = tuple(record.get(col) for col in pk_columns)
                records_map[pk_value] = record

            return records_map
        except Exception as e:
            self.logger.error(f"Failed to get records map for {table_name}: {e}")
            return {}

    def _should_update_based_on_timestamp(self, source_record: dict, target_record: dict,
                                          timestamp_columns: list) -> bool:
        """Determine if source record should overwrite target based on timestamps."""
        if not timestamp_columns:
            # No timestamp columns - always update (source wins)
            return True

        from datetime import datetime
        import dateutil.parser

        try:
            # Compare first available timestamp column
            for col in timestamp_columns:
                source_ts = source_record.get(col)
                target_ts = target_record.get(col)

                if source_ts is None or target_ts is None:
                    continue

                # Parse timestamps
                if isinstance(source_ts, str):
                    source_dt = dateutil.parser.parse(source_ts)
                else:
                    source_dt = source_ts

                if isinstance(target_ts, str):
                    target_dt = dateutil.parser.parse(target_ts)
                else:
                    target_dt = target_ts

                # Source wins if it's newer
                return source_dt > target_dt

            # If no valid timestamps found, source wins
            return True

        except Exception as e:
            self.logger.error(f"Error comparing timestamps: {e}")
            return True  # Default to source wins

    def _sync_single_record(self, record: dict, table_name: str, target_manager: DatabaseManager,
                            pk_columns: list, is_update: bool) -> bool:
        """Sync a single record to target database."""
        try:
            if is_update:
                # Update existing record
                set_clauses = []
                update_values = []
                where_clauses = []
                where_values = []

                # Build SET clause for non-PK columns
                for col, value in record.items():
                    if col not in pk_columns:
                        if target_manager.config.db_type == 'sqlite':
                            set_clauses.append(f"{col} = ?")
                        else:
                            set_clauses.append(f"{col} = %s")
                        update_values.append(value)

                # Build WHERE clause for PK columns
                for col in pk_columns:
                    if target_manager.config.db_type == 'sqlite':
                        where_clauses.append(f"{col} = ?")
                    else:
                        where_clauses.append(f"{col} = %s")
                    where_values.append(record[col])

                if not set_clauses:
                    return True  # Nothing to update

                query = f"UPDATE {table_name} SET {', '.join(set_clauses)} WHERE {' AND '.join(where_clauses)}"
                params = update_values + where_values

            else:
                # Insert new record
                columns = list(record.keys())
                values = [record[col] for col in columns]

                if target_manager.config.db_type == 'sqlite':
                    placeholders = ', '.join(['?' for _ in columns])
                else:
                    placeholders = ', '.join(['%s' for _ in columns])

                query = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})"
                params = values

            # Execute the query
            result = target_manager.execute_query(query, tuple(params))
            return result and result[0].get('affected_rows', 0) > 0

        except Exception as e:
            self.logger.error(f"Failed to sync record: {e}")
            return False

    def _resolve_conflict(self, table_name: str, change: ChangeRecord,
                          target_manager: DatabaseManager, conflict_resolution: str) -> bool:
        """
        Resolve conflicts during bidirectional sync.

        Args:
            table_name: Name of the table
            change: Change record causing conflict
            target_manager: Target database manager
            conflict_resolution: Resolution strategy (newer_wins, local_wins, cloud_wins)

        Returns:
            True if conflict resolved and change should be applied, False otherwise
        """
        try:
            # Get target record timestamp if it exists
            pk_conditions = []
            pk_params = []

            for col, val in change.primary_key_values.items():
                if target_manager.config.db_type == 'sqlite':
                    pk_conditions.append(f"{col} = ?")
                else:
                    pk_conditions.append(f"{col} = %s")
                pk_params.append(val)

            # Check if there's a conflicting change in target's changelog
            changelog_table = f"{table_name}_changelog"
            conflict_query = f"""
            SELECT MAX(timestamp) as latest_timestamp 
            FROM {changelog_table}
            WHERE {' AND '.join([f"JSON_EXTRACT(primary_key_values, '$.{col}') = {'?' if target_manager.config.db_type == 'sqlite' else '%s'}" for col in change.primary_key_values.keys()])}
            AND database_id = %s
            """

            params = list(change.primary_key_values.values()) + [target_manager.config.id]
            results = target_manager.execute_query(conflict_query, tuple(params))

            if results and results[0].get('latest_timestamp'):
                target_timestamp = results[0]['latest_timestamp']
                change_timestamp = change.timestamp

                if conflict_resolution == 'newer_wins':
                    return change_timestamp > target_timestamp
                elif conflict_resolution == 'local_wins':
                    return target_manager.config.is_local
                elif conflict_resolution == 'cloud_wins':
                    return not target_manager.config.is_local

            return True  # No conflict found

        except Exception as e:
            self.logger.error(f"Error resolving conflict: {e}")
            return True  # Default to applying the change

    def stop_sync(self):
        """Stop the synchronization process."""
        self.logger.info("Stopping synchronization...")
        self.is_running = False

    def get_sync_status(self) -> Dict[str, Any]:
        """
        Get current synchronization status.

        Returns:
            Dictionary containing sync status information
        """
        return {
            'is_running': self.is_running,
            'database_pair': self.db_pair.name,
            'last_sync': self.db_pair.last_sync,
            'total_tables': len(self.db_pair.tables),
            'sync_enabled_tables': len(self.db_pair.get_sync_enabled_tables()),
            'last_results': [result.to_dict() for result in self.sync_results[-10:]]  # Last 10 results
        }

    def validate_sync_configuration(self) -> List[str]:
        """
        Validate the sync configuration and return any issues found.

        Returns:
            List of validation error messages
        """
        errors = []

        try:
            # Test database connections
            if not self.local_manager.test_connection():
                errors.append(f"Cannot connect to local database: {self.db_pair.local_db.name}")

            if not self.cloud_manager.test_connection():
                errors.append(f"Cannot connect to cloud database: {self.db_pair.cloud_db.name}")

            # Check if sync-enabled tables exist in both databases
            if not errors:  # Only check tables if connections are working
                try:
                    local_tables = set(self.local_manager.get_tables())
                    cloud_tables = set(self.cloud_manager.get_tables())

                    for table_config in self.db_pair.get_sync_enabled_tables():
                        table_name = table_config.table_name

                        if table_name not in local_tables:
                            errors.append(f"Table '{table_name}' not found in local database")

                        if table_name not in cloud_tables:
                            errors.append(f"Table '{table_name}' not found in cloud database")

                        # Check for primary keys
                        if table_name in local_tables:
                            local_pk = self.local_manager.get_primary_key_columns(table_name)
                            if not local_pk:
                                errors.append(f"No primary key found for table '{table_name}' in local database")

                        if table_name in cloud_tables:
                            cloud_pk = self.cloud_manager.get_primary_key_columns(table_name)
                            if not cloud_pk:
                                errors.append(f"No primary key found for table '{table_name}' in cloud database")

                except Exception as e:
                    errors.append(f"Error validating table configuration: {e}")

        except Exception as e:
            errors.append(f"Error validating sync configuration: {e}")

        return errors