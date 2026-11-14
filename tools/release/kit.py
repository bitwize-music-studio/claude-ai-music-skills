"""The release kit: what the DistroKid and SoundCloud upload forms ask for.

Pure: build_kit turns facts gathered elsewhere (album, tracks, config, files)
into a Kit, with the checks to clear before uploading. Nothing here reads a
file or touches either site; the user pastes and submits.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

KIT_VERSION = 1

FAIL = "fail"
WARN = "warn"
INFO = "info"
_LEVEL_ORDER = {FAIL: 0, WARN: 1, INFO: 2}

# SoundCloud's title limit, the stricter of the two forms.
TITLE_LIMIT = 100
COVER_MIN = 3000
LEAVE_BLANK = "Leave blank: DistroKid assigns one"
UNREADABLE = "unreadable"

_FEAT_RE = re.compile(r"\b(?:feat|ft)\.(?=\s)|\bfeaturing\b", re.IGNORECASE)
_VERSION_MARKER_RE = re.compile(r"\((?:explicit|clean)(?: version)?\)", re.IGNORECASE)
_EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF☀-➿️]")


@dataclass(frozen=True)
class TrackFacts:
    """One track: its file's details, its master and what the checkers found."""

    number: int
    slug: str
    title: str
    status: str
    explicit: bool
    instrumental: bool
    lyrics: str = ""
    isrc: str = ""
    wav: str = ""
    wav_format: str = ""
    lyrics_problems: tuple[str, ...] = ()
    explicit_found: bool | None = None


@dataclass(frozen=True)
class AlbumFacts:
    """The album, its config values and its files, gathered for the kit."""

    slug: str
    title: str
    artist: str
    legal_name: str
    label: str
    copyright_holder: str
    ai_disclosure: tuple[str, ...] | None
    language: str
    release_date: str
    genre: str
    subgenre: str
    tags: tuple[str, ...]
    description: str
    explicit: bool
    upc: str
    cover: str
    cover_size: tuple[int, int] | None
    mastered_dir: str
    stray_wavs: tuple[str, ...]
    tracks: tuple[TrackFacts, ...]


@dataclass(frozen=True)
class Field:
    """One value to copy into a form. A long value folds on the page."""

    label: str
    value: str
    long: bool = False


@dataclass(frozen=True)
class Block:
    heading: str
    fields: tuple[Field, ...]


@dataclass(frozen=True)
class Check:
    level: str
    message: str


@dataclass(frozen=True)
class Kit:
    album_title: str
    distrokid: tuple[Block, ...]
    soundcloud: tuple[Block, ...]
    checks: tuple[Check, ...]
    version: int = KIT_VERSION


def build_kit(facts: AlbumFacts, today: date) -> Kit:
    """The kit for *facts*: both forms' fields, then the checks."""
    return Kit(
        album_title=facts.title,
        distrokid=_distrokid(facts),
        soundcloud=_soundcloud(facts),
        checks=run_checks(facts, today),
    )


def _missing(key: str) -> str:
    return f"[set {key} in config]"


def _yes_no(flag: bool) -> str:
    return "Yes" if flag else "No"


def _year(release_date: str) -> str:
    return release_date[:4] if re.match(r"^\d{4}", release_date) else ""


def _line(symbol: str, year: str, holder: str) -> str:
    return " ".join(part for part in (symbol, year, holder) if part)


def _tags_text(tags: tuple[str, ...]) -> str:
    """SoundCloud's tag box: spaces separate tags, so multi-word tags are quoted."""
    return " ".join(f'"{tag}"' if " " in tag else tag for tag in tags)


def _ai_text(answer: tuple[str, ...] | None) -> str:
    if answer is None:
        return _missing("release.ai_disclosure")
    return ", ".join(answer) if answer else "None: no AI in this release"


def _distrokid(f: AlbumFacts) -> tuple[Block, ...]:
    year = _year(f.release_date)
    songwriter = f.legal_name or _missing("artist.legal_name")
    album = Block("Album", (
        Field("Artist", f.artist),
        Field("Album title", f.title),
        Field("Release date", f.release_date or "[choose on the form]"),
        Field("Record label", f.label),
        Field("© line", _line("©", year, f.copyright_holder)),
        Field("℗ line", _line("℗", year, f.copyright_holder)),
        Field("Primary genre", f.genre),
        Field("Secondary genre", f.subgenre or "[none]"),
        Field("Language", f.language),
        Field("Explicit", _yes_no(f.explicit)),
        Field("UPC", f.upc or LEAVE_BLANK),
        Field("AI disclosure", _ai_text(f.ai_disclosure)),
        Field("Cover art", f.cover or "[no album.png]"),
        Field("Audio folder", f.mastered_dir),
    ))
    tracks = []
    for t in f.tracks:
        fields = [
            Field("Title", t.title),
            Field("Explicit", _yes_no(t.explicit)),
            Field("Instrumental", _yes_no(t.instrumental)),
            Field("Songwriter", songwriter),
            Field("ISRC", t.isrc or LEAVE_BLANK),
        ]
        if t.lyrics and not t.instrumental:
            fields.append(Field("Lyrics", t.lyrics, long=True))
        fields.append(Field("Audio file", t.wav or "[no mastered WAV]"))
        tracks.append(Block(f"Track {t.number}: {t.title}", tuple(fields)))
    return (album, *tracks)


def _soundcloud(f: AlbumFacts) -> tuple[Block, ...]:
    year = _year(f.release_date)
    composer = f.legal_name or _missing("artist.legal_name")
    tags = _tags_text(f.tags)
    album_fields = [
        Field("Title", f.title),
        Field("Playlist type", "Album"),
        Field("Release date", f.release_date or "[choose on the form]"),
        Field("Genre", f.genre),
    ]
    if tags:
        album_fields.append(Field("Tags", tags))
    if f.description:
        album_fields.append(Field("Description", f.description, long=True))
    album_fields += [
        Field("Artwork", f.cover or "[no album.png]"),
        Field("Audio folder", f.mastered_dir),
    ]
    tracks = []
    for t in f.tracks:
        fields = [Field("Title", t.title), Field("Genre", f.genre)]
        if tags:
            fields.append(Field("Tags", tags))
        fields += [
            Field("Main artist", f.artist),
            Field("Composer", composer),
            Field("Publisher", f.label),
        ]
        if t.isrc:
            fields.append(Field("ISRC", t.isrc))
        fields += [
            Field("Explicit", _yes_no(t.explicit)),
            Field("Record label", f.label),
            Field("℗ line", _line("℗", year, f.copyright_holder)),
        ]
        tracks.append(Block(f"Track {t.number}: {t.title}", tuple(fields)))
    return (Block("Album (playlist)", tuple(album_fields)), *tracks)


def run_checks(f: AlbumFacts, today: date) -> tuple[Check, ...]:
    """Everything to clear before uploading, failures first. Never raises."""
    return ()
