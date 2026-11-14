#!/usr/bin/env python3
"""Unit tests for handlers/take_extend.py — the request that carries a take on.

    get_extension_request(album, track, take, continue_at, from_section)

The tool never talks to Suno. The track-file builder and the album fixture come
from test_handlers_generation.py.

Usage:
    python -m pytest tests/unit/state/test_handlers_take_extend.py -v
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
    CLIP_A,
    CLIP_B,
    DEFAULT_STYLE,
    LEGACY_KEEPER_ROW,
    _row,
    _run,
    _setup_block,
    _write_with,
    album,
)

from handlers import take_extend as _extend_mod  # noqa: E402

pytestmark = pytest.mark.unit

WORKSPACE_ID = "be7f57b5-0cef-4769-ab0e-44b4861bd895"
VERSE_2_ON = (
    "[Verse 2 - soft intimate]\n"
    "Steam is rising, tracing little circles\n"
    "Paper sails are drifting on the pane\n"
    "\n"
    "[Chorus - warm lifting]\n"
    "Slow down, slow down, let the hour unfold\n"
    "\n"
    "[Outro - fading]\n"
    "Slow down\n"
    "\n"
    "[End]"
)
LYRICS = (
    "[Verse 1 - soft intimate]\n"
    "Kettle on, the window fogged with morning\n"
    "Paper boats are lined up on the sill\n"
    "\n"
    "[Chorus - warm lifting]\n"
    "Slow down, slow down, let the hour unfold\n"
    "\n"
) + VERSE_2_ON
LOG = (
    _row(1, CLIP_A, notes="0:52, via MCP, 10 credits"),
    _row(2, CLIP_B, notes="0:55, via MCP, 10 credits"),
)


def _extend(take=0, continue_at="", from_section="", track_slug="01-first-track"):
    return json.loads(_run(_extend_mod.get_extension_request(
        "test-album", track_slug, take, continue_at, from_section,
    )))


def _codes(result, severity=None):
    return [p["code"] for p in result["problems"] if severity is None or p["severity"] == severity]


@pytest.fixture
def song(album):  # noqa: F811
    album(lyrics=LYRICS, log_rows=LOG)
    return album


class TestRequest:
    def test_carries_on_from_a_time_with_the_named_section(self, song):
        result = _extend(take=2, continue_at="0:46", from_section="Verse 2")
        assert result["found"] is True
        assert result["supported"] is True
        assert result["tool"] == "audio-extensions-create"
        assert result["source"] == {
            "take": 2, "clip_id": CLIP_B, "url": f"https://suno.com/song/{CLIP_B}",
            "keeper": False, "version": "", "duration_s": 55,
        }
        assert (result["continue_at_s"], result["continue_at"]) == (46.0, "0:46")
        assert result["from_section"] == "Verse 2"
        assert result["request"] == {
            "id": CLIP_B,
            "continue_at": 46.0,
            "lyrics": VERSE_2_ON,
            "style": DEFAULT_STYLE,
            "negative_style": "choir, crowd vocals",
            "model": "v6",
            "max_mode": True,
            "controls": {"variety": 0, "weirdness": 0.5, "style_influence": 0.5},
        }
        assert result["needs_grant"] == [
            "controls.weirdness", "controls.style_influence", "negative_style",
        ]
        assert result["join"] == {"tool": "audio-full-song", "credits": 0}
        assert result["log_notes"] == "take 2 extended from 0:46"
        assert result["problems"] == []

    def test_cost_doubles_with_max_mode(self, song):
        assert _extend(take=2, continue_at="46", from_section="Verse 2")["credits"] == 20
        song(lyrics=LYRICS, log_rows=LOG, settings={"Max Mode": "Off"})
        result = _extend(take=2, continue_at="46", from_section="Verse 2")
        assert result["credits"] == 10 and "max_mode" not in result["request"]

    def test_only_what_an_extension_takes_is_sent(self, song):
        """No vocal gender (the tool has none), no duration (it would cap the ending) and
        no title (the continuation takes its source's)."""
        song(lyrics=LYRICS, log_rows=LOG, settings={"Duration": "3:15", "Vocal Gender": "Female"})
        request = _extend(take=1, continue_at="40", from_section="Verse 2")["request"]
        assert not {"vocal_gender", "duration", "title", "instrumental"} & set(request)

    def test_the_album_workspace_files_the_continuations(self, song):
        song.state["albums"]["test-album"]["suno_workspace"] = {"id": WORKSPACE_ID, "name": "T"}
        result = _extend(take=1, continue_at="40", from_section="Verse 2")
        assert result["request"]["workspace_id"] == WORKSPACE_ID

    def test_a_voice_is_passed_on_for_the_skill_to_resolve(self, song):
        _write_with(song, _setup_block(voice="RTB", influence="75"), lyrics=LYRICS, log_rows=LOG)
        result = _extend(take=1, continue_at="40", from_section="Verse 2")
        assert result["voice"] == {"name": "RTB"}
        # On an extension audio_influence means likeness to the source take, not to the Voice.
        assert "audio_influence" not in result["request"]["controls"]
        assert "controls.audio_influence" not in result["needs_grant"]

    def test_a_cover_track_extends_like_any_other(self, song):
        """The cover source is where the take came from; it plays no part in carrying it on."""
        _write_with(song, _setup_block(source="Splice sample, uploaded by hand"),
                    lyrics=LYRICS, log_rows=LOG)
        result = _extend(take=1, continue_at="40", from_section="Verse 2")
        assert result["supported"] is True and result["request"]["id"] == CLIP_A

    def test_style_problems_stop_the_request(self, song):
        song(lyrics=LYRICS, log_rows=LOG, style=None)
        result = _extend(take=1, continue_at="40", from_section="Verse 2")
        assert result["supported"] is False
        assert "style_missing" in _codes(result, "blocking")


class TestContinueAt:
    @pytest.mark.parametrize("given,seconds,shown", [
        ("46", 46.0, "0:46"), ("46.5", 46.5, "0:46"), ("0:46", 46.0, "0:46"),
        ("0:46.5", 46.5, "0:46"), (" 0:09 ", 9.0, "0:09"), ("0.4", 0.4, "0:00"),
    ])
    def test_seconds_or_minutes_and_seconds(self, song, given, seconds, shown):
        result = _extend(take=2, continue_at=given, from_section="Verse 2")
        assert result["supported"] is True
        assert (result["continue_at_s"], result["continue_at"]) == (seconds, shown)
        assert result["request"]["continue_at"] == seconds

    def test_the_time_is_needed(self, song):
        result = _extend(take=2, from_section="Verse 2")
        assert result["supported"] is False and result["request"] == {}
        assert _codes(result, "blocking") == ["needs_continue_at"]

    @pytest.mark.parametrize("given", ["soon", "1:75", "-5", "1:2:3"])
    def test_an_unreadable_time(self, song, given):
        assert _codes(_extend(take=2, continue_at=given, from_section="Verse 2"), "blocking") == [
            "continue_at_unrecognized",
        ]

    def test_too_early(self, song):
        assert _codes(_extend(take=2, continue_at="0.2", from_section="Verse 2"), "blocking") == [
            "continue_at_too_early",
        ]

    def test_past_the_end_of_the_take(self, song):
        result = _extend(take=2, continue_at="2:00", from_section="Verse 2")
        assert _codes(result, "blocking") == ["continue_at_past_end"]
        assert "0:55" in result["problems"][0]["detail"]

    def test_a_take_of_unknown_length_is_not_second_guessed(self, song):
        song(lyrics=LYRICS, log_rows=(_row(1, CLIP_A),))
        assert _extend(continue_at="2:00", from_section="Verse 2")["supported"] is True

    def test_end_means_the_whole_take(self, song):
        result = _extend(take=2, continue_at="end", from_section="Verse 2")
        assert result["supported"] is True
        assert result["continue_at_s"] == 55.0
        assert _codes(result, "warning") == ["continue_from_end"]

    def test_end_needs_a_known_length(self, song):
        song(lyrics=LYRICS, log_rows=(_row(1, CLIP_A),))
        assert _codes(_extend(continue_at="end", from_section="Verse 2"), "blocking") == [
            "take_length_unknown",
        ]


class TestSections:
    def test_the_sections_are_listed_in_order(self, song):
        assert _extend(take=1, continue_at="40")["sections"] == [
            "Verse 1", "Chorus #1", "Verse 2", "Chorus #2", "Outro", "End",
        ]

    @pytest.mark.parametrize("wanted", ["verse 2", "[Verse 2]", "  VERSE 2 ", "[Verse 2 - soft intimate]"])
    def test_a_section_is_matched_loosely(self, song, wanted):
        result = _extend(take=1, continue_at="40", from_section=wanted)
        assert result["from_section"] == "Verse 2"
        assert result["request"]["lyrics"] == VERSE_2_ON

    def test_a_repeated_section_needs_its_number(self, song):
        result = _extend(take=1, continue_at="40", from_section="Chorus")
        assert _codes(result, "blocking") == ["section_ambiguous"]
        assert "Chorus #2" in result["problems"][0]["detail"]

    def test_a_numbered_section(self, song):
        result = _extend(take=1, continue_at="40", from_section="chorus #2")
        assert result["from_section"] == "Chorus #2"
        assert result["request"]["lyrics"].startswith("[Chorus - warm lifting]\nSlow down")
        assert result["request"]["lyrics"].count("[Chorus") == 1
        assert result["request"]["lyrics"].endswith("[End]")

    @pytest.mark.parametrize("wanted", ["Bridge", "Chorus #3", "Verse 2 #2"])
    def test_an_unknown_section(self, song, wanted):
        result = _extend(take=1, continue_at="40", from_section=wanted)
        assert _codes(result, "blocking") == ["section_not_found"]
        assert "Verse 2" in result["problems"][0]["detail"]

    def test_without_a_section_suno_writes_on_by_itself(self, song):
        result = _extend(take=1, continue_at="40")
        assert result["supported"] is True
        assert "lyrics" not in result["request"]
        assert _codes(result, "warning") == ["no_section_named"]

    def test_an_instrumental_needs_no_section(self, song):
        song(instrumental_fm="true", instrumental_table="Yes", lyrics="[Intro]\n\n[End]", log_rows=LOG)
        result = _extend(take=1, continue_at="40")
        assert result["supported"] is True and result["problems"] == []
        assert "lyrics" not in result["request"]


class TestWhichTake:
    def test_the_keeper_is_the_default(self, song):
        song(lyrics=LYRICS, log_rows=(_row(1, CLIP_A, "✓", notes="0:52, via MCP"), _row(2, CLIP_B)))
        assert _extend(continue_at="40", from_section="Verse 2")["source"]["take"] == 1

    def test_several_undecided_takes_need_a_choice(self, song):
        assert _codes(_extend(continue_at="40", from_section="Verse 2"), "blocking") == [
            "take_ambiguous",
        ]

    def test_a_legacy_share_link_cannot_be_extended(self, song):
        song(lyrics=LYRICS, log_rows=(LEGACY_KEEPER_ROW,))
        assert "take_has_no_clip_id" in _codes(
            _extend(take=1, continue_at="40", from_section="Verse 2"), "blocking")

    def test_a_version_is_not_extended(self, song):
        song(lyrics=LYRICS, log_rows=(
            _row(1, CLIP_A, "✓"),
            _row(2, CLIP_B, notes="0:55, instrumental version of take 1, via MCP, 10 credits"),
        ))
        assert _codes(_extend(take=2, continue_at="40"), "blocking") == ["source_is_a_version"]

    def test_a_spoken_track_is_not_extended(self, song):
        _write_with(song, spoken=True, lyrics=LYRICS, log_rows=LOG)
        assert "extension_not_for_speech" in _codes(
            _extend(take=1, continue_at="40", from_section="Verse 2"), "blocking")

    def test_no_takes(self, album):  # noqa: F811
        assert _codes(_extend(continue_at="40"), "blocking") == ["no_takes"]

    def test_unknown_track(self, song):
        assert _extend(track_slug="99-missing", continue_at="40")["found"] is False
