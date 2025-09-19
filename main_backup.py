#!/usr/bin/env python3
"""
Database Synchronization Tool - Main Entry Point

This is the main entry point for the Database Synchronization Tool.
Supports command line arguments for startup options and system tray integration.
"""

import sys
import os
import logging
from pathlib import Path
from utils.app_paths import setup_logging, app_paths

# Add the current directory to Python path for imports
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtGui import QPalette, QColor, QIcon
from PySide6.QtCore import QTimer

from ui.main_window import MainWindow
from utils.startup_manager import parse_command_line_args
from utils.constants import APP_NAME, APP_VERSION, ORGANIZATION_NAME


def setup_application_properties(app: QApplication):
    """Set up application properties and styling."""
    # Set application properties
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(ORGANIZATION_NAME)
    app.setQuitOnLastWindowClosed(False)  # Keep app running when window is closed

    # Set application icon
    icon_path = Path("assets/icon.ico")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # Apply a modern dark theme
    app.setStyle("Fusion")
    dark_palette = QPalette()

    # Define colors
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


def get_app_data_dir():
    """Get the application data directory in user space."""
    if os.name == 'nt':  # Windows
        # Use LOCALAPPDATA for logs and temp data, APPDATA for config
        app_data = os.environ.get('LOCALAPPDATA', os.path.expanduser('~\\AppData\\Local'))
        app_dir = Path(app_data) / "Database Sync Tool"
    else:  # Linux/Mac
        app_dir = Path.home() / ".database-sync-tool"

    # Create the directory if it doesn't exist
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir


def get_config_dir():
    """Get the configuration directory in user space."""
    if os.name == 'nt':  # Windows
        # Use APPDATA for persistent config data
        app_data = os.environ.get('APPDATA', os.path.expanduser('~\\AppData\\Roaming'))
        config_dir = Path(app_data) / "Database Sync Tool"
    else:  # Linux/Mac
        config_dir = Path.home() / ".database-sync-tool"

    # Create the directory if it doesn't exist
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def setup_logging():
    """Set up logging configuration with proper user-writable paths."""
    # Use user data directory for logs
    app_data_dir = get_app_data_dir()
    log_dir = app_data_dir / "logs"
    log_dir.mkdir(exist_ok=True)

    # Create log file path
    log_file = log_dir / "app.log"

    try:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        logging.info(f"Logging initialized. Log file: {log_file}")
    except PermissionError as e:
        # Fallback to temp directory if user data directory fails
        import tempfile
        temp_log = Path(tempfile.gettempdir()) / "database_sync_tool_app.log"
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(temp_log, encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        logging.warning(f"Could not write to user data directory, using temp: {temp_log}")
        logging.warning(f"Original error: {e}")


def get_user_config_path():
    """Get the path for the user's config file."""
    config_dir = get_config_dir()
    return config_dir / "config.json"


def migrate_config_from_install_dir():
    """Migrate config from installation directory to user directory if needed."""
    user_config = get_user_config_path()

    # If user config already exists, don't migrate
    if user_config.exists():
        return user_config

    # Try to find config in installation directory
    possible_install_configs = [
        Path("config.json"),  # Current directory (for development)
        Path(sys.executable).parent / "config.json",  # Next to executable
        Path(sys.executable).parent / "_internal" / "config.json"  # PyInstaller internal
    ]

    for install_config in possible_install_configs:
        if install_config.exists():
            try:
                # Copy config to user directory
                import shutil
                shutil.copy2(install_config, user_config)
                logging.info(f"Migrated config from {install_config} to {user_config}")
                break
            except Exception as e:
                logging.warning(f"Could not migrate config from {install_config}: {e}")

    return user_config


def handle_exception(exc_type, exc_value, exc_traceback):
    """Handle uncaught exceptions."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logging.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))


def main():
    """Main application entry point."""
    # Set up exception handling
    sys.excepthook = handle_exception

    # Parse command line arguments
    args = parse_command_line_args()

    # IMPORTANT: Migrate config before setting up logging
    app_paths.migrate_from_install_dir()

    # Set up logging with proper user paths
    setup_logging()

    # Log startup information
    logging.info(f"Starting {APP_NAME} v{APP_VERSION}")
    logging.info(f"Command line args: {sys.argv}")
    logging.info(f"Python version: {sys.version}")
    logging.info(f"Working directory: {os.getcwd()}")
    logging.info(f"Config file: {app_paths.config_file}")
    logging.info(f"Logs directory: {app_paths.logs_dir}")

    # Create QApplication
    app = QApplication(sys.argv)

    # Set up application properties and styling
    setup_application_properties(app)

    try:
        # Check for required dependencies
        missing_deps = check_dependencies()
        if missing_deps:
            show_dependency_error(missing_deps)
            return 1

        # Create and configure main window
        window = MainWindow()

        # Handle startup arguments
        if args.minimized:
            # Window will handle minimized startup internally
            logging.info("Starting in minimized mode")
        else:
            # Show window normally
            window.show()
            window.raise_()
            window.activateWindow()

        # Set up application exit handler
        app.aboutToQuit.connect(lambda: logging.info(f"{APP_NAME} shutting down"))

        logging.info(f"{APP_NAME} started successfully")

        # Run the application
        exit_code = app.exec()
        logging.info(f"{APP_NAME} exited with code {exit_code}")
        return exit_code

    except Exception as e:
        logging.critical(f"Fatal error during startup: {e}", exc_info=True)

        # Try to show error dialog if possible
        try:
            QMessageBox.critical(
                None,
                "Startup Error",
                f"A fatal error occurred during startup:\n\n{e}\n\n"
                f"Please check the log files for more details."
            )
        except:
            pass  # If we can't show the dialog, just log and exit

        return 1


def check_dependencies():
    """Check for required dependencies and return list of missing ones."""
    missing = []

    # Check for database drivers
    try:
        import pymysql
    except ImportError:
        missing.append("pymysql (for MySQL support)")

    try:
        import psycopg2
    except ImportError:
        missing.append("psycopg2 (for PostgreSQL support)")

    # SQLite is built into Python, so no need to check

    # Check for Windows-specific modules (if on Windows)
    if sys.platform.startswith('win'):
        try:
            import winreg
        except ImportError:
            missing.append("winreg (for Windows startup integration)")

    return missing


def show_dependency_error(missing_deps):
    """Show error dialog for missing dependencies."""
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    deps_text = "\n".join(f"• {dep}" for dep in missing_deps)

    QMessageBox.critical(
        None,
        "Missing Dependencies",
        f"The following required dependencies are missing:\n\n{deps_text}\n\n"
        f"Please install them using pip:\n"
        f"pip install pymysql psycopg2-binary\n\n"
        f"The application cannot start without these dependencies."
    )


def create_desktop_shortcut():
    """Create desktop shortcut (Windows only)."""
    if not sys.platform.startswith('win'):
        return False

    try:
        import win32com.client
        import os

        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        shortcut_path = os.path.join(desktop, f"{APP_NAME}.lnk")

        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(shortcut_path)
        shortcut.Targetpath = sys.executable
        shortcut.Arguments = f'"{__file__}"'
        shortcut.WorkingDirectory = str(Path(__file__).parent)

        # Set icon if available
        icon_path = Path("assets/icon.ico")
        if icon_path.exists():
            shortcut.IconLocation = str(icon_path)

        shortcut.save()
        return True

    except ImportError:
        logging.warning("pywin32 not available, cannot create desktop shortcut")
        return False
    except Exception as e:
        logging.error(f"Failed to create desktop shortcut: {e}")
        return False


if __name__ == "__main__":
    # Ensure we're in the correct directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)

    exit_code = main()
    sys.exit(exit_code)