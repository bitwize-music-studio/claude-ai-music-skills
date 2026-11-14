"""Asking an installed Codex CLI for an image.

Nothing here runs Codex. ``run`` is injected, and the stand-in below behaves the
way the real CLI was observed to behave (codex-cli 0.164.0):

* ``codex exec --json`` prints one JSON event per line, the first of them
  ``{"type": "thread.started", "thread_id": ...}``;
* the built-in image tool saves its PNG under
  ``$CODEX_HOME/generated_images/<thread_id>/``, and the agent then copies it
  to where it was asked to;
* the image is 1254x1254 whatever size is asked for.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.artwork import codex as codex_art  # noqa: E402

THREAD = "01a1c653-e5f0-7132-8a03-86496d1215e9"


def _png(path: Path, size: int = 1254) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (size, size), (30, 120, 130)).save(path, "PNG")


def _events(*agent_messages: str) -> str:
    lines = [{"type": "thread.started", "thread_id": THREAD}, {"type": "turn.started"}]
    lines += [{"type": "item.completed", "item": {"type": "agent_message", "text": m}}
              for m in agent_messages]
    lines.append({"type": "turn.completed", "usage": {"input_tokens": 1}})
    return "\n".join(json.dumps(line) for line in lines) + "\n"


class FakeCodex:
    """Stands in for ``subprocess.run``; records the call and plays one behaviour."""

    def __init__(self, behaviour: str = "copies", codex_home: Path | None = None,
                 returncode: int = 0, stderr: str = "") -> None:
        self.behaviour = behaviour
        self.codex_home = codex_home
        self.returncode = returncode
        self.stderr = stderr
        self.calls: list[dict] = []

    def __call__(self, cmd, **kwargs):
        self.calls.append({"cmd": list(cmd), **kwargs})
        if self.behaviour == "missing":
            raise FileNotFoundError(cmd[0])
        if self.behaviour == "hangs":
            raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout", 0))
        workdir = Path(cmd[cmd.index("-C") + 1])
        filename = next(
            word.rstrip(".") for word in kwargs["input"].split() if word.rstrip(".").endswith(".png")
        )
        if self.behaviour == "copies":
            _png(workdir / filename)
        elif self.behaviour == "forgets to copy":
            assert self.codex_home is not None
            _png(self.codex_home / "generated_images" / THREAD / "exec-1.png")
        elif self.behaviour == "writes text":
            (workdir / filename).write_text("not an image", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, self.returncode, _events("done"), self.stderr)


# ---------------------------------------------------------------------------
# generate_image
# ---------------------------------------------------------------------------


class TestGenerateImage:
    def test_the_image_codex_saves_is_returned_with_its_size(self, tmp_path):
        fake = FakeCodex("copies")
        result = codex_art.generate_image(
            "/bin/codex", "a paper boat at dawn", tmp_path / "candidates", "cover-1.png", run=fake,
        )
        assert result["ok"] is True
        assert result["path"] == str(tmp_path / "candidates" / "cover-1.png")
        assert (result["width"], result["height"]) == (1254, 1254)
        assert result["saved_by"] == "codex"
        assert isinstance(result["seconds"], int)

    def test_the_folder_is_made_if_it_is_not_there(self, tmp_path):
        target_dir = tmp_path / "audio" / "album" / "artwork-candidates"
        codex_art.generate_image("/bin/codex", "p", target_dir, "cover-1.png", run=FakeCodex())
        assert target_dir.is_dir()

    def test_codex_is_run_once_without_a_session_and_boxed_into_the_folder(self, tmp_path):
        fake = FakeCodex()
        codex_art.generate_image("/bin/codex", "p", tmp_path, "cover-1.png", run=fake, timeout=120)
        (call,) = fake.calls
        cmd = call["cmd"]
        assert cmd[:2] == ["/bin/codex", "exec"]
        assert "--ephemeral" in cmd                 # leaves nothing in the user's session list
        assert "--skip-git-repo-check" in cmd       # an audio folder is not a repository
        assert cmd[cmd.index("-s") + 1] == "workspace-write"
        assert cmd[cmd.index("-C") + 1] == str(tmp_path)
        assert "--json" in cmd
        assert call["timeout"] == 120

    def test_the_prompt_travels_on_stdin_not_the_command_line(self, tmp_path):
        """A prompt is prose: quotes, ampersands, newlines. It must not meet a shell."""
        fake = FakeCodex()
        prompt = 'Neon "city" & rain | 100% mood\nsecond line'
        codex_art.generate_image("/bin/codex", prompt, tmp_path, "cover-1.png", run=fake)
        (call,) = fake.calls
        assert call["cmd"][-1] == "-"
        assert not any("Neon" in part for part in call["cmd"])
        assert prompt in call["input"]
        assert "cover-1.png" in call["input"]

    def test_things_to_avoid_are_passed_along(self, tmp_path):
        fake = FakeCodex()
        codex_art.generate_image("/bin/codex", "p", tmp_path, "c.png", avoid="text, watermark", run=fake)
        assert "Avoid: text, watermark" in fake.calls[0]["input"]

    def test_an_image_codex_made_but_did_not_copy_is_fetched(self, tmp_path):
        """The original always lands in CODEX_HOME; the copy is only the agent's last step."""
        home = tmp_path / "codex-home"
        fake = FakeCodex("forgets to copy", codex_home=home)
        result = codex_art.generate_image(
            "/bin/codex", "p", tmp_path / "out", "cover-1.png", run=fake, codex_home=home,
        )
        assert result["ok"] is True
        assert result["saved_by"] == "plugin"
        assert Path(result["path"]).is_file()
        assert (result["width"], result["height"]) == (1254, 1254)

    def test_no_image_at_all_is_an_error_with_what_codex_said(self, tmp_path):
        fake = FakeCodex("nothing", returncode=1, stderr="Error: usage limit reached")
        result = codex_art.generate_image(
            "/bin/codex", "p", tmp_path, "cover-1.png", run=fake, codex_home=tmp_path / "home",
        )
        assert result["ok"] is False
        assert "exit 1" in result["error"]
        assert "usage limit reached" in result["error"]

    def test_a_file_that_is_not_an_image_is_an_error_and_is_removed(self, tmp_path):
        result = codex_art.generate_image(
            "/bin/codex", "p", tmp_path, "cover-1.png", run=FakeCodex("writes text"),
            codex_home=tmp_path / "home",
        )
        assert result["ok"] is False
        assert "not an image" in result["error"]
        assert not (tmp_path / "cover-1.png").exists()

    def test_a_run_that_never_ends_is_an_error(self, tmp_path):
        result = codex_art.generate_image(
            "/bin/codex", "p", tmp_path, "cover-1.png", run=FakeCodex("hangs"), timeout=5,
        )
        assert result["ok"] is False
        assert "5 seconds" in result["error"]

    def test_a_missing_program_is_an_error(self, tmp_path):
        result = codex_art.generate_image("/nope/codex", "p", tmp_path, "c.png", run=FakeCodex("missing"))
        assert result["ok"] is False
        assert "/nope/codex" in result["error"]

    def test_an_existing_file_is_never_overwritten(self, tmp_path):
        _png(tmp_path / "cover-1.png", size=64)
        fake = FakeCodex()
        result = codex_art.generate_image("/bin/codex", "p", tmp_path, "cover-1.png", run=fake)
        assert result["ok"] is False
        assert "already exists" in result["error"]
        assert fake.calls == []

    @pytest.mark.parametrize("name", ["../escape.png", "sub/cover.png", "cover.jpg", ""])
    def test_only_a_plain_png_name_is_accepted(self, tmp_path, name):
        fake = FakeCodex()
        result = codex_art.generate_image("/bin/codex", "p", tmp_path, name, run=fake)
        assert result["ok"] is False
        assert fake.calls == []


# ---------------------------------------------------------------------------
# codex_status
# ---------------------------------------------------------------------------

FEATURES = """\
artifact                                 under development  false
image_generation                         stable             true
multi_agent                              stable             true
"""


def _status_runner(version="codex-cli 0.164.0\n", login="Logged in using ChatGPT\n",
                   features=FEATURES, login_code=0):
    def run(cmd, **kwargs):
        args = cmd[1:]
        if args == ["--version"]:
            return subprocess.CompletedProcess(cmd, 0, version, "")
        if args == ["login", "status"]:
            return subprocess.CompletedProcess(cmd, login_code, "", login)   # printed on stderr
        if args == ["features", "list"]:
            return subprocess.CompletedProcess(cmd, 0, features, "")
        raise AssertionError(cmd)
    return run


class TestCodexStatus:
    def test_a_signed_in_codex_with_image_generation(self):
        status = codex_art.codex_status("/bin/codex", run=_status_runner())
        assert status == {
            "version": "codex-cli 0.164.0", "logged_in": True, "image_generation": True,
        }

    def test_not_signed_in(self):
        status = codex_art.codex_status(
            "/bin/codex", run=_status_runner(login="Not logged in\n", login_code=1))
        assert status["logged_in"] is False

    def test_image_generation_switched_off(self):
        off = FEATURES.replace("stable             true\nmulti", "stable             false\nmulti")
        assert codex_art.codex_status("/bin/codex", run=_status_runner(features=off))["image_generation"] is False

    def test_an_older_codex_that_does_not_list_the_feature(self):
        status = codex_art.codex_status("/bin/codex", run=_status_runner(features="artifact  x  false\n"))
        assert status["image_generation"] is None

    def test_an_answer_it_cannot_read_is_unknown_not_a_guess(self):
        status = codex_art.codex_status("/bin/codex", run=_status_runner(login="???\n"))
        assert status["logged_in"] is None

    def test_a_codex_that_will_not_run(self):
        def run(cmd, **kwargs):
            raise FileNotFoundError(cmd[0])
        assert codex_art.codex_status("/nope", run=run) == {
            "version": "", "logged_in": None, "image_generation": None,
        }

    def test_each_question_has_a_short_deadline(self):
        seen = []

        def run(cmd, **kwargs):
            seen.append(kwargs.get("timeout"))
            return subprocess.CompletedProcess(cmd, 0, "", "")
        codex_art.codex_status("/bin/codex", run=run)
        assert seen and all(t is not None and t <= 30 for t in seen)


# ---------------------------------------------------------------------------
# find_codex
# ---------------------------------------------------------------------------


class TestFindCodex:
    def test_a_configured_path_wins(self, tmp_path):
        exe = tmp_path / "my-codex"
        exe.write_text("#!/bin/sh\n", encoding="utf-8")
        assert codex_art.find_codex(str(exe), which=lambda name: "/usr/bin/codex") == str(exe)

    def test_a_configured_path_that_is_not_there_is_not_trusted(self, tmp_path):
        found = codex_art.find_codex(str(tmp_path / "gone"), which=lambda name: "/usr/bin/codex")
        assert found == "/usr/bin/codex"

    def test_the_path_is_searched(self):
        assert codex_art.find_codex("", which=lambda name: "/opt/bin/codex") == "/opt/bin/codex"

    def test_the_usual_install_folder_is_tried_when_the_path_misses_it(self, tmp_path):
        """An MCP server does not always inherit the shell's PATH."""
        exe = tmp_path / ".local" / "bin" / "codex"
        exe.parent.mkdir(parents=True)
        exe.write_text("#!/bin/sh\n", encoding="utf-8")
        assert codex_art.find_codex("", which=lambda name: None, home=tmp_path) == str(exe)

    def test_nothing_found(self, tmp_path):
        assert codex_art.find_codex("", which=lambda name: None, home=tmp_path) == ""


# ---------------------------------------------------------------------------
# artwork_settings
# ---------------------------------------------------------------------------


class TestArtworkSettings:
    @pytest.mark.parametrize("config", [None, {}, {"artwork": None}, {"artwork": []}, {"artwork": "codex"}])
    def test_the_default_is_manual_with_one_candidate(self, config):
        assert codex_art.artwork_settings(config) == {
            "generator": "manual", "candidates": 1, "codex_path": "",
        }

    def test_codex_can_be_chosen(self):
        settings = codex_art.artwork_settings({"artwork": {"generator": "codex", "candidates": 3}})
        assert settings["generator"] == "codex"
        assert settings["candidates"] == 3

    @pytest.mark.parametrize("written", ["Codex", " codex ", "CODEX"])
    def test_the_generator_is_read_loosely(self, written):
        assert codex_art.artwork_settings({"artwork": {"generator": written}})["generator"] == "codex"

    @pytest.mark.parametrize("bad", ["midjourney", 7, True, ["codex"], None])
    def test_an_unknown_generator_falls_back_to_manual(self, bad):
        assert codex_art.artwork_settings({"artwork": {"generator": bad}})["generator"] == "manual"

    @pytest.mark.parametrize("written, expected", [
        (0, 1), (-2, 1), (1, 1), (4, 4), (9, 4), ("3", 3), ("many", 1), (True, 1), (None, 1), (2.9, 2),
    ])
    def test_candidates_stay_between_one_and_four(self, written, expected):
        assert codex_art.artwork_settings({"artwork": {"candidates": written}})["candidates"] == expected

    @pytest.mark.parametrize("written, expected", [
        ("~/bin/codex", "~/bin/codex"), ("", ""), (None, ""), (42, ""),
    ])
    def test_the_codex_path_is_a_string_or_nothing(self, written, expected):
        assert codex_art.artwork_settings({"artwork": {"codex_path": written}})["codex_path"] == expected
