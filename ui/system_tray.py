"""
System tray manager for the Database Synchronization Application.

This module handles system tray operations including minimize to tray,
tray menu, and notifications.
"""

import logging
from typing import Optional
from pathlib import Path

from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QMessageBox
from PySide6.QtCore import QObject, Signal, QTimer
from PySide6.QtGui import QIcon, QAction, QPixmap


class SystemTrayManager(QObject):
    """Manages system tray functionality."""

    # Signals
    show_window = Signal()
    exit_application = Signal()
    start_sync = Signal()
    stop_sync = Signal()

    def __init__(self, parent=None):
        """Initialize the system tray manager."""
        super().__init__(parent)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.tray_icon: Optional[QSystemTrayIcon] = None
        self.parent_window = parent

        # Check if system tray is available
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.logger.warning("System tray is not available on this system")
            if parent:
                QMessageBox.critical(
                    parent,
                    "System Tray",
                    "System tray is not available on this system.\n"
                    "The application will work normally but cannot minimize to tray."
                )
            return

        self.setup_tray_icon()
        self.setup_tray_menu()

    def setup_tray_icon(self):
        """Set up the system tray icon."""
        # Load icon
        icon_path = Path("assets/icon.ico")
        if icon_path.exists():
            icon = QIcon(str(icon_path))
        else:
            # Fallback to a default icon if file not found
            # Create a simple colored icon as fallback
            pixmap = QPixmap(16, 16)
            pixmap.fill()
            icon = QIcon(pixmap)

        self.tray_icon = QSystemTrayIcon(icon, self.parent())
        self.tray_icon.setToolTip("Database Sync Tool")

        # Connect signals
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        self.tray_icon.messageClicked.connect(self.on_message_clicked)

    def setup_tray_menu(self):
        """Set up the system tray context menu."""
        if not self.tray_icon:
            return

        tray_menu = QMenu()

        # Show/Hide action
        self.show_action = QAction("Show", self)
        self.show_action.triggered.connect(self.show_window.emit)
        tray_menu.addAction(self.show_action)

        tray_menu.addSeparator()

        # Sync actions
        self.start_sync_action = QAction("Start Sync", self)
        self.start_sync_action.triggered.connect(self.start_sync.emit)
        tray_menu.addAction(self.start_sync_action)

        self.stop_sync_action = QAction("Stop Sync", self)
        self.stop_sync_action.triggered.connect(self.stop_sync.emit)
        self.stop_sync_action.setEnabled(False)
        tray_menu.addAction(self.stop_sync_action)

        tray_menu.addSeparator()

        # Exit action
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.exit_application.emit)
        tray_menu.addAction(exit_action)

        self.tray_icon.setContextMenu(tray_menu)

    def show_tray_icon(self):
        """Show the system tray icon."""
        if self.tray_icon and QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon.show()
            self.logger.info("System tray icon shown")

    def hide_tray_icon(self):
        """Hide the system tray icon."""
        if self.tray_icon:
            self.tray_icon.hide()
            self.logger.info("System tray icon hidden")

    def update_sync_status(self, is_running: bool):
        """
        Update sync status in tray menu.

        Args:
            is_running: Whether sync is currently running
        """
        if not self.tray_icon:
            return

        self.start_sync_action.setEnabled(not is_running)
        self.stop_sync_action.setEnabled(is_running)

        # Update tooltip
        status = "Running" if is_running else "Stopped"
        self.tray_icon.setToolTip(f"Database Sync Tool - {status}")

    def show_notification(self, title: str, message: str,
                         icon: QSystemTrayIcon.MessageIcon = QSystemTrayIcon.Information,
                         timeout: int = 5000):
        """
        Show system tray notification.

        Args:
            title: Notification title
            message: Notification message
            icon: Icon type
            timeout: Display timeout in milliseconds
        """
        if self.tray_icon and QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon.showMessage(title, message, icon, timeout)

    def on_tray_icon_activated(self, reason: QSystemTrayIcon.ActivationReason):
        """Handle tray icon activation."""
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_window.emit()
        elif reason == QSystemTrayIcon.Trigger:
            # Single click - could toggle window visibility
            pass

    def on_message_clicked(self):
        """Handle notification message click."""
        self.show_window.emit()

    def is_available(self) -> bool:
        """Check if system tray is available."""
        return QSystemTrayIcon.isSystemTrayAvailable() and self.tray_icon is not None