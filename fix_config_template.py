#!/usr/bin/env python3
"""
Script to create a proper config template with default settings only
"""

import json
import os
from pathlib import Path

def create_default_config_template():
    """Create config template with only default settings."""
    # Default configuration with 'admin' password hash
    default_config = {
        "app_password_hash": "d74ff0ee8da3b9806b18c877dbf29bbde50b5bd8e4dad7a3a725000feb82e8f1",
        "database_pairs": [],
        "log_level": "INFO",
        "auto_start": False,
        "default_sync_interval": 300,
        "max_log_size": 10,
        "backup_enabled": True
    }

    # Write to config.json.template (this is what the installer will use)
    template_path = Path('config.json.template')
    with open(template_path, 'w', encoding='utf-8') as f:
        json.dump(default_config, f, indent=4)
    
    print(f"✓ Created fresh config template: {template_path}")
    print("  Password: 'admin'")
    print("  Database pairs: empty")
    return str(template_path)

def backup_existing_config():
    """Backup your existing config.json so you don't lose your settings."""
    config_path = Path('config.json')
    if config_path.exists():
        backup_path = Path('config.json.backup')
        
        # Create backup
        import shutil
        shutil.copy2(config_path, backup_path)
        print(f"✓ Backed up existing config to: {backup_path}")
        return str(backup_path)
    else:
        print("  No existing config.json found")
        return None

def verify_template():
    """Verify the template has correct default values."""
    template_path = Path('config.json.template')
    if not template_path.exists():
        print("✗ Template file not found!")
        return False
    
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # Verify key settings
        checks = [
            (config.get('app_password_hash') == 'd74ff0ee8da3b9806b18c877dbf29bbde50b5bd8e4dad7a3a725000feb82e8f1', 
             "Password hash matches 'admin'"),
            (config.get('database_pairs') == [], "Database pairs is empty"),
            (config.get('log_level') == 'INFO', "Log level is INFO"),
            (config.get('auto_start') == False, "Auto start is disabled"),
            (config.get('default_sync_interval') == 300, "Sync interval is 300"),
            (config.get('max_log_size') == 10, "Max log size is 10"),
            (config.get('backup_enabled') == True, "Backup is enabled")
        ]
        
        print("\nTemplate verification:")
        all_good = True
        for check, description in checks:
            if check:
                print(f"✓ {description}")
            else:
                print(f"✗ {description}")
                all_good = False
        
        return all_good
        
    except Exception as e:
        print(f"✗ Error reading template: {e}")
        return False

if __name__ == "__main__":
    print("Creating fresh config template for installer...")
    print("=" * 50)
    
    # Backup existing config if it exists
    backup_existing_config()
    
    # Create fresh template with defaults
    template_path = create_default_config_template()
    
    # Verify the template
    if verify_template():
        print("\n✓ Config template is ready for installer!")
        print(f"  Template file: {template_path}")
        print("  New installations will get clean default settings")
    else:
        print("\n✗ Config template has issues!")
