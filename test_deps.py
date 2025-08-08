#!/usr/bin/env python3
import subprocess
import shutil
from pathlib import Path

# Copy the functions from the previous artifact
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
        
        print(f"ISCC return code: {result.returncode}")
        print(f"ISCC output contains 'Inno Setup': {'Inno Setup' in output_text}")
        
        if 'Inno Setup' in output_text and result.returncode == 1:
            print("✓ ISCC executable works correctly")
            return True
        else:
            print(f"✗ ISCC test failed - Return code: {result.returncode}")
            print(f"Output preview: {output_text[:200]}...")
            return False
    except Exception as e:
        print(f"✗ Error testing ISCC: {e}")
        return False

if __name__ == "__main__":
    print("Testing new ISCC finder...")
    print("-" * 40)
    
    iscc_path = find_iscc()
    if iscc_path:
        print(f"\nTesting executable: {iscc_path}")
        test_iscc_executable(iscc_path)
    else:
        print("✗ Could not find ISCC")