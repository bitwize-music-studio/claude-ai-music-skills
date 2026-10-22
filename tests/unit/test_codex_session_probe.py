"""Regression checks for model evidence attribution and session persistence."""

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


def tool_event(tool, arguments=None):
    return {"type": "item.completed", "item": {
        "type": "mcp_tool_call", "tool": tool, "arguments": arguments or {},
        "status": "completed", "error": None,
    }}


def answer_event(answer):
    return {"type": "item.completed", "item": {"type": "agent_message", "text": answer}}


def run_model_stub(probe, monkeypatch, home, mode):
    """Run both model turns with synthetic CLI events and real temporary state."""
    state_file = home / ".bitwize-music/cache/state.json"
    state_file.parent.mkdir(parents=True)
    session = {"last_album": probe.ALBUM, "last_phase": "Source Verification", "updated_at": "before"}
    state_file.write_text(json.dumps({"session": session}), encoding="utf-8")
    arguments = {"album": probe.ALBUM, "phase": "Source Verification"}
    required = [tool_event(tool) for tool in ("get_session", "find_album", "get_album_progress", "list_tracks")]
    recommendation = answer_event("Probe Album: $bitwize-music:verify-sources")
    # Startup has all the old checker's evidence; resume must still stand alone.
    startup = [tool_event("health_check", {"runtime": "codex"}), *required,
               tool_event("update_session", arguments), recommendation]
    if mode == "startup_health_missing":
        startup = startup[1:]
    resume = [*required, tool_event("update_session", arguments), recommendation]
    if mode == "no_resume":
        resume = [answer_event("I cannot resume the album or update the session.")]
    elif mode == "borrowed_recommendation":
        resume[-1] = answer_event("Resume completed.")
    elif mode == "clear":
        resume[-2] = tool_event("update_session", {"clear": True})

    turns = iter([startup, resume])
    started = []

    class FakeProcess:
        pid = 9999999
        returncode = 0

        def __init__(self, *args, **kwargs):
            self.events = next(turns)
            started.append(args[0])

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def communicate(self, timeout):
            if len(started) == 2 and mode != "unchanged":
                saved = {**session, "updated_at": "after"}
                if mode == "wrong_album":
                    saved["last_album"] = "another-album"
                elif mode == "wrong_phase":
                    saved["last_phase"] = "Writing"
                state_file.write_text(json.dumps({"session": saved}), encoding="utf-8")
            return "\n".join(json.dumps(e) for e in self.events), ""

        def wait(self):
            return 0

        def poll(self):
            return 0

    monkeypatch.setattr(probe.subprocess, "Popen", FakeProcess)
    monkeypatch.setattr(probe.os, "killpg", lambda *args: None, raising=False)
    probe.check_model("fake-codex", home, {"HOME": str(home), "CODEX_HOME": str(home)}, home)
    return started


@pytest.mark.parametrize("mode, message", [
    ("no_resume", "Resume missed workflow tools"),
    ("borrowed_recommendation", "Resume missed album/source gate"),
    ("clear", "Resume did not update the expected album and phase"),
    ("unchanged", "Resume session update was not persisted"),
    ("wrong_album", "Resume persisted the wrong album or phase"),
    ("wrong_phase", "Resume persisted the wrong album or phase"),
    ("startup_health_missing", "Startup did not select Codex health diagnostics"),
])
def test_model_probe_rejects_invalid_turn_evidence(probe, monkeypatch, tmp_path, mode, message):
    with pytest.raises(probe.ProbeError, match=message):
        run_model_stub(probe, monkeypatch, tmp_path, mode)


def test_model_probe_accepts_independent_resume_and_saved_update(probe, monkeypatch, tmp_path):
    started = run_model_stub(probe, monkeypatch, tmp_path, "success")
    assert len(started) == 2
    assert probe.read_saved_session(tmp_path)["updated_at"] == "after"


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


def test_session_probe_rejects_server_from_checkout(probe, host_app, tmp_path):
    host_app.plugin_root = tmp_path / "source checkout"
    with pytest.raises(probe.ProbeError, match="not the copy installed"):
        probe.SessionProbe(host_app, tmp_path / "foreign workspace", codex_home=tmp_path / "codex home")


def test_session_probe_reports_mcp_startup_error(probe, host_app, tmp_path):
    host_app.server = {**host_app.server, "tools": None,
                       "runtimeStatus": "failed", "toolsError": "synthetic launcher missing"}
    with pytest.raises(probe.ProbeError, match="synthetic launcher missing"):
        probe.SessionProbe(host_app, tmp_path / "foreign workspace", codex_home=tmp_path / "codex home")


def test_venv_link_cleanup_preserves_source(probe, tmp_path):
    source = tmp_path / "dependency venv"
    source.mkdir()
    marker = source / "dependency.txt"
    marker.write_text("keep the source dependencies", encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="isolated home ", dir=tmp_path) as scratch:
        target = Path(scratch) / "venv"
        probe.link_venv(source, target)
        assert (target / marker.name).samefile(marker)
    assert marker.read_text(encoding="utf-8") == "keep the source dependencies"
