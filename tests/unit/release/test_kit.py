"""The release kit's fields and checks, from gathered facts. Pure: no files."""

from __future__ import annotations

import sys
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.release.kit import (
    FAIL,
    INFO,
    LEAVE_BLANK,
    WARN,
    AlbumFacts,
    TrackFacts,
    build_kit,
)

pytestmark = pytest.mark.unit

TODAY = date(2000, 1, 1)


def _track(number: int = 1, **changes) -> TrackFacts:
    base = TrackFacts(
        number=number, slug=f"{number:02d}-harbor", title="Harbor", status="Final",
        explicit=False, instrumental=False, lyrics="Paper boats on the water",
        wav=f"/audio/mastered/{number:02d}-harbor.wav", wav_format="PCM_24 96000 Hz",
        explicit_found=False,
    )
    return replace(base, **changes)


def _facts(**changes) -> AlbumFacts:
    base = AlbumFacts(
        slug="paper-boats", title="Paper Boats", artist="bitwize",
        legal_name="Jane Q. Writer", label="bitwize", copyright_holder="bitwize",
        ai_disclosure=("Vocals", "Instrumental"), language="English",
        release_date="2000-02-01", genre="Folk", subgenre="Indie Folk",
        tags=("folk", "sea shanty"), description="Songs about small boats.",
        explicit=False, upc="", cover="/audio/album.png", cover_size=(3000, 3000),
        mastered_dir="/audio/mastered", stray_wavs=(), tracks=(_track(1),),
    )
    return replace(base, **changes)


def _fields(block) -> dict[str, str]:
    return {f.label: f.value for f in block.fields}


class TestDistroKid:
    def test_album_block(self):
        album = _fields(build_kit(_facts(), TODAY).distrokid[0])
        assert album["Artist"] == "bitwize"
        assert album["Album title"] == "Paper Boats"
        assert album["Release date"] == "2000-02-01"
        assert album["Record label"] == "bitwize"
        assert album["© line"] == "© 2000 bitwize"
        assert album["℗ line"] == "℗ 2000 bitwize"
        assert album["Primary genre"] == "Folk"
        assert album["Secondary genre"] == "Indie Folk"
        assert album["Language"] == "English"
        assert album["Explicit"] == "No"
        assert album["UPC"] == LEAVE_BLANK
        assert album["AI disclosure"] == "Vocals, Instrumental"
        assert album["Cover art"] == "/audio/album.png"
        assert album["Audio folder"] == "/audio/mastered"

    def test_track_block(self):
        block = build_kit(_facts(), TODAY).distrokid[1]
        assert block.heading == "Track 1: Harbor"
        track = _fields(block)
        assert track["Title"] == "Harbor"
        assert track["Songwriter"] == "Jane Q. Writer"
        assert track["ISRC"] == LEAVE_BLANK
        assert track["Lyrics"] == "Paper boats on the water"
        assert track["Audio file"] == "/audio/mastered/01-harbor.wav"
        assert next(f for f in block.fields if f.label == "Lyrics").long is True

    def test_an_instrumental_has_no_lyrics_field(self):
        facts = _facts(tracks=(_track(1, instrumental=True, lyrics=""),))
        track = _fields(build_kit(facts, TODAY).distrokid[1])
        assert "Lyrics" not in track
        assert track["Instrumental"] == "Yes"

    def test_codes_already_held_are_used(self):
        facts = _facts(upc="123456789012", tracks=(_track(1, isrc="QZABC2000001"),))
        kit = build_kit(facts, TODAY)
        assert _fields(kit.distrokid[0])["UPC"] == "123456789012"
        assert _fields(kit.distrokid[1])["ISRC"] == "QZABC2000001"

    def test_missing_config_shows_where_to_set_it(self):
        kit = build_kit(_facts(legal_name="", ai_disclosure=None), TODAY)
        assert _fields(kit.distrokid[1])["Songwriter"] == "[set artist.legal_name in config]"
        assert _fields(kit.distrokid[0])["AI disclosure"] == "[set release.ai_disclosure in config]"

    def test_an_empty_ai_answer_means_none(self):
        kit = build_kit(_facts(ai_disclosure=()), TODAY)
        assert _fields(kit.distrokid[0])["AI disclosure"] == "None: no AI in this release"


class TestSoundCloud:
    def test_album_playlist_block(self):
        album = _fields(build_kit(_facts(), TODAY).soundcloud[0])
        assert album["Title"] == "Paper Boats"
        assert album["Playlist type"] == "Album"
        assert album["Tags"] == 'folk "sea shanty"'
        assert album["Description"] == "Songs about small boats."
        assert album["Artwork"] == "/audio/album.png"

    def test_track_block(self):
        track = _fields(build_kit(_facts(), TODAY).soundcloud[1])
        assert track["Main artist"] == "bitwize"
        assert track["Composer"] == "Jane Q. Writer"
        assert track["Publisher"] == "bitwize"
        assert track["℗ line"] == "℗ 2000 bitwize"
        assert "ISRC" not in track  # SoundCloud assigns none; shown only when held

    def test_no_description_no_field(self):
        album = _fields(build_kit(_facts(description=""), TODAY).soundcloud[0])
        assert "Description" not in album


def _messages(facts, level=None, today=TODAY):
    return [c.message for c in build_kit(facts, today).checks if level in (None, c.level)]


class TestChecks:
    def test_a_ready_album_has_only_the_format_note(self):
        checks = build_kit(_facts(), TODAY).checks
        assert [(c.level, c.message) for c in checks] == [(INFO, "Masters: PCM_24 96000 Hz")]

    def test_failures_come_first(self):
        facts = _facts(release_date="", legal_name="")
        levels = [c.level for c in build_kit(facts, TODAY).checks]
        assert levels == sorted(levels, key=[FAIL, WARN, INFO].index)

    def test_a_track_without_a_master(self):
        assert _messages(_facts(tracks=(_track(1, wav="", wav_format=""),)), FAIL) == [
            "Track 1 (Harbor) has no mastered WAV"]

    def test_an_unreadable_master(self):
        assert _messages(_facts(tracks=(_track(1, wav_format="unreadable"),)), FAIL) == [
            "Track 1 (Harbor) has a master that can't be read as a WAV"]

    def test_a_stray_wav(self):
        assert _messages(_facts(stray_wavs=("99-demo.wav",)), FAIL) == [
            "mastered/99-demo.wav matches no track: move it out before uploading"]

    @pytest.mark.parametrize("cover, size, message", [
        ("", None, "No cover (album.png or album.jpg) beside mastered/: add it with /bitwize-music:import-art"),
        ("/a/album.png", None, "The cover can't be read as an image"),
        ("/a/album.png", (3000, 2000), "The cover is 3000×2000: it must be square"),
    ])
    def test_a_cover_that_blocks(self, cover, size, message):
        assert _messages(_facts(cover=cover, cover_size=size), FAIL) == [message]

    def test_a_small_square_cover_only_warns(self):
        """Stores recommend 3000×3000, but a smaller square cover has gone out."""
        facts = _facts(cover_size=(2508, 2508))
        assert _messages(facts, FAIL) == []
        assert _messages(facts, WARN) == [
            "The cover is 2508×2508, under the 3000×3000 stores recommend"]

    def test_a_code_that_isnt_one_is_left_blank_with_a_warning(self):
        facts = _facts(upc_ignored="TBD", tracks=(_track(1, isrc_ignored="pending"),))
        assert _messages(facts, WARN) == [
            "UPC 'TBD' in the album README isn't a UPC (12 or 13 digits): fix it, "
            "or the field stays blank and DistroKid assigns one",
            "Track 1 (Harbor) ISRC 'pending' isn't an ISRC (12 characters, like "
            "USABC2300001): fix it, or the field stays blank and DistroKid assigns one",
        ]
        kit = build_kit(facts, TODAY)
        assert _fields(kit.distrokid[0])["UPC"] == LEAVE_BLANK
        assert _fields(kit.distrokid[1])["ISRC"] == LEAVE_BLANK

    def test_missing_config(self):
        assert _messages(_facts(legal_name="", ai_disclosure=None), FAIL) == [
            "Set artist.legal_name in config: DistroKid needs the songwriter's real name",
            "Set release.ai_disclosure in config: your standard answer to DistroKid's AI "
            "question ([] for none)",
        ]

    @pytest.mark.parametrize("release_date, message", [
        ("", "No release date in the album README: set release_date, or choose it on the form"),
        ("someday", "Release date 'someday' isn't YYYY-MM-DD"),
        ("1999-12-31", "Release date 1999-12-31 is in the past"),
    ])
    def test_the_release_date(self, release_date, message):
        assert _messages(_facts(release_date=release_date), WARN) == [message]

    @pytest.mark.parametrize("title, message", [
        ("", "Track 1 title is empty"),
        ("Harbor (feat. Gulls)", "Track 1 title names a featured artist: both forms have a field for that"),
        ("Harbor ft. Gulls", "Track 1 title names a featured artist: both forms have a field for that"),
        ("Harbor (Explicit)", "Track 1 title says (Explicit) or (Clean): set the explicit flag instead"),
        ("Harbor 🌊", "Track 1 title has an emoji, which stores reject"),
        ("H" * 101, "Track 1 title is 101 characters: SoundCloud allows 100"),
    ])
    def test_track_titles(self, title, message):
        assert message in _messages(_facts(tracks=(_track(1, title=title),)), WARN)

    def test_a_word_containing_ft_is_fine(self):
        assert _messages(_facts(tracks=(_track(1, title="Left Behind"),)), WARN) == []

    def test_the_album_title_is_checked_too(self):
        assert _messages(_facts(title="Boats 🌊"), WARN) == [
            "Album title has an emoji, which stores reject"]

    @pytest.mark.parametrize("explicit, found, message", [
        (True, False, "Track 1 (Harbor) is marked explicit, but no explicit words were found"),
        (False, True, "Track 1 (Harbor) has explicit words but isn't marked explicit"),
    ])
    def test_the_explicit_flag(self, explicit, found, message):
        facts = _facts(tracks=(_track(1, explicit=explicit, explicit_found=found),))
        assert _messages(facts, WARN) == [message]

    def test_lyrics(self):
        assert _messages(_facts(tracks=(_track(1, lyrics=""),)), WARN) == [
            "Track 1 (Harbor) has no Streaming Lyrics"]
        facts = _facts(tracks=(_track(1, lyrics_problems=("Section tags found",)),))
        assert _messages(facts, WARN) == ["Track 1 (Harbor) Streaming Lyrics: Section tags found"]

    def test_an_instrumental_needs_no_lyrics(self):
        facts = _facts(tracks=(_track(1, instrumental=True, lyrics="",
                                      lyrics_problems=("Section missing",)),))
        assert _messages(facts, WARN) == []

    def test_tracks_not_final(self):
        facts = _facts(tracks=(_track(1), _track(2, status="Generated"), _track(3, status="In Progress")))
        assert _messages(facts, WARN) == ["Not Final yet: track 2, 3"]

    def test_formats_are_listed_once_each(self):
        facts = _facts(tracks=(_track(1), _track(2), _track(3, wav_format="PCM_16 44100 Hz")))
        assert _messages(facts, INFO) == ["Masters: PCM_16 44100 Hz; PCM_24 96000 Hz"]
