#!/usr/bin/env python3
"""
Unit tests for the cross-platform venv-path helper.

Usage:
    python -m pytest tests/unit/shared/test_venv.py -v
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.shared.venv import venv_dir, venv_python


@pytest.mark.unit
class TestVenvDir:
    """Tests for venv_dir()."""

    def test_default_home(self):
        """With no override, resolves under Path.home()."""
        result = venv_dir()
        assert result == Path.home() / ".bitwize-music" / "venv"

    def test_home_override(self, tmp_path):
        """With home= override, resolves under the given path."""
        result = venv_dir(home=tmp_path)
        assert result == tmp_path / ".bitwize-music" / "venv"


@pytest.mark.unit
class TestVenvPython:
    """Tests for venv_python()."""

    @pytest.mark.parametrize(
        "platform, parent, filename",
        [
            ("win32", "Scripts", "python.exe"),
            ("linux", "bin", "python3"),
            ("darwin", "bin", "python3"),
        ],
    )
    def test_platform_specific_path(self, monkeypatch, platform, parent, filename):
        """venv_python() picks the right interpreter path per sys.platform."""
        monkeypatch.setattr(sys, "platform", platform)
        result = venv_python()
        assert result.name == filename
        assert result.parent.name == parent
        assert result == Path.home() / ".bitwize-music" / "venv" / parent / filename

    def test_checks_platform_at_call_time(self, monkeypatch):
        """sys.platform is read inside the function, not cached at import time."""
        monkeypatch.setattr(sys, "platform", "linux")
        assert venv_python().name == "python3"

        monkeypatch.setattr(sys, "platform", "win32")
        assert venv_python().name == "python.exe"

    def test_home_override(self, tmp_path, monkeypatch):
        """With home= override, resolves under the given path."""
        monkeypatch.setattr(sys, "platform", "linux")
        result = venv_python(home=tmp_path)
        assert result == tmp_path / ".bitwize-music" / "venv" / "bin" / "python3"

    def test_home_override_windows(self, tmp_path, monkeypatch):
        """home= override also applies on the win32 branch."""
        monkeypatch.setattr(sys, "platform", "win32")
        result = venv_python(home=tmp_path)
        assert result == tmp_path / ".bitwize-music" / "venv" / "Scripts" / "python.exe"
