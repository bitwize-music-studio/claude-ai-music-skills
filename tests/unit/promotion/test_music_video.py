#!/usr/bin/env python3
"""tools/promotion/music_video.py — laying a music video out as shots for Suno's Sequences.

    plan_shots(duration_s, sections, ...)   — shots on the song's sections, each short enough for a clip
    billed_seconds(shots)                    — what the clips would be charged for
    build_sequence_request(...)              — the arguments for Suno's sequence-create

Nothing here talks to Suno.

Usage:
    python -m pytest tests/unit/promotion/test_music_video.py -v
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.promotion import music_video as mv

pytestmark = pytest.mark.unit

SONG = "0c1d2e3f-4a5b-4c6d-8e7f-a0b1c2d3e4f5"

# The sections Suno's audio-analysis gave for a 55-second test song.
SECTIONS = [
    {"start_s": 0, "end_s": 9.44, "label": "A"},
    {"start_s": 9.44, "end_s": 29.32, "label": "B"},
    {"start_s": 29.32, "end_s": 38.68, "label": "C"},
    {"start_s": 38.68, "end_s": 48.36, "label": "D"},
    {"start_s": 48.36, "end_s": 55.16, "label": "E"},
]


def _total(shots):
    return round(sum(shot["duration_s"] for shot in shots), 2)


# ===========================================================================
# plan_shots
# ===========================================================================


class TestPlanShots:
    def test_shots_follow_the_sections_and_a_long_section_is_split(self):
        shots = mv.plan_shots(55.16, SECTIONS)
        assert [shot["section"] for shot in shots] == ["A", "B", "B", "C", "D", "E"]
        assert [shot["duration_s"] for shot in shots] == [9.44, 9.94, 9.94, 9.36, 9.68, 6.8]
        assert [shot["start_s"] for shot in shots] == [0, 9.44, 19.38, 29.32, 38.68, 48.36]

    def test_the_shots_cover_the_song_exactly(self):
        shots = mv.plan_shots(55.16, SECTIONS)
        assert _total(shots) == 55.16
        for before, after in zip(shots, shots[1:], strict=False):
            assert round(before["start_s"] + before["duration_s"], 2) == after["start_s"]

    def test_no_shot_is_longer_than_a_clip_can_be(self):
        shots = mv.plan_shots(200.0, [{"start_s": 0, "end_s": 200.0, "label": "A"}], max_shot_s=15)
        assert all(shot["duration_s"] <= 15 for shot in shots)
        assert _total(shots) == 200.0

    @pytest.mark.parametrize("longest", [6, 8, 10, 15])
    def test_the_longest_shot_can_be_chosen(self, longest):
        shots = mv.plan_shots(55.16, SECTIONS, max_shot_s=longest)
        assert all(shot["duration_s"] <= longest for shot in shots)
        assert _total(shots) == 55.16

    def test_a_longest_shot_outside_what_a_clip_can_be_is_refused(self):
        for bad in (4, 16, 0, -1, float("nan"), "10", None, True):
            with pytest.raises(ValueError, match="5 to 15"):
                mv.plan_shots(55.16, SECTIONS, max_shot_s=bad)

    def test_a_section_too_short_for_a_clip_joins_its_neighbour(self):
        """A clip is at least five seconds, so a two-second shot would be charged for five."""
        sections = [
            {"start_s": 0, "end_s": 2.0, "label": "intro"},
            {"start_s": 2.0, "end_s": 12.0, "label": "A"},
            {"start_s": 12.0, "end_s": 14.5, "label": "tag"},
        ]
        shots = mv.plan_shots(14.5, sections)
        assert [shot["duration_s"] for shot in shots] == [7.25, 7.25] or all(
            shot["duration_s"] >= 5 for shot in shots
        )
        assert _total(shots) == 14.5
        assert all(shot["duration_s"] >= 5 for shot in shots)

    def test_gaps_and_overlaps_in_the_sections_do_not_lose_time(self):
        sections = [
            {"start_s": 0.4, "end_s": 20.0, "label": "A"},
            {"start_s": 19.0, "end_s": 41.0, "label": "B"},
        ]
        shots = mv.plan_shots(45.0, sections)
        assert shots[0]["start_s"] == 0 and _total(shots) == 45.0

    def test_without_sections_the_song_is_cut_evenly(self):
        shots = mv.plan_shots(55.16, [])
        assert _total(shots) == 55.16
        assert all(5 <= shot["duration_s"] <= 10 for shot in shots)
        assert {shot["section"] for shot in shots} == {""}

    def test_a_split_lands_on_a_bar_line_when_the_tempo_is_known(self):
        """4/4 at 189.4 BPM from 0.149 s: a bar is 1.267 s, so section B is cut at a bar, not in mid-phrase."""
        shots = mv.plan_shots(
            55.16, SECTIONS, bpm=189.4, time_signature=4, first_downbeat_s=0.149,
        )
        cut = shots[2]["start_s"]                         # the middle of section B
        bars = (cut - 0.149) / (4 * 60 / 189.4)
        assert abs(bars - round(bars)) < 0.02
        assert _total(shots) == 55.16

    def test_a_bar_line_is_not_taken_when_it_would_leave_a_shot_too_short_for_a_clip(self):
        """10.5 s at 60 BPM: the only bar lines are at 4 and 8 s, and a 4-second shot is charged as 5."""
        shots = mv.plan_shots(10.5, [], bpm=60)
        assert [shot["duration_s"] for shot in shots] == [5.25, 5.25]

    def test_a_cut_on_a_bar_line_never_pushes_a_shot_past_the_longest(self):
        """Rounded to hundredths after the check, a shot came out 10.01 s and was charged as 11."""
        sections = [{"start_s": 0, "end_s": 20.435, "label": "A"}, {"start_s": 20.435, "end_s": 80.435, "label": "B"}]
        shots = mv.plan_shots(80.435, sections, bpm=120, first_downbeat_s=0.435)
        assert max(shot["duration_s"] for shot in shots) <= 10
        waltz = mv.plan_shots(200.0, [], max_shot_s=15, bpm=96, time_signature=3, first_downbeat_s=0.18)
        assert max(shot["duration_s"] for shot in waltz) <= 15

    @pytest.mark.parametrize("seed", range(40))
    def test_any_song_gives_shots_within_the_limits(self, seed):
        """Whatever the sections and the tempo: the song is covered, and each shot can be one clip."""
        rng = random.Random(seed)
        sections, at = [], 0.0
        while at < rng.uniform(40, 260):
            length = round(rng.uniform(1.5, 40), 2)
            sections.append({"start_s": round(at, 2), "end_s": round(at + length, 2), "label": str(len(sections))})
            at += length
        duration = round(at + rng.uniform(0, 3), 2)
        longest = rng.choice([8, 10, 12, 15])
        tempo = {} if seed % 3 == 0 else {
            "bpm": rng.uniform(60, 190), "time_signature": rng.choice([3, 4, 6]),
            "first_downbeat_s": rng.uniform(0, 2),
        }
        shots = mv.plan_shots(duration, sections, max_shot_s=longest, **tempo)
        assert _total(shots) == duration
        assert shots[0]["start_s"] == 0
        for before, after in zip(shots, shots[1:], strict=False):
            assert round(before["start_s"] + before["duration_s"], 2) == after["start_s"]
        assert all(shot["duration_s"] <= longest for shot in shots), [s["duration_s"] for s in shots]
        if longest >= 10:
            # every section is at least five seconds once short ones are joined, and
            # halving anything over ten seconds leaves more than five
            assert all(shot["duration_s"] >= 5 for shot in shots), [s["duration_s"] for s in shots]
        mv.build_sequence_request(SONG, "T", shots)          # and Suno's own limits hold

    def test_a_song_too_short_for_a_clip_is_refused(self):
        with pytest.raises(ValueError, match="at least 5"):
            mv.plan_shots(3.0, [])

    def test_a_song_that_would_take_more_shots_than_suno_plans_is_refused(self):
        with pytest.raises(ValueError, match="40"):
            mv.plan_shots(600.0, [], max_shot_s=6)

    @pytest.mark.parametrize("duration", [0, -5, float("nan"), float("inf"), "55", None, True])
    def test_a_length_that_is_not_one(self, duration):
        with pytest.raises(ValueError, match="length"):
            mv.plan_shots(duration, SECTIONS)

    def test_sections_that_are_not_sections_are_refused(self):
        for bad in ("A", [{"start_s": "x", "end_s": 3}], [{"label": "A"}], [3]):
            with pytest.raises(ValueError, match="section"):
                mv.plan_shots(55.16, bad)


# ===========================================================================
# billed_seconds
# ===========================================================================


class TestBilledSeconds:
    def test_each_clip_is_charged_by_the_whole_second_rounded_up(self):
        shots = [{"duration_s": 9.44}, {"duration_s": 6.8}, {"duration_s": 10}]
        assert mv.billed_seconds(shots) == 10 + 7 + 10

    def test_the_measured_plan(self):
        assert mv.billed_seconds(mv.plan_shots(55.16, SECTIONS)) == 57

    def test_a_shot_shorter_than_the_shortest_clip_counts_as_one(self):
        """A clip is at least five seconds long. What Suno charges a shorter shot was not measured."""
        assert mv.billed_seconds([{"duration_s": 2.0}]) == 5


# ===========================================================================
# build_sequence_request
# ===========================================================================


CAST = [{"name": "Mara", "asset_ids": ["ast_1234"], "description": "red coat"}]
PLACES = [{"name": "Kitchen", "asset_ids": ["ast_5678", "ast_9abc"]}]


def _shots():
    return [
        {"duration_s": 9.44, "notes": "Wide: a windowsill at dawn. Slow push in."},
        {"duration_s": 9.94, "notes": "Close on a row of lanterns."},
    ]


class TestBuildSequenceRequest:
    def test_the_sequence(self):
        request = mv.build_sequence_request(
            SONG, "First Track", _shots(), aspect="16:9",
            style={"look": "watercolour", "rules": "no people, no text"},
        )
        assert request == {
            "title": "First Track",
            "song_id": SONG,
            "aspect": "16:9",
            "lyrics": False,
            "style": {"look": "watercolour", "rules": "no people, no text"},
            "shots": [
                {"duration_s": 9.44, "notes": "Wide: a windowsill at dawn. Slow push in."},
                {"duration_s": 9.94, "notes": "Close on a row of lanterns."},
            ],
        }

    def test_the_words_can_be_burned_in(self):
        assert mv.build_sequence_request(SONG, "T", _shots(), lyrics=True)["lyrics"] is True

    def test_the_shape_defaults_to_wide(self):
        assert mv.build_sequence_request(SONG, "T", _shots())["aspect"] == "16:9"
        assert mv.build_sequence_request(SONG, "T", _shots(), aspect="9x16")["aspect"] == "9:16"
        with pytest.raises(ValueError, match="4:3"):
            mv.build_sequence_request(SONG, "T", _shots(), aspect="4:3")

    def test_no_style_is_left_out(self):
        assert "style" not in mv.build_sequence_request(SONG, "T", _shots())

    def test_a_shot_keeps_only_what_suno_takes(self):
        shots = [{"duration_s": 9.44, "start_s": 0, "section": "A", "notes": " Wide. ", "characters": ["Mara"], "set": "Kitchen"}]
        (shot,) = mv.build_sequence_request(SONG, "T", shots, characters=CAST, sets=PLACES)["shots"]
        assert shot == {"duration_s": 9.44, "notes": "Wide.", "characters": ["Mara"], "set": "Kitchen"}

    def test_the_cast_and_the_sets(self):
        request = mv.build_sequence_request(SONG, "T", _shots(), characters=CAST, sets=PLACES)
        assert request["characters"] == [{"name": "Mara", "asset_ids": ["ast_1234"], "description": "red coat"}]
        assert request["sets"] == [{"name": "Kitchen", "asset_ids": ["ast_5678", "ast_9abc"]}]

    @pytest.mark.parametrize(("shot", "fragment"), [
        ({"duration_s": 8, "characters": ["Mara"]}, "character"),      # nobody is cast
        ({"duration_s": 8, "set": "Kitchen"}, "set"),                  # there are no sets
    ])
    def test_a_shot_cannot_cite_what_the_sequence_does_not_have(self, shot, fragment):
        with pytest.raises(ValueError, match=fragment):
            mv.build_sequence_request(SONG, "T", [shot])

    @pytest.mark.parametrize("cited", [["Nobody"], "Mara", [3], [["Mara"]]])
    def test_a_citation_that_is_not_a_name_from_the_cast(self, cited):
        with pytest.raises(ValueError, match="character"):
            mv.build_sequence_request(SONG, "T", [{"duration_s": 8, "characters": cited}], characters=CAST)

    @pytest.mark.parametrize("place", ["Garden", 3, ["Kitchen"]])
    def test_a_set_that_is_not_among_the_sets(self, place):
        with pytest.raises(ValueError, match="set"):
            mv.build_sequence_request(SONG, "T", [{"duration_s": 8, "set": place}], sets=PLACES)

    @pytest.mark.parametrize("cast", [
        [{"name": "", "asset_ids": ["ast_1"]}],
        [{"name": "x" * 61, "asset_ids": ["ast_1"]}],
        [{"name": "Mara", "asset_ids": []}],
        [{"name": "Mara", "asset_ids": ["a", "b", "c", "d"]}],
        [{"name": "Mara", "asset_ids": "ast_1"}],
        [{"name": "Mara", "asset_ids": ["ast_1"]}, {"name": "Mara", "asset_ids": ["ast_2"]}],
        [{"name": "Mara", "asset_ids": ["ast_1"], "description": "d" * 501}],
        [{"name": f"C{n}", "asset_ids": ["ast_1"]} for n in range(13)],
        "Mara", [3],
    ])
    def test_a_cast_suno_would_refuse(self, cast):
        with pytest.raises(ValueError, match="character"):
            mv.build_sequence_request(SONG, "T", _shots(), characters=cast)

    def test_more_than_suno_keeps_with_a_sequence_is_refused(self):
        """The style, the cast, the sets and the notes together hold at most 32 KB."""
        shots = [{"duration_s": 5, "notes": "n" * 1000} for _ in range(40)]
        with pytest.raises(ValueError, match="32"):
            mv.build_sequence_request(SONG, "T", shots)
        assert mv.build_sequence_request(SONG, "T", shots[:20])

    def test_a_shot_without_notes_has_none(self):
        (shot,) = mv.build_sequence_request(SONG, "T", [{"duration_s": 8}])["shots"]
        assert shot == {"duration_s": 8}

    @pytest.mark.parametrize("shots", [
        [], "shots", [{"notes": "no length"}], [{"duration_s": 16}], [{"duration_s": 0}],
        [{"duration_s": float("nan")}], [{"duration_s": 8, "notes": "x" * 1001}], [3],
    ])
    def test_shots_suno_would_refuse(self, shots):
        with pytest.raises(ValueError, match="[Ss]hot"):
            mv.build_sequence_request(SONG, "T", shots)

    def test_more_shots_than_suno_plans(self):
        with pytest.raises(ValueError, match="40"):
            mv.build_sequence_request(SONG, "T", [{"duration_s": 5}] * 41)

    @pytest.mark.parametrize("song", ["", "not-a-song", SONG + "0"])
    def test_a_song_id_that_is_not_one(self, song):
        with pytest.raises(ValueError, match="song"):
            mv.build_sequence_request(song, "T", _shots())

    def test_a_title_is_needed_and_trimmed(self):
        assert mv.build_sequence_request(SONG, "  First Track ", _shots())["title"] == "First Track"
        with pytest.raises(ValueError, match="title"):
            mv.build_sequence_request(SONG, "  ", _shots())

    def test_a_style_that_is_not_an_object(self):
        with pytest.raises(ValueError, match="style"):
            mv.build_sequence_request(SONG, "T", _shots(), style="watercolour")
