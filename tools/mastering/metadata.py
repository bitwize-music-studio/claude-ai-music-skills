"""ID3v2.4 metadata embedding for mastered WAV delivery files (#290).

Embeds artist, album, title, track number, year, genre, copyright, label,
ISRC, and UPC into WAV files using ID3v2.4 tags via mutagen. All fields are
optional; unset fields are silently skipped.

Tag mapping:
  title          → TIT2 (track title)
  artist         → TPE1 (lead artist)
  album          → TALB (album name)
  track_number   → TRCK (track number)
  year           → TDRC (recording year)
  genre          → TCON (content type / genre)
  copyright_text → TCOP (copyright message)
  label          → TPUB (publisher/label)
  isrc           → TSRC (ISRC code, per-track)
  upc            → TXXX:UPC (album UPC/EAN barcode, per-track copy)
"""

from __future__ import annotations

from pathlib import Path


class MetadataEmbedError(RuntimeError):
    """Raised when metadata embedding cannot proceed (missing file, mutagen error)."""


def embed_wav_metadata(
    path: Path | str,
    *,
    title: str = "",
    artist: str = "",
    album: str = "",
    track_number: str = "",
    year: str = "",
    genre: str = "",
    copyright_text: str = "",
    label: str = "",
    isrc: str = "",
    upc: str = "",
) -> None:
    """Embed ID3v2.4 tags into a WAV file in-place.

    Args:
        path:           Path to the WAV file (modified in-place).
        title:          Track title (TIT2).
        artist:         Lead artist (TPE1).
        album:          Album name (TALB).
        track_number:   Track number (TRCK). Optional.
        year:           Recording year (TDRC). Optional.
        genre:          Genre / content type (TCON). Optional.
        copyright_text: Copyright notice, e.g. "2026 bitwize" (TCOP).
        label:          Label/publisher (TPUB).
        isrc:           Per-track ISRC code (TSRC). Optional.
        upc:            Album UPC/EAN barcode (TXXX:UPC). Optional.

    Raises:
        MetadataEmbedError: File not found or mutagen write fails.
    """
    from mutagen.id3 import TALB, TCON, TCOP, TDRC, TIT2, TPUB, TPE1, TRCK, TSRC, TXXX
    from mutagen.wave import WAVE

    path = Path(path)
    if not path.is_file():
        raise MetadataEmbedError(f"WAV file not found: {path}")

    try:
        audio = WAVE(str(path))
    except Exception as exc:
        raise MetadataEmbedError(f"Could not open {path.name}: {exc}") from exc

    if audio.tags is None:
        audio.add_tags()

    tags = audio.tags
    if title:
        tags.add(TIT2(encoding=3, text=title))
    if artist:
        tags.add(TPE1(encoding=3, text=artist))
    if album:
        tags.add(TALB(encoding=3, text=album))
    if track_number:
        tags.add(TRCK(encoding=3, text=track_number))
    if year:
        tags.add(TDRC(encoding=3, text=year))
    if genre:
        tags.add(TCON(encoding=3, text=genre))
    if copyright_text:
        tags.add(TCOP(encoding=3, text=copyright_text))
    if label:
        tags.add(TPUB(encoding=3, text=label))
    if isrc:
        tags.add(TSRC(encoding=3, text=isrc))
    if upc:
        tags.add(TXXX(encoding=3, desc="UPC", text=upc))

    try:
        audio.save()
    except Exception as exc:
        raise MetadataEmbedError(f"Could not save tags to {path.name}: {exc}") from exc
