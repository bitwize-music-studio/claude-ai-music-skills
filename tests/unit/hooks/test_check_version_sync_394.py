"""Regression tests for issue #394.

``check_version_sync`` opened ``plugin.json`` / ``marketplace.json`` with a bare
``open()`` (the platform-default text encoding) and only caught
``(json.JSONDecodeError, OSError)``. A ``UnicodeDecodeError`` — a ``ValueError``
subclass, not an ``OSError`` or ``JSONDecodeError`` — raised while decoding a
manifest that is not valid in the active encoding therefore escaped
``check_sync()`` and, since ``main()`` does not wrap it, crashed the hook with a
traceback. These tests lock in graceful degradation: an undecodable manifest
degrades to ``[]`` and valid manifests (including valid UTF-8 with accents)
still parse.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

# Import the standalone hook module via importlib (hooks/ is not a package).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

_MODULE_PATH = _PROJECT_ROOT / "hooks" / "check_version_sync.py"
_spec = importlib.util.spec_from_file_location("check_version_sync_394", _MODULE_PATH)
check_version_sync = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_version_sync)


# A lone 0xE9 byte is cp1252 'é' but an invalid UTF-8 sequence (bare lead byte),
# i.e. exactly the "author name with an accent saved in a non-UTF-8 encoding"
# scenario from the issue.
_NON_UTF8_PLUGIN = b'{"version": "0.94.0", "author": "Jos\xe9"}'
_NON_UTF8_MARKETPLACE = b'{"plugins": [{"version": "0.94.0", "name": "Jos\xe9"}]}'


def _manifest_dir(tmp_path: Path) -> Path:
    d = tmp_path / ".claude-plugin"
    d.mkdir()
    return d


def _event(file_path: Path) -> dict:
    return {"tool_input": {"file_path": str(file_path)}}


def _write_plugin(d: Path, version: str) -> Path:
    p = d / "plugin.json"
    p.write_text(json.dumps({"version": version}), encoding="utf-8")
    return p


def _write_marketplace(d: Path, version: str) -> Path:
    p = d / "marketplace.json"
    p.write_text(json.dumps({"plugins": [{"version": version}]}), encoding="utf-8")
    return p


def test_non_utf8_plugin_manifest_returns_cleanly(tmp_path):
    """A non-UTF-8 plugin.json must degrade to [] instead of raising."""
    d = _manifest_dir(tmp_path)
    plugin = d / "plugin.json"
    plugin.write_bytes(_NON_UTF8_PLUGIN)
    _write_marketplace(d, "0.94.0")

    # Under the bug this raised UnicodeDecodeError out of check_sync().
    assert check_version_sync.check_sync(_event(plugin)) == []


def test_non_utf8_marketplace_manifest_returns_cleanly(tmp_path):
    """The second open() (marketplace.json) must degrade cleanly too."""
    d = _manifest_dir(tmp_path)
    plugin = _write_plugin(d, "0.94.0")
    (d / "marketplace.json").write_bytes(_NON_UTF8_MARKETPLACE)

    assert check_version_sync.check_sync(_event(plugin)) == []


def test_valid_matching_versions_returns_empty(tmp_path):
    """Valid, in-sync manifests still parse and report no issues."""
    d = _manifest_dir(tmp_path)
    plugin = _write_plugin(d, "0.94.0")
    _write_marketplace(d, "0.94.0")

    assert check_version_sync.check_sync(_event(plugin)) == []


def test_valid_utf8_accented_author_parses(tmp_path):
    """Valid UTF-8 content with an accent must parse regardless of locale."""
    d = _manifest_dir(tmp_path)
    plugin = d / "plugin.json"
    plugin.write_text(
        json.dumps({"version": "0.94.0", "author": "José"}, ensure_ascii=False),
        encoding="utf-8",
    )
    _write_marketplace(d, "0.94.0")

    assert check_version_sync.check_sync(_event(plugin)) == []


def test_valid_mismatched_versions_reports(tmp_path, monkeypatch):
    """A genuine version mismatch is still detected after the fix."""
    d = _manifest_dir(tmp_path)
    plugin = _write_plugin(d, "0.94.0")
    _write_marketplace(d, "0.93.0")

    # Deterministically take the "other file not mid-edit" branch: pretend the
    # working tree has no other pending manifest edit.
    def _fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

    monkeypatch.setattr(check_version_sync.subprocess, "run", _fake_run)

    issues = check_version_sync.check_sync(_event(plugin))
    assert len(issues) == 1
    assert "0.94.0" in issues[0]
    assert "0.93.0" in issues[0]


def test_hook_main_does_not_crash_on_non_utf8_manifest(tmp_path):
    """End-to-end: the hook process exits 0 with no traceback, not a crash."""
    d = _manifest_dir(tmp_path)
    plugin = d / "plugin.json"
    plugin.write_bytes(_NON_UTF8_PLUGIN)
    _write_marketplace(d, "0.94.0")

    payload = json.dumps({"tool_input": {"file_path": str(plugin)}})
    result = subprocess.run(
        [sys.executable, str(_MODULE_PATH)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert "Traceback" not in result.stderr, result.stderr
    assert result.returncode == 0, (result.returncode, result.stderr)
