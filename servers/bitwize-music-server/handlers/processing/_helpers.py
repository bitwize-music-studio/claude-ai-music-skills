"""Shared helpers for processing submodules."""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

from handlers import _shared
from handlers._shared import _normalize_slug
from handlers._shared import _resolve_audio_dir as _resolve_audio_dir  # noqa: F401


def _extract_track_number_from_stem(stem: str) -> int | None:
    """Extract leading digits from a stem like '01-first-pour' -> 1."""
    match = re.match(r'^(\d+)', stem)
    return int(match.group(1)) if match else None


def _build_title_map(album_slug: str, wav_files: list[Path]) -> dict[str, str]:
    """Map WAV stems to clean titles from state cache, falling back to slug_to_title.

    Returns dict: {stem: clean_title} e.g. {"01-first-pour": "First Pour"}
    """
    from tools.shared.text_utils import sanitize_filename, slug_to_title

    # Try to get track titles from state cache
    state = _shared.cache.get_state()
    albums = state.get("albums", {})
    album = albums.get(_normalize_slug(album_slug), {})
    tracks = album.get("tracks", {})

    title_map = {}
    for wav_file in wav_files:
        stem = wav_file.stem  # e.g. "01-first-pour"
        # Try matching stem directly in cache tracks
        if stem in tracks:
            title = tracks[stem].get("title", slug_to_title(stem))
        else:
            # Try without leading number prefix (e.g. "first-pour")
            stripped = re.sub(r'^\d+-', '', stem)
            if stripped in tracks:
                title = tracks[stripped].get("title", slug_to_title(stem))
            else:
                # Fallback: derive title from slug
                title = slug_to_title(stem)
        title_map[stem] = sanitize_filename(title)

    return title_map


def _check_mastering_deps() -> str | None:
    """Return error message if mastering deps missing, else None."""
    missing = []
    for mod in ("numpy", "scipy", "soundfile", "pyloudnorm"):
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    if missing:
        return (
            f"Missing mastering dependencies: {', '.join(missing)}. "
            "Install: pip install pyloudnorm scipy numpy soundfile"
        )
    return None


def _check_ffmpeg() -> str | None:
    """Return error message if ffmpeg not found, else None."""
    if not shutil.which("ffmpeg"):
        return (
            "ffmpeg not found. Install: "
            "brew install ffmpeg (macOS) or apt install ffmpeg (Linux)"
        )
    return None


def _check_matchering() -> str | None:
    """Return error message if matchering not installed, else None."""
    try:
        __import__("matchering")
    except ImportError:
        return "matchering not installed. Install: pip install matchering"
    return None


def _import_sheet_music_module(module_name: str) -> Any:
    """Import a module from tools/sheet-music/ using importlib (hyphenated dir)."""
    import importlib.util
    assert _shared.PLUGIN_ROOT is not None
    module_path = _shared.PLUGIN_ROOT / "tools" / "sheet-music" / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(
        f"sheet_music_{module_name}", str(module_path)
    )
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _import_cloud_module(module_name: str) -> Any:
    """Import a module from tools/cloud/ using importlib (hyphenated dir)."""
    import importlib.util
    assert _shared.PLUGIN_ROOT is not None
    module_path = _shared.PLUGIN_ROOT / "tools" / "cloud" / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(
        f"cloud_{module_name}", str(module_path)
    )
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _check_cloud_enabled() -> str | None:
    """Return error message if cloud uploads not enabled, else None."""
    try:
        from tools.shared.config import load_config
        config = load_config()
    except Exception:
        return (
            "Could not load config. Ensure ~/.bitwize-music/config.yaml exists."
        )
    if not config:
        return "Config not found. Run /bitwize-music:configure first."
    cloud_config = config.get("cloud", {})
    if not cloud_config.get("enabled", False):
        return (
            "Cloud uploads not enabled. "
            "Set cloud.enabled: true in ~/.bitwize-music/config.yaml. "
            "See config/README.md for setup instructions."
        )
    return None


def _check_anthemscore() -> str | None:
    """Return error message if AnthemScore not found, else None."""
    try:
        transcribe_mod = _import_sheet_music_module("transcribe")
        if transcribe_mod.find_anthemscore() is None:
            return (
                "AnthemScore not found. Install from: https://www.lunaverus.com/ "
                "(Professional edition recommended for CLI support)"
            )
    except Exception:
        # Fall back to path search
        paths = [
            "/Applications/AnthemScore.app/Contents/MacOS/AnthemScore",
            "/usr/bin/anthemscore",
            "/usr/local/bin/anthemscore",
        ]
        if not any(Path(p).exists() for p in paths) and not shutil.which("anthemscore"):
            return (
                "AnthemScore not found. Install from: https://www.lunaverus.com/ "
                "(Professional edition recommended for CLI support)"
            )
    return None


def _check_songbook_deps() -> str | None:
    """Return error message if songbook deps missing, else None."""
    missing = []
    for mod in ("pypdf", "reportlab"):
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    if missing:
        return (
            f"Missing songbook dependencies: {', '.join(missing)}. "
            "Install: pip install pypdf reportlab"
        )
    return None


def _check_mixing_deps() -> str | None:
    """Return error message if mixing deps missing, else None."""
    missing = []
    for mod in ("numpy", "scipy", "soundfile", "noisereduce"):
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    if missing:
        return (
            f"Missing mixing dependencies: {', '.join(missing)}. "
            "Install: pip install noisereduce scipy numpy soundfile"
        )
    return None
