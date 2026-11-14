"""The album's listening playlist: an extended M3U in UTF-8 (``.m3u8``).

Mastering writes ``<album slug>.m3u8`` beside ``mastered/``, never inside it:
``mastered/`` is what goes to the distributor, so it stays WAV-only. Each
entry is a path relative to the playlist, so the album folder can be moved,
or opened from another machine, and the playlist still plays.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

PLAYLIST_SUFFIX = ".m3u8"


@dataclass(frozen=True)
class PlaylistEntry:
    """One track of the playlist."""

    path: str
    """Relative to the playlist's folder, with forward slashes."""
    seconds: int
    """The track's length, rounded; -1 when it is not known."""
    title: str
    """What a player shows for the track."""


def playlist_path(audio_dir: Path, album_slug: str) -> Path:
    """Where an album's playlist goes: ``<audio dir>/<album slug>.m3u8``."""
    return audio_dir / f"{album_slug}{PLAYLIST_SUFFIX}"


def render_m3u8(album_name: str, entries: list[PlaylistEntry]) -> str:
    """The playlist's text: ``#EXTM3U``, the album's name, then each track in order."""
    lines = ["#EXTM3U"]
    name = _one_line(album_name)
    if name:
        lines.append(f"#PLAYLIST:{name}")
    for entry in entries:
        lines.append(f"#EXTINF:{entry.seconds},{_one_line(entry.title)}")
        lines.append(entry.path)
    return "\n".join(lines) + "\n"


def _one_line(text: str) -> str:
    """Collapse whitespace: a line break in a name would start another entry."""
    return " ".join(text.split())
