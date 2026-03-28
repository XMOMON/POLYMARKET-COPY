#!/usr/bin/env python3
"""
Auto-sync Polymarket bot code to GitHub.
Commits and pushes if any tracked files have changed.
"""
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Workspace paths
WORKSPACE = Path("/Users/mac/.openclaw/workspace")
REPO_DIR = WORKSPACE / "POLYMARKET-COPY"
TRACKED_FILES = [
    "polymarket_copytrade.py",
    "dashboard.html",
    "copytrade-config.json",
    "README.md",
    "install.sh",
    "requirements.txt",
    "license_check.py",
    "tools/generate_license.py",
    "SELLING.md",
    "auto_sync.py",
]

def git(args):
    """Run git command in repo dir."""
    return subprocess.run(["git"] + args, cwd=REPO_DIR, capture_output=True, text=True)

def has_changes():
    """Check if any tracked files have uncommitted changes."""
    result = git(["status", "--porcelain"])
    if result.returncode != 0:
        print("Git status error:", result.stderr)
        return False
    output = result.stdout
    for f in TRACKED_FILES:
        if f in output:
            return True
    return False

def main():
    print(f"[{datetime.now()}] Checking for changes...")
    if not has_changes():
        print("No changes. Skipping.")
        return 0

    # Stage all tracked files (just in case)
    git(["add"] + TRACKED_FILES)

    # Commit with timestamp message
    commit_msg = f"Auto-update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    result = git(["commit", "-m", commit_msg])
    if "nothing to commit" in result.stdout:
        print("Nothing new to commit.")
        return 0

    # Push
    push = git(["push", "origin", "main"])
    if push.returncode == 0:
        print("✅ Pushed to GitHub automatically:", commit_msg)
        print(push.stdout.strip())
        return 0
    else:
        print("❌ Push failed:", push.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
