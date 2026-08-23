"""Shared helpers for processing submodules."""

from __future__ import annotations

import logging
import re
import shutil
from pathlib import Path
from typing import Any

from handlers import _shared
from handlers._shared import _normalize_slug
from handlers._shared import _resolve_audio_dir as _resolve_audio_dir

logger = logging.getLogger(__name__)


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
        logger.warning(
            "Optional module %s not available: Could not load import spec for %s",
            module_name,
            module_path,
        )
        return None
    try:
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    except (ImportError, OSError) as exc:
        logger.warning("Optional sheet-music module %r not available: %s", module_name, exc)
        return None
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
        logger.warning(
            "Optional module %s not available: Could not load import spec for %s",
            module_name,
            module_path,
        )
        return None
    try:
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    except (ImportError, OSError) as exc:
        logger.warning("Optional cloud module %r not available: %s", module_name, exc)
        return None
    return mod


def _check_cloud_enabled() -> str | None:
    """Return error message if cloud uploads not enabled, else None."""
    try:
        from tools.shared.config import coerce_yaml_bool, load_config
        config = load_config()
    except (ImportError, OSError, KeyError) as exc:
        logger.warning("Config load failed: %s", exc)
        return (
            "Could not load config. Ensure ~/.bitwize-music/config.yaml exists."
        )
    if not config:
        return "Config not found. Run /bitwize-music:configure first."
    cloud_config = config.get("cloud", {})
    if not coerce_yaml_bool(
        cloud_config.get("enabled", False), default=False, context="cloud.enabled"
    ):
        return (
            "Cloud uploads not enabled. "
            "Set cloud.enabled: true in ~/.bitwize-music/config.yaml. "
            "See config/README.md for setup instructions."
        )
    return None


def _check_anthemscore() -> str | None:
    """Return error message if AnthemScore not found, else None."""
    transcribe_mod = _import_sheet_music_module("transcribe")
    if transcribe_mod is not None:
        try:
            if transcribe_mod.find_anthemscore() is None:
                return (
                    "AnthemScore not found. Install from: https://www.lunaverus.com/ "
                    "(Professional edition recommended for CLI support)"
                )
            return None
        except (ImportError, OSError) as exc:
            logger.warning("AnthemScore check failed, falling back to path search: %s", exc)
    # Fall back to path search
    # Keep in sync with find_anthemscore() in tools/sheet-music/transcribe.py.
    # Listing every platform's paths is safe: the non-native ones simply never
    # exist (a Windows drive path can't resolve on macOS/Linux, and vice versa).
    paths = [
        "/Applications/AnthemScore.app/Contents/MacOS/AnthemScore",
        "/usr/bin/anthemscore",
        "/usr/local/bin/anthemscore",
        r"C:\Program Files\AnthemScore\AnthemScore.exe",
        r"C:\Program Files (x86)\AnthemScore\AnthemScore.exe",
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


def _derive_album_genre(album_slug: str) -> str:
    """Best-effort genre lookup for an album, keyed by slug, from state.

    The state cache is the authoritative source for an album's genre —
    it is the exact value `_resolve_audio_dir` already reads to build the
    album's on-disk path (`{audio_root}/artists/[artist]/albums/[genre]/
    [album]`), so this reuses that source rather than re-deriving genre
    by splitting the resolved path back apart, which would duplicate
    `_album_dir`'s layout logic and break for a symlinked audio
    directory (a supported layout — `confine=False` at
    `_resolve_audio_dir`).

    Used by the polish handlers (`polish_audio`, `polish_album`,
    `analyze_mix_issues`, #556) to default `genre` from the album's own
    genre when the caller omits it, so genre-scoped mix overrides apply
    without the caller having to pass `genre` explicitly.

    Returns "" — today's no-genre behavior — on any failure: a
    malformed slug, an album missing from state, or no `genre` recorded
    for it. Never raises.
    """
    try:
        normalized = _normalize_slug(album_slug)
    except ValueError:
        return ""
    state = _shared.cache.get_state()
    albums = state.get("albums", {})
    album_data = albums.get(normalized, {})
    genre = album_data.get("genre", "")
    return genre if isinstance(genre, str) else ""


def _all_known_genres() -> set[str]:
    """Union of the mix and mastering preset genre keys (#556 round 3).

    The two preset files are independent and very differently sized —
    `tools/mixing/mix-presets.yaml` carries ~73 genres,
    `tools/mastering/genre-presets.yaml` ~407 — so membership in one says
    nothing about the other. Anything that needs to answer "is this a
    real genre at all?" (as opposed to "does the mix chain have a section
    for it?") has to ask both, or it rejects ~334 legitimate genres.

    Both loaders are re-read here rather than snapshotted: overrides can
    add genres mid-session, and a membership test that predates the edit
    is exactly the fresh-vs-stale split this round set out to remove.
    Both are small YAML reads.
    """
    from tools.mastering.master_tracks import load_genre_presets
    from tools.mixing.mix_tracks import load_mix_presets

    return set(load_mix_presets().get("genres", {})) | set(load_genre_presets())


def _genre_known_anywhere(genre: str) -> bool:
    """True when `genre` has a section in EITHER preset set (#556 round 3)."""
    return bool(genre) and genre.lower() in _all_known_genres()


def _warn_unknown_genre_for_qc(
    genre: str,
    album_slug: str,
    *,
    preset_kind: str,
    was_explicit: bool,
) -> None:
    """Log that `genre` isn't recognized by the named preset set, so QC is
    running WITHOUT a genre preset for it (blank fallback).

    Sole caller is `polish_album`'s stage-3 QC guard. `qc_track` reads
    the mastering presets and raises `ValueError` for a genre they don't
    carry, so a genre that is fine for the mix chain but absent from the
    mastering set has to be dropped before it gets there — otherwise the
    exception escapes `run_in_executor` and kills verify mid-run.

    `was_explicit` distinguishes the two ways this is reached (#556 round
    3). Round 2 called this `_warn_unknown_derived_genre` and described
    every case as DERIVED, which sent anyone reading the log to the
    album's state entry even when the value came from an argument they
    had just typed. Both origins are legitimate here: the mix and
    mastering preset sets are independent files with very different
    genre lists.

    `preset_kind` names the set that rejected it, so the message points
    at the right file.

    Deduped once per process per distinct (album, genre, preset_kind,
    origin) via the shared warn-once mechanism
    (`tools.shared.config._should_warn`, #556). The origin is part of the
    key deliberately: round 2 shared one key between two checks that read
    different sources, so whichever ran first consumed the single slot
    and the surviving line could describe the opposite of what happened.
    """
    from tools.shared.config import _should_warn

    origin = "explicit" if was_explicit else "derived"
    key = f"unknown_{preset_kind}_genre_for_qc:{album_slug}:{origin}"
    if _should_warn(key, genre):
        logger.warning(
            "Genre %r for album %r (%s) is not a known %s-preset genre; "
            "running QC without a genre preset.",
            genre, album_slug,
            "passed explicitly" if was_explicit
            else "derived from the album's state entry",
            preset_kind,
        )


def _note_unpresetted_mix_genre(genre: str, album_slug: str) -> None:
    """Log that `genre` has no `tools/mixing/mix-presets.yaml` section —
    informational only. Unlike `_warn_unknown_genre_for_qc`, this does
    NOT mean the genre is dropped.

    #556 round 3: this is reached by an EXPLICIT genre as well as a
    derived one. An explicit genre is now hard-errored only when neither
    preset set knows it, so a real genre that simply has no mix section
    (~334 of the ~407 mastering genres) lands here instead of being
    rejected.

    #556 round 2: `_get_stem_settings`/`_get_full_mix_settings`/
    `_resolve_analyzer_peak_ratio` already resolve a mix-unknown genre
    gracefully — shipped per-stem defaults, plus the mastering-preset
    click-threshold overlay via `_resolve_master_click_thresholds`,
    which reads the SEPARATE mastering preset set and may well still
    recognize the genre there (e.g. a niche "dark-cabaret" that's a real
    mastering genre with no mix-side section). Blanking a genre in this
    situation (round 1's behavior) threw that overlay away for no
    reason, and worse: `analyze_mix_issues` never blanked while
    `polish_audio`/`polish_album` did, so the two independently
    re-derived the SAME state genre and applied DIFFERENT fallback
    treatments to it — the exact analyzer/polish disagreement D3 item 1
    exists to prevent, reproduced live on a real catalog. The genre is
    kept and used unchanged wherever it flows; only this note is logged.

    Deduped the same way `_warn_unknown_derived_genre` is (once per
    process per distinct album+genre).
    """
    from tools.shared.config import _should_warn

    key = f"unpresetted_mix_genre:{album_slug}"
    if _should_warn(key, genre):
        logger.warning(
            "Genre %r for album %r has no tools/mixing/mix-presets.yaml "
            "section; resolving via shipped per-stem defaults and the "
            "mastering-preset click-threshold overlay where applicable.",
            genre, album_slug,
        )


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
