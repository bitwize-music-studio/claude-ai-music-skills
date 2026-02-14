"""Path resolver utility for bitwize-music tools.

Eliminates manual path construction across skills by providing a single
function that resolves content, audio, and document paths correctly.

The mirrored path structure:
    {content_root}/artists/[artist]/albums/[genre]/[album]/   # Content
    {audio_root}/artists/[artist]/albums/[genre]/[album]/     # Audio
    {documents_root}/artists/[artist]/albums/[genre]/[album]/ # Documents
"""

import os
from pathlib import Path
from typing import Optional

from tools.shared.config import load_config


def resolve_path(
    path_type: str,
    album: str,
    artist: Optional[str] = None,
    genre: Optional[str] = None,
    config: Optional[dict] = None,
) -> Path:
    """Resolve a path for the given type and album.

    Args:
        path_type: One of "content", "audio", "documents".
        album: Album slug (e.g., "my-album").
        artist: Artist name override. If None, reads from config.
        genre: Genre slug (required for all path types).
        config: Pre-loaded config dict. If None, loads from disk.

    Returns:
        Resolved absolute Path.

    Raises:
        ValueError: If path_type is invalid or required args are missing.
    """
    if path_type not in ("content", "audio", "documents"):
        raise ValueError(
            f"Invalid path_type '{path_type}'. Must be 'content', 'audio', or 'documents'."
        )

    if config is None:
        config = load_config(required=True)

    if artist is None:
        artist = config.get("artist", {}).get("name", "")
    if not artist:
        raise ValueError("Artist name is required but not found in config.")

    paths = config.get("paths", {})

    if not genre:
        raise ValueError("Genre is required for path resolution.")

    root_keys = {
        "content": "content_root",
        "audio": "audio_root",
        "documents": "documents_root",
    }
    root = paths.get(root_keys[path_type], ".")
    base = Path(os.path.expanduser(root)).resolve()
    return base / "artists" / artist / "albums" / genre / album


def resolve_tracks_dir(
    album: str,
    genre: str,
    artist: Optional[str] = None,
    config: Optional[dict] = None,
) -> Path:
    """Resolve the tracks/ directory for an album.

    Convenience wrapper around resolve_path for the common case.

    Args:
        album: Album slug.
        genre: Genre slug.
        artist: Artist name override.
        config: Pre-loaded config dict.

    Returns:
        Path to the tracks/ directory.
    """
    return resolve_path("content", album, artist=artist, genre=genre, config=config) / "tracks"


def resolve_overrides_dir(config: Optional[dict] = None) -> Path:
    """Resolve the overrides directory path.

    Args:
        config: Pre-loaded config dict. If None, loads from disk.

    Returns:
        Path to overrides directory.
    """
    if config is None:
        config = load_config(required=True)

    paths = config.get("paths", {})
    overrides_raw = paths.get("overrides", "")

    if overrides_raw:
        return Path(os.path.expanduser(overrides_raw)).resolve()

    # Default: {content_root}/overrides
    content_root = paths.get("content_root", ".")
    return Path(os.path.expanduser(content_root)).resolve() / "overrides"
