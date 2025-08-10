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
import tempfile


# CRITICAL: Change working directory BEFORE any other imports
# This prevents any module from creating files in the installation directory
def setup_user_working_directory():
    """Setup user-writable working directory for the application."""
    if getattr(sys, 'frozen', False):  # If running as exe
        if os.name == 'nt':  # Windows
            user_data = os.environ.get('LOCALAPPDATA', os.path.expanduser('~\\AppData\\Local'))
            app_dir = os.path.join(user_data, "Database Sync Tool")
        else:
            app_dir = os.path.join(os.path.expanduser("~"), ".database-sync-tool")

        # Create directory if it doesn't exist
        os.makedirs(app_dir, exist_ok=True)

        # Change to this directory so ALL relative paths work from here
        os.chdir(app_dir)

        # Create common subdirectories
        os.makedirs("logs", exist_ok=True)
        os.makedirs("backups", exist_ok=True)
        os.makedirs("temp", exist_ok=True)

        return app_dir

    return None


# Setup working directory FIRST, before any other imports
user_app_dir = setup_user_working_directory()

# Add the current directory to Python path for imports
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtGui import QPalette, QColor, QIcon
from PySide6.QtCore import QTimer

from ui.main_window import MainWindow
from utils.startup_manager import parse_command_line_args
from utils.constants import APP_NAME, APP_VERSION, ORGANIZATION_NAME

# Import path management after directory setup
try:
    from utils.app_paths import setup_logging, app_paths
except ImportError:
    # Fallback if app_paths module is not available
    def setup_logging():
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_dir / "app.log", encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )


def setup_application_properties(app: QApplication):
    """Set up application properties and styling."""
    # Set application properties
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(ORGANIZATION_NAME)
    app.setQuitOnLastWindowClosed(False)  # Keep app running when window is closed

    # Set application icon - look in original installation directory
    icon_paths = [
        Path("assets/icon.ico"),  # Current directory (user data dir)
        Path(sys.executable).parent / "assets" / "icon.ico",  # Next to exe
        current_dir / "assets" / "icon.ico"  # Original source directory
    ]

    for icon_path in icon_paths:
        if icon_path.exists():
            app.setWindowIcon(QIcon(str(icon_path)))
            break

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


def handle_exception(exc_type, exc_value, exc_traceback):
    """Handle uncaught exceptions."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logging.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))


def override_file_operations():
    """Override common file operations to prevent writing to installation directory."""
    if not getattr(sys, 'frozen', False):
        return  # Only do this for frozen executables

    # Store original open function
    original_open = open

    def safe_open(file, mode='r', **kwargs):
        """Wrapper around open() to redirect problematic paths to user directory."""
        if isinstance(file, (str, Path)):
            file_path = Path(file)

            # If trying to write to installation directory, redirect to user directory
            if 'w' in str(mode) or 'a' in str(mode):
                install_dir = Path(sys.executable).parent
                if str(file_path.resolve()).startswith(str(install_dir.resolve())):
                    # Redirect to current working directory (user data dir)
                    new_path = Path.cwd() / file_path.name
                    logging.warning(f"Redirected file write from {file_path} to {new_path}")
                    file = new_path

        return original_open(file, mode, **kwargs)

    # Replace the built-in open function
    import builtins
    builtins.open = safe_open


def main():
    """Main application entry point."""
    # Set up exception handling
    sys.excepthook = handle_exception

    # Parse command line arguments
    args = parse_command_line_args()

    # Override file operations to prevent installation directory writes
    override_file_operations()

    # Set up logging with proper user paths
    setup_logging()

    # Log startup information
    logging.info(f"Starting {APP_NAME} v{APP_VERSION}")
    logging.info(f"Command line args: {sys.argv}")
    logging.info(f"Python version: {sys.version}")
    logging.info(f"Working directory: {os.getcwd()}")
    if user_app_dir:
        logging.info(f"User app directory: {user_app_dir}")

    # Log path information if available
    try:
        from utils.app_paths import app_paths
        logging.info(f"Config file: {app_paths.config_file}")
        logging.info(f"Logs directory: {app_paths.logs_dir}")
    except ImportError:
        logging.info("App paths module not available, using current directory")

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
    # The working directory setup is already done at module import time
    exit_code = main()
    sys.exit(exit_code)