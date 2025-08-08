#!/usr/bin/env python3
"""
Debug script to test ISCC availability
"""

import subprocess
import sys


def test_iscc():
    print("Testing ISCC availability...")
    print(f"Python version: {sys.version}")
    print(f"Platform: {sys.platform}")
    print("-" * 50)

    try:
        print("Attempting to run 'iscc'...")
        result = subprocess.run(['iscc'], capture_output=True, text=True, timeout=10)

        print(f"Return code: {result.returncode}")
        print(f"STDOUT length: {len(result.stdout) if result.stdout else 0}")
        print(f"STDERR length: {len(result.stderr) if result.stderr else 0}")

        if result.stdout:
            print("STDOUT content:")
            print(result.stdout[:500])  # First 500 chars

        if result.stderr:
            print("STDERR content:")
            print(result.stderr[:500])  # First 500 chars

        # Check for success indicators
        success_indicators = [
            b'Inno Setup' in result.stderr.encode() if result.stderr else False,
            b'Inno Setup' in result.stdout.encode() if result.stdout else False,
            'Inno Setup' in result.stderr if result.stderr else False,
            'Inno Setup' in result.stdout if result.stdout else False,
            result.returncode == 1
        ]

        print(f"Success indicators: {success_indicators}")
        print(f"Any success indicator True: {any(success_indicators)}")

        if result.returncode == 1 and ('Inno Setup' in (result.stderr or '') or 'Inno Setup' in (result.stdout or '')):
            print("✓ ISCC appears to be working correctly!")
            return True
        else:
            print("✗ ISCC test failed")
            return False

    except subprocess.TimeoutExpired:
        print("✗ ISCC command timed out")
        return False
    except FileNotFoundError:
        print("✗ ISCC not found (FileNotFoundError)")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False


if __name__ == "__main__":
    test_iscc()