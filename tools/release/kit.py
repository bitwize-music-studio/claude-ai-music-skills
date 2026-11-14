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
        Field("Cover art", f.cover or "[no cover]"),
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
        Field("Artwork", f.cover or "[no cover]"),
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
    checks: list[Check] = []
    for t in f.tracks:
        if not t.wav:
            checks.append(Check(FAIL, f"Track {t.number} ({t.title}) has no mastered WAV"))
        elif t.wav_format == UNREADABLE:
            checks.append(Check(FAIL, f"Track {t.number} ({t.title}) has a master that can't be read as a WAV"))
    for name in f.stray_wavs:
        checks.append(Check(FAIL, f"mastered/{name} matches no track: move it out before uploading"))
    checks += _cover_checks(f)
    if not f.legal_name:
        checks.append(Check(FAIL, "Set artist.legal_name in config: DistroKid needs the songwriter's real name"))
    if f.ai_disclosure is None:
        checks.append(Check(
            FAIL,
            "Set release.ai_disclosure in config: your standard answer to DistroKid's AI "
            "question ([] for none)",
        ))
    checks += _date_checks(f.release_date, today)
    checks += _title_checks("Album title", f.title)
    for t in f.tracks:
        checks += _title_checks(f"Track {t.number} title", t.title)
        checks += _track_checks(t)
    not_final = [str(t.number) for t in f.tracks if t.status != "Final"]
    if not_final:
        checks.append(Check(WARN, "Not Final yet: track " + ", ".join(not_final)))
    formats = sorted({t.wav_format for t in f.tracks if t.wav_format and t.wav_format != UNREADABLE})
    if formats:
        checks.append(Check(INFO, "Masters: " + "; ".join(formats)))
    return tuple(sorted(checks, key=lambda c: _LEVEL_ORDER[c.level]))


def _cover_checks(f: AlbumFacts) -> list[Check]:
    if not f.cover:
        return [Check(FAIL, "No cover (album.png or album.jpg) beside mastered/: add it with /bitwize-music:import-art")]
    if f.cover_size is None:
        return [Check(FAIL, "The cover can't be read as an image")]
    width, height = f.cover_size
    # Written as an escape: ruff's RUF001 rejects the multiplication sign as a literal.
    if width != height:
        return [Check(FAIL, f"The cover is {width}\u00d7{height}: it must be square")]
    if width < COVER_MIN:
        # Stores recommend 3000x3000, but smaller square covers have gone out.
        return [Check(WARN, f"The cover is {width}\u00d7{height}, under the "
                            f"{COVER_MIN}\u00d7{COVER_MIN} stores recommend")]
    return []


def _date_checks(release_date: str, today: date) -> list[Check]:
    if not release_date:
        return [Check(WARN, "No release date in the album README: set release_date, or choose it on the form")]
    try:
        when = date.fromisoformat(release_date)
    except ValueError:
        return [Check(WARN, f"Release date {release_date!r} isn't YYYY-MM-DD")]
    if when < today:
        return [Check(WARN, f"Release date {release_date} is in the past")]
    return []


def _title_checks(what: str, title: str) -> list[Check]:
    if not title.strip():
        return [Check(WARN, f"{what} is empty")]
    found = []
    if _FEAT_RE.search(title):
        found.append(f"{what} names a featured artist: both forms have a field for that")
    if _VERSION_MARKER_RE.search(title):
        found.append(f"{what} says (Explicit) or (Clean): set the explicit flag instead")
    if _EMOJI_RE.search(title):
        found.append(f"{what} has an emoji, which stores reject")
    if len(title) > TITLE_LIMIT:
        found.append(f"{what} is {len(title)} characters: SoundCloud allows {TITLE_LIMIT}")
    return [Check(WARN, message) for message in found]


def _track_checks(t: TrackFacts) -> list[Check]:
    checks: list[Check] = []
    name = f"Track {t.number} ({t.title})"
    if t.explicit_found is not None and t.explicit_found != t.explicit:
        if t.explicit:
            checks.append(Check(WARN, f"{name} is marked explicit, but no explicit words were found"))
        else:
            checks.append(Check(WARN, f"{name} has explicit words but isn't marked explicit"))
    if not t.instrumental:
        if not t.lyrics:
            checks.append(Check(WARN, f"{name} has no Streaming Lyrics"))
        elif t.lyrics_problems:
            checks.append(Check(WARN, f"{name} Streaming Lyrics: " + "; ".join(t.lyrics_problems)))
    return checks
