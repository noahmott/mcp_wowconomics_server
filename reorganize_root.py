#!/usr/bin/env python3
"""
Reorganize the root directory structure for better organization
"""

import os
import shutil
from pathlib import Path

# Directory structure for reorganization
REORGANIZATION_PLAN = {
    # Move test files to tests directory
    "test_mcp_tools.py": "tests/test_mcp_tools.py",
    
    # Move cleanup script to scripts
    "cleanup_codebase.py": "scripts/cleanup_codebase.py",
    
    # Move deployment files to deployment directory
    "DEPLOY_TO_HEROKU.txt": "docs/deployment/DEPLOY_TO_HEROKU.md",
    "app.json": "deployment/app.json",
    "heroku.yml": "deployment/heroku.yml",
    "Procfile": "deployment/Procfile",
    
    # Database file to data directory
    "wowguild.db": "data/wowguild.db",
    
    # Remove unnecessary file
    "nul": None,  # Delete this
}

# Directories to create
NEW_DIRECTORIES = [
    "deployment",
    "scripts",
    "docs/deployment",
]

# Files to update references in
UPDATE_REFERENCES = {
    "README.md": [
        ("DEPLOY_TO_HEROKU.txt", "docs/deployment/DEPLOY_TO_HEROKU.md"),
        ("test_mcp_tools.py", "tests/test_mcp_tools.py"),
    ]
}


def create_directories():
    """Create new directory structure"""
    for dir_path in NEW_DIRECTORIES:
        os.makedirs(dir_path, exist_ok=True)
        print(f"Created directory: {dir_path}")


def move_files():
    """Move files according to reorganization plan"""
    moved_count = 0
    deleted_count = 0
    
    for src, dst in REORGANIZATION_PLAN.items():
        if os.path.exists(src):
            if dst is None:
                # Delete the file
                os.remove(src)
                print(f"Deleted: {src}")
                deleted_count += 1
            else:
                # Create destination directory if needed
                dst_dir = os.path.dirname(dst)
                if dst_dir:
                    os.makedirs(dst_dir, exist_ok=True)
                
                # Move the file
                try:
                    shutil.move(src, dst)
                    print(f"Moved: {src} -> {dst}")
                    moved_count += 1
                except PermissionError:
                    print(f"Warning: Could not move {src} (file in use)")
                except Exception as e:
                    print(f"Error moving {src}: {e}")
        else:
            print(f"Not found: {src}")
    
    return moved_count, deleted_count


def update_file_references():
    """Update references in files"""
    for file_path, replacements in UPDATE_REFERENCES.items():
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            for old_ref, new_ref in replacements:
                content = content.replace(old_ref, new_ref)
            
            if content != original_content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"Updated references in: {file_path}")


def create_deployment_readme():
    """Create a README for the deployment directory"""
    readme_content = """# Deployment Configuration

This directory contains all deployment-related files for the WoW Guild MCP Server.

## Files:

- `Procfile` - Heroku process configuration
- `heroku.yml` - Heroku build configuration
- `app.json` - Heroku app manifest

## Deployment Instructions:

See [DEPLOY_TO_HEROKU.md](../docs/deployment/DEPLOY_TO_HEROKU.md) for detailed deployment instructions.
"""
    
    with open("deployment/README.md", "w") as f:
        f.write(readme_content)
    print("Created deployment/README.md")


def create_scripts_readme():
    """Create a README for the scripts directory"""
    readme_content = """# Scripts

Utility scripts for maintaining and managing the codebase.

## Available Scripts:

- `cleanup_codebase.py` - Remove old/unnecessary files with backup
- `reorganize_root.py` - Reorganize root directory structure

## Usage:

```bash
python scripts/cleanup_codebase.py
```
"""
    
    with open("scripts/README.md", "w") as f:
        f.write(readme_content)
    print("Created scripts/README.md")


def clean_up_tests_directory():
    """Organize the tests directory better"""
    # Move Redis-specific tests to their own subdirectory (already done)
    # Just create a README
    tests_readme = """# Tests

Test suite for the WoW Guild MCP Server.

## Test Organization:

- `test_refactored_tools.py` - Comprehensive test suite for all tools
- `quick_test_tools.py` - Quick testing utility for individual tools
- `test_config.py` - Test configuration and scenarios
- `redis/` - Redis-specific tests
- `test_character_*.py` - Character API tests

## Running Tests:

### Quick Test:
```bash
python tests/quick_test_tools.py
```

### Comprehensive Test:
```bash
python tests/test_refactored_tools.py
```

### Test Specific Tool:
```bash
python tests/quick_test_tools.py guild  # Test guild tools
python tests/quick_test_tools.py item   # Test item tools
```
"""
    
    with open("tests/README.md", "w") as f:
        f.write(tests_readme)
    print("Created tests/README.md")


def main():
    """Main reorganization function"""
    print("Starting root directory reorganization...")
    print("=" * 60)
    
    # Create new directories
    create_directories()
    
    # Move files
    moved, deleted = move_files()
    
    # Update file references
    update_file_references()
    
    # Create README files
    create_deployment_readme()
    create_scripts_readme()
    clean_up_tests_directory()
    
    # Move this script itself to scripts directory
    if os.path.exists("reorganize_root.py"):
        shutil.move("reorganize_root.py", "scripts/reorganize_root.py")
        print(f"Moved reorganize_root.py to scripts/")
        moved += 1
    
    print("=" * 60)
    print(f"Reorganization complete!")
    print(f"Moved: {moved} files")
    print(f"Deleted: {deleted} files")
    print(f"Created: 3 README files")
    
    print("\nNew structure:")
    print("  - deployment/ - Deployment configuration files")
    print("  - scripts/ - Utility scripts")
    print("  - tests/ - All test files")
    print("  - docs/ - All documentation")
    print("  - app/ - Main application code")
    print("  - config/ - Configuration files")
    print("  - data/ - Data files")


if __name__ == "__main__":
    main()