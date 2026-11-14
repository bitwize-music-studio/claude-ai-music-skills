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
