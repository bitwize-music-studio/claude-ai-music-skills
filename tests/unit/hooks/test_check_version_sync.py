"""Tests for hooks/check_version_sync.py."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

_MODULE_PATH = _PROJECT_ROOT / "hooks" / "check_version_sync.py"
_spec = importlib.util.spec_from_file_location("check_version_sync", _MODULE_PATH)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


@pytest.mark.unit
class TestCheckSyncEncoding:
    """#394: manifest files must be read as UTF-8, and decode failures must
    not raise past check_sync (only JSONDecodeError/OSError were caught)."""

    def _plugin_dir(self, tmp_path):
        plugin_dir = tmp_path / ".claude-plugin"
        plugin_dir.mkdir()
        return plugin_dir

    def test_utf8_manifest_content_is_read_correctly(self, tmp_path):
        """A non-ASCII (but valid UTF-8) version string must not be mangled
        by falling back to a platform default encoding."""
        plugin_dir = self._plugin_dir(tmp_path)
        (plugin_dir / "plugin.json").write_text(
            json.dumps({"version": "1.0.0-café"}), encoding="utf-8"
        )
        (plugin_dir / "marketplace.json").write_text(
            json.dumps({"plugins": [{"version": "1.0.0-café"}]}), encoding="utf-8"
        )
        data = {"tool_input": {"file_path": str(plugin_dir / "plugin.json")}}
        assert mod.check_sync(data) == []

    def test_non_utf8_manifest_does_not_raise(self, tmp_path):
        """A manifest file with bytes invalid in UTF-8 must be treated as
        unreadable (empty issue list), not raise UnicodeDecodeError."""
        plugin_dir = self._plugin_dir(tmp_path)
        # 0xff is not valid UTF-8 anywhere in a byte stream.
        (plugin_dir / "plugin.json").write_bytes(b'{"version": "1.0.0-\xff"}')
        (plugin_dir / "marketplace.json").write_text(
            json.dumps({"plugins": [{"version": "1.0.0"}]}), encoding="utf-8"
        )
        data = {"tool_input": {"file_path": str(plugin_dir / "plugin.json")}}
        assert mod.check_sync(data) == []
