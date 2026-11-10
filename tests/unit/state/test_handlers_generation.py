#!/usr/bin/env python3
"""Unit tests for handlers/generation.py — the Suno MCP bridge tools.

    get_generation_request(album, track)  — track file -> audio-create payload
    log_generation(album, track, ...)     — append takes to the Generation Log
    get_suno_import_plan(album, track)    — keeper clip id + import target paths

None of these tools talks to Suno, so every test runs against a temp track
file and a mock state cache. Follows the fixture style of
test_handlers_content.py.

Usage:
    python -m pytest tests/unit/state/test_handlers_generation.py -v
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SERVER_PATH = PROJECT_ROOT / "servers" / "bitwize-music-server" / "server.py"

# ---------------------------------------------------------------------------
# Mock MCP SDK if not installed (same pattern as test_handlers_content.py)
# ---------------------------------------------------------------------------

try:
    import mcp.server.fastmcp  # noqa: F401
except ImportError:

    class _FakeFastMCP:
        def __init__(self, name="", **kwargs):
            self.name = name
            self._tools = {}

        def tool(self):
            def decorator(fn):
                self._tools[fn.__name__] = fn
                return fn
            return decorator

        def run(self, transport="stdio"):
            pass

    mcp_mod = types.ModuleType("mcp")
    mcp_server_mod = types.ModuleType("mcp.server")
    mcp_fastmcp_mod = types.ModuleType("mcp.server.fastmcp")
    mcp_fastmcp_mod.FastMCP = _FakeFastMCP
    mcp_mod.server = mcp_server_mod
    mcp_server_mod.fastmcp = mcp_fastmcp_mod
    sys.modules["mcp"] = mcp_mod
    sys.modules["mcp.server"] = mcp_server_mod
    sys.modules["mcp.server.fastmcp"] = mcp_fastmcp_mod


def _import_server():
    spec = importlib.util.spec_from_file_location("state_server_generation", SERVER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


server = _import_server()

from handlers import _shared as _shared_mod  # noqa: E402
from handlers import generation as _gen_mod  # noqa: E402


def _run(coro):
    return asyncio.run(coro)


class MockStateCache:
    def __init__(self, state):
        self._state = state

    def get_state(self):
        return self._state

    def get_state_ref(self):
        return self._state or {}


# ---------------------------------------------------------------------------
# Track file builder
# ---------------------------------------------------------------------------

DEFAULT_STYLE = (
    "Male baritone, gritty. Alternative rock, clean electric guitar, tight drums. "
    "Modern production."
)
DEFAULT_LYRICS = (
    "[Verse 1 - calm]\nNeon rain on the boulevard tonight\n\n"
    "[Chorus - big]\nHold the line\n\n[End]"
)
DEFAULT_SETTINGS = {
    "Model": "v6",
    "Variety": "Off",
    "Max Mode": "On",
    "Vocal Gender": "Male",
    "Duration": "Auto",
    "Weirdness": "50",
    "Style Influence": "50",
}
PLACEHOLDER_ROW = "| — | — | — | — | — | — |"
CLIP_A = "4ef71736-b95e-489b-b5ac-1a41badceb08"
CLIP_B = "6455b9ea-f786-4769-ac20-a2eb3eb49fee"


def _code(body):
    return "" if body is None else f"```\n{body}\n```\n"


def track_md(
    *,
    title="First Track",
    instrumental_fm="false",
    instrumental_table="No",
    style=DEFAULT_STYLE,
    exclude="choir, crowd vocals",
    lyrics=DEFAULT_LYRICS,
    settings=None,
    log_rows=(PLACEHOLDER_ROW,),
    suno_link="—",
    status="In Progress",
):
    """A realistic track file. ``settings=False`` drops the Generation Settings
    section; ``log_rows=None`` drops the Generation Log section entirely."""
    if settings is False:
        settings_block = ""
    else:
        rows = dict(DEFAULT_SETTINGS)
        rows.update(settings or {})
        table = "\n".join(f"| **{k}** | {v} |" for k, v in rows.items())
        settings_block = (
            "### Generation Settings\n\n| Setting | Value |\n|---------|-------|\n"
            f"{table}\n\n"
        )
    if log_rows is None:
        log_block = ""
    else:
        table = "\n".join(log_rows)
        log_block = (
            "## Generation Log\n\n"
            "Mark keepers with ✓ in the Rating column.\n\n"
            "| # | Date | Model | Result | Notes | Rating |\n"
            "|---|------|-------|--------|-------|--------|\n"
            f"{table}\n\n"
            "<!-- OPTIONAL: SoundCloud Waveform Art -->\n\n"
        )
    return (
        "---\n"
        f'title: "{title}"\n'
        "track_number: 1\n"
        f"instrumental: {instrumental_fm}\n"
        "explicit: false\n"
        'suno_url: ""\n'
        "---\n\n"
        f"# {title}\n\n"
        "## Track Details\n\n"
        "| Attribute | Detail |\n|-----------|--------|\n"
        "| **Track #** | 01 |\n"
        f"| **Title** | {title} |\n"
        f"| **Status** | {status} |\n"
        f"| **Suno Link** | {suno_link} |\n"
        "| **Stems** | No |\n"
        f"| **Instrumental** | {instrumental_table} |\n"
        "| **Explicit** | No |\n"
        "| **Sources Verified** | N/A |\n\n"
        "## Concept\n\nA test track.\n\n"
        "## Suno Inputs\n\n"
        f"### Style Box\n*Copy this into Suno's \"Style of Music\" field:*\n\n{_code(style)}\n"
        f"### Exclude Styles\n\n{_code(exclude)}\n"
        f"{settings_block}"
        f"### Lyrics Box\n\n{_code(lyrics)}\n"
        "## Streaming Lyrics\n\n```\nNeon rain on the boulevard tonight\n```\n\n"
        f"{log_block}"
        "## Waveform Art\n\n### ChatGPT Prompt\n\n```\nGenerate a wide cinematic image.\n```\n"
    )


@pytest.fixture
def album(tmp_path, monkeypatch):
    """One album with one track on disk + a mock cache. Returns a helper that
    (re)writes the track file and hands back its path."""
    album_dir = tmp_path / "content" / "album"
    tracks_dir = album_dir / "tracks"
    tracks_dir.mkdir(parents=True)
    track_path = tracks_dir / "01-first-track.md"
    track_path.write_text(track_md(), encoding="utf-8")

    state = {
        "config": {
            "content_root": str(tmp_path / "content"),
            "audio_root": str(tmp_path / "audio"),
            "artist_name": "testartist",
        },
        "albums": {
            "test-album": {
                "title": "Test Album",
                "genre": "electronic",
                "path": str(album_dir),
                "tracks": {
                    "01-first-track": {
                        "title": "First Track",
                        "status": "In Progress",
                        "path": str(track_path),
                    },
                    "02-no-path": {"title": "No Path", "status": "Not Started", "path": ""},
                },
            },
        },
    }
    monkeypatch.setattr(_shared_mod, "cache", MockStateCache(state))
    monkeypatch.setattr(_gen_mod, "write_state", MagicMock())

    def write(**kwargs):
        track_path.write_text(track_md(**kwargs), encoding="utf-8")
        return track_path

    write.path = track_path
    write.state = state
    write.audio_dir = tmp_path / "audio" / "artists" / "testartist" / "albums" / "electronic" / "test-album"
    return write


def _request(album_slug="test-album", track_slug="01-first-track"):
    return json.loads(_run(_gen_mod.get_generation_request(album_slug, track_slug)))


def _codes(result, severity=None):
    return [
        p["code"] for p in result["problems"]
        if severity is None or p["severity"] == severity
    ]


# ===========================================================================
# get_generation_request
# ===========================================================================


class TestGetGenerationRequest:
    def test_vocal_track_maps_every_setting(self, album):
        result = _request()
        assert result["found"] is True
        assert result["supported"] is True
        assert result["track_slug"] == "01-first-track"
        assert result["track_status"] == "In Progress"
        assert result["request"] == {
            "title": "First Track",
            "style": DEFAULT_STYLE,
            "lyrics": DEFAULT_LYRICS,
            "negative_style": "choir, crowd vocals",
            "model": "v6",
            "max_mode": True,
            "vocal_gender": "male",
            "controls": {"weirdness": 0.5, "style_influence": 0.5},
        }
        assert result["needs_grant"] == ["controls", "negative_style", "vocal_gender"]
        assert result["ignored"] == []
        assert result["problems"] == []

    def test_track_number_prefix_resolves(self, album):
        assert _request(track_slug="01")["track_slug"] == "01-first-track"

    @pytest.mark.parametrize("exclude", ["(none)", "[exclusions, if any]", "—", None])
    def test_no_exclusions_omits_negative_style(self, album, exclude):
        album(exclude=exclude)
        result = _request()
        assert "negative_style" not in result["request"]
        assert "negative_style" not in result["needs_grant"]

    def test_no_prefixed_exclusions_are_sent_bare_with_a_warning(self, album):
        """Tracks written before 0.102.0 list exclusions as 'no drums'. The field
        is already the negation, so 'no drums' there asks for the opposite."""
        album(exclude="no drums, No electric guitar,\nno autotune")
        result = _request()
        assert result["request"]["negative_style"] == "drums, electric guitar, autotune"
        assert "negative_style_no_prefix" in _codes(result, "warning")
        assert result["supported"] is True

    def test_bare_exclusions_raise_no_warning(self, album):
        result = _request()
        assert result["request"]["negative_style"] == "choir, crowd vocals"
        assert "negative_style_no_prefix" not in _codes(result)

    def test_only_a_leading_no_is_a_negation(self, album):
        """'no wave' is a genre, and 'no' inside a word is not a prefix."""
        album(exclude="no wave, nose flute, piano solo, no drums")
        assert _request()["request"]["negative_style"] == "no wave, nose flute, piano solo, drums"

    def test_instrumental_keeps_tag_lyrics_and_drops_vocal_gender(self, album):
        tags = "[Intro]\n\n[Main Theme]\n\n[Outro]\n\n[End]"
        album(instrumental_fm="true", instrumental_table="Yes", lyrics=tags)
        result = _request()
        assert result["supported"] is True
        assert result["request"]["instrumental"] is True
        assert result["request"]["lyrics"] == tags
        assert "vocal_gender" not in result["request"]

    def test_instrumental_without_lyrics_box_is_supported(self, album):
        album(instrumental_fm="true", instrumental_table="Yes", lyrics=None)
        result = _request()
        assert result["supported"] is True
        assert "lyrics" not in result["request"]

    def test_instrumental_mismatch_blocks(self, album):
        album(instrumental_fm="true", instrumental_table="No")
        result = _request()
        assert result["supported"] is False
        assert "instrumental_mismatch" in _codes(result, "blocking")

    def test_custom_model_is_unsupported(self, album):
        album(settings={"Model": "Custom: bitwize-house"})
        result = _request()
        assert result["supported"] is False
        assert "custom_model_unsupported" in _codes(result, "blocking")
        assert "model" not in result["request"]

    def test_unrecognized_model_blocks(self, album):
        album(settings={"Model": "V5"})
        result = _request()
        assert result["supported"] is False
        assert "model_unrecognized" in _codes(result, "blocking")

    def test_missing_generation_settings_warns_and_uses_defaults(self, album):
        album(settings=False)
        result = _request()
        assert result["supported"] is True
        assert "generation_settings_missing" in _codes(result, "warning")
        for key in ("model", "controls", "max_mode", "vocal_gender", "duration"):
            assert key not in result["request"]

    @pytest.mark.parametrize(
        "cell,expected,warned",
        [("3:15", 195, False), ("0:10", 15, True), ("7:00", 360, True)],
    )
    def test_duration_is_seconds_clamped_to_api_range(self, album, cell, expected, warned):
        album(settings={"Duration": cell})
        result = _request()
        assert result["request"]["duration"] == expected
        assert ("duration_clamped" in _codes(result, "warning")) is warned

    def test_auto_duration_is_omitted(self, album):
        assert "duration" not in _request()["request"]

    def test_sliders_convert_to_fractions(self, album):
        album(settings={"Weirdness": "35", "Style Influence": "80"})
        assert _request()["request"]["controls"] == {"weirdness": 0.35, "style_influence": 0.8}

    def test_unset_and_bad_sliders(self, album):
        album(settings={"Weirdness": "—", "Style Influence": "loud"})
        result = _request()
        assert "controls" not in result["request"]
        assert "controls" not in result["needs_grant"]
        assert "style_influence_unrecognized" in _codes(result, "warning")

    def test_slider_above_100_is_clamped(self, album):
        album(settings={"Weirdness": "150"})
        result = _request()
        assert result["request"]["controls"]["weirdness"] == 1.0
        assert "weirdness_clamped" in _codes(result, "warning")

    def test_max_mode_off_is_omitted(self, album):
        album(settings={"Max Mode": "Off"})
        assert "max_mode" not in _request()["request"]

    def test_variety_above_off_is_reported_as_ignored(self, album):
        album(settings={"Variety": "High"})
        ignored = _request()["ignored"]
        assert [i["setting"] for i in ignored] == ["Variety"]
        assert ignored[0]["value"] == "High"

    def test_missing_style_blocks(self, album):
        album(style=None)
        result = _request()
        assert result["supported"] is False
        assert "style_missing" in _codes(result, "blocking")

    def test_template_style_blocks(self, album):
        album(style="[genre], [tempo/BPM], [mood], [vocal description], [instruments], [production notes]")
        assert "style_placeholder" in _codes(_request(), "blocking")

    def test_missing_lyrics_on_vocal_track_blocks(self, album):
        album(lyrics=None)
        assert "lyrics_missing" in _codes(_request(), "blocking")

    def test_template_lyrics_block(self, album):
        album(lyrics="[Verse 1 - calm reflective]\n[Lyrics here...]")
        assert "lyrics_placeholder" in _codes(_request(), "blocking")

    def test_over_long_fields_block(self, album):
        album(lyrics="la " * 2000, style="x" * 1001)
        codes = _codes(_request(), "blocking")
        assert "lyrics_too_long" in codes
        assert "style_too_long" in codes

    def test_unknown_album(self, album):
        result = _request(album_slug="nope")
        assert result["found"] is False

    def test_unknown_track(self, album):
        result = _request(track_slug="99-missing")
        assert result["found"] is False

    def test_track_without_path(self, album):
        result = _request(track_slug="02-no-path")
        assert result["found"] is False
        assert "path" in result["error"].lower()


# ===========================================================================
# log_generation
# ===========================================================================


def _log(clips, model="v6", notes="via MCP, 10 credits", track_slug="01-first-track"):
    return json.loads(_run(_gen_mod.log_generation(
        "test-album", track_slug, model, clips, notes,
    )))


def _two_clips():
    return [
        {"clip_id": CLIP_A, "status": "complete", "duration_s": 63.16},
        {"clip_id": CLIP_B, "status": "complete", "duration_s": 193.56},
    ]


@pytest.fixture
def fixed_today(monkeypatch):
    monkeypatch.setattr(_gen_mod, "_today", lambda: "2026-06-15")


class TestLogGeneration:
    def test_replaces_placeholder_row(self, album, fixed_today):
        result = _log(_two_clips())
        assert result["success"] is True
        text = album.path.read_text(encoding="utf-8")
        assert PLACEHOLDER_ROW not in text
        assert (
            f"| 1 | 2026-06-15 | v6 | [Listen](https://suno.com/song/{CLIP_A}) "
            "| 1:03, via MCP, 10 credits | — |\n"
            f"| 2 | 2026-06-15 | v6 | [Listen](https://suno.com/song/{CLIP_B}) "
            "| 3:14, via MCP, 10 credits | — |\n"
        ) in text

    def test_returns_rows_with_urls(self, album, fixed_today):
        result = _log(_two_clips())
        assert [r["row"] for r in result["rows"]] == [1, 2]
        assert result["rows"][0]["url"] == f"https://suno.com/song/{CLIP_A}"
        assert result["rows"][1]["clip_id"] == CLIP_B

    def test_appends_after_existing_rows_and_continues_numbering(self, album, fixed_today):
        existing = (
            "| 1 | 2026-02-12 | V5 | [Keeper](https://suno.com/s/4hZKwZySCc8Lc63Q) | first | ✓ |",
            "| 2 | 2026-02-12 | V5 | [Listen](https://suno.com/s/OLQGp22IPLbpsOdX) | dark | — |",
        )
        album(log_rows=existing)
        result = _log(_two_clips())
        assert [r["row"] for r in result["rows"]] == [3, 4]
        lines = album.path.read_text(encoding="utf-8").split("\n")
        start = lines.index(existing[0])
        assert lines[start + 1] == existing[1]
        assert lines[start + 2].startswith("| 3 | 2026-06-15 | v6 | [Listen](")
        assert lines[start + 3].startswith("| 4 | 2026-06-15 | v6 | [Listen](")
        assert lines[start + 4] == ""

    def test_leaves_the_rest_of_the_file_alone(self, album, fixed_today):
        before = album.path.read_text(encoding="utf-8")
        _log(_two_clips())
        after = album.path.read_text(encoding="utf-8")
        head, tail = before.split(PLACEHOLDER_ROW)
        assert after.startswith(head)
        assert after.endswith(tail)
        assert "| **Status** | In Progress |" in after

    def test_failed_clip_is_logged_as_failed(self, album, fixed_today):
        _log([{"clip_id": CLIP_A, "status": "error", "error": "moderation: lyrics rejected"}])
        text = album.path.read_text(encoding="utf-8")
        assert (
            "| 1 | 2026-06-15 | v6 | Failed "
            "| via MCP, 10 credits, error: moderation: lyrics rejected | — |"
        ) in text

    def test_notes_and_model_cannot_break_the_table(self, album, fixed_today):
        _log(
            [{"clip_id": CLIP_A, "status": "complete"}],
            model="v6 | wild", notes="via | MCP\nsecond line",
        )
        text = album.path.read_text(encoding="utf-8")
        assert (
            f"| 1 | 2026-06-15 | v6 / wild | [Listen](https://suno.com/song/{CLIP_A}) "
            "| via / MCP second line | — |"
        ) in text

    def test_empty_notes_leave_a_dash(self, album, fixed_today):
        _log([{"clip_id": CLIP_A, "status": "complete"}], notes="")
        assert "| — | — |\n" in album.path.read_text(encoding="utf-8")

    def test_uppercase_clip_id_is_normalized(self, album, fixed_today):
        result = _log([{"clip_id": CLIP_A.upper(), "status": "complete"}])
        assert result["rows"][0]["clip_id"] == CLIP_A

    @pytest.mark.parametrize("bad", ["", "not-a-uuid", "https://suno.com/song/x", "4ef71736"])
    def test_invalid_clip_id_is_rejected_before_writing(self, album, fixed_today, bad):
        before = album.path.read_text(encoding="utf-8")
        result = _log([{"clip_id": bad, "status": "complete"}])
        assert "error" in result
        assert album.path.read_text(encoding="utf-8") == before

    def test_no_clips_is_an_error(self, album):
        assert "error" in _log([])

    def test_missing_generation_log_section_is_an_error(self, album, fixed_today):
        album(log_rows=None)
        before = album.path.read_text(encoding="utf-8")
        result = _log(_two_clips())
        assert "Generation Log" in result["error"]
        assert album.path.read_text(encoding="utf-8") == before

    def test_section_without_a_table_gets_one(self, album, fixed_today):
        text = track_md().replace(
            "| # | Date | Model | Result | Notes | Rating |\n"
            "|---|------|-------|--------|-------|--------|\n"
            f"{PLACEHOLDER_ROW}\n\n",
            "",
        )
        album.path.write_text(text, encoding="utf-8")
        _log([{"clip_id": CLIP_A, "status": "complete"}])
        after = album.path.read_text(encoding="utf-8")
        assert (
            "| # | Date | Model | Result | Notes | Rating |\n"
            "|---|------|-------|--------|-------|--------|\n"
            f"| 1 | 2026-06-15 | v6 | [Listen](https://suno.com/song/{CLIP_A}) "
            "| via MCP, 10 credits | — |\n"
        ) in after
        assert after.index("| 1 | 2026-06-15") < after.index("## Waveform Art")

    def test_refreshes_the_cache_entry(self, album, fixed_today):
        _log(_two_clips())
        entry = album.state["albums"]["test-album"]["tracks"]["01-first-track"]
        assert entry["mtime"] == album.path.stat().st_mtime
        _gen_mod.write_state.assert_called_once_with(album.state)

    def test_unknown_track(self, album):
        assert _log(_two_clips(), track_slug="99-missing")["found"] is False


# ===========================================================================
# parse_generation_log
# ===========================================================================


def _row(number, clip_id, rating="—", notes="via MCP"):
    return (
        f"| {number} | 2026-06-15 | v6 | [Listen](https://suno.com/song/{clip_id}) "
        f"| {notes} | {rating} |"
    )


LEGACY_KEEPER_ROW = (
    "| 1 | 2026-02-12 | V5 | [Keeper](https://suno.com/s/4hZKwZySCc8Lc63Q) | solo piano | ✓ |"
)


class TestParseGenerationLog:
    def test_rows_with_song_urls_carry_clip_ids(self):
        text = track_md(log_rows=(_row(1, CLIP_A, notes="1:03, via MCP"), _row(2, CLIP_B, "✓")))
        takes = _gen_mod.parse_generation_log(text)
        assert [(t["row"], t["clip_id"], t["approved"]) for t in takes] == [
            (1, CLIP_A, False), (2, CLIP_B, True),
        ]
        assert takes[0] == {
            "row": 1,
            "date": "2026-06-15",
            "model": "v6",
            "url": f"https://suno.com/song/{CLIP_A}",
            "clip_id": CLIP_A,
            "notes": "1:03, via MCP",
            "rating": "—",
            "approved": False,
        }

    def test_legacy_share_links_have_no_clip_id(self):
        take = _gen_mod.parse_generation_log(track_md(log_rows=(LEGACY_KEEPER_ROW,)))[0]
        assert take["url"] == "https://suno.com/s/4hZKwZySCc8Lc63Q"
        assert take["clip_id"] is None
        assert take["approved"] is True

    def test_rows_without_a_link_are_kept(self):
        rows = (
            "| 1 | 2026-09-30 | v6 | Kept | user: legit awesome | ✓ |",
            "| 2 | 2026-06-15 | v6 | Failed | error: moderation | — |",
        )
        takes = _gen_mod.parse_generation_log(track_md(log_rows=rows))
        assert [(t["row"], t["url"], t["approved"]) for t in takes] == [
            (1, None, True), (2, None, False),
        ]

    def test_bare_url_in_the_result_cell(self):
        row = f"| 1 | 2026-06-15 | v6 | https://suno.com/song/{CLIP_A} | first | — |"
        assert _gen_mod.parse_generation_log(track_md(log_rows=(row,)))[0]["clip_id"] == CLIP_A

    def test_header_separator_and_placeholder_are_not_takes(self):
        assert _gen_mod.parse_generation_log(track_md()) == []

    def test_no_generation_log_section(self):
        assert _gen_mod.parse_generation_log(track_md(log_rows=None)) == []

    def test_older_five_column_table(self):
        text = (
            "# Old Track\n\n## Generation Log\n\n"
            "| # | Date | Result | Notes | Rating |\n|---|------|--------|-------|--------|\n"
            "| 1 | 2025-12-27 | [Listen](https://suno.com/s/Cae0VZjtvVTOrnBy) | First gen | ✓ |\n"
        )
        take = _gen_mod.parse_generation_log(text)[0]
        assert take["url"] == "https://suno.com/s/Cae0VZjtvVTOrnBy"
        assert take["model"] == ""
        assert take["notes"] == "First gen"
        assert take["approved"] is True


# ===========================================================================
# get_suno_import_plan
# ===========================================================================


def _plan(track_slug="01-first-track"):
    return json.loads(_run(_gen_mod.get_suno_import_plan("test-album", track_slug)))


class TestGetSunoImportPlan:
    def test_clip_id_comes_from_the_suno_link(self, album):
        album(suno_link=f"[Listen](https://suno.com/song/{CLIP_A})", status="Final")
        plan = _plan()
        assert plan["found"] is True
        assert plan["clip_id"] == CLIP_A
        assert plan["clip_source"] == "suno_link"
        assert plan["song_url"] == f"https://suno.com/song/{CLIP_A}"
        assert plan["problems"] == []
        assert plan["wav"] == {
            "path": str(album.audio_dir / "01-first-track.wav"),
            "existing": None,
        }
        stems_dir = album.audio_dir / "stems" / "01-first-track"
        assert plan["stems"]["dir"] == str(stems_dir)
        assert plan["stems"]["exists"] is False
        assert len(plan["stems"]["files"]) == 12
        assert plan["stems"]["files"]["vocals"] == str(stems_dir / "0 Lead Vocals.wav")
        assert plan["stems"]["files"]["fx"] == str(stems_dir / "9 FX.wav")

    def test_bare_url_suno_link(self, album):
        album(suno_link=f"https://suno.com/song/{CLIP_B}")
        assert _plan()["clip_id"] == CLIP_B

    def test_originals_directory_is_the_import_target_when_present(self, album):
        album(suno_link=f"https://suno.com/song/{CLIP_A}")
        (album.audio_dir / "originals").mkdir(parents=True)
        assert _plan()["wav"]["path"] == str(
            album.audio_dir / "originals" / "01-first-track.wav"
        )

    def test_an_already_imported_file_is_reported(self, album):
        album(suno_link=f"https://suno.com/song/{CLIP_A}")
        album.audio_dir.mkdir(parents=True)
        hand_named = album.audio_dir / "01 - First Track.wav"
        hand_named.write_bytes(b"RIFF")
        assert _plan()["wav"]["existing"] == str(hand_named)

    def test_falls_back_to_the_single_approved_take(self, album):
        album(log_rows=(_row(1, CLIP_A), _row(2, CLIP_B, "✓")))
        plan = _plan()
        assert plan["clip_id"] == CLIP_B
        assert plan["clip_source"] == "generation_log"
        assert plan["problems"] == []

    def test_two_approved_takes_and_no_link_is_ambiguous(self, album):
        album(log_rows=(_row(1, CLIP_A, "✓"), _row(2, CLIP_B, "✓")))
        plan = _plan()
        assert plan["clip_id"] is None
        assert _codes(plan, "blocking") == ["keeper_ambiguous"]

    def test_no_approved_take(self, album):
        album(log_rows=(_row(1, CLIP_A), _row(2, CLIP_B)))
        plan = _plan()
        assert plan["clip_id"] is None
        assert _codes(plan, "blocking") == ["no_keeper"]

    def test_legacy_share_link_carries_no_clip_id(self, album):
        album(suno_link="https://suno.com/s/4hZKwZySCc8Lc63Q", log_rows=(LEGACY_KEEPER_ROW,))
        plan = _plan()
        assert plan["clip_id"] is None
        assert plan["song_url"] == "https://suno.com/s/4hZKwZySCc8Lc63Q"
        assert _codes(plan, "blocking") == ["legacy_link"]

    def test_stem_filenames_route_to_the_right_mix_buckets(self, tmp_path):
        """The names written for Suno's 12 stems must land in the processing
        bucket discover_stems gives each instrument — 'fx' has no bucket of its
        own and belongs in 'other'."""
        from tools.mixing.mix_tracks import discover_stems

        for filename in _gen_mod.SUNO_STEM_FILENAMES.values():
            (tmp_path / filename).write_bytes(b"")
        routed = {bucket: Path(str(path)).name for bucket, path in discover_stems(tmp_path).items()}
        assert routed == {
            "vocals": "0 Lead Vocals.wav",
            "backing_vocals": "1 Backing Vocals.wav",
            "drums": "2 Drums.wav",
            "bass": "3 Bass.wav",
            "guitar": "4 Guitar.wav",
            "keyboard": "5 Keyboard.wav",
            "percussion": "6 Percussion.wav",
            "strings": "7 Strings.wav",
            "synth": "8 Synth.wav",
            "other": "9 FX.wav",
            "brass": "10 Brass.wav",
            "woodwinds": "11 Woodwinds.wav",
        }

    def test_audio_root_not_configured(self, album):
        album.state["config"]["audio_root"] = ""
        assert "error" in _plan()

    def test_unknown_track(self, album):
        assert _plan(track_slug="99-missing")["found"] is False


# ===========================================================================
# Album workspaces: get_album_workspace / set_album_workspace
# ===========================================================================

WORKSPACE_ID = "be7f57b5-0cef-4769-ab0e-44b4861bd895"
CLIP_C = "71af26e1-7ca6-486b-8511-a5a93ddc10df"

README_WITH_BLOCK = """---
title: "Test Album"
release_date: ""  # YYYY-MM-DD (fill in when releasing)
genres: ["electronic"]
suno_workspace:  # Suno workspace that holds this album's takes; /bitwize-music:generate fills it in
  id: ""
  name: ""
streaming:
  spotify: ""       # Fill in when released
---

# Test Album

## Album Details

| Attribute | Detail |
|-----------|--------|
| **Status** | In Progress |
"""

README_WITHOUT_BLOCK = """---
title: "Test Album"
release_date: ""  # YYYY-MM-DD (fill in when releasing)
genres: ["electronic"]
---

# Test Album
"""


def _workspace(album_slug="test-album"):
    return json.loads(_run(_gen_mod.get_album_workspace(album_slug)))


def _set(album_slug="test-album", workspace_id=WORKSPACE_ID, name="Test Album"):
    return json.loads(_run(_gen_mod.set_album_workspace(album_slug, workspace_id, name)))


def _readme(album, text=README_WITH_BLOCK):
    path = Path(album.state["albums"]["test-album"]["path"]) / "README.md"
    path.write_text(text, encoding="utf-8")
    return path


class TestGetAlbumWorkspace:
    def test_album_without_a_workspace(self, album):
        result = _workspace()
        assert result["found"] is True
        assert result["album_slug"] == "test-album"
        assert result["album_title"] == "Test Album"
        assert result["workspace"] is None
        assert result["suggested_name"] == "Test Album"
        assert result["clips"] == []
        assert result["batches"] == []
        assert result["enabled"] is True

    def test_album_with_a_workspace(self, album):
        album.state["albums"]["test-album"]["suno_workspace"] = {"id": WORKSPACE_ID, "name": "Test Album"}
        assert _workspace()["workspace"] == {"id": WORKSPACE_ID, "name": "Test Album"}

    def test_clips_come_from_every_generation_log(self, album):
        album(log_rows=(_row(1, CLIP_A), _row(2, CLIP_B, rating="✓"), LEGACY_KEEPER_ROW))
        second = album.path.parent / "02-second.md"
        second.write_text(track_md(title="Second", log_rows=(_row(1, CLIP_C),)), encoding="utf-8")
        album.state["albums"]["test-album"]["tracks"]["02-second"] = {
            "title": "Second", "status": "Generated", "path": str(second),
        }
        result = _workspace()
        assert result["clips"] == [
            {"track_slug": "01-first-track", "take": 1, "clip_id": CLIP_A, "keeper": False},
            {"track_slug": "01-first-track", "take": 2, "clip_id": CLIP_B, "keeper": True},
            {"track_slug": "02-second", "take": 1, "clip_id": CLIP_C, "keeper": False},
        ]
        assert result["batches"] == [[CLIP_A, CLIP_B, CLIP_C]]

    def test_batches_hold_at_most_fifty_clips(self, album, monkeypatch):
        """workspaces-update-clips takes 50 ids per call."""
        rows = tuple(_row(n, f"{n:08x}-0000-4000-8000-000000000000") for n in range(1, 121))
        album(log_rows=rows)
        batches = _workspace()["batches"]
        assert [len(b) for b in batches] == [50, 50, 20]
        assert batches[0][0] == "00000001-0000-4000-8000-000000000000"

    def test_placeholder_title_suggests_the_slug(self, album):
        album.state["albums"]["test-album"]["title"] = "[Album Title]"
        result = _workspace()
        assert result["album_title"] == "[Album Title]"
        assert result["suggested_name"] == "test-album"

    def test_config_switch(self, album):
        album.state["config"]["generation"] = {"suno_workspaces": False}
        assert _workspace()["enabled"] is False

    def test_unknown_album(self, album):
        assert _workspace("nope")["found"] is False


class TestSetAlbumWorkspace:
    def test_fills_the_template_block_and_keeps_comments(self, album):
        path = _readme(album)
        result = _set()
        assert result == {
            "updated": True, "path": str(path),
            "workspace": {"id": WORKSPACE_ID, "name": "Test Album"},
        }
        text = path.read_text(encoding="utf-8")
        assert f'  id: "{WORKSPACE_ID}"' in text
        assert '  name: "Test Album"' in text
        assert "# YYYY-MM-DD (fill in when releasing)" in text      # comments survive
        assert "# Suno workspace that holds this album's takes" in text
        assert "# Fill in when released" in text
        assert text.endswith("| **Status** | In Progress |\n")      # body untouched
        from tools.state.parsers import parse_album_readme
        assert parse_album_readme(path)["suno_workspace"] == {"id": WORKSPACE_ID, "name": "Test Album"}

    def test_adds_the_block_to_an_older_readme(self, album):
        path = _readme(album, README_WITHOUT_BLOCK)
        assert _set()["updated"] is True
        text = path.read_text(encoding="utf-8")
        assert text.startswith('---\ntitle: "Test Album"\n')
        assert "# YYYY-MM-DD (fill in when releasing)" in text
        assert "\nsuno_workspace:  # Suno workspace that holds this album's takes" in text
        assert f'\n  id: "{WORKSPACE_ID}"\n  name: "Test Album"\n---\n' in text
        from tools.state.parsers import parse_album_readme
        assert parse_album_readme(path)["suno_workspace"] == {"id": WORKSPACE_ID, "name": "Test Album"}

    def test_replaces_an_earlier_workspace(self, album):
        path = _readme(album)
        _set()
        other = "0f3c6c19-0c42-4d4f-9a37-7f5fd1bd2e01"
        assert _set(workspace_id=other, name="Renamed")["workspace"] == {"id": other, "name": "Renamed"}
        text = path.read_text(encoding="utf-8")
        assert text.count("suno_workspace:") == 1
        assert WORKSPACE_ID not in text
        assert f'  id: "{other}"' in text and '  name: "Renamed"' in text

    def test_name_with_quotes_cannot_break_the_frontmatter(self, album):
        path = _readme(album)
        assert _set(name='Say "Hi" \\ again')["updated"] is True
        from tools.state.parsers import parse_album_readme
        assert parse_album_readme(path)["suno_workspace"]["name"] == 'Say "Hi" \\ again'

    def test_refreshes_the_cache_entry(self, album):
        _readme(album)
        _set()
        assert album.state["albums"]["test-album"]["suno_workspace"] == {"id": WORKSPACE_ID, "name": "Test Album"}
        _gen_mod.write_state.assert_called_once()

    @pytest.mark.parametrize("bad", ["", "not-a-uuid", "be7f57b5-0cef-4769-ab0e", "../../etc"])
    def test_rejects_a_bad_workspace_id_before_writing(self, album, bad):
        path = _readme(album)
        before = path.read_text(encoding="utf-8")
        result = _set(workspace_id=bad)
        assert "error" in result
        assert path.read_text(encoding="utf-8") == before

    def test_name_is_required(self, album):
        _readme(album)
        assert "error" in _set(name="   ")

    def test_missing_readme_is_an_error(self, album):
        assert "README" in _set()["error"]

    def test_readme_without_frontmatter_is_an_error(self, album):
        _readme(album, "# Test Album\n\nNo frontmatter here.\n")
        assert "frontmatter" in _set()["error"].lower()

    def test_unknown_album(self, album):
        assert _set("nope")["found"] is False


class TestWorkspaceInOtherTools:
    def test_generation_request_carries_the_workspace_id(self, album):
        album.state["albums"]["test-album"]["suno_workspace"] = {"id": WORKSPACE_ID, "name": "Test Album"}
        assert _request()["request"]["workspace_id"] == WORKSPACE_ID

    def test_generation_request_without_a_workspace(self, album):
        assert "workspace_id" not in _request()["request"]

    def test_import_plan_carries_the_workspace(self, album):
        album(suno_link=f"[Listen](https://suno.com/song/{CLIP_A})", status="Final")
        assert _plan()["workspace"] is None
        album.state["albums"]["test-album"]["suno_workspace"] = {"id": WORKSPACE_ID, "name": "Test Album"}
        assert _plan()["workspace"] == {"id": WORKSPACE_ID, "name": "Test Album"}
