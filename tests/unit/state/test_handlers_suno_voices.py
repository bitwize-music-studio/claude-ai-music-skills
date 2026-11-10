#!/usr/bin/env python3
"""Unit tests for handlers/suno_voices.py — a saved Suno Voice on a track.

    set_track_voice(album, voice, track) — write the Voice row that
    /bitwize-music:generate reads, adding the block when the track has none

The plugin's server cannot reach Suno, so these tests never touch it: the skill
confirms the Voice exists with Suno's voices-list before it calls the tool.
Reuses the track-file builder and album fixture from test_handlers_generation.py.

Usage:
    python -m pytest tests/unit/state/test_handlers_suno_voices.py -v
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.unit.state.test_handlers_generation import (  # noqa: E402
    _request,
    _run,
    album,  # noqa: F401 - pytest fixture
    track_md,
)

from handlers import suno_voices as _voices_mod  # noqa: E402

pytestmark = pytest.mark.unit

ROOT_CLIP = "7713bc1c-29a6-4df4-9c24-145fbe25b010"
SAVED_FROM = f"https://suno.com/song/{ROOT_CLIP}"
SOURCE = "https://suno.com/song/71af26e1-7ca6-486b-8511-a5a93ddc10df"

TEMPLATE_BLOCK = """## Cover / Voice Setup

### Original Song Reference

*What this cover reworks. Delete this subsection if the track is not a Cover.*

| Attribute | Detail |
|-----------|--------|
| **Cover of** | [Original song, or the prior generation this reworks] |
| **Source audio** | [Song address on Suno, https://suno.com/song/… / uploaded sample e.g. Splice / — ] |
| **Keeps** | [What carries over: topline melody, structure] |
| **Reimagines** | [The new target genre/style the Cover shifts it into] |
| **Audio Influence** | [0–100 — higher hews closer to the source, or to the Voice; shown only when audio is attached] |

### Voice Selection

*The saved Voice applied to this track. Delete this subsection if no Voice is used.*

| Attribute | Detail |
|-----------|--------|
| **Voice** | [Saved Voice name, or —] |
| **Vocal identity** | [What it locks in, e.g. male baritone, gravelly, folk storyteller] |
| **Saved from** | [The generation or recording this Voice was captured from] |

### Cover-Specific Style Guidance

Keep it close to the original.

"""

COVER_ONLY_BLOCK = f"""## Cover / Voice Setup

### Original Song Reference

| Attribute | Detail |
|-----------|--------|
| **Cover of** | Paper Boats |
| **Source audio** | {SOURCE} |

"""


def _with_block(block: str, **kwargs) -> str:
    """A track file with *block* placed where the template puts it."""
    text = track_md(**kwargs)
    return text.replace("## Suno Inputs\n", block + "## Suno Inputs\n", 1)


def _set(voice, track="01-first-track", album_slug="test-album", **kwargs):
    return json.loads(_run(_voices_mod.set_track_voice(album_slug, voice, track, **kwargs)))


def _rows(text: str) -> dict[str, str]:
    """The Voice Selection table's rows, by key."""
    start = text.index("### Voice Selection")
    rows = {}
    for line in text[start:].splitlines()[1:]:
        if line.startswith("#"):
            break
        if line.startswith("| **"):
            key, value = line.strip("| ").split("** |", 1)
            rows[key.strip("* ")] = value.strip(" |")
    return rows


class TestATrackWithoutTheBlock:
    def test_the_block_goes_where_the_template_puts_it(self, album):  # noqa: F811
        result = _set("RTB", saved_from=SAVED_FROM)
        assert result["updated"] == ["01-first-track"]
        text = album.path.read_text(encoding="utf-8")
        assert text.index("## Cover / Voice Setup") < text.index("## Suno Inputs")
        assert text.index("## Concept") < text.index("## Cover / Voice Setup")
        assert _rows(text) == {"Voice": "RTB", "Vocal identity": "—", "Saved from": SAVED_FROM}

    def test_generate_then_sings_in_the_voice(self, album):  # noqa: F811
        """The contract that matters: the generation request names the Voice."""
        assert _request()["voice"] is None
        _set("RTB")
        assert _request()["voice"] == {"name": "RTB"}

    def test_nothing_else_in_the_file_changes(self, album):  # noqa: F811
        before = album.path.read_text(encoding="utf-8")
        _set("RTB")
        after = album.path.read_text(encoding="utf-8")
        added = after.replace(after[after.index("## Cover / Voice Setup"):after.index("## Suno Inputs")], "")
        assert added == before

    def test_a_track_with_no_suno_inputs_gets_it_at_the_end(self, album):  # noqa: F811
        album.path.write_text("# Old Track\n\n## Lyrics\n\nsome words\n", encoding="utf-8")
        _set("RTB")
        text = album.path.read_text(encoding="utf-8")
        assert text.startswith("# Old Track\n\n## Lyrics\n\nsome words\n")
        assert _rows(text)["Voice"] == "RTB"


class TestATrackWithTheBlock:
    def test_the_template_rows_are_filled_in_place(self, album):  # noqa: F811
        album.path.write_text(_with_block(TEMPLATE_BLOCK), encoding="utf-8")
        _set("RTB", saved_from=SAVED_FROM, vocal_identity="male baritone, warm")
        text = album.path.read_text(encoding="utf-8")
        assert text.count("### Voice Selection") == 1
        assert _rows(text) == {
            "Voice": "RTB", "Vocal identity": "male baritone, warm", "Saved from": SAVED_FROM,
        }
        assert "### Original Song Reference" in text
        assert "Keep it close to the original." in text
        assert _request()["kind"] == "song"  # the cover rows are still placeholders

    def test_a_cover_only_block_gains_a_voice_selection(self, album):  # noqa: F811
        album.path.write_text(_with_block(COVER_ONLY_BLOCK), encoding="utf-8")
        _set("RTB")
        text = album.path.read_text(encoding="utf-8")
        assert text.index("### Original Song Reference") < text.index("### Voice Selection")
        assert text.index("### Voice Selection") < text.index("## Suno Inputs")
        request = _request()
        assert request["kind"] == "cover"
        assert request["voice"] == {"name": "RTB"}

    def test_changing_the_voice_clears_what_described_the_old_one(self, album):  # noqa: F811
        album.path.write_text(_with_block(TEMPLATE_BLOCK), encoding="utf-8")
        _set("Mac", saved_from=SAVED_FROM, vocal_identity="gravelly tenor")
        _set("RTB")
        assert _rows(album.path.read_text(encoding="utf-8")) == {
            "Voice": "RTB", "Vocal identity": "—", "Saved from": "—",
        }

    def test_the_same_voice_again_keeps_its_description(self, album):  # noqa: F811
        _set("RTB", saved_from=SAVED_FROM, vocal_identity="male baritone")
        before = album.path.read_text(encoding="utf-8")
        result = _set("rtb")  # Suno's name search ignores case too
        assert result["unchanged"] == ["01-first-track"]
        assert result["updated"] == []
        assert album.path.read_text(encoding="utf-8") == before

    def test_taking_the_voice_off(self, album):  # noqa: F811
        _set("RTB", saved_from=SAVED_FROM)
        result = _set("—")
        assert result["voice"] is None
        assert _rows(album.path.read_text(encoding="utf-8")) == {
            "Voice": "—", "Vocal identity": "—", "Saved from": "—",
        }
        assert _request()["voice"] is None

    def test_taking_it_off_a_track_that_never_had_one_adds_nothing(self, album):  # noqa: F811
        before = album.path.read_text(encoding="utf-8")
        result = _set("—")
        assert result["unchanged"] == ["01-first-track"]
        assert album.path.read_text(encoding="utf-8") == before

    def test_a_heading_inside_the_lyrics_is_not_a_section(self, album):  # noqa: F811
        lyrics = "[Verse 1]\n## Suno Inputs\nNeon rain\n\n[End]"
        album(lyrics=lyrics)
        _set("RTB")
        text = album.path.read_text(encoding="utf-8")
        assert text.count("## Cover / Voice Setup") == 1
        assert text.index("## Cover / Voice Setup") < text.index("### Style Box")


class TestRefusals:
    def test_an_instrumental_track_cannot_take_a_voice(self, album):  # noqa: F811
        album(instrumental_fm="true", instrumental_table="Yes")
        before = album.path.read_text(encoding="utf-8")
        result = _set("RTB")
        assert "instrumental" in result["error"]
        assert album.path.read_text(encoding="utf-8") == before

    @pytest.mark.parametrize("voice", ["", "   ", "A | B", "two\nlines", "x" * 201])
    def test_a_voice_the_table_cannot_hold(self, album, voice):  # noqa: F811
        before = album.path.read_text(encoding="utf-8")
        assert "error" in _set(voice)
        assert album.path.read_text(encoding="utf-8") == before

    def test_a_description_the_table_cannot_hold(self, album):  # noqa: F811
        assert "error" in _set("RTB", saved_from="a | b")

    def test_an_unknown_track(self, album):  # noqa: F811
        assert "error" in _set("RTB", track="09-nope")

    def test_an_unknown_album(self, album):  # noqa: F811
        assert "error" in _set("RTB", album_slug="no-such-album")


class TestTheWholeAlbum:
    @pytest.fixture
    def three_tracks(self, album):  # noqa: F811
        instrumental = album.path.parent / "03-interlude.md"
        instrumental.write_text(
            track_md(title="Interlude", instrumental_fm="true", instrumental_table="Yes"),
            encoding="utf-8",
        )
        album.state["albums"]["test-album"]["tracks"]["03-interlude"] = {
            "title": "Interlude", "status": "In Progress", "path": str(instrumental),
        }
        return album

    def test_every_vocal_track_gets_it_and_the_rest_are_listed(self, three_tracks):
        result = _set("RTB", track="")
        assert result["updated"] == ["01-first-track"]
        assert {s["track"]: s["reason"] for s in result["skipped"]} == {
            "02-no-path": "no track file",
            "03-interlude": "instrumental",
        }
        assert "Cover / Voice Setup" not in (three_tracks.path.parent / "03-interlude.md").read_text(encoding="utf-8")

    def test_taking_it_off_the_album_reaches_instrumentals_too(self, three_tracks):
        """Clearing is always safe, so nothing is skipped for being instrumental."""
        _set("RTB", track="")
        result = _set("—", track="")
        assert result["updated"] == ["01-first-track"]
        assert result["unchanged"] == ["03-interlude"]
