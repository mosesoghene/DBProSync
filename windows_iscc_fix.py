import subprocess
import sys
import shutil
from pathlib import Path

def find_iscc():
    """Find the Inno Setup Compiler executable on Windows."""
    # First try using shutil.which (more reliable than subprocess on Windows)
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

def test_iscc_executable(iscc_path):
    """Test if the ISCC executable works."""
    try:
        result = subprocess.run([iscc_path], capture_output=True, text=True, timeout=10)
        output_text = (result.stdout or '') + (result.stderr or '')
        
        if 'Inno Setup' in output_text and result.returncode == 1:
            print("✓ ISCC executable works correctly")
            return True
        else:
            print(f"✗ ISCC test failed - Return code: {result.returncode}")
            return False
    except Exception as e:
        print(f"✗ Error testing ISCC: {e}")
        return False

def check_dependencies():
    """Check if required tools are available."""
    missing = []
    
    # Check PyInstaller
    try:
        result = subprocess.run(['pyinstaller', '--version'], capture_output=True, check=True, timeout=10)
        print("✓ Found pyinstaller")
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        print("✗ Missing pyinstaller")
        missing.append("pyinstaller: PyInstaller (pip install pyinstaller)")
    
    # Check ISCC (Inno Setup Compiler) - Windows-specific approach
    iscc_path = find_iscc()
    if iscc_path and test_iscc_executable(iscc_path):
        print("✓ Found and verified ISCC")
        # Store the path for later use
        globals()['ISCC_PATH'] = iscc_path
    else:
        print("✗ ISCC not found or not working")
        missing.append("iscc: Inno Setup Compiler (Download from https://jrsoftware.org/isinfo.php)")

    return missing

def build_installer():
    """Build the installer using Inno Setup."""
    print("Building installer...")

    # Use the stored ISCC path or find it again
    iscc_path = globals().get('ISCC_PATH') or find_iscc()
    
    if not iscc_path:
        print("✗ Inno Setup Compiler not found.")
        print("  Make sure Inno Setup is installed and ISCC.exe is accessible")
        return False

    # Create supporting files
    create_config_template()
    create_readme()
    create_license()

    # Ensure installer directory exists
    os.makedirs('dist/installer', exist_ok=True)

    try:
        print(f"Using ISCC at: {iscc_path}")
        run_command([iscc_path, 'installer.iss'])
        print("✓ Installer built successfully!")

        # Find and report the installer location
        installer_files = list(Path('dist/installer').glob('*.exe'))
        if installer_files:
            print(f"✓ Installer created: {installer_files[0]}")

        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to build installer: {e}")
        return False