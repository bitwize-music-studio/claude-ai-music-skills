"""Word-count targets in get_lyrics_stats agree with the craft reference.

``skills/lyric-writer/craft-reference.md`` § Song Length is what the
lyric-writer follows. ``get_lyrics_stats`` restated its numbers once, the
reference was then revised upward ("the previous lower targets ... produce
2:00–2:30 tracks"), and the tool kept the old ones: a 280-word pop track was
inside the skill's range and reported OVER by the tool.

The tool also ignored Target Duration, which the reference puts first: the
track's, then the album's, then the genre's default.

The first class here reads the reference itself, so the two cannot drift apart
again without a test failing.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from handlers import _shared as _shared_mod
from handlers import text_analysis

REFERENCE = PROJECT_ROOT / "skills" / "lyric-writer" / "craft-reference.md"

_RANGE = r"(\d+)\s*[–-]\s*(\d+)"
_CLOCK_RANGE = r"(\d+):(\d\d)\s*[–-]\s*(\d+):(\d\d)"


REVIEWER_CHECKLIST = PROJECT_ROOT / "skills" / "lyric-reviewer" / "checklist-reference.md"
SUNO_BEST_PRACTICES = PROJECT_ROOT / "reference" / "suno" / "best-practices.md"


def _table_after(heading_fragment: str, source: Path = REFERENCE) -> list[list[str]]:
    """Cells of the first markdown table after the line containing *heading_fragment*."""
    lines = source.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if heading_fragment in line)
    rows: list[list[str]] = []
    for line in lines[start + 1:]:
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if not set(cells[0]) <= set("-: "):  # skip the |---| separator
                rows.append(cells)
        elif rows:
            break
    return rows[1:]  # drop the header row


def _genre_slugs(cell: str) -> list[str]:
    """"Pop / Synth-Pop" -> ["pop", "synth-pop"]; "Ballad (any)" -> ["ballad"]."""
    names = re.sub(r"\(.*?\)", "", cell).split("/")
    return [name.strip().lower().replace(" ", "-") for name in names if name.strip()]


class TestTheToolRestatesTheReference:
    def test_every_genre_row_matches(self):
        rows = _table_after("Word Count Targets by Genre (Suno)")
        assert len(rows) >= 7, "the reference's genre table was not found"
        checked = 0
        for cells in rows:
            low, high = map(int, re.search(_RANGE, cells[2]).groups())
            for slug in _genre_slugs(cells[0]):
                assert slug in text_analysis._GENRE_WORD_TARGETS, (
                    f"the reference has a row for {slug!r}; the tool has no target for it"
                )
                assert text_analysis._GENRE_WORD_TARGETS[slug] == {"min": low, "max": high}, slug
                checked += 1
        assert checked >= 14

    def test_every_duration_row_matches(self):
        rows = _table_after("Duration → Word Count mapping")
        assert len(rows) == 4, "the reference's duration table was not found"
        for cells in rows:
            m1, s1, m2, s2 = map(int, re.search(_CLOCK_RANGE, cells[0]).groups())
            midpoint = ((m1 * 60 + s1) + (m2 * 60 + s2)) // 2
            plain = dict(zip(("min", "max"), map(int, re.search(_RANGE, cells[1]).groups())))
            rap = dict(zip(("min", "max"), map(int, re.search(_RANGE, cells[2]).groups())))
            assert text_analysis._words_for_duration(midpoint, hip_hop=False) == plain, cells[0]
            assert text_analysis._words_for_duration(midpoint, hip_hop=True) == rap, cells[0]

    def test_the_default_is_the_reference_default_duration(self):
        """An unknown genre gets the row for the default 3:30–5:00 target."""
        text = REFERENCE.read_text(encoding="utf-8")
        default = re.search(r"### Default Target Duration\s+\*\*" + _CLOCK_RANGE, text)
        m1, s1, m2, s2 = map(int, default.groups())
        midpoint = ((m1 * 60 + s1) + (m2 * 60 + s2)) // 2
        assert text_analysis._DEFAULT_WORD_TARGET == text_analysis._words_for_duration(
            midpoint, hip_hop=False,
        )


class TestOtherDocumentsQuoteTheSameNumbers:
    """The reference is not the only place the targets are written down.

    The lyric-reviewer's checklist and the Suno best-practices page each carried
    a copy of the older, lower targets, so the reviewer and the writer disagreed
    about the same lyric sheet.
    """

    def test_the_reviewers_length_table_matches(self):
        rows = _table_after("**Genre targets**", REVIEWER_CHECKLIST)
        assert len(rows) >= 6, "the reviewer's Length Check table was not found"
        for cells in rows:
            low, high = map(int, re.search(_RANGE, cells[1]).groups())
            for slug in _genre_slugs(cells[0]):
                assert text_analysis._GENRE_WORD_TARGETS.get(slug) == {"min": low, "max": high}, (
                    f"lyric-reviewer says {low}-{high} for {slug!r}"
                )

    def test_best_practices_states_the_default_range(self):
        text = SUNO_BEST_PRACTICES.read_text(encoding="utf-8")
        section = text.split("### Keep Lyrics Concise", 1)[1].split("###", 1)[0]
        default = text_analysis._DEFAULT_WORD_TARGET
        rap = text_analysis._GENRE_WORD_TARGETS["hip-hop"]
        ranges = [tuple(map(int, m)) for m in re.findall(_RANGE, section)]
        assert (default["min"], default["max"]) in ranges, ranges
        assert (rap["min"], rap["max"]) in ranges, ranges


class TestReadingATargetDuration:
    @pytest.mark.parametrize("cell, seconds", [
        ("3:30", 210),
        ("~5:00", 300),
        ("3:00–3:30", 195),                 # en dash range: the midpoint
        ("3:30-5:00", 255),
        ("3:30 – 4:30", 240),
        ("~5:00 (flexible guideline)", 300),
        ("1:40 — set on the Suno slider, 2:00 at most", 100),  # not a range
        ("[3:30–5:00]", 255),
    ])
    def test_times_are_read(self, cell, seconds):
        assert text_analysis._duration_seconds(cell) == seconds

    @pytest.mark.parametrize("cell", [None, "", "—", "-", "TBD", "about four minutes"])
    def test_no_time_means_unset(self, cell):
        assert text_analysis._duration_seconds(cell) is None

    @pytest.mark.parametrize("seconds, expected", [
        (100, {"min": 120, "max": 180}),     # under 2:00 still uses the shortest row
        (149, {"min": 120, "max": 180}),
        (150, {"min": 150, "max": 250}),     # a boundary belongs to the longer row
        (209, {"min": 150, "max": 250}),
        (210, {"min": 220, "max": 400}),
        (299, {"min": 220, "max": 400}),
        (300, {"min": 350, "max": 500}),
        (450, {"min": 350, "max": 500}),     # over 7:00 still uses the longest row
    ])
    def test_rows_are_half_open(self, seconds, expected):
        assert text_analysis._words_for_duration(seconds, hip_hop=False) == expected


# ---------------------------------------------------------------------------
# get_lyrics_stats end to end
# ---------------------------------------------------------------------------


class _FakeCache:
    def __init__(self, state: dict) -> None:
        self._state = state

    def get_state(self) -> dict:
        return self._state


def _run(coro):
    return json.loads(asyncio.run(coro))


def _track_text(words: int, duration: str | None, genre: str | None = None) -> str:
    fm = 'title: "T"\n' + (f'genre: "{genre}"\n' if genre else "")
    row = f"| **Target Duration** | {duration} |\n" if duration is not None else ""
    lyrics = " ".join(["word"] * words)
    return (
        f"---\n{fm}---\n\n# T\n\n## Track Details\n\n"
        "| Attribute | Detail |\n|-----------|--------|\n"
        "| **Status** | In Progress |\n" + row +
        f"\n## Lyrics Box\n\n```\n[Verse 1]\n{lyrics}\n```\n"
    )


@pytest.fixture
def stats(tmp_path, monkeypatch):
    """Build a one-track album and return get_lyrics_stats for it."""
    def build(*, album_genre: str = "pop", words: int = 280,
              duration: str | None = "—", album_duration: str | None = None,
              track_genre: str | None = None) -> dict:
        album_dir = tmp_path / "album"
        (album_dir / "tracks").mkdir(parents=True, exist_ok=True)
        readme = "# Album\n\n## Production Notes\n\n**Suno Settings**:\n"
        if album_duration is not None:
            readme += f"- **Target Duration**: {album_duration}\n"
        readme += "- **Default Model**: v6\n"
        (album_dir / "README.md").write_text(readme, encoding="utf-8")
        track = album_dir / "tracks" / "01-t.md"
        track.write_text(_track_text(words, duration, track_genre), encoding="utf-8")
        cache = _FakeCache({
            "config": {},
            "albums": {"a": {
                "genre": album_genre,
                "path": str(album_dir),
                "tracks": {"01-t": {"path": str(track), "title": "T", "genre": track_genre or ""}},
            }},
        })
        monkeypatch.setattr(_shared_mod, "cache", cache)
        return _run(text_analysis.get_lyrics_stats("a"))
    return build


class TestGenreTargetsFollowTheReference:
    def test_a_280_word_pop_track_is_within_target(self, stats):
        """The reported case: inside the skill's 250–350 and called OVER by the tool."""
        row = stats(album_genre="pop", words=280)["tracks"][0]
        assert row["target"] == {"min": 250, "max": 350}
        assert row["target_basis"] == "genre"
        assert row["status"] == "OK"

    @pytest.mark.parametrize("genre, target", [
        ("rock", {"min": 250, "max": 400}),
        ("country", {"min": 250, "max": 400}),
        ("hip-hop", {"min": 400, "max": 600}),
        ("electronic", {"min": 220, "max": 300}),
        ("synthwave", {"min": 220, "max": 300}),
        ("punk", {"min": 150, "max": 250}),
        ("ballad", {"min": 200, "max": 300}),
    ])
    def test_other_genres(self, stats, genre, target):
        assert stats(album_genre=genre)["tracks"][0]["target"] == target

    def test_an_unknown_genre_gets_the_default(self, stats):
        row = stats(album_genre="cinematic")["tracks"][0]
        assert row["target"] == {"min": 220, "max": 400}
        assert row["target_basis"] == "default"


class TestTargetDurationComesFirst:
    def test_the_tracks_own_duration_sets_the_target(self, stats):
        """A 3:00–3:30 pop track wants 150–250 words, not the genre's 250–350."""
        row = stats(album_genre="pop", words=230, duration="3:00–3:30")["tracks"][0]
        assert row["target"] == {"min": 150, "max": 250}
        assert row["target_basis"] == "track_duration"
        assert row["target_duration"] == "3:00–3:30"
        assert row["status"] == "OK"

    def test_the_same_track_is_over_at_280_words(self, stats):
        row = stats(album_genre="pop", words=280, duration="3:00–3:30")["tracks"][0]
        assert row["status"] == "OVER"
        assert "3:00–3:30" in row["note"]

    def test_a_dash_falls_through_to_the_album(self, stats):
        row = stats(words=230, duration="—", album_duration="3:00–3:30")["tracks"][0]
        assert row["target"] == {"min": 150, "max": 250}
        assert row["target_basis"] == "album_duration"
        assert "album" in row["note"]

    def test_a_track_with_no_duration_row_falls_through_too(self, stats):
        row = stats(words=230, duration=None, album_duration="3:00–3:30")["tracks"][0]
        assert row["target_basis"] == "album_duration"

    def test_the_track_wins_over_the_album(self, stats):
        row = stats(words=400, duration="~5:00", album_duration="3:00–3:30")["tracks"][0]
        assert row["target"] == {"min": 350, "max": 500}
        assert row["target_basis"] == "track_duration"

    def test_the_album_templates_placeholder_is_not_a_decision(self, stats):
        """templates/album.md ships "- **Target Duration**: [3:30–5:00]"."""
        row = stats(album_genre="punk", words=200, album_duration="[3:30–5:00]")["tracks"][0]
        assert row["target"] == {"min": 150, "max": 250}
        assert row["target_basis"] == "genre"

    def test_neither_set_uses_the_genre(self, stats):
        row = stats(album_genre="pop", duration="—", album_duration=None)["tracks"][0]
        assert row["target_basis"] == "genre"

    def test_hip_hop_uses_its_own_column(self, stats):
        row = stats(album_genre="hip-hop", words=600, duration="~5:00")["tracks"][0]
        assert row["target"] == {"min": 550, "max": 750}

    def test_a_tracks_own_genre_picks_the_column(self, stats):
        """A rap track on a pop album, with a duration, is still counted as rap."""
        row = stats(album_genre="pop", words=450, duration="4:00", track_genre="hip-hop")["tracks"][0]
        assert row["target"] == {"min": 400, "max": 600}

    @pytest.mark.parametrize("genre", ["ambient", "lo-fi"])
    def test_sparse_genres_keep_their_own_target(self, stats, genre):
        """The duration rows assume a song sung throughout; these are not."""
        row = stats(album_genre=genre, words=100, duration="~5:00")["tracks"][0]
        assert row["target"] == {"min": 50, "max": 150}
        assert row["target_basis"] == "genre"
        assert row["status"] == "OK"

    def test_the_album_summary_follows_the_albums_duration(self, stats):
        result = stats(album_genre="pop", album_duration="3:00–3:30")
        assert result["target"] == {"min": 150, "max": 250}
        assert result["target_basis"] == "album_duration"

    def test_the_album_summary_is_the_genre_without_one(self, stats):
        result = stats(album_genre="pop")
        assert result["target"] == {"min": 250, "max": 350}
        assert result["target_basis"] == "genre"
