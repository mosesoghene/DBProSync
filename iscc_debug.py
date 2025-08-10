#!/usr/bin/env python3
"""
Debug script to diagnose ISCC compilation issues
"""

import subprocess
import sys
import shutil
from pathlib import Path
import os

def find_iscc():
    """Find the Inno Setup Compiler executable on Windows."""
    # First try using shutil.which
    iscc_path = shutil.which('iscc')
    if iscc_path:
        print(f"Found iscc via shutil.which: {iscc_path}")
        return iscc_path
    
    # Try the exact path we know exists
    known_path = r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    if Path(known_path).exists():
        print(f"Found iscc at known location: {known_path}")
        return known_path
    
    # Try other common paths
    common_paths = [
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
        r"C:\Program Files (x86)\Inno Setup 5\ISCC.exe", 
        r"C:\Program Files\Inno Setup 5\ISCC.exe",
    ]
    
    for path in common_paths:
        if Path(path).exists():
            print(f"Found iscc at: {path}")
            return path
    
    return None

def debug_iscc_compile():
    """Run ISCC with verbose output to see what's failing."""
    print("Debugging ISCC compilation...")
    print("=" * 50)
    
    iscc_path = find_iscc()
    if not iscc_path:
        print("✗ ISCC not found!")
        return False
    
    # Check if installer.iss exists
    if not Path('installer.iss').exists():
        print("✗ installer.iss not found!")
        return False
    
    print(f"Using ISCC: {iscc_path}")
    print(f"Script file: {Path('installer.iss').absolute()}")
    print(f"Working directory: {Path.cwd()}")
    
    # List files that the script expects to find
    print("\nChecking required files:")
    required_files = [
        'dist/DatabaseSyncTool/DatabaseSyncTool.exe',
        'assets/icon.ico',
        'LICENSE.txt',
        'README.txt',
        'config.json.template'
    ]
    
    for file_path in required_files:
        path = Path(file_path)
        if path.exists():
            print(f"✓ {file_path}")
        else:
            print(f"✗ {file_path} - MISSING!")
    
    # Check dist directory structure
    print("\nDist directory structure:")
    dist_path = Path('dist')
    if dist_path.exists():
        for item in dist_path.rglob('*'):
            if item.is_file():
                print(f"  {item}")
    else:
        print("  dist/ directory not found!")
    
    # Try to compile with verbose output
    print("\nRunning ISCC compilation:")
    try:
        # Use more verbose flags
        cmd = [iscc_path, '/V9', 'installer.iss']  # /V9 = maximum verbosity
        print(f"Command: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=Path.cwd()
        )
        
        print(f"\nReturn code: {result.returncode}")
        print(f"STDOUT length: {len(result.stdout)}")
        print(f"STDERR length: {len(result.stderr)}")
        
        if result.stdout:
            print("\n--- STDOUT ---")
            print(result.stdout)
        
        if result.stderr:
            print("\n--- STDERR ---")
            print(result.stderr)
        
        if result.returncode == 0:
            print("\n✓ Compilation successful!")
            return True
        else:
            print(f"\n✗ Compilation failed with exit code {result.returncode}")
            return False
            
    except subprocess.TimeoutExpired:
        print("✗ ISCC compilation timed out!")
        return False
    except Exception as e:
        print(f"✗ Error running ISCC: {e}")
        return False

def create_minimal_test_script():
    """Create a minimal test script to verify ISCC works."""
    test_script = '''[Setup]
AppName=Test App
AppVersion=1.0
DefaultDirName={pf}\\Test App
OutputBaseFilename=test_installer
OutputDir=dist\\installer

[Files]
Source: "installer.iss"; DestDir: "{app}"
'''
    
    with open('test_minimal.iss', 'w') as f:
        f.write(test_script)
    
    print("Created minimal test script: test_minimal.iss")
    
    # Try to compile the minimal script
    iscc_path = find_iscc()
    if iscc_path:
        try:
            os.makedirs('dist/installer', exist_ok=True)
            result = subprocess.run([iscc_path, 'test_minimal.iss'], 
                                  capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                print("✓ Minimal script compiled successfully!")
                print("✓ ISCC is working correctly")
                return True
            else:
                print(f"✗ Minimal script failed: {result.returncode}")
                if result.stdout:
                    print("STDOUT:", result.stdout[:500])
                if result.stderr:
                    print("STDERR:", result.stderr[:500])
                return False
        except Exception as e:
            print(f"✗ Error testing minimal script: {e}")
            return False
    else:
        print("✗ ISCC not found for testing")
        return False

if __name__ == "__main__":
    print("ISCC Compilation Debugger")
    print("=" * 40)
    
    # First test with minimal script
    print("Step 1: Testing ISCC with minimal script...")
    if create_minimal_test_script():
        print("\nStep 2: Debugging main installer script...")
        debug_iscc_compile()
    else:
        print("\n✗ ISCC itself is not working properly!")
        print("  Please check your Inno Setup installation.")
