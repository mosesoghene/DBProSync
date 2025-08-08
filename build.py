#!/usr/bin/env python3
"""
Build script for Database Sync Tool.

This script creates a Windows executable using PyInstaller and
optionally builds an installer using Inno Setup.
"""

import sys
import os
import shutil
import subprocess
import argparse
from pathlib import Path


def run_command(cmd, check=True, cwd=None):
    """Run a command and return the result."""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, check=check, cwd=cwd, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    return result


def clean_build_dirs():
    """Clean previous build directories."""
    dirs_to_clean = ['build', 'dist', '__pycache__']

    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            print(f"Cleaning {dir_name}...")
            shutil.rmtree(dir_name)

    # Clean .pyc files
    for root, dirs, files in os.walk('.'):
        for file in files:
            if file.endswith('.pyc'):
                os.remove(os.path.join(root, file))


def check_dependencies():
    """Check if required tools are available."""
    required_tools = {
        'pyinstaller': 'PyInstaller (pip install pyinstaller)',
        'iscc': 'Inno Setup Compiler (Download from https://jrsoftware.org/isinfo.php)'
    }

    missing = []
    for tool, description in required_tools.items():
        try:
            subprocess.run([tool, '--version'], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            missing.append(f"{tool}: {description}")

    return missing


def create_spec_file():
    """Create PyInstaller spec file with custom configuration."""
    spec_content = '''
# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

# Get the project root directory
project_root = Path.cwd()

block_cipher = None

# Define data files to include
datas = [
    (str(project_root / 'assets'), 'assets'),
    (str(project_root / 'config.json'), '.'),
]

# Define hidden imports for database drivers
hiddenimports = [
    'pymysql',
    'psycopg2',
    'sqlite3',
    'PySide6.QtCore',
    'PySide6.QtWidgets',
    'PySide6.QtGui',
    'winreg',
    'win32com.client'
]

a = Analysis(
    ['main.py'],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Remove unnecessary modules to reduce size
excluded_modules = [
    'tkinter',
    'matplotlib',
    'numpy',
    'pandas',
    'scipy',
    'PIL',
    'cv2',
    'sklearn',
]

a.binaries = [x for x in a.binaries if not any(exc in x[0] for exc in excluded_modules)]
a.datas = [x for x in a.datas if not any(exc in x[0] for exc in excluded_modules)]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='DatabaseSyncTool',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Windows app, not console
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_root / 'assets' / 'icon.ico'),
    version='version_info.txt'
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='DatabaseSyncTool',
)
'''

    with open('DatabaseSyncTool.spec', 'w') as f:
        f.write(spec_content.strip())


def create_version_info():
    """Create version info file for Windows executable."""
    version_info = '''
# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=(1, 0, 0, 0),
    prodvers=(1, 0, 0, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u'Moses Oghene'),
        StringStruct(u'FileDescription', u'Database Synchronization Tool'),
        StringStruct(u'FileVersion', u'1.0.0.0'),
        StringStruct(u'InternalName', u'DatabaseSyncTool'),
        StringStruct(u'LegalCopyright', u'Copyright (C) 2024 Moses Oghene'),
        StringStruct(u'OriginalFilename', u'DatabaseSyncTool.exe'),
        StringStruct(u'ProductName', u'Database Sync Tool'),
        StringStruct(u'ProductVersion', u'1.0.0.0')])
      ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
'''

    with open('version_info.txt', 'w') as f:
        f.write(version_info.strip())


def build_executable(debug=False):
    """Build the executable using PyInstaller."""
    print("Building executable...")

    # Create spec file and version info
    create_spec_file()
    create_version_info()

    # Build command
    cmd = ['pyinstaller', 'DatabaseSyncTool.spec']
    if not debug:
        cmd.extend(['--clean', '--noconfirm'])

    try:
        run_command(cmd)
        print("✓ Executable built successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to build executable: {e}")
        return False


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

    import json
    with open('config.json.template', 'w') as f:
        json.dump(template, f, indent=4)


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

    with open('README.txt', 'w') as f:
        f.write(readme_content.strip())


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

    with open('LICENSE.txt', 'w') as f:
        f.write(license_content.strip())


def build_installer():
    """Build the installer using Inno Setup."""
    print("Building installer...")

    # Check if Inno Setup is available
    try:
        run_command(['iscc', '--version'], check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("✗ Inno Setup Compiler not found. Please install Inno Setup.")
        print("  Download from: https://jrsoftware.org/isinfo.php")
        return False

    # Create supporting files
    create_config_template()
    create_readme()
    create_license()

    # Ensure installer directory exists
    os.makedirs('dist/installer', exist_ok=True)

    try:
        run_command(['iscc', 'installer.iss'])
        print("✓ Installer built successfully!")

        # Find and report the installer location
        installer_files = list(Path('dist/installer').glob('*.exe'))
        if installer_files:
            print(f"✓ Installer created: {installer_files[0]}")

        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to build installer: {e}")
        return False


def main():
    """Main build function."""
    parser = argparse.ArgumentParser(description='Build Database Sync Tool')
    parser.add_argument('--clean', action='store_true', help='Clean build directories first')
    parser.add_argument('--debug', action='store_true', help='Build in debug mode')
    parser.add_argument('--no-installer', action='store_true', help='Skip installer creation')
    parser.add_argument('--installer-only', action='store_true', help='Only build installer (skip executable)')

    args = parser.parse_args()

    # Change to script directory
    os.chdir(Path(__file__).parent)

    print("Database Sync Tool Build Script")
    print("=" * 40)

    # Clean if requested
    if args.clean:
        clean_build_dirs()

    # Check dependencies
    missing_deps = check_dependencies()
    if missing_deps:
        print("✗ Missing required tools:")
        for dep in missing_deps:
            print(f"  - {dep}")
        return 1

    success = True

    # Build executable unless installer-only
    if not args.installer_only:
        success = build_executable(debug=args.debug)

    # Build installer if executable succeeded and not disabled
    if success and not args.no_installer:
        # Check if executable exists (either just built or from previous build)
        exe_path = Path('dist/DatabaseSyncTool/DatabaseSyncTool.exe')
        if exe_path.exists():
            success = build_installer()
        else:
            print("✗ Executable not found. Cannot build installer.")
            success = False

    print("\n" + "=" * 40)
    if success:
        print("✓ Build completed successfully!")

        # Show what was built
        if Path('dist/DatabaseSyncTool/DatabaseSyncTool.exe').exists():
            print(f"✓ Executable: dist/DatabaseSyncTool/DatabaseSyncTool.exe")

        installer_files = list(Path('dist/installer').glob('*.exe'))
        if installer_files:
            print(f"✓ Installer: {installer_files[0]}")
    else:
        print("✗ Build failed!")

    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())