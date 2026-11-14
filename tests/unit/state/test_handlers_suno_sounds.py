#!/usr/bin/env python3
"""Unit tests for handlers/suno_sounds.py — the request for a sound effect or a loop.

    get_sound_request(album, description, loop, fit_track, title)

The tool never talks to Suno. The track-file builder and the album fixture come
from test_handlers_generation.py.

Usage:
    python -m pytest tests/unit/state/test_handlers_suno_sounds.py -v
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.unit.state.test_handlers_generation import (  # noqa: F401  (album is a fixture)
    _run,
    album,
)

from handlers import suno_sounds as _sounds_mod  # noqa: E402

pytestmark = pytest.mark.unit

WORKSPACE = {"id": "be7f57b5-0cef-4769-ab0e-44b4861bd895", "name": "Test Album"}


def _sound(description="soft rain on a window", loop=False, fit_track="", title="",
           album_slug="test-album"):
    return json.loads(_run(_sounds_mod.get_sound_request(
        album_slug, description, loop, fit_track, title,
    )))


def _codes(result, severity=None):
    return [p["code"] for p in result["problems"] if severity is None or p["severity"] == severity]


class TestRequest:
    def test_a_one_shot(self, album):  # noqa: F811
        result = _sound("a single soft door knock")
        assert result["found"] is True and result["supported"] is True
        assert result["tool"] == "sounds-create"
        assert result["request"] == {"description": "a single soft door knock", "loop": False}
        assert (result["sounds"], result["credits"]) == (2, 2)
        assert result["fit"] is None
        sounds_dir = album.audio_dir / "sounds"
        assert result["save"] == {
            "dir": str(sounds_dir),
            "files": [
                str(sounds_dir / "a-single-soft-door-knock-1.wav"),
                str(sounds_dir / "a-single-soft-door-knock-2.wav"),
            ],
        }
        assert result["problems"] == []

    def test_a_titled_loop(self, album):  # noqa: F811
        result = _sound("soft rain on a window, gentle and steady", loop=True, title="Window Rain")
        assert result["request"] == {
            "description": "soft rain on a window, gentle and steady", "loop": True,
            "title": "Window Rain",
        }
        assert result["save"]["files"][0].endswith("window-rain-1.wav")

    def test_whitespace_is_tidied(self, album):  # noqa: F811
        assert _sound("  rain\n on  tin ")["request"]["description"] == "rain on tin"

    def test_a_long_description_makes_a_short_file_name(self, album):  # noqa: F811
        name = Path(_sound("thunder " * 40)["save"]["files"][0]).name
        assert len(name) <= 48 + len("-1.wav") and name.startswith("thunder-thunder")

    @pytest.mark.parametrize("description", ["", "   "])
    def test_a_description_is_needed(self, album, description):  # noqa: F811
        result = _sound(description)
        assert _codes(result, "blocking") == ["needs_description"]
        assert result["supported"] is False and result["request"] == {}

    def test_a_description_without_letters_still_names_a_file(self, album):  # noqa: F811
        assert _sound("!!!")["save"]["files"][0].endswith("sound-1.wav")

    def test_limits(self, album):  # noqa: F811
        assert _codes(_sound("x" * 501), "blocking") == ["description_too_long"]
        assert _codes(_sound("rain", title="t" * 257), "blocking") == ["title_too_long"]
        assert _sound("x" * 500)["supported"] is True

    def test_the_workspace_is_reported_not_sent(self, album):  # noqa: F811
        """sounds-create takes no workspace: the skill files the sounds afterwards."""
        album.state["albums"]["test-album"]["suno_workspace"] = WORKSPACE
        result = _sound("rain")
        assert result["workspace"] == WORKSPACE
        assert "workspace_id" not in result["request"]

    def test_no_workspace(self, album):  # noqa: F811
        assert _sound("rain")["workspace"] is None

    def test_unknown_album(self, album):  # noqa: F811
        assert _sound("rain", album_slug="nope")["found"] is False


class TestFitToATrack:
    def test_tempo_and_key_come_from_the_track(self, album):  # noqa: F811
        album(style="Indie folk in G major at 96 BPM, fingerpicked acoustic guitar")
        result = _sound("fingerpicked acoustic guitar pattern", loop=True, fit_track="01")
        assert result["request"] == {
            "description": "fingerpicked acoustic guitar pattern", "loop": True,
            "tempo": 96, "key": "G",
        }
        assert result["fit"] == {"track_slug": "01-first-track", "tempo": 96, "key": "G"}
        assert result["problems"] == []

    @pytest.mark.parametrize("style,key", [
        ("Dark trap in A minor, 140 BPM", "Am"),
        ("Soul ballad, key of Bb minor, 70 BPM", "A#m"),
        ("Synthwave, F# major, 110 BPM", "F#"),
        ("Jazz trio in Db major at 120 BPM", "C#"),
        ("Folk, key of D, 96 BPM", "D"),
        ("Folk, key: Em, 96 BPM", "Em"),
        ("Chamber pop in E♭ minor at 80 BPM", "D#m"),
        ("Ambient in C♯ minor, 60 BPM", "C#m"),
        ("Hymn in Cb major at 60 BPM", "B"),
        ("Rock anthem, 120 BPM", None),
        ("a major label sound, 120 BPM", None),
        ("A blues shuffle in minor, 96 BPM", None),
    ])
    def test_keys(self, album, style, key):  # noqa: F811
        album(style=style)
        result = _sound("bass loop", loop=True, fit_track="01")
        assert result["request"].get("key") == key
        assert result["fit"]["key"] == key

    def test_a_tempo_range_uses_its_middle(self, album):  # noqa: F811
        album(style="Dark trap, 130-140 BPM, 808s")
        assert _sound("hi-hat loop", loop=True, fit_track="01")["request"]["tempo"] == 135

    def test_a_track_that_names_neither(self, album):  # noqa: F811
        album(style="Indie folk, fingerpicked acoustic guitar")
        result = _sound("guitar loop", loop=True, fit_track="01")
        assert "tempo" not in result["request"] and "key" not in result["request"]
        assert _codes(result, "warning") == ["nothing_to_fit"]
        assert result["supported"] is True

    def test_unknown_track(self, album):  # noqa: F811
        assert _sound("loop", loop=True, fit_track="99-missing")["found"] is False
