#!/usr/bin/env python3
"""
Cleanup script to remove unnecessary files from the codebase
"""

import os
import shutil

# Files to remove (old server implementations)
FILES_TO_REMOVE = [
    "app/main.py",
    "app/main_redis.py", 
    "app/mcp_server.py",
    "app/mcp_server_redis.py",
    "app/mcp_server_fastmcp_refactored.py",  # We have the clean version now
    "app/core/tool_registry.py",  # Not used in refactored version
]

# Backup directory
BACKUP_DIR = "backup_removed_files"


def main():
    """Remove unnecessary files with backup"""
    
    # Create backup directory
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
        print(f"✅ Created backup directory: {BACKUP_DIR}")
    
    removed_count = 0
    
    for file_path in FILES_TO_REMOVE:
        if os.path.exists(file_path):
            # Create backup
            backup_path = os.path.join(BACKUP_DIR, os.path.basename(file_path))
            shutil.copy2(file_path, backup_path)
            print(f"📦 Backed up: {file_path} -> {backup_path}")
            
            # Remove file
            os.remove(file_path)
            print(f"🗑️  Removed: {file_path}")
            removed_count += 1
        else:
            print(f"⚠️  Not found: {file_path}")
    
    print(f"\n✅ Cleanup complete! Removed {removed_count} files.")
    print(f"📁 Backups saved in: {BACKUP_DIR}")
    
    # Rename the clean version to be the main one
    if os.path.exists("app/mcp_server_fastmcp_clean.py"):
        if os.path.exists("app/mcp_server_fastmcp.py"):
            # Backup the original
            shutil.copy2("app/mcp_server_fastmcp.py", os.path.join(BACKUP_DIR, "mcp_server_fastmcp_original.py"))
            print(f"📦 Backed up original mcp_server_fastmcp.py")
        
        # Replace with clean version
        os.rename("app/mcp_server_fastmcp_clean.py", "app/mcp_server_fastmcp.py")
        print(f"✨ Replaced mcp_server_fastmcp.py with clean version")


if __name__ == "__main__":
    main()