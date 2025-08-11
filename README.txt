Database Sync Tool v1.0.0
==========================

A powerful database synchronization tool for keeping your local and cloud databases in sync.

INSTALLATION
------------
Run the installer as Administrator to install to Program Files.

FIRST RUN
---------
1. Start the application
2. Set up your password (default is 'pass' or 'admin')
3. Configure your database connections in Settings
4. Set up sync infrastructure (creates triggers and changelog tables)
5. Start synchronization

FEATURES
--------
- Bidirectional database synchronization
- Support for MySQL, PostgreSQL, and SQLite
- Change tracking with database triggers
- Scheduled and manual sync operations
- System tray integration
- Windows startup integration
- Comprehensive logging and monitoring
- Conflict resolution strategies

SYSTEM REQUIREMENTS
-------------------
- Windows 10 version 1809 (build 17763) or later
- Administrative privileges for installation
- Network access to your databases

STARTUP OPTIONS
---------------
The application supports the following command line options:
- --minimized: Start minimized to system tray
- --auto-sync: Automatically start synchronization (requires valid config)

TROUBLESHOOTING
---------------
- Check log files in the logs directory
- Ensure database drivers are properly installed
- Verify network connectivity to your databases
- Run as Administrator if experiencing permission issues

SUPPORT
-------
For support and documentation, please contact the developer.

Copyright (C) 2024 Moses Oghene