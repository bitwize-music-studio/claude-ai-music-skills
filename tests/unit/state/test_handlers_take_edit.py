#!/usr/bin/env python3
"""Unit tests for handlers/take_edit.py — the request that edits one take in place.

    get_edit_request(album, track, take, instruction, take_lyrics)

The tool never talks to Suno. The track-file builder and the album fixture come
from test_handlers_generation.py.

Usage:
    python -m pytest tests/unit/state/test_handlers_take_edit.py -v
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
    LEGACY_KEEPER_ROW,
    _row,
    _run,
    album,
)

from handlers import take_edit as _edit_mod  # noqa: E402

pytestmark = pytest.mark.unit

WORKSPACE_ID = "be7f57b5-0cef-4769-ab0e-44b4861bd895"
LYRICS = (
    "[Verse 1 - soft intimate]\n"
    "Kettle on, the window fogged with morning\n"
    "Paper boats are lined up on the sill\n"
    "Every little plan I made is yawning\n"
    "Waiting for the day to hold still\n"
    "\n"
    "[Chorus - warm lifting]\n"
    "Slow down, slow down, let the hour unfold\n"
    "Slow down, slow down, there's a light to hold\n"
    "\n"
    "[End]"
)


def _edit(take=0, instruction="", take_lyrics="", track_slug="01-first-track"):
    return json.loads(_run(_edit_mod.get_edit_request(
        "test-album", track_slug, take, instruction, take_lyrics,
    )))


def _codes(result, severity=None):
    return [p["code"] for p in result["problems"] if severity is None or p["severity"] == severity]


@pytest.fixture
def song(album):  # noqa: F811
    album(lyrics=LYRICS, log_rows=(_row(1, CLIP_A), _row(2, CLIP_B)))
    return album


# ===========================================================================
# With an instruction
# ===========================================================================


class TestInstruction:
    def test_names_the_song_and_carries_the_instruction(self, song):
        result = _edit(take=2, instruction="drop the synth in the second verse")
        assert result["found"] is True
        assert result["supported"] is True
        assert result["mode"] == "instruction"
        assert result["source"] == {
            "take": 2, "clip_id": CLIP_B, "url": f"https://suno.com/song/{CLIP_B}", "keeper": False,
        }
        assert result["request"] == {
            "reference_audio_ids": [CLIP_B],
            "description": "In First Track, drop the synth in the second verse",
            "model": "v6",
        }
        assert result["changes"] == []
        assert result["problems"] == []

    def test_only_what_an_edit_may_carry_is_sent(self, song):
        """duration, instrumental and vocal_gender make Suno regenerate the whole song."""
        song(lyrics=LYRICS, log_rows=(_row(1, CLIP_A),),
             settings={"Duration": "3:15", "Vocal Gender": "Female", "Max Mode": "On"})
        request = _edit(instruction="redo 0:45 to 1:00 with more energy")["request"]
        assert set(request) == {"reference_audio_ids", "description", "model"}

    def test_the_album_workspace_files_the_edited_takes(self, song):
        song.state["albums"]["test-album"]["suno_workspace"] = {"id": WORKSPACE_ID, "name": "Test Album"}
        assert _edit(take=1, instruction="drop the synth")["request"]["workspace_id"] == WORKSPACE_ID

    def test_an_instruction_that_already_names_the_song_is_left_alone(self, song):
        result = _edit(take=1, instruction="in first track, cut the last chorus")
        assert result["request"]["description"] == "in first track, cut the last chorus"

    def test_whitespace_is_tidied(self, song):
        result = _edit(take=1, instruction="  drop   the\nsynth  ")
        assert result["request"]["description"] == "In First Track, drop the synth"

    @pytest.mark.parametrize("instruction", [
        "make it like https://suno.com/song/4ef71736-b95e-489b-b5ac-1a41badceb08",
        "copy the hook from 4ef71736-b95e-489b-b5ac-1a41badceb08",
        "see suno.com/s/abc for the feel",
    ])
    def test_ids_and_links_are_refused(self, song, instruction):
        """Suno: never put an id or link in the description."""
        result = _edit(take=1, instruction=instruction)
        assert result["supported"] is False
        assert "id_or_link_in_instruction" in _codes(result, "blocking")

    def test_too_long(self, song):
        result = _edit(take=1, instruction="more reverb " * 300)
        assert "description_too_long" in _codes(result, "blocking")

    def test_unknown_or_custom_model_is_left_to_suno(self, song):
        song(lyrics=LYRICS, log_rows=(_row(1, CLIP_A),), settings={"Model": "Custom: my-model"})
        assert "model" not in _edit(instruction="drop the synth")["request"]


# ===========================================================================
# From the Lyrics Box
# ===========================================================================


class TestFromLyrics:
    def test_a_changed_line_becomes_a_change(self, song):
        song(lyrics=LYRICS.replace("Waiting for the day", "Waiting for the tide"),
             log_rows=(_row(1, CLIP_A), _row(2, CLIP_B)))
        result = _edit(take=2, take_lyrics=LYRICS)
        assert result["supported"] is True
        assert result["mode"] == "lyrics"
        assert result["changes"] == [{
            "kind": "change",
            "old": "Waiting for the day to hold still",
            "new": "Waiting for the tide to hold still",
        }]
        assert result["places"] == 1
        assert result["request"]["description"] == (
            'In First Track, change "Waiting for the day to hold still" '
            'to "Waiting for the tide to hold still".'
        )

    def test_a_removed_line_is_cut_and_a_new_line_is_added(self, song):
        new = LYRICS.replace("Every little plan I made is yawning\n", "").replace(
            "Slow down, slow down, there's a light to hold",
            "Slow down, slow down, there's a light to hold\nHold it close",
        )
        song(lyrics=new, log_rows=(_row(1, CLIP_A),))
        result = _edit(take=1, take_lyrics=LYRICS)
        assert result["changes"] == [
            {"kind": "cut", "old": "Every little plan I made is yawning"},
            {"kind": "add", "new": "Hold it close", "after": "Slow down, slow down, there's a light to hold"},
        ]
        description = result["request"]["description"]
        assert 'cut the line "Every little plan I made is yawning"' in description
        assert 'after the line "Slow down, slow down, there\'s a light to hold", add the line "Hold it close"' in description

    def test_a_line_added_at_the_start(self, song):
        song(lyrics=LYRICS.replace("Kettle on,", "Good morning\nKettle on,"), log_rows=(_row(1, CLIP_A),))
        result = _edit(take=1, take_lyrics=LYRICS)
        assert result["changes"] == [{"kind": "add", "new": "Good morning", "after": ""}]
        assert 'add the line "Good morning" at the start' in result["request"]["description"]

    def test_a_line_with_a_double_quote_is_wrapped_in_single_quotes(self, song):
        song(lyrics=LYRICS.replace("Waiting for the day to hold still", 'She said "wait" and held still'),
             log_rows=(_row(1, CLIP_A),))
        description = _edit(take=1, take_lyrics=LYRICS)["request"]["description"]
        assert "to 'She said \"wait\" and held still'" in description

    def test_tags_and_performance_cues_are_not_lyrics(self, song):
        song(lyrics=LYRICS.replace("[Verse 1 - soft intimate]", "[Verse 1 - bold]"), log_rows=(_row(1, CLIP_A),))
        result = _edit(take=1, take_lyrics=LYRICS)
        assert result["supported"] is False
        assert "nothing_to_change" in _codes(result, "blocking")

    def test_identical_lyrics_have_nothing_to_change(self, song):
        result = _edit(take=1, take_lyrics=LYRICS)
        assert "nothing_to_change" in _codes(result, "blocking")
        assert "description" not in result["request"]

    def test_more_than_five_places_warns_that_suno_re_sings_the_song(self, song):
        old = "[Verse]\n" + "\n".join(f"Old line number {n}" for n in range(1, 9))
        new = "[Verse]\n" + "\n".join(f"New line number {n}" for n in range(1, 9))
        song(lyrics=new, log_rows=(_row(1, CLIP_A),))
        result = _edit(take=1, take_lyrics=old)
        assert result["places"] == 8
        assert result["supported"] is True
        assert "edit_rewrites_song" in _codes(result, "warning")

    def test_five_places_do_not_warn(self, song):
        old = "[Verse]\n" + "\n".join(f"Old line number {n}" for n in range(1, 6))
        new = "[Verse]\n" + "\n".join(f"New line number {n}" for n in range(1, 6))
        song(lyrics=new, log_rows=(_row(1, CLIP_A),))
        result = _edit(take=1, take_lyrics=old)
        assert result["places"] == 5
        assert "edit_rewrites_song" not in _codes(result)

    def test_an_instruction_wins_over_the_lyrics(self, song):
        result = _edit(take=1, instruction="drop the synth", take_lyrics="[Verse]\nSomething else")
        assert result["mode"] == "instruction"
        assert result["changes"] == []


# ===========================================================================
# Which take, and refusals
# ===========================================================================


class TestWhichTake:
    def test_the_keeper_is_the_default(self, song):
        song(lyrics=LYRICS, log_rows=(_row(1, CLIP_A), _row(2, CLIP_B, rating="✓")))
        result = _edit(instruction="drop the synth")
        assert result["source"]["take"] == 2
        assert result["source"]["keeper"] is True

    def test_a_single_take_is_the_default(self, song):
        song(lyrics=LYRICS, log_rows=(_row(1, CLIP_A),))
        assert _edit(instruction="drop the synth")["source"]["take"] == 1

    def test_several_undecided_takes_need_a_choice(self, song):
        result = _edit(instruction="drop the synth")
        assert result["supported"] is False
        assert "take_ambiguous" in _codes(result, "blocking")
        assert result["source"] is None
        assert result["request"] == {}

    def test_unknown_take_number(self, song):
        result = _edit(take=7, instruction="drop the synth")
        assert "take_not_found" in _codes(result, "blocking")

    def test_a_legacy_share_link_cannot_be_edited(self, song):
        song(lyrics=LYRICS, log_rows=(LEGACY_KEEPER_ROW,))
        result = _edit(take=1, instruction="drop the synth")
        assert "take_has_no_clip_id" in _codes(result, "blocking")

    def test_no_takes(self, song):
        song(lyrics=LYRICS)
        assert "no_takes" in _codes(_edit(instruction="drop the synth"), "blocking")

    def test_nothing_to_go_on(self, song):
        result = _edit(take=1)
        assert result["supported"] is False
        assert "needs_instruction" in _codes(result, "blocking")

    def test_unknown_track(self, song):
        assert _edit(track_slug="99-missing", instruction="x")["found"] is False
