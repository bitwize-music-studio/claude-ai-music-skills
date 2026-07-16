"""Locate the user-level plugin venv (~/.bitwize-music/venv) cross-platform."""

import sys
from pathlib import Path


def venv_dir(home: Path | None = None) -> Path:
    """Return the plugin venv directory (~/.bitwize-music/venv)."""
    return (home or Path.home()) / ".bitwize-music" / "venv"


def venv_python(home: Path | None = None) -> Path:
    """Return the venv's Python interpreter path (platform-specific)."""
    d = venv_dir(home)
    if sys.platform == "win32":
        return d / "Scripts" / "python.exe"
    return d / "bin" / "python3"
