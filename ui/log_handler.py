"""
Custom log handler for displaying logs in the UI.

This module provides a logging handler that can display log messages
in Qt widgets while also maintaining thread safety.
"""

import logging
from datetime import datetime
from typing import Optional
from PySide6.QtWidgets import QTextEdit
from PySide6.QtCore import QObject, Signal, QMutex
from PySide6.QtGui import QTextCursor, QColor


class LogSignals(QObject):
    """Signals for thread-safe log message emission."""
    log_received = Signal(str, str, str)  # timestamp, level, message


class UILogHandler(logging.Handler):
    """Custom logging handler that displays messages in a QTextEdit widget."""

    def __init__(self, text_widget: Optional[QTextEdit] = None):
        """
        Initialize the UI log handler.

        Args:
            text_widget: QTextEdit widget to display logs in
        """
        super().__init__()
        self.text_widget = text_widget
        self.signals = LogSignals()
        self.mutex = QMutex()

        # Connect signal to handler method
        self.signals.log_received.connect(self._handle_log_message)

        # Color scheme for different log levels
        self.level_colors = {
            'DEBUG': QColor(128, 128, 128),  # Gray
            'INFO': QColor(0, 0, 0),  # Black
            'WARNING': QColor(255, 140, 0),  # Orange
            'ERROR': QColor(255, 0, 0),  # Red
            'CRITICAL': QColor(139, 0, 0)  # Dark Red
        }

        # Set default format
        self.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))

    def set_text_widget(self, text_widget: QTextEdit):
        """
        Set or change the text widget for log display.

        Args:
            text_widget: QTextEdit widget to display logs in
        """
        self.mutex.lock()
        try:
            self.text_widget = text_widget
        finally:
            self.mutex.unlock()

    def emit(self, record: logging.LogRecord):
        """
        Emit a log record to the UI widget.

        Args:
            record: Log record to emit
        """
        try:
            # Format the message
            message = self.format(record)
            timestamp = datetime.fromtimestamp(record.created).strftime('%H:%M:%S')
            level = record.levelname

            # Emit signal for thread-safe UI update
            self.signals.log_received.emit(timestamp, level, message)

        except Exception:
            # Handle errors in log handler gracefully
            self.handleError(record)

    def _handle_log_message(self, timestamp: str, level: str, message: str):
        """
        Handle log message in the UI thread.

        Args:
            timestamp: Formatted timestamp
            level: Log level
            message: Log message
        """
        self.mutex.lock()
        try:
            if not self.text_widget:
                return

            # Get current cursor position
            cursor = self.text_widget.textCursor()
            cursor.movePosition(QTextCursor.End)

            # Format the log entry
            log_entry = f"[{timestamp}] {level}: {message}"

            # Set color based on log level
            if level in self.level_colors:
                self.text_widget.setTextColor(self.level_colors[level])
            else:
                self.text_widget.setTextColor(self.level_colors['INFO'])

            # Append the message
            cursor.insertText(log_entry + '\n')

            # Auto-scroll to bottom
            self.text_widget.ensureCursorVisible()

            # Limit the number of lines to prevent memory issues
            self._limit_log_lines()

        finally:
            self.mutex.unlock()

    def _limit_log_lines(self, max_lines: int = 1000):
        """
        Limit the number of log lines displayed to prevent memory issues.

        Args:
            max_lines: Maximum number of lines to keep
        """
        if not self.text_widget:
            return

        document = self.text_widget.document()
        if document.blockCount() > max_lines:
            # Remove excess lines from the beginning
            cursor = QTextCursor(document)
            cursor.movePosition(QTextCursor.Start)

            # Calculate how many lines to remove
            lines_to_remove = document.blockCount() - max_lines

            # Select and delete excess lines
            for _ in range(lines_to_remove):
                cursor.select(QTextCursor.BlockUnderCursor)
                cursor.removeSelectedText()
                cursor.deleteChar()  # Remove the newline

    def clear_logs(self):
        """Clear all log messages from the widget."""
        self.mutex.lock()
        try:
            if self.text_widget:
                self.text_widget.clear()
        finally:
            self.mutex.unlock()

    def save_logs_to_file(self, filename: str) -> bool:
        """
        Save current log content to a file.

        Args:
            filename: Path to save the logs

        Returns:
            True if saved successfully, False otherwise
        """
        self.mutex.lock()
        try:
            if not self.text_widget:
                return False

            content = self.text_widget.toPlainText()

            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)

            return True

        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to save logs to file: {e}")
            return False
        finally:
            self.mutex.unlock()


class LogLevelFilter(logging.Filter):
    """Filter logs by minimum level."""

    def __init__(self, min_level: int = logging.INFO):
        """
        Initialize the filter.

        Args:
            min_level: Minimum log level to display
        """
        super().__init__()
        self.min_level = min_level

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Filter log records based on level.

        Args:
            record: Log record to filter

        Returns:
            True if record should be displayed, False otherwise
        """
        return record.levelno >= self.min_level

    def set_min_level(self, level: int):
        """
        Set the minimum log level.

        Args:
            level: Minimum log level
        """
        self.min_level = level


class LogManager:
    """Manages logging configuration for the application."""

    def __init__(self, log_file: str = "sync_app.log"):
        """
        Initialize the log manager.

        Args:
            log_file: Path to the log file
        """
        self.log_file = log_file
        self.ui_handler: Optional[UILogHandler] = None
        self.file_handler: Optional[logging.FileHandler] = None
        self.level_filter: Optional[LogLevelFilter] = None

        self.setup_logging()

    def setup_logging(self):
        """Set up logging configuration."""
        # Get root logger
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)

        # Clear any existing handlers
        logger.handlers.clear()

        # Create file handler
        self.file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        self.file_handler.setLevel(logging.DEBUG)

        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        self.file_handler.setFormatter(formatter)

        # Add file handler to root logger
        logger.addHandler(self.file_handler)

        # Create level filter
        self.level_filter = LogLevelFilter(logging.INFO)

        logging.info("Logging system initialized")

    def add_ui_handler(self, text_widget: QTextEdit, min_level: int = logging.INFO):
        """
        Add UI handler for displaying logs in a widget.

        Args:
            text_widget: QTextEdit widget for log display
            min_level: Minimum log level to display in UI
        """
        # Create UI handler
        self.ui_handler = UILogHandler(text_widget)
        self.ui_handler.setLevel(min_level)

        # Create simple formatter for UI
        ui_formatter = logging.Formatter('%(name)s - %(message)s')
        self.ui_handler.setFormatter(ui_formatter)

        # Add filter
        self.ui_handler.addFilter(self.level_filter)

        # Add to root logger
        logging.getLogger().addHandler(self.ui_handler)

        logging.info("UI log handler added")

    def remove_ui_handler(self):
        """Remove the UI handler."""
        if self.ui_handler:
            logging.getLogger().removeHandler(self.ui_handler)
            self.ui_handler = None
            logging.info("UI log handler removed")

    def set_log_level(self, level: str):
        """
        Set the logging level.

        Args:
            level: Log level string (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        numeric_level = getattr(logging, level.upper(), logging.INFO)

        # Update file handler level
        if self.file_handler:
            self.file_handler.setLevel(numeric_level)

        # Update filter level
        if self.level_filter:
            self.level_filter.set_min_level(numeric_level)

        logging.info(f"Log level set to {level.upper()}")

    def clear_ui_logs(self):
        """Clear logs from the UI widget."""
        if self.ui_handler:
            self.ui_handler.clear_logs()

    def save_ui_logs(self, filename: str) -> bool:
        """
        Save UI logs to a file.

        Args:
            filename: Path to save the logs

        Returns:
            True if saved successfully, False otherwise
        """
        if self.ui_handler:
            return self.ui_handler.save_logs_to_file(filename)
        return False

    def cleanup(self):
        """Clean up logging resources."""
        if self.ui_handler:
            self.remove_ui_handler()

        if self.file_handler:
            logging.getLogger().removeHandler(self.file_handler)
            self.file_handler.close()
            self.file_handler = None

        logging.info("Log manager cleaned up")