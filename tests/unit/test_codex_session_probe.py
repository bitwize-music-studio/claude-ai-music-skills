"""Regression checks for the isolated Codex MCP session probe."""

import importlib
import json
import tempfile
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


@pytest.fixture
def probe(monkeypatch, project_root):
    monkeypatch.syspath_prepend(str(project_root / "tests/e2e"))
    return importlib.import_module("codex_session_resume_check")


@pytest.fixture
def host_app(probe, tmp_path):
    class HostApp:
        def __init__(self):
            self.server = {
                "name": probe.EXPECTED_MCP_SERVER,
                "pluginId": probe.EXPECTED_PLUGIN_ID,
                "tools": {"health_check": {}},
            }
            self.plugin_root = tmp_path / "codex home" / "plugins" / "installed plugin"
            reference = self.plugin_root / "reference"
            reference.mkdir(parents=True)
            (reference / "runtime-compatibility.md").write_text("Runtime guide", encoding="utf-8")
            (reference / "plugin-rules.md").write_text("Plugin rules", encoding="utf-8")

        def request(self, request_id, method, arguments):
            if method == "thread/start":
                return {"thread": {"id": "synthetic-thread"}}
            if method == "mcpServerStatus/list":
                return {"data": [self.server]}
            assert method == "mcpServer/tool/call"
            assert arguments["tool"] == "get_plugin_version"
            return {"content": [{"type": "text", "text": json.dumps({
                "plugin_root": str(self.plugin_root),
            })}]}

    return HostApp()


def test_session_probe_accepts_installed_server(probe, host_app, tmp_path):
    probe.SessionProbe(host_app, tmp_path / "foreign workspace", codex_home=tmp_path / "codex home")


@pytest.mark.parametrize("filename", ["runtime-compatibility.md", "plugin-rules.md"])
def test_session_probe_rejects_missing_workflow_reference(probe, host_app, tmp_path, filename):
    (host_app.plugin_root / "reference" / filename).unlink()
    with pytest.raises(probe.ProbeError, match="Installed plugin is missing"):
        probe.SessionProbe(host_app, tmp_path / "foreign workspace", codex_home=tmp_path / "codex home")


def test_session_probe_rejects_server_from_checkout(probe, host_app, tmp_path):
    host_app.plugin_root = tmp_path / "source checkout"
    with pytest.raises(probe.ProbeError, match="not the copy installed"):
        probe.SessionProbe(host_app, tmp_path / "foreign workspace", codex_home=tmp_path / "codex home")


def test_session_probe_reports_mcp_startup_error(probe, host_app, tmp_path):
    host_app.server = {**host_app.server, "tools": None,
                       "runtimeStatus": "failed", "toolsError": "synthetic launcher missing"}
    with pytest.raises(probe.ProbeError, match="synthetic launcher missing"):
        probe.SessionProbe(host_app, tmp_path / "foreign workspace", codex_home=tmp_path / "codex home")


@pytest.mark.parametrize("directory_name", ["dependency venv", "Alice&Bob", "Alice%TEMP%Bob", "Alice^Bob"])
def test_venv_link_cleanup_preserves_source(probe, tmp_path, directory_name):
    source = tmp_path / directory_name
    source.mkdir()
    marker = source / "dependency.txt"
    marker.write_text("keep the source dependencies", encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="isolated home ", dir=tmp_path) as scratch:
        target = Path(scratch) / "venv"
        probe.link_venv(source, target)
        assert (target / marker.name).samefile(marker)
    assert marker.read_text(encoding="utf-8") == "keep the source dependencies"
