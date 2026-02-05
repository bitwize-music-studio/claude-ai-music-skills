#!/usr/bin/env python3
"""
Cross-platform wrapper for MCP server that uses venv if available.

Priority order:
1. ~/.bitwize-music/venv/bin/python3 (or python.exe on Windows)
2. python3 (system/user install)

Works on Linux, macOS, Windows, and WSL.
"""
import os
import subprocess
import sys
from pathlib import Path

# Get the directory containing this script
SCRIPT_DIR = Path(__file__).parent
SERVER_PY = SCRIPT_DIR / "server.py"

# Check for venv (platform-specific paths)
HOME = Path.home()
VENV_DIR = HOME / ".bitwize-music" / "venv"

if sys.platform == "win32":
    # Windows: Scripts/python.exe
    VENV_PYTHON = VENV_DIR / "Scripts" / "python.exe"
else:
    # Linux/macOS/WSL: bin/python3
    VENV_PYTHON = VENV_DIR / "bin" / "python3"

# Use venv if it exists, otherwise fall back to current Python
if VENV_PYTHON.exists():
    python_cmd = str(VENV_PYTHON)
else:
    python_cmd = sys.executable

# Set CLAUDE_PLUGIN_ROOT if not already set (derive from file location)
if "CLAUDE_PLUGIN_ROOT" not in os.environ:
    plugin_root = SCRIPT_DIR.parent.parent
    os.environ["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)

# Execute the server with the selected Python
sys.exit(subprocess.call([python_cmd, str(SERVER_PY)] + sys.argv[1:]))
