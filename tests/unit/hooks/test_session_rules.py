"""Tests for the ``session_rules`` SessionStart hook and the rules it delivers.

Claude Code never loads a ``CLAUDE.md`` from a plugin's folder, so
``reference/plugin-rules.md``, printed by ``hooks/session_rules.py`` at session
start, is the only way the plugin's standing rules reach a user (#664).

Three things would make that fail silently, and each has a guard here:

- **Size.** Claude Code keeps SessionStart output whole only below 10,000
  characters; longer output is replaced by a 2 KB preview (measured on 2.1.329).
  The rules must fit under the hook's ``LIMIT`` with a long install path filled
  in, or users get a pointer instead of the rules.
- **Scope.** The plugin is installed at user scope, so the hook runs in every
  session on the machine. It must print the rules only inside the music
  workspace, and a sibling folder that merely shares a prefix is not inside.
- **Interpreter.** ``hooks.json`` runs it on the system ``python3``, not the
  venv, so it must stay standard-library only and import on Python 3.9.

Usage:
    python -m pytest tests/unit/hooks/test_session_rules.py -v
"""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_MODULE_PATH = _PROJECT_ROOT / "hooks" / "session_rules.py"
_RULES_PATH = _PROJECT_ROOT / "reference" / "plugin-rules.md"
_spec = importlib.util.spec_from_file_location("session_rules_hook", _MODULE_PATH)
session_rules = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(session_rules)

# A long but realistic install path: a Windows marketplace cache under a long
# user name. Every {plugin_root} in the rules is replaced by this.
_LONG_ROOT = Path(
    "C:/Users/a-rather-long-windows-user-name/.claude/plugins/cache/"
    "bitwize-music-studio-claude-ai-music-skills/bitwize-music/0.199.99"
)

_CONFIG = """\
artist:
  name: "bitwize"   # keep casing

paths:
  # where albums live
  content_root: "{content}"
  audio_root: '{audio}'
  documents_root: {documents}  # no quotes
  overrides: "{content}/overrides"

generation:
  content_root: "/not/a/path/key"
"""


def _config(tmp_path: Path) -> tuple[str, Path, Path, Path]:
    content = tmp_path / "music"
    audio = tmp_path / "audio"
    documents = tmp_path / "docs"
    for folder in (content, audio, documents):
        folder.mkdir()
    text = _CONFIG.format(content=content, audio=audio, documents=documents)
    return text, content, audio, documents


# --- The rules file -----------------------------------------------------------


class TestRulesFile:
    def test_fits_under_the_hook_limit_with_a_long_install_path(self):
        rendered = session_rules.render(_RULES_PATH.read_text(encoding="utf-8"), _LONG_ROOT)
        assert len(rendered) <= session_rules.LIMIT, (
            f"reference/plugin-rules.md renders to {len(rendered)} characters; the hook "
            f"prints it only under {session_rules.LIMIT}. Move detail into a skill or "
            "reference file and link it."
        )

    def test_the_hook_limit_stays_under_claude_codes_cap(self):
        assert session_rules.LIMIT < 10_000

    def test_every_plugin_root_path_it_names_exists(self):
        text = _RULES_PATH.read_text(encoding="utf-8")
        paths = re.findall(r"\{plugin_root\}/([^\s`)]+)", text)
        assert paths, "expected the rules to link reference files"
        missing = [p for p in paths if not (_PROJECT_ROOT / p.rstrip("/.,")).exists()]
        assert missing == []

    def test_every_skill_it_routes_to_exists(self):
        text = _RULES_PATH.read_text(encoding="utf-8")
        routing = text.split("## Workflow and routing", 1)[1].split("\n## ", 1)[0]
        # Backticked names after an arrow; MCP tools (``list_skills``) have underscores.
        names = {n for n in re.findall(r"→ `([a-z0-9_-]+)", routing) if "_" not in n}
        names |= set(re.findall(r"`/bitwize-music:([a-z0-9-]+)", text))
        assert len(names) > 20
        skills = {p.name for p in (_PROJECT_ROOT / "skills").iterdir() if p.is_dir()}
        assert sorted(names - skills) == []

    @pytest.mark.parametrize(
        "rule",
        [
            "/bitwize-music:resume",
            "Never spend Suno credits",
            "Never pick a take",
            "Pronunciation is a hard rule",
            "human source verification comes before generation",
            "/bitwize-music:session-start",
            "A collaborator, not a yes-man",
        ],
    )
    def test_keeps_the_rules_that_must_reach_every_user(self, rule):
        assert rule in _RULES_PATH.read_text(encoding="utf-8")


# --- Reading the config -------------------------------------------------------


class TestWorkspaceRoots:
    def test_reads_the_three_roots_quoted_or_not(self, tmp_path):
        text, content, audio, documents = _config(tmp_path)
        assert session_rules.workspace_roots(text) == [content, audio, documents]

    def test_ignores_the_same_key_outside_paths(self, tmp_path):
        text, *_ = _config(tmp_path)
        assert Path("/not/a/path/key") not in session_rules.workspace_roots(text)

    def test_expands_the_home_folder(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        roots = session_rules.workspace_roots('paths:\n  content_root: "~/music-projects"\n')
        assert roots == [tmp_path / "music-projects"]

    def test_no_paths_block_means_no_roots(self):
        assert session_rules.workspace_roots("artist:\n  name: x\n") == []
        assert session_rules.workspace_roots("") == []


class TestInWorkspace:
    def test_the_root_itself_and_folders_below_it(self, tmp_path):
        root = tmp_path / "music"
        (root / "artists" / "bitwize").mkdir(parents=True)
        assert session_rules.in_workspace(root, [root])
        assert session_rules.in_workspace(root / "artists" / "bitwize", [root])

    def test_a_sibling_sharing_a_prefix_is_outside(self, tmp_path):
        root = tmp_path / "music"
        sibling = tmp_path / "music-other"
        root.mkdir()
        sibling.mkdir()
        assert not session_rules.in_workspace(sibling, [root])

    def test_elsewhere_is_outside(self, tmp_path):
        assert not session_rules.in_workspace(tmp_path / "elsewhere", [tmp_path / "music"])


# --- What the hook prints ----------------------------------------------------


class TestBuildOutput:
    def test_inside_the_workspace_it_prints_the_rules_with_the_root_filled_in(self, tmp_path):
        text, content, *_ = _config(tmp_path)
        out = session_rules.build_output(content, text, _PROJECT_ROOT)
        assert out.startswith("# bitwize-music: rules for every session")
        assert "{plugin_root}" not in out
        assert f"{_PROJECT_ROOT.as_posix()}/reference/SKILL_INDEX.md" in out

    def test_in_the_audio_root_too(self, tmp_path):
        text, _, audio, _ = _config(tmp_path)
        assert "Never spend Suno credits" in session_rules.build_output(audio, text, _PROJECT_ROOT)

    def test_outside_the_workspace_it_prints_only_the_pointer(self, tmp_path):
        text, *_ = _config(tmp_path)
        out = session_rules.build_output(tmp_path / "some-repo", text, _PROJECT_ROOT)
        assert out.startswith("The bitwize-music plugin is installed")
        assert f"{_PROJECT_ROOT.as_posix()}/reference/plugin-rules.md" in out
        assert len(out) < 500

    def test_without_a_config_it_says_the_plugin_is_not_set_up(self, tmp_path):
        out = session_rules.build_output(tmp_path, None, _PROJECT_ROOT)
        assert "not set up yet" in out
        assert "/bitwize-music:configure" in out
        assert "outside the music workspace" not in out
        assert f"{_PROJECT_ROOT.as_posix()}/reference/plugin-rules.md" in out
        assert len(out) < 500

    def test_a_config_naming_no_workspace_is_not_set_up_either(self, tmp_path):
        out = session_rules.build_output(tmp_path, "artist:\n  name: x\n", _PROJECT_ROOT)
        assert "not set up yet" in out

    def test_with_a_workspace_set_the_pointer_says_outside(self, tmp_path):
        text, *_ = _config(tmp_path)
        out = session_rules.build_output(tmp_path / "elsewhere", text, _PROJECT_ROOT)
        assert "outside the music workspace" in out
        assert "not set up yet" not in out

    def test_rules_too_long_to_survive_fall_back_to_the_pointer(self, tmp_path):
        text, content, *_ = _config(tmp_path)
        fake_root = tmp_path / "plugin"
        (fake_root / "reference").mkdir(parents=True)
        (fake_root / "reference" / "plugin-rules.md").write_text(
            "x" * (session_rules.LIMIT + 1), encoding="utf-8"
        )
        out = session_rules.build_output(content, text, fake_root)
        assert out.startswith("The bitwize-music plugin is installed")

    def test_a_missing_rules_file_falls_back_to_the_pointer(self, tmp_path):
        text, content, *_ = _config(tmp_path)
        out = session_rules.build_output(content, text, tmp_path / "no-plugin-here")
        assert out.startswith("The bitwize-music plugin is installed")


class TestSessionCwd:
    def test_takes_cwd_from_the_hook_input(self, tmp_path):
        assert session_rules.session_cwd(json.dumps({"cwd": str(tmp_path)})) == tmp_path

    @pytest.mark.parametrize("stdin", ["", "not json", "[]", '{"cwd": 3}'])
    def test_falls_back_to_the_process_cwd(self, stdin):
        assert session_rules.session_cwd(stdin) == Path.cwd()


# --- Running it as Claude Code does ----------------------------------------


def _run(tmp_path: Path, cwd: Path, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["HOME"] = str(tmp_path)
    env["USERPROFILE"] = str(tmp_path)
    env["CLAUDE_PLUGIN_ROOT"] = str(_PROJECT_ROOT)
    payload = stdin if stdin is not None else json.dumps(
        {"hook_event_name": "SessionStart", "source": "startup", "cwd": str(cwd)}
    )
    return subprocess.run(  # noqa: S603 - fixed interpreter and script path
        [sys.executable, str(_MODULE_PATH)],
        input=payload,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        timeout=30,
        check=False,
    )


class TestAsAHook:
    def _write_config(self, tmp_path: Path) -> Path:
        text, content, *_ = _config(tmp_path)
        (tmp_path / ".bitwize-music").mkdir()
        (tmp_path / ".bitwize-music" / "config.yaml").write_text(text, encoding="utf-8")
        return content

    def test_prints_the_rules_inside_the_workspace(self, tmp_path):
        content = self._write_config(tmp_path)
        result = _run(tmp_path, content / "artists")
        assert result.returncode == 0
        assert result.stdout.startswith("# bitwize-music: rules for every session")
        assert len(result.stdout) < 10_000

    def test_prints_the_pointer_elsewhere(self, tmp_path):
        self._write_config(tmp_path)
        result = _run(tmp_path, tmp_path / "another-repo")
        assert result.returncode == 0
        assert result.stdout.startswith("The bitwize-music plugin is installed")

    def test_with_no_config_it_says_the_plugin_is_not_set_up(self, tmp_path):
        result = _run(tmp_path, tmp_path)
        assert result.returncode == 0
        assert "not set up yet" in result.stdout

    @pytest.mark.parametrize("stdin", ["", "{not json", "\x00\x01"])
    def test_bad_input_never_fails_the_session(self, tmp_path, stdin):
        result = _run(tmp_path, tmp_path, stdin=stdin)
        assert result.returncode == 0
        assert result.stderr == ""


class TestRegistration:
    def test_hooks_json_runs_it_on_start_clear_and_compaction(self):
        hooks = json.loads((_PROJECT_ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
        entries = hooks["hooks"]["SessionStart"]
        commands = [h["command"] for e in entries for h in e["hooks"]]
        assert "python3 ${CLAUDE_PLUGIN_ROOT}/hooks/session_rules.py" in commands
        matchers = {m for e in entries for m in e.get("matcher", "").split("|")}
        assert {"startup", "resume", "clear", "compact"} <= matchers


class TestSystemPython:
    def test_imports_only_the_standard_library(self):
        tree = ast.parse(_MODULE_PATH.read_text(encoding="utf-8"))
        modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.add(node.module.split(".")[0])
        stdlib = set(sys.stdlib_module_names) | {"__future__"}
        assert modules - stdlib == set()

    def test_defers_annotations_for_python_3_9(self):
        # ``str | None`` in a signature raises TypeError at import on 3.9 unless
        # annotations are deferred; the same bug once silenced validate_track.
        tree = ast.parse(_MODULE_PATH.read_text(encoding="utf-8"))
        first = next(n for n in tree.body if not isinstance(n, ast.Expr))
        assert isinstance(first, ast.ImportFrom) and first.module == "__future__"
        assert any(a.name == "annotations" for a in first.names)
