#!/usr/bin/env python3
"""
Script to create all supporting files needed for the installer
"""

import json
import os
from pathlib import Path

def create_config_template():
    """Create a configuration template file."""
    template = {
        "app_password_hash": "d74ff0ee8da3b9806b18c877dbf29bbde50b5bd8e4dad7a3a725000feb82e8f1",
        "database_pairs": [],
        "log_level": "INFO",
        "auto_start": False,
        "default_sync_interval": 300,
        "max_log_size": 10,
        "backup_enabled": True
    }

    with open('config.json.template', 'w') as f:
        json.dump(template, f, indent=4)
    print("✓ Created config.json.template")

def create_readme():
    """Create a README file for distribution."""
    readme_content = '''Database Sync Tool v1.0.0
==========================

A powerful database synchronization tool for keeping your local and cloud databases in sync.

INSTALLATION
------------
Run the installer as Administrator to install to Program Files.

FIRST RUN
---------
1. Start the application
2. Set up your password (default is 'admin')
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
'''

    with open('README.txt', 'w', encoding='utf-8') as f:
        f.write(readme_content.strip())
    print("✓ Created README.txt")

def create_license():
    """Create a basic license file."""
    license_content = '''MIT License

Copyright (c) 2024 Moses Oghene

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
'''

    with open('LICENSE.txt', 'w', encoding='utf-8') as f:
        f.write(license_content.strip())
    print("✓ Created LICENSE.txt")

def create_basic_icon():
    """Create a basic icon file if one doesn't exist."""
    assets_dir = Path('assets')
    icon_path = assets_dir / 'icon.ico'
    
    if icon_path.exists():
        print(f"✓ Icon already exists: {icon_path}")
        return
    
    # Create assets directory if it doesn't exist
    assets_dir.mkdir(exist_ok=True)
    
    # Create a minimal ICO file (16x16 black square)
    # This is a basic ICO file structure - you should replace with a proper icon
    ico_data = bytes([
        # ICO header
        0x00, 0x00,  # Reserved
        0x01, 0x00,  # Type: ICO
        0x01, 0x00,  # Number of images: 1
        # Image directory entry
        0x10,        # Width: 16
        0x10,        # Height: 16
        0x00,        # Colors: 0 (256 colors)
        0x00,        # Reserved
        0x01, 0x00,  # Planes: 1
        0x20, 0x00,  # Bits per pixel: 32
        0x80, 0x04, 0x00, 0x00,  # Image data size: 1152 bytes
        0x16, 0x00, 0x00, 0x00,  # Image data offset: 22
    ])
    
    # Add a simple bitmap data (this creates a basic icon)
    # For a proper icon, you should use an actual ICO file
    bitmap_data = b'\x00' * 1152  # Simple black 16x16 icon
    
    try:
        with open(icon_path, 'wb') as f:
            f.write(ico_data + bitmap_data)
        print(f"✓ Created basic icon: {icon_path}")
        print("  (You should replace this with a proper icon file)")
    except Exception as e:
        print(f"✗ Could not create icon: {e}")
        print("  You'll need to create assets/icon.ico manually")

def check_required_files():
    """Check if all required files exist."""
    print("\nChecking required files:")
    
    required_files = [
        ('dist/DatabaseSyncTool/DatabaseSyncTool.exe', 'Main executable'),
        ('assets/icon.ico', 'Application icon'),
        ('config.json.template', 'Configuration template'),
        ('README.txt', 'Documentation'),
        ('LICENSE.txt', 'License file')
    ]
    
    all_exist = True
    for file_path, description in required_files:
        path = Path(file_path)
        if path.exists():
            print(f"✓ {description}: {file_path}")
        else:
            print(f"✗ {description}: {file_path} - MISSING!")
            all_exist = False
    
    return all_exist

if __name__ == "__main__":
    print("Creating supporting files for installer...")
    print("=" * 50)
    
    # Create all supporting files
    create_config_template()
    create_readme()
    create_license()
    create_basic_icon()
    
    # Ensure installer output directory exists
    os.makedirs('dist/installer', exist_ok=True)
    print("✓ Created dist/installer directory")
    
    print("\n" + "=" * 50)
    
    # Check if all required files now exist
    if check_required_files():
        print("\n✓ All required files are present!")
        print("You can now run the installer build.")
    else:
        print("\n✗ Some files are still missing.")
        print("Make sure you've built the executable first with:")
        print("  python build.py --no-installer")
