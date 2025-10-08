"""
Background sync worker for the Database Synchronization Application.

This module handles threaded synchronization operations to keep the UI responsive
while sync operations are running in the background.
"""

import logging
import time
from typing import List, Dict, Any
from datetime import datetime

from PySide6.QtCore import QObject, Signal, QMutex, QWaitCondition

from .models import DatabasePair, JobStatus, SyncResult
from .sync_engine import SyncEngine


class SyncWorker(QObject):
    """Background worker for database synchronization operations."""

    # Signals for communication with UI
    status_changed = Signal(str)  # JobStatus value
    log_message = Signal(str, str)  # level, message
    progress_updated = Signal(int)  # progress percentage (0-100)
    sync_completed = Signal(list)  # List of SyncResult objects
    error_occurred = Signal(str)  # Error message

    def __init__(self):
        """Initialize the sync worker."""
        super().__init__()
        self.logger = logging.getLogger(self.__class__.__name__)

        # Worker state
        self._is_running = False
        self._is_scheduled = False
        self._stop_requested = False
        self._current_status = JobStatus.STOPPED

        # Thread synchronization
        self._mutex = QMutex()
        self._condition = QWaitCondition()

        # Sync configuration
        self._db_pairs: List[DatabasePair] = []
        self._sync_engines: Dict[str, SyncEngine] = {}

        # Statistics
        self._sync_stats = {
            'total_syncs': 0,
            'successful_syncs': 0,
            'failed_syncs': 0,
            'last_sync_time': None,
            'total_records_synced': 0
        }

    @property
    def is_running(self) -> bool:
        """Check if worker is currently running."""
        self._mutex.lock()
        try:
            return self._is_running
        finally:
            self._mutex.unlock()

    @property
    def is_scheduled(self) -> bool:
        """Check if scheduled sync is active."""
        self._mutex.lock()
        try:
            return self._is_scheduled
        finally:
            self._mutex.unlock()

    @property
    def current_status(self) -> JobStatus:
        """Get current job status."""
        self._mutex.lock()
        try:
            return self._current_status
        finally:
            self._mutex.unlock()

    def set_database_pairs(self, db_pairs: List[DatabasePair]):
        """
        Set the database pairs to sync.

        Args:
            db_pairs: List of database pair configurations
        """
        self._mutex.lock()
        try:
            self._db_pairs = db_pairs
            self._sync_engines.clear()

            # Create sync engines for each pair
            for pair in db_pairs:
                if pair.is_enabled:
                    self._sync_engines[pair.id] = SyncEngine(pair)

            self.log_message.emit("INFO", f"Configured {len(self._sync_engines)} database pairs for sync")

        finally:
            self._mutex.unlock()

    def start_scheduled_sync(self):
        """Start scheduled synchronization."""
        self._mutex.lock()
        try:
            if self._is_running:
                self.log_message.emit("WARNING", "Sync already running")
                return

            if not self._sync_engines:
                self.error_occurred.emit("No database pairs configured")
                return

            self._is_scheduled = True
            self._stop_requested = False
            self._update_status(JobStatus.RUNNING)

            self.log_message.emit("INFO", "Scheduled synchronization started")

        finally:
            self._mutex.unlock()

    def stop_scheduled_sync(self):
        """Stop scheduled synchronization."""
        self._mutex.lock()
        try:
            self._is_scheduled = False
            self._stop_requested = True

            # Stop all running sync engines
            for engine in self._sync_engines.values():
                engine.stop_sync()

            self._update_status(JobStatus.STOPPED)
            self.log_message.emit("INFO", "Scheduled synchronization stopped")

        finally:
            self._mutex.unlock()

    def run_manual_sync(self):
        """Run a one-time manual synchronization."""
        self._mutex.lock()
        try:
            if self._is_running:
                self.log_message.emit("WARNING", "Sync already in progress")
                return

            if not self._sync_engines:
                self.error_occurred.emit("No database pairs configured")
                return

            self._is_running = True
            self._stop_requested = False
            self._update_status(JobStatus.RUNNING)

        finally:
            self._mutex.unlock()

        # Run sync in background
        try:
            self._perform_sync_operation("Manual sync")
        finally:
            self._mutex.lock()
            try:
                self._is_running = False
                if not self._is_scheduled:
                    self._update_status(JobStatus.STOPPED)
            finally:
                self._mutex.unlock()

    def run_scheduled_sync_cycle(self):
        """Run a scheduled sync cycle."""
        if not self.is_scheduled:
            return

        self._mutex.lock()
        try:
            if self._is_running:
                self.log_message.emit("DEBUG", "Skipping scheduled sync - already running")
                return

            self._is_running = True

        finally:
            self._mutex.unlock()

        # Run sync in background
        try:
            self._perform_sync_operation("Scheduled sync")
        finally:
            self._mutex.lock()
            try:
                self._is_running = False
            finally:
                self._mutex.unlock()

    def _perform_sync_operation(self, operation_name: str):
        """
        Perform the actual synchronization operation.

        Args:
            operation_name: Name of the operation for logging
        """
        self.log_message.emit("INFO", f"{operation_name} started")
        start_time = datetime.now()

        all_results = []
        total_engines = len(self._sync_engines)
        completed_engines = 0

        try:
            for pair_id, engine in self._sync_engines.items():
                if self._stop_requested:
                    self.log_message.emit("INFO", f"{operation_name} stopped by user")
                    break

                pair_name = engine.db_pair.name
                self.log_message.emit("INFO", f"Syncing database pair: {pair_name}")

                # Validate configuration before sync
                validation_errors = engine.validate_sync_configuration()
                if validation_errors:
                    self.log_message.emit("ERROR", f"Validation failed for {pair_name}: {'; '.join(validation_errors)}")

                    # Create error result
                    error_result = SyncResult(success=False, table_name="validation")
                    for error in validation_errors:
                        error_result.add_error(error)
                    all_results.append(error_result)

                    completed_engines += 1
                    self._update_progress(completed_engines, total_engines)
                    continue

                # Perform sync
                try:
                    sync_results = engine.sync_all_tables()
                    all_results.extend(sync_results)

                    # Log results
                    successful_tables = sum(1 for result in sync_results if result.success)
                    total_records = sum(result.records_synced for result in sync_results)

                    self.log_message.emit("INFO",
                        f"Completed {pair_name}: {successful_tables}/{len(sync_results)} tables, "
                        f"{total_records} records synced")

                    # Update statistics
                    self._update_sync_stats(sync_results)

                except Exception as e:
                    self.log_message.emit("ERROR", f"Error syncing {pair_name}: {e}")
                    error_result = SyncResult(success=False, table_name="sync_error")
                    error_result.add_error(str(e))
                    all_results.append(error_result)

                completed_engines += 1
                self._update_progress(completed_engines, total_engines)

                # Small delay between pairs to prevent overwhelming the databases
                if not self._stop_requested and completed_engines < total_engines:
                    time.sleep(0.5)

            # Complete the operation
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            successful_results = [r for r in all_results if r.success]
            failed_results = [r for r in all_results if not r.success]
            total_records = sum(r.records_synced for r in successful_results)

            self.log_message.emit("INFO",
                f"{operation_name} completed in {duration:.2f}s: "
                f"{len(successful_results)} successful, {len(failed_results)} failed, "
                f"{total_records} records synced")

            # Update final statistics
            self._sync_stats['total_syncs'] += 1
            if failed_results:
                self._sync_stats['failed_syncs'] += 1
            else:
                self._sync_stats['successful_syncs'] += 1

            self._sync_stats['last_sync_time'] = end_time.isoformat()

            # Emit completion signal
            self.sync_completed.emit([result.to_dict() for result in all_results])

            if not self._is_scheduled:
                self._update_status(JobStatus.COMPLETED)

        except Exception as e:
            self.logger.error(f"Unexpected error during {operation_name}: {e}")
            self.error_occurred.emit(f"Sync operation failed: {e}")
            self._update_status(JobStatus.ERROR)

        finally:
            self._update_progress(100, 100)  # Ensure progress shows complete

    def _update_status(self, status: JobStatus):
        """Update the current status and emit signal."""
        self._current_status = status
        self.status_changed.emit(status.value)
        self.logger.debug(f"Status changed to: {status.value}")

    def _update_progress(self, completed: int, total: int):
        """Update and emit progress percentage."""
        if total > 0:
            percentage = min(100, int((completed / total) * 100))
            self.progress_updated.emit(percentage)

    def _update_sync_stats(self, sync_results: List[SyncResult]):
        """Update synchronization statistics."""
        for result in sync_results:
            self._sync_stats['total_records_synced'] += result.records_synced

    def get_sync_statistics(self) -> Dict[str, Any]:
        """
        Get synchronization statistics.

        Returns:
            Dictionary containing sync statistics
        """
        self._mutex.lock()
        try:
            stats = self._sync_stats.copy()
            stats['is_running'] = self._is_running
            stats['is_scheduled'] = self._is_scheduled
            stats['current_status'] = self._current_status.value
            stats['configured_pairs'] = len(self._db_pairs)
            stats['active_engines'] = len(self._sync_engines)
            return stats
        finally:
            self._mutex.unlock()

    def setup_sync_infrastructure(self) -> bool:
        """
        Set up sync infrastructure for all configured database pairs.

        Returns:
            True if setup successful for all pairs, False otherwise
        """
        self._mutex.lock()
        try:
            if self._is_running:
                self.log_message.emit("WARNING", "Cannot setup infrastructure while sync is running")
                return False

            if not self._sync_engines:
                self.error_occurred.emit("No database pairs configured")
                return False

            self._is_running = True
            self._update_status(JobStatus.RUNNING)

        finally:
            self._mutex.unlock()

        self.log_message.emit("INFO", "Setting up sync infrastructure...")

        success = True
        total_pairs = len(self._sync_engines)
        completed_pairs = 0

        try:
            for pair_id, engine in self._sync_engines.items():
                pair_name = engine.db_pair.name
                self.log_message.emit("INFO", f"Setting up infrastructure for: {pair_name}")

                if not engine.setup_sync_infrastructure():
                    self.log_message.emit("ERROR", f"Failed to setup infrastructure for: {pair_name}")
                    success = False
                else:
                    self.log_message.emit("INFO", f"Successfully set up infrastructure for: {pair_name}")

                completed_pairs += 1
                self._update_progress(completed_pairs, total_pairs)

                # Small delay between setups
                if completed_pairs < total_pairs:
                    time.sleep(0.5)

            if success:
                self.log_message.emit("INFO", "Sync infrastructure setup completed successfully")
            else:
                self.log_message.emit("WARNING", "Sync infrastructure setup completed with errors")

            return success

        except Exception as e:
            self.logger.error(f"Error setting up sync infrastructure: {e}")
            self.error_occurred.emit(f"Infrastructure setup failed: {e}")
            return False

        finally:
            self._mutex.lock()
            try:
                self._is_running = False
                self._update_status(JobStatus.STOPPED)
            finally:
                self._mutex.unlock()

    def teardown_sync_infrastructure(self) -> bool:
        """
        Teardown sync infrastructure for all configured database pairs.

        Returns:
            True if teardown successful for all pairs, False otherwise
        """
        self._mutex.lock()
        try:
            if self._is_running:
                self.log_message.emit("WARNING", "Cannot teardown infrastructure while sync is running")
                return False

            if not self._sync_engines:
                self.error_occurred.emit("No database pairs configured")
                return False

            self._is_running = True
            self._update_status(JobStatus.RUNNING)

        finally:
            self._mutex.unlock()

        self.log_message.emit("INFO", "Tearing down sync infrastructure...")

        success = True
        total_pairs = len(self._sync_engines)
        completed_pairs = 0

        try:
            for pair_id, engine in self._sync_engines.items():
                pair_name = engine.db_pair.name
                self.log_message.emit("INFO", f"Removing infrastructure for: {pair_name}")

                if not engine.teardown_sync_infrastructure():
                    self.log_message.emit("ERROR", f"Failed to teardown infrastructure for: {pair_name}")
                    success = False
                else:
                    self.log_message.emit("INFO", f"Successfully removed infrastructure for: {pair_name}")

                completed_pairs += 1
                self._update_progress(completed_pairs, total_pairs)

                # Small delay between teardowns
                if completed_pairs < total_pairs:
                    time.sleep(0.5)

            if success:
                self.log_message.emit("INFO", "Sync infrastructure teardown completed successfully")
            else:
                self.log_message.emit("WARNING", "Sync infrastructure teardown completed with errors")

            return success

        except Exception as e:
            self.logger.error(f"Error tearing down sync infrastructure: {e}")
            self.error_occurred.emit(f"Infrastructure teardown failed: {e}")
            return False

        finally:
            self._mutex.lock()
            try:
                self._is_running = False
                self._update_status(JobStatus.STOPPED)
            finally:
                self._mutex.unlock()

    def get_database_pair_status(self, pair_id: str) -> Dict[str, Any]:
        """
        Get status information for a specific database pair.

        Args:
            pair_id: ID of the database pair

        Returns:
            Dictionary containing pair status information
        """
        self._mutex.lock()
        try:
            if pair_id in self._sync_engines:
                engine = self._sync_engines[pair_id]
                return engine.get_sync_status()
            else:
                return {
                    'error': 'Database pair not found or not enabled',
                    'pair_id': pair_id
                }
        finally:
            self._mutex.unlock()

    def validate_all_configurations(self) -> Dict[str, List[str]]:
        """
        Validate all database pair configurations.

        Returns:
            Dictionary mapping pair IDs to lists of validation errors
        """
        self._mutex.lock()
        try:
            if self._is_running:
                return {'error': ['Cannot validate while sync is running']}

            validation_results = {}

            for pair_id, engine in self._sync_engines.items():
                try:
                    errors = engine.validate_sync_configuration()
                    validation_results[pair_id] = errors

                    if errors:
                        self.log_message.emit("WARNING",
                            f"Validation issues found for {engine.db_pair.name}: {len(errors)} errors")
                    else:
                        self.log_message.emit("INFO",
                            f"Configuration valid for {engine.db_pair.name}")

                except Exception as e:
                    validation_results[pair_id] = [f"Validation error: {e}"]
                    self.log_message.emit("ERROR",
                        f"Error validating {engine.db_pair.name}: {e}")

            return validation_results

        finally:
            self._mutex.unlock()

    def reset_statistics(self):
        """Reset synchronization statistics."""
        self._mutex.lock()
        try:
            self._sync_stats = {
                'total_syncs': 0,
                'successful_syncs': 0,
                'failed_syncs': 0,
                'last_sync_time': None,
                'total_records_synced': 0
            }
            self.log_message.emit("INFO", "Sync statistics reset")
        finally:
            self._mutex.unlock()

    def cleanup(self):
        """Clean up resources and stop all operations."""
        self._mutex.lock()
        try:
            self._stop_requested = True
            self._is_scheduled = False

            # Stop all sync engines
            for engine in self._sync_engines.values():
                try:
                    engine.stop_sync()
                except Exception as e:
                    self.logger.error(f"Error stopping sync engine: {e}")

            self._sync_engines.clear()
            self._db_pairs.clear()

            if self._is_running:
                self._update_status(JobStatus.STOPPED)

            self.log_message.emit("INFO", "Sync worker cleaned up")

        finally:
            self._mutex.unlock()