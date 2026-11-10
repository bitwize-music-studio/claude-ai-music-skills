#!/usr/bin/env python3
"""Unit tests for handlers/take_check.py — the take-check tools.

    get_take_check_plan(album, track)                  — questions for Suno's listening agent
    evaluate_take_check(album, track, clip, answers)   — its answers -> an advisory report

Neither tool talks to Suno. The track-file builder and the album fixture come
from test_handlers_generation.py.

Usage:
    python -m pytest tests/unit/state/test_handlers_take_check.py -v
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

from handlers import take_check as _check_mod  # noqa: E402

pytestmark = pytest.mark.unit

LYRICS = (
    "[Verse 1 - soft intimate]\n"
    "Kettle on, the window fogged with morning\n"
    "Paper boats are lined up on the sill\n"
    "\n"
    "[Chorus - warm lifting]\n"
    "Slow down, slow down, let the hour unfold\n"
    "[Whispered] Slow down\n"
    "\n"
    "[Instrumental Break]\n"
    "\n"
    "[Outro]\n"
    "Slow down\n"
    "\n"
    "[End]"
)
STYLE = "Female alto, warm and intimate. Indie folk at 96 BPM, fingerpicked acoustic guitar, upright bass."


def _plan(track_slug="01-first-track"):
    return json.loads(_run(_check_mod.get_take_check_plan("test-album", track_slug)))


def _evaluate(answers, clip_id=CLIP_A, duration_s=0.0):
    return json.loads(_run(_check_mod.evaluate_take_check(
        "test-album", "01-first-track", clip_id, answers, duration_s,
    )))


def _answer(prose="All good.", **fields):
    return f"{prose}\n\n```json\n{json.dumps(fields)}\n```"


def _clean(**overrides):
    fields = {
        "missing_lines": [], "changed_lines": [], "unclear_lines": [],
        "bpm": 96.2, "key": "G major", "time_signature": "4/4",
        "has_vocals": True, "vocal_gender": "female", "vocal": "soft, breathy alto",
        "instruments": ["fingerpicked acoustic guitar", "upright bass"],
        "problems": [], "ends_cleanly": True,
    }
    fields.update(overrides)
    return _answer(**fields)


def _check(result, name):
    return next((c for c in result["checks"] if c["check"] == name), None)


@pytest.fixture
def song(album):  # noqa: F811
    """The album fixture with a realistic vocal track."""
    album(
        lyrics=LYRICS, style=STYLE, exclude="electric guitar, synth",
        settings={"Vocal Gender": "Female"},
        log_rows=(_row(1, CLIP_A), _row(2, CLIP_B)),
    )
    return album


# ===========================================================================
# lyric_lines
# ===========================================================================


class TestLyricLines:
    def test_numbers_the_sung_lines_and_names_their_sections(self):
        assert _check_mod.lyric_lines(LYRICS) == [
            {"n": 1, "section": "Verse 1", "text": "Kettle on, the window fogged with morning"},
            {"n": 2, "section": "Verse 1", "text": "Paper boats are lined up on the sill"},
            {"n": 3, "section": "Chorus", "text": "Slow down, slow down, let the hour unfold"},
            {"n": 4, "section": "Chorus", "text": "Slow down"},
            {"n": 5, "section": "Outro", "text": "Slow down"},
        ]

    def test_tags_only_lyrics_have_no_lines(self):
        assert _check_mod.lyric_lines("[Intro]\n\n[Main Theme]\n\n[End]") == []

    def test_lines_before_any_tag_have_no_section(self):
        assert _check_mod.lyric_lines("la la la\n[Verse]\nhello")[0] == {
            "n": 1, "section": "", "text": "la la la",
        }


# ===========================================================================
# get_take_check_plan
# ===========================================================================


class TestGetTakeCheckPlan:
    def test_vocal_track(self, song):
        plan = _plan()
        assert plan["found"] is True
        assert plan["track_slug"] == "01-first-track"
        assert plan["instrumental"] is False
        assert [line["n"] for line in plan["lines"]] == [1, 2, 3, 4, 5]
        assert plan["takes"] == [
            {"take": 1, "clip_id": CLIP_A, "keeper": False, "duration_s": None},
            {"take": 2, "clip_id": CLIP_B, "keeper": False, "duration_s": None},
        ]
        assert plan["default_takes"] == [1, 2]
        assert plan["targets"] == {
            "bpm": [96, 96], "vocal_gender": "female",
            "exclude": ["electric guitar", "synth"], "duration_s": None,
        }
        assert plan["enabled"] is True

    def test_one_question_lists_every_line_and_asks_for_json(self, song):
        questions = _plan()["questions"]
        assert len(questions) == 1
        question = questions[0]
        assert (question["first"], question["last"]) == (1, 5)
        text = question["question"]
        assert "[Verse 1]\n1. Kettle on, the window fogged with morning\n2. Paper boats" in text
        assert "[Chorus]\n3. Slow down, slow down, let the hour unfold\n4. Slow down" in text
        assert "soft intimate" not in text          # performance cues are not lyrics
        assert "[Whispered]" not in text
        for field in ("missing_lines", "changed_lines", "unclear_lines", "changes", "bpm", "key",
                      "has_vocals", "vocal_gender", "instruments", "problems", "ends_cleanly"):
            assert field in text
        assert len(text) <= 2000

    def test_long_lyrics_are_split_across_questions(self, song):
        lines = "\n".join(f"This is lyric line number {n} of a rather long song" for n in range(1, 91))
        song(lyrics=f"[Verse 1]\n{lines}", log_rows=(_row(1, CLIP_A),))
        questions = _plan()["questions"]
        assert len(questions) > 1
        assert all(len(q["question"]) <= 2000 for q in questions)
        # Every line is asked about exactly once, in order.
        assert questions[0]["first"] == 1
        assert questions[-1]["last"] == 90
        for before, after in zip(questions, questions[1:]):
            assert after["first"] == before["last"] + 1
        # Only the first question asks about the sound of the take.
        assert "bpm" in questions[0]["question"]
        assert all("bpm" not in q["question"] for q in questions[1:])
        assert all("missing_lines" in q["question"] for q in questions)
        assert "[Verse 1]" in questions[1]["question"]   # the section is named again

    def test_instrumental_track_gets_one_question_about_the_sound(self, song):
        song(instrumental_fm="true", instrumental_table="Yes",
             lyrics="[Intro]\n\n[Main Theme]\n\n[End]", log_rows=(_row(1, CLIP_A),))
        plan = _plan()
        assert plan["instrumental"] is True
        assert plan["lines"] == []
        assert plan["targets"]["vocal_gender"] is None
        (question,) = plan["questions"]
        assert (question["first"], question["last"]) == (0, 0)
        assert "instrumental" in question["question"]
        assert "has_vocals" in question["question"]
        assert "missing_lines" not in question["question"]

    def test_tempo_range_and_musical_direction_fallback(self, song):
        song(style="Dark trap, 130-140 BPM, 808s", log_rows=(_row(1, CLIP_A),))
        assert _plan()["targets"]["bpm"] == [130, 140]
        song(style="Dark trap, heavy 808s", log_rows=(_row(1, CLIP_A),))
        assert _plan()["targets"]["bpm"] is None

    def test_no_exclusions(self, song):
        song(exclude="(none)", lyrics=LYRICS, log_rows=(_row(1, CLIP_A),))
        assert _plan()["targets"]["exclude"] == []

    def test_old_style_no_exclusions_are_read_bare(self, song):
        song(exclude="no drums, no piano solo", lyrics=LYRICS, log_rows=(_row(1, CLIP_A),))
        assert _plan()["targets"]["exclude"] == ["drums", "piano solo"]

    def test_default_takes_are_the_ones_awaiting_a_decision(self, song):
        song(lyrics=LYRICS, log_rows=(
            _row(1, CLIP_A), _row(2, CLIP_B),
            _row(3, "71af26e1-7ca6-486b-8511-a5a93ddc10df"),
            _row(4, "ede52b0a-e021-4b7e-8954-bc7628a969f6"),
        ))
        assert _plan()["default_takes"] == [3, 4]

    def test_a_keeper_is_the_default_once_chosen(self, song):
        song(lyrics=LYRICS, log_rows=(_row(1, CLIP_A), _row(2, CLIP_B, rating="✓")))
        plan = _plan()
        assert plan["takes"][1]["keeper"] is True
        assert plan["default_takes"] == [2]

    def test_legacy_share_links_cannot_be_checked(self, song):
        song(lyrics=LYRICS, log_rows=(LEGACY_KEEPER_ROW,))
        plan = _plan()
        assert plan["takes"] == []
        assert plan["default_takes"] == []

    def test_config_switch(self, song):
        song.state["config"]["generation"] = {"take_check": False}
        assert _plan()["enabled"] is False

    def test_unknown_track(self, song):
        assert _plan("99-missing")["found"] is False


# ===========================================================================
# evaluate_take_check
# ===========================================================================


class TestEvaluateTakeCheck:
    def test_clean_take(self, song):
        result = _evaluate([_clean()])
        assert result["found"] is True
        assert result["clip_id"] == CLIP_A
        assert result["take"] == 1
        assert result["status"] == "ok"
        assert result["summary"] == "nothing flagged"
        assert _check(result, "lyrics") == {
            "check": "lyrics", "status": "ok", "detail": "all 5 lines sung as written",
        }
        assert _check(result, "tempo")["status"] == "ok"
        assert _check(result, "vocal")["status"] == "ok"
        assert _check(result, "excluded") is None
        assert _check(result, "problems") is None
        assert result["flagged_lines"] == {"missing": [], "changed": [], "unclear": []}
        assert result["changes"] == []

    def test_what_was_heard_instead_is_passed_on(self, song):
        result = _evaluate([_clean(changed_lines=[1, 2], changes=[
            "line 1: 'Kettle' sounds like 'Cattle'", "line 2: 'are lined up' is sung 'all lined up'",
        ])])
        detail = _check(result, "lyrics")["detail"]
        assert "2 lines sung with different words" in detail
        assert "heard: line 1: 'Kettle' sounds like 'Cattle'; line 2: 'are lined up' is sung 'all lined up'" in detail
        assert len(result["changes"]) == 2

    def test_a_real_answer_with_a_broken_closing_fence_is_read(self, song):
        """Verbatim shape of a real answer: the block ends "}`," not with three backticks."""
        answer = (
            "Most of the lyric is recognizable, but several words differ.\n\n```json\n"
            '{"missing_lines":[],"changed_lines":[1,2],"unclear_lines":[],"bpm":95,"key":"A# major",'
            '"time_signature":"4/4","has_vocals":true,"vocal_gender":"female","vocal":"Soft, airy.",'
            '"instruments":["fingerpicked acoustic guitar"],"problems":["Line 2 says shelf instead of sill."],'
            '"ends_cleanly":true}`,'
        )
        result = _evaluate([answer])
        assert [line["n"] for line in result["flagged_lines"]["changed"]] == [1, 2]
        assert _check(result, "tempo")["status"] == "ok"
        assert _check(result, "unread") is None

    def test_missing_changed_and_unclear_lines_are_quoted(self, song):
        result = _evaluate([_clean(missing_lines=[2], changed_lines=[3], unclear_lines=[1, 2])])
        assert result["status"] == "warn"
        lyrics = _check(result, "lyrics")
        assert lyrics["status"] == "warn"
        assert 'line 2 not sung: "Paper boats are lined up on the sill"' in lyrics["detail"]
        assert 'line 3 sung with different words: "Slow down, slow down, let the hour unfold"' in lyrics["detail"]
        assert 'line 1 hard to understand: "Kettle on, the window fogged with morning"' in lyrics["detail"]
        assert result["flagged_lines"]["missing"] == [{"n": 2, "section": "Verse 1", "text": "Paper boats are lined up on the sill"}]
        assert [line["n"] for line in result["flagged_lines"]["unclear"]] == [1]   # 2 is already missing
        assert result["summary"] == "1 thing to check"

    def test_many_flagged_lines_are_summarised(self, song):
        lines = "\n".join(f"Line number {n}" for n in range(1, 13))
        song(lyrics=f"[Verse]\n{lines}", style=STYLE, log_rows=(_row(1, CLIP_A),))
        detail = _check(_evaluate([_clean(missing_lines=list(range(1, 11)))]), "lyrics")["detail"]
        assert "10 lines not sung" in detail
        assert '"Line number 1"' in detail and "and 7 more" in detail

    def test_line_numbers_can_arrive_as_strings_and_junk_is_ignored(self, song):
        result = _evaluate([_clean(missing_lines=["2", "x", 99, None, 2.0], changed_lines="3")])
        assert [line["n"] for line in result["flagged_lines"]["missing"]] == [2]
        assert result["flagged_lines"]["changed"] == []

    @pytest.mark.parametrize("bpm,status,phrase", [
        (96.2, "ok", "96.2 BPM"),
        ("95", "ok", "95 BPM"),
        (190.3, "ok", "double time"),
        (48, "ok", "half time"),
        (112, "warn", "112 BPM measured, 96 asked"),
        ("190.2 BPM (feels like 95)", "ok", "double time"),
    ])
    def test_tempo(self, song, bpm, status, phrase):
        tempo = _check(_evaluate([_clean(bpm=bpm)]), "tempo")
        assert tempo["status"] == status
        assert phrase in tempo["detail"]

    def test_tempo_range(self, song):
        song(style="Dark trap, 130-140 BPM", lyrics=LYRICS, log_rows=(_row(1, CLIP_A),))
        assert _check(_evaluate([_clean(bpm=137)]), "tempo")["status"] == "ok"
        tempo = _check(_evaluate([_clean(bpm=120)]), "tempo")
        assert tempo["status"] == "warn" and "130-140 asked" in tempo["detail"]

    def test_tempo_without_a_target_is_information(self, song):
        song(style="Indie folk, fingerpicked guitar", lyrics=LYRICS, log_rows=(_row(1, CLIP_A),))
        tempo = _check(_evaluate([_clean(bpm=101)]), "tempo")
        assert tempo["status"] == "info" and "101 BPM" in tempo["detail"]

    def test_no_tempo_in_the_answer(self, song):
        assert _check(_evaluate([_clean(bpm=None)]), "tempo") is None

    def test_key_is_information(self, song):
        assert _check(_evaluate([_clean()]), "key") == {"check": "key", "status": "info", "detail": "G major"}

    @pytest.mark.parametrize("heard,status", [
        ("female", "ok"), ("Female", "ok"), ("male", "warn"), ("mixed", "info"), ("none", "warn"),
    ])
    def test_vocal_gender(self, song, heard, status):
        vocal = _check(_evaluate([_clean(vocal_gender=heard)]), "vocal")
        assert vocal["status"] == status
        if heard == "male":
            assert "male lead heard, female asked" in vocal["detail"]

    def test_vocal_without_a_target_just_describes_the_voice(self, song):
        song(settings={"Vocal Gender": "—"}, lyrics=LYRICS, style=STYLE, log_rows=(_row(1, CLIP_A),))
        vocal = _check(_evaluate([_clean()]), "vocal")
        assert vocal["status"] == "info" and "soft, breathy alto" in vocal["detail"]

    @pytest.mark.parametrize("instruments,vocal,heard", [
        (["fingerpicked acoustic guitar", "soft synth pad"], "alto", ["synth"]),
        (["clean electric guitar", "Synths"], "alto", ["electric guitar", "synth"]),
        (["acoustic guitar"], "alto", []),
        (["electric piano"], "alto", []),                    # "electric guitar" is not "electric piano"
    ])
    def test_excluded_elements_that_are_heard(self, song, instruments, vocal, heard):
        excluded = _check(_evaluate([_clean(instruments=instruments, vocal=vocal)]), "excluded")
        if not heard:
            assert excluded is None
        else:
            assert excluded["status"] == "warn"
            for item in heard:
                assert item in excluded["detail"]

    def test_excluded_plural_matches_a_singular_instrument(self, song):
        song(exclude="drums, choir", lyrics=LYRICS, style=STYLE, log_rows=(_row(1, CLIP_A),))
        excluded = _check(_evaluate([_clean(instruments=["drum machine"], vocal="lead with a choir behind")]), "excluded")
        assert "drums" in excluded["detail"] and "choir" in excluded["detail"]

    def test_problems_and_ending(self, song):
        result = _evaluate([_clean(problems=["clipping in the last chorus"], ends_cleanly=False)])
        assert _check(result, "problems") == {
            "check": "problems", "status": "warn", "detail": "clipping in the last chorus",
        }
        assert _check(result, "ending")["status"] == "warn"
        assert result["summary"] == "2 things to check"

    def test_duration_against_the_track_target(self, song):
        text = song.path.read_text(encoding="utf-8")
        assert "| **Target Duration** |" not in text  # the builder has no such row: no check
        assert _check(_evaluate([_clean()], duration_s=200), "duration") is None

    def test_instrumental_with_a_voice_is_flagged(self, song):
        song(instrumental_fm="true", instrumental_table="Yes",
             lyrics="[Intro]\n\n[End]", style=STYLE, log_rows=(_row(1, CLIP_A),))
        result = _evaluate([_answer(bpm=96, has_vocals=True, vocal_gender="female",
                                    instruments=["piano"], problems=[], ends_cleanly=True)])
        assert _check(result, "lyrics") == {
            "check": "lyrics", "status": "warn", "detail": "a voice is heard on an instrumental track",
        }
        assert _check(result, "vocal") is None
        quiet = _evaluate([_answer(bpm=96, has_vocals=False, vocal_gender="none",
                                   instruments=["piano"], problems=[], ends_cleanly=True)])
        assert _check(quiet, "lyrics") == {"check": "lyrics", "status": "ok", "detail": "no voice heard"}
        assert quiet["status"] == "ok"

    def test_answers_are_merged_across_questions(self, song):
        lines = "\n".join(f"This is lyric line number {n} of a rather long song" for n in range(1, 91))
        song(lyrics=f"[Verse 1]\n{lines}", style=STYLE, log_rows=(_row(1, CLIP_A),))
        questions = _plan()["questions"]
        answers = [_clean(missing_lines=[2])] + [
            _answer(missing_lines=[q["last"]], changed_lines=[], unclear_lines=[]) for q in questions[1:]
        ]
        result = _evaluate(answers)
        flagged = [line["n"] for line in result["flagged_lines"]["missing"]]
        assert flagged == [2] + [q["last"] for q in questions[1:]]
        assert _check(result, "tempo")["status"] == "ok"      # the sound comes from the first answer

    def test_a_line_number_outside_its_question_is_ignored(self, song):
        lines = "\n".join(f"This is lyric line number {n} of a rather long song" for n in range(1, 91))
        song(lyrics=f"[Verse 1]\n{lines}", style=STYLE, log_rows=(_row(1, CLIP_A),))
        questions = _plan()["questions"]
        answers = [_clean(missing_lines=[90])] + [
            _answer(missing_lines=[], changed_lines=[], unclear_lines=[]) for _ in questions[1:]
        ]
        assert _evaluate(answers)["flagged_lines"]["missing"] == []

    def test_an_answer_without_json_leaves_its_lines_unchecked(self, song):
        result = _evaluate(["I could not listen to this song."])
        unread = _check(result, "unread")
        assert unread["status"] == "info"
        assert "lines 1-5 were not checked" in unread["detail"]
        assert _check(result, "lyrics") is None
        assert result["status"] == "ok"

    def test_json_without_a_fence_is_still_read(self, song):
        result = _evaluate(['Here you go: {"missing_lines": [2], "bpm": 96}'])
        assert [line["n"] for line in result["flagged_lines"]["missing"]] == [2]

    def test_the_last_json_block_wins(self, song):
        answer = '```json\n{"missing_lines": [1]}\n```\nCorrection:\n```json\n{"missing_lines": [3], "bpm": 96}\n```'
        assert [line["n"] for line in _evaluate([answer])["flagged_lines"]["missing"]] == [3]

    def test_wrong_number_of_answers(self, song):
        result = _evaluate([_clean(), _clean()])
        assert "error" in result and "1 answer" in result["error"]

    def test_take_is_null_for_a_clip_the_log_does_not_hold(self, song):
        assert _evaluate([_clean()], clip_id="0f3c6c19-0c42-4d4f-9a37-7f5fd1bd2e01")["take"] is None

    @pytest.mark.parametrize("bad", ["", "not-a-clip", "../../etc/passwd"])
    def test_bad_clip_id(self, song, bad):
        assert "error" in _evaluate([_clean()], clip_id=bad)

    def test_unknown_track(self, song):
        result = json.loads(_run(_check_mod.evaluate_take_check("test-album", "99-missing", CLIP_A, [_clean()])))
        assert result["found"] is False


class TestVersionsAreNotChecked:
    def test_an_instrumental_version_is_left_out(self, song):
        """The lyric check has nothing to hold an instrumental version against."""
        song(lyrics=LYRICS, log_rows=(
            _row(1, CLIP_A),
            _row(2, CLIP_B, notes="0:55, instrumental version of take 1, via MCP, 10 credits"),
        ))
        plan = _plan()
        assert [take["take"] for take in plan["takes"]] == [1]
        assert plan["default_takes"] == [1]
