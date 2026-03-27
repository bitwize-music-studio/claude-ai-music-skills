"""Processing tools — audio mastering, sheet music, promo videos, mix polishing."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import shutil
from pathlib import Path
from typing import Any

from handlers import _shared
from handlers._shared import (
    ALBUM_COMPLETE,
    TRACK_FINAL,
    TRACK_GENERATED,
    TRACK_NOT_STARTED,
    _find_album_or_error,
    _find_wav_source_dir,
    _normalize_slug,
    _resolve_audio_dir,
    _safe_json,
    _update_frontmatter_block,
)

logger = logging.getLogger("bitwize-music-state")


# =============================================================================
# Module-specific helpers
# =============================================================================


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


# =============================================================================
# Processing Tools — Mastering, Sheet Music, Promo Videos
# =============================================================================
#
# These tools wrap the Python scripts in tools/mastering/, tools/sheet-music/,
# and tools/promotion/ so Claude can invoke them directly via MCP instead of
# telling the user to run CLI commands.
#
# Architecture:
# - Direct import of library functions (not subprocess) for structured results
# - asyncio.run_in_executor() for CPU-heavy work (keeps MCP event loop alive)
# - Lazy dependency checking at invocation time (server starts without optional deps)
# - Block-and-return (no streaming/progress — MCP has no such mechanism)
# =============================================================================


async def analyze_audio(album_slug: str, subfolder: str = "") -> str:
    """Analyze audio tracks for mastering decisions.

    Scans WAV files in the album's audio directory and returns per-track
    metrics including LUFS, peak levels, spectral balance, and tinniness.

    Args:
        album_slug: Album slug (e.g., "my-album")
        subfolder: Optional subfolder within audio dir (e.g., "mastered")

    Returns:
        JSON with per-track metrics, summary, and recommendations
    """
    dep_err = _check_mastering_deps()
    if dep_err:
        return _safe_json({"error": dep_err})

    err, audio_dir = _resolve_audio_dir(album_slug, subfolder)
    if err:
        return err
    assert audio_dir is not None

    from tools.mastering.analyze_tracks import analyze_track

    source_dir = _find_wav_source_dir(audio_dir)
    wav_files = sorted(source_dir.glob("*.wav"))
    wav_files = [f for f in wav_files if "venv" not in str(f)]
    if not wav_files:
        return _safe_json({
            "error": f"No WAV files found in {audio_dir}",
            "suggestion": "Check the album slug or subfolder.",
        })

    loop = asyncio.get_running_loop()
    results = []
    for wav in wav_files:
        result = await loop.run_in_executor(None, analyze_track, str(wav))
        results.append(result)

    # Build summary
    import numpy as np
    lufs_values = [r["lufs"] for r in results]
    avg_lufs = float(np.mean(lufs_values))
    lufs_range = float(max(lufs_values) - min(lufs_values))
    tinny_tracks = [r["filename"] for r in results if r["tinniness_ratio"] > 0.6]

    recommendations = []
    if lufs_range > 2.0:
        recommendations.append(
            f"LUFS range is {lufs_range:.1f} dB — target < 2 dB for album consistency."
        )
    if tinny_tracks:
        recommendations.append(
            f"Tinny tracks needing high-mid EQ cut (2-6kHz): {', '.join(tinny_tracks)}"
        )
    if avg_lufs < -16:
        recommendations.append(
            f"Average LUFS is {avg_lufs:.1f} — consider boosting toward -14 LUFS for streaming."
        )

    return _safe_json({
        "tracks": results,
        "summary": {
            "track_count": len(results),
            "avg_lufs": avg_lufs,
            "lufs_range": lufs_range,
            "tinny_tracks": tinny_tracks,
        },
        "recommendations": recommendations,
    })


async def qc_audio(album_slug: str, subfolder: str = "", checks: str = "") -> str:
    """Run technical QC checks on audio tracks.

    Scans WAV files for mono compatibility, phase correlation, clipping,
    clicks/pops, silence issues, format validation, and spectral balance.

    Args:
        album_slug: Album slug (e.g., "my-album")
        subfolder: Optional subfolder within audio dir (e.g., "mastered")
        checks: Comma-separated checks to run (default: all).
                Options: mono, phase, clipping, clicks, silence, format, spectral

    Returns:
        JSON with per-track QC results, summary, and verdicts
    """
    dep_err = _check_mastering_deps()
    if dep_err:
        return _safe_json({"error": dep_err})

    err, audio_dir = _resolve_audio_dir(album_slug, subfolder)
    if err:
        return err
    assert audio_dir is not None

    from tools.mastering.qc_tracks import ALL_CHECKS, qc_track

    source_dir = _find_wav_source_dir(audio_dir) if not subfolder else audio_dir
    wav_files = sorted(source_dir.glob("*.wav"))
    wav_files = [f for f in wav_files if "venv" not in str(f)]
    if not wav_files:
        return _safe_json({
            "error": f"No WAV files found in {audio_dir}",
            "suggestion": "Check the album slug or subfolder.",
        })

    # Parse checks filter
    active_checks = None
    if checks:
        active_checks = [c.strip() for c in checks.split(",")]
        invalid = [c for c in active_checks if c not in ALL_CHECKS]
        if invalid:
            return _safe_json({
                "error": f"Unknown checks: {', '.join(invalid)}",
                "valid_checks": ALL_CHECKS,
            })

    loop = asyncio.get_running_loop()
    results = []
    for wav in wav_files:
        result = await loop.run_in_executor(None, qc_track, str(wav), active_checks)
        results.append(result)

    # Build summary
    passed = sum(1 for r in results if r["verdict"] == "PASS")
    warned = sum(1 for r in results if r["verdict"] == "WARN")
    failed = sum(1 for r in results if r["verdict"] == "FAIL")

    if failed > 0:
        verdict = "FAILURES FOUND"
    elif warned > 0:
        verdict = "WARNINGS"
    else:
        verdict = "ALL PASS"

    return _safe_json({
        "tracks": results,
        "summary": {
            "total": len(results),
            "passed": passed,
            "warned": warned,
            "failed": failed,
        },
        "verdict": verdict,
    })


async def master_audio(
    album_slug: str,
    genre: str = "",
    target_lufs: float = -14.0,
    ceiling_db: float = -1.0,
    cut_highmid: float = 0.0,
    cut_highs: float = 0.0,
    dry_run: bool = False,
    source_subfolder: str = "",
) -> str:
    """Master audio tracks for streaming platforms.

    Normalizes loudness, applies optional EQ, and limits peaks. Creates
    mastered files in a mastered/ subfolder within the audio directory.

    Args:
        album_slug: Album slug (e.g., "my-album")
        genre: Genre preset to apply (overrides EQ/LUFS defaults if set)
        target_lufs: Target integrated loudness (default: -14.0)
        ceiling_db: True peak ceiling in dB (default: -1.0)
        cut_highmid: High-mid EQ cut in dB at 3.5kHz (e.g., -2.0)
        cut_highs: High shelf cut in dB at 8kHz
        dry_run: If true, analyze only without writing files
        source_subfolder: Read WAV files from this subfolder instead of the
            base audio dir (e.g., "polished" to master from mix-engineer output)

    Returns:
        JSON with per-track results, settings applied, and summary
    """
    dep_err = _check_mastering_deps()
    if dep_err:
        return _safe_json({"error": dep_err})

    err, audio_dir = _resolve_audio_dir(album_slug)
    if err:
        return err
    assert audio_dir is not None

    # If source_subfolder specified, read from that subfolder
    if source_subfolder:
        source_dir = audio_dir / source_subfolder
        if not source_dir.is_dir():
            return _safe_json({
                "error": f"Source subfolder not found: {source_dir}",
                "suggestion": f"Run polish_audio first to create {source_subfolder}/ output.",
            })
    else:
        source_dir = _find_wav_source_dir(audio_dir)

    import numpy as np
    import pyloudnorm as pyln
    import soundfile as sf

    from tools.mastering.master_tracks import (
        load_genre_presets,
    )
    from tools.mastering.master_tracks import (
        master_track as _master_track,
    )

    # Apply genre preset if specified
    effective_lufs = target_lufs
    effective_highmid = cut_highmid
    effective_highs = cut_highs
    effective_compress = 1.5
    genre_applied = None

    if genre:
        presets = load_genre_presets()
        genre_key = genre.lower()
        if genre_key not in presets:
            return _safe_json({
                "error": f"Unknown genre: {genre}",
                "available_genres": sorted(presets.keys()),
            })
        preset_lufs, preset_highmid, preset_highs, preset_compress = presets[genre_key]
        # Genre preset provides defaults; explicit non-default args override
        if target_lufs == -14.0:
            effective_lufs = preset_lufs
        if cut_highmid == 0.0:
            effective_highmid = preset_highmid
        if cut_highs == 0.0:
            effective_highs = preset_highs
        effective_compress = preset_compress
        genre_applied = genre_key

    # Build EQ settings
    eq_settings = []
    if effective_highmid != 0:
        eq_settings.append((3500.0, effective_highmid, 1.5))
    if effective_highs != 0:
        eq_settings.append((8000.0, effective_highs, 0.7))

    output_dir = audio_dir / "mastered"
    if not dry_run:
        output_dir.mkdir(exist_ok=True)

    wav_files = sorted([
        f for f in source_dir.iterdir()
        if f.suffix.lower() == ".wav" and "venv" not in str(f)
    ])

    if not wav_files:
        return _safe_json({"error": f"No WAV files found in {source_dir}"})

    loop = asyncio.get_running_loop()
    track_results = []

    for wav_file in wav_files:
        output_path = output_dir / wav_file.name
        if dry_run:
            # Dry run: just measure current loudness
            def _dry_run_measure(path: Path) -> dict[str, Any] | None:
                data, rate = sf.read(str(path))
                if len(data.shape) == 1:
                    data = np.column_stack([data, data])
                meter = pyln.Meter(rate)
                current = meter.integrated_loudness(data)
                if not np.isfinite(current):
                    return None
                return {
                    "filename": path.name,
                    "original_lufs": current,
                    "final_lufs": effective_lufs,
                    "gain_applied": effective_lufs - current,
                    "final_peak": -1.0,
                    "dry_run": True,
                }
            result = await loop.run_in_executor(None, _dry_run_measure, wav_file)
        else:
            # Look up per-track fade_out from state cache
            fade_out_val = 5.0  # default
            state = _shared.cache.get_state() or {}
            albums = state.get("albums", {})
            album_data = albums.get(_normalize_slug(album_slug))
            if album_data:
                track_slug = wav_file.stem
                track_info = album_data.get("tracks", {}).get(track_slug, {})
                if track_info.get("fade_out") is not None:
                    fade_out_val = track_info["fade_out"]

            def _do_master(in_path: Path, out_path: Path, fo: float) -> dict[str, Any]:
                return _master_track(
                    str(in_path), str(out_path),
                    target_lufs=effective_lufs,
                    eq_settings=eq_settings if eq_settings else None,
                    ceiling_db=ceiling_db,
                    fade_out=fo,
                    compress_ratio=effective_compress,
                )
            result = await loop.run_in_executor(None, _do_master, wav_file, output_path, fade_out_val)
            if result and not result.get("skipped"):
                result["filename"] = wav_file.name

        if result and not result.get("skipped"):
            track_results.append(result)

    if not track_results:
        return _safe_json({"error": "No tracks processed (all silent or no WAV files)."})

    gains = [r["gain_applied"] for r in track_results]
    finals = [r["final_lufs"] for r in track_results]

    return _safe_json({
        "tracks": track_results,
        "settings": {
            "target_lufs": effective_lufs,
            "ceiling_db": ceiling_db,
            "cut_highmid": effective_highmid,
            "cut_highs": effective_highs,
            "genre": genre_applied,
            "dry_run": dry_run,
        },
        "summary": {
            "tracks_processed": len(track_results),
            "gain_range": [min(gains), max(gains)],
            "final_lufs_range": max(finals) - min(finals),
            "output_dir": str(output_dir) if not dry_run else None,
        },
    })


async def fix_dynamic_track(album_slug: str, track_filename: str) -> str:
    """Fix a track with excessive dynamic range that won't reach target LUFS.

    Applies gentle compression followed by standard mastering to bring
    the track into line with the rest of the album.

    Args:
        album_slug: Album slug (e.g., "my-album")
        track_filename: WAV filename (e.g., "01-track-name.wav")

    Returns:
        JSON with before/after metrics
    """
    dep_err = _check_mastering_deps()
    if dep_err:
        return _safe_json({"error": dep_err})

    err, audio_dir = _resolve_audio_dir(album_slug)
    if err:
        return err
    assert audio_dir is not None

    input_path = audio_dir / track_filename
    if not input_path.exists():
        input_path = _find_wav_source_dir(audio_dir) / track_filename
    if not input_path.exists():
        return _safe_json({
            "error": f"Track file not found: {track_filename}",
            "available_files": [f.name for f in _find_wav_source_dir(audio_dir).glob("*.wav")],
        })

    output_dir = audio_dir / "mastered"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / track_filename

    from tools.mastering.fix_dynamic_track import fix_dynamic

    def _do_fix(in_path: Path, out_path: Path) -> dict[str, Any]:
        import numpy as np
        import soundfile as sf

        data, rate = sf.read(str(in_path))
        if len(data.shape) == 1:
            data = np.column_stack([data, data])

        data, metrics = fix_dynamic(data, rate)

        sf.write(str(out_path), data, rate, subtype="PCM_16")

        return {
            "filename": in_path.name,
            "original_lufs": metrics["original_lufs"],
            "final_lufs": metrics["final_lufs"],
            "final_peak_db": metrics["final_peak_db"],
            "output_path": str(out_path),
        }

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, _do_fix, input_path, output_path)
    return _safe_json(result)


async def master_with_reference(
    album_slug: str,
    reference_filename: str,
    target_filename: str = "",
) -> str:
    """Master tracks using a professionally mastered reference track.

    Uses the matchering library to match your track(s) to a reference.
    If target_filename is empty, processes all WAV files in the album's
    audio directory.

    Args:
        album_slug: Album slug (e.g., "my-album")
        reference_filename: Reference WAV filename in audio dir (e.g., "reference.wav")
        target_filename: Optional single target WAV (empty = batch all)

    Returns:
        JSON with per-track results
    """
    dep_err = _check_matchering()
    if dep_err:
        return _safe_json({"error": dep_err})

    err, audio_dir = _resolve_audio_dir(album_slug)
    if err:
        return err
    assert audio_dir is not None

    reference_path = audio_dir / reference_filename
    if not reference_path.exists():
        reference_path = _find_wav_source_dir(audio_dir) / reference_filename
    if not reference_path.exists():
        return _safe_json({
            "error": f"Reference file not found: {reference_filename}",
            "suggestion": "Place the reference WAV in the album's audio directory.",
        })

    output_dir = audio_dir / "mastered"
    output_dir.mkdir(exist_ok=True)

    try:
        from tools.mastering.reference_master import (
            master_with_reference as _ref_master,
        )
    except (ImportError, SystemExit):
        return _safe_json({
            "error": "matchering not installed. Install: pip install matchering",
        })

    loop = asyncio.get_running_loop()

    if target_filename:
        # Single file
        target_path = audio_dir / target_filename
        if not target_path.exists():
            target_path = _find_wav_source_dir(audio_dir) / target_filename
        if not target_path.exists():
            return _safe_json({
                "error": f"Target file not found: {target_filename}",
                "available_files": [f.name for f in _find_wav_source_dir(audio_dir).glob("*.wav")],
            })
        output_path = output_dir / target_filename

        try:
            await loop.run_in_executor(
                None, _ref_master, target_path, reference_path, output_path
            )
            return _safe_json({
                "tracks": [{"filename": target_filename, "success": True, "output": str(output_path)}],
                "summary": {"success": 1, "failed": 0},
            })
        except Exception as e:
            return _safe_json({
                "tracks": [{"filename": target_filename, "success": False, "error": str(e)}],
                "summary": {"success": 0, "failed": 1},
            })
    else:
        # Batch all WAVs
        source_dir = _find_wav_source_dir(audio_dir)
        wav_files = sorted([
            f for f in source_dir.glob("*.wav")
            if "venv" not in str(f) and f != reference_path
        ])
        if not wav_files:
            return _safe_json({"error": f"No WAV files found in {audio_dir}"})

        results = []
        for wav_file in wav_files:
            output_path = output_dir / wav_file.name
            try:
                await loop.run_in_executor(
                    None, _ref_master, wav_file, reference_path, output_path
                )
                results.append({"filename": wav_file.name, "success": True, "output": str(output_path)})
            except Exception as e:
                results.append({"filename": wav_file.name, "success": False, "error": str(e)})

        success_count = sum(1 for r in results if r["success"])
        return _safe_json({
            "tracks": results,
            "summary": {"success": success_count, "failed": len(results) - success_count},
        })


async def transcribe_audio(
    album_slug: str,
    track_filename: str = "",
    formats: str = "pdf,xml,midi",
    dry_run: bool = False,
) -> str:
    """Convert WAV files to sheet music using AnthemScore.

    Creates symlinks with clean track titles (from state cache) so AnthemScore
    embeds proper titles in its output. Falls back to slug_to_title() when
    the state cache has no track data.

    Output goes to sheet-music/source/ with clean title filenames and a
    .manifest.json recording track ordering and slug mapping.

    Args:
        album_slug: Album slug (e.g., "my-album")
        track_filename: Optional single WAV filename (empty = all WAVs)
        formats: Comma-separated output formats: "pdf", "xml", "midi" (default: "pdf,xml")
        dry_run: If true, show what would be done without doing it

    Returns:
        JSON with per-track results and summary
    """
    import tempfile

    anthemscore_err = _check_anthemscore()
    if anthemscore_err:
        return _safe_json({"error": anthemscore_err})

    err, audio_dir = _resolve_audio_dir(album_slug)
    if err:
        return err
    assert audio_dir is not None

    transcribe_mod = _import_sheet_music_module("transcribe")
    find_anthemscore = transcribe_mod.find_anthemscore
    transcribe_track = transcribe_mod.transcribe_track

    anthemscore_path = find_anthemscore()
    if not anthemscore_path:
        return _safe_json({
            "error": "AnthemScore not found on this system.",
            "suggestion": "Install from https://www.lunaverus.com/",
        })

    output_dir = audio_dir / "sheet-music" / "source"
    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)

    # Parse formats
    fmt_list = [f.strip().lower() for f in formats.split(",")]

    # Build a namespace-like object for transcribe_track's args
    class Args:
        pass
    args = Args()
    args.pdf = "pdf" in fmt_list  # type: ignore[attr-defined]
    args.xml = "xml" in fmt_list  # type: ignore[attr-defined]
    args.midi = "midi" in fmt_list  # type: ignore[attr-defined]
    args.treble = False  # type: ignore[attr-defined]
    args.bass = False  # type: ignore[attr-defined]
    args.dry_run = dry_run  # type: ignore[attr-defined]

    if track_filename:
        wav_files = [audio_dir / track_filename]
        if not wav_files[0].exists():
            wav_files = [_find_wav_source_dir(audio_dir) / track_filename]
        if not wav_files[0].exists():
            return _safe_json({
                "error": f"Track file not found: {track_filename}",
                "available_files": [f.name for f in _find_wav_source_dir(audio_dir).glob("*.wav")],
            })
    else:
        source_dir = _find_wav_source_dir(audio_dir)
        wav_files = sorted(source_dir.glob("*.wav"))
        wav_files = [f for f in wav_files if "venv" not in str(f)]

    if not wav_files:
        return _safe_json({"error": f"No WAV files found in {audio_dir}"})

    # Build title map from state cache (falls back to slug_to_title)
    title_map = _build_title_map(album_slug, wav_files)

    # Dry run: just report the title mapping
    if dry_run:
        manifest_tracks = []
        for wav_file in wav_files:
            stem = wav_file.stem
            clean_title = title_map.get(stem, stem)
            track_num = _extract_track_number_from_stem(stem)
            manifest_tracks.append({
                "number": track_num,
                "source_slug": stem,
                "title": clean_title,
            })
        return _safe_json({
            "dry_run": True,
            "title_map": title_map,
            "manifest": {"tracks": manifest_tracks},
            "output_dir": str(output_dir),
            "formats": fmt_list,
        })

    # Create temp dir with clean-titled symlinks
    tmp_dir = None
    try:
        tmp_dir = Path(tempfile.mkdtemp(prefix=f"{album_slug}-transcribe-"))

        # Disambiguate duplicate titles
        used_titles: dict[str, int] = {}
        symlink_map = {}  # clean_title -> (symlink_path, original_wav)
        for wav_file in wav_files:
            stem = wav_file.stem
            clean_title = title_map.get(stem, stem)
            # Handle duplicate titles
            if clean_title in used_titles:
                used_titles[clean_title] += 1
                clean_title = f"{clean_title} ({used_titles[clean_title]})"
            else:
                used_titles[clean_title] = 1

            symlink_path = tmp_dir / f"{clean_title}.wav"
            try:
                symlink_path.symlink_to(wav_file.resolve())
            except OSError:
                # Fallback: copy if symlinks fail (e.g., Windows)
                shutil.copy2(wav_file, symlink_path)
            symlink_map[clean_title] = (symlink_path, wav_file)

        # Transcribe from symlinked files
        loop = asyncio.get_running_loop()
        results = []
        manifest_tracks = []

        for clean_title, (symlink_path, original_wav) in symlink_map.items():
            stem = original_wav.stem
            track_num = _extract_track_number_from_stem(stem)

            success = await loop.run_in_executor(
                None, transcribe_track, anthemscore_path, symlink_path, output_dir, args
            )

            outputs = []
            if success:
                for fmt in fmt_list:
                    ext = {"pdf": ".pdf", "xml": ".xml", "midi": ".mid"}.get(fmt, "")
                    out_file = output_dir / f"{clean_title}{ext}"
                    if out_file.exists():
                        outputs.append(str(out_file))

            results.append({
                "filename": original_wav.name,
                "clean_title": clean_title,
                "success": success,
                "outputs": outputs,
            })
            manifest_tracks.append({
                "number": track_num,
                "source_slug": stem,
                "title": clean_title,
            })

        # Sort manifest by track number
        manifest_tracks.sort(key=lambda t: (t["number"] is None, t["number"] or 0))

        # Write .manifest.json to source/
        manifest = {"tracks": manifest_tracks}
        manifest_path = output_dir / ".manifest.json"
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2)

        success_count = sum(1 for r in results if r["success"])
        return _safe_json({
            "tracks": results,
            "manifest": manifest,
            "summary": {
                "success": success_count,
                "failed": len(results) - success_count,
                "output_dir": str(output_dir),
                "formats": fmt_list,
            },
        })
    finally:
        # Clean up temp dir
        if tmp_dir and tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)


async def prepare_singles(
    album_slug: str,
    dry_run: bool = False,
    xml_only: bool = False,
) -> str:
    """Prepare consumer-ready sheet music singles with clean titles.

    Reads source files from the album's sheet-music/source/ directory.
    If source/ has a .manifest.json (from transcribe_audio), files are
    already clean-titled. Otherwise falls back to numbered file discovery
    with slug_to_title derivation.

    Output files are numbered: "01 - First Pour.pdf", etc.
    Creates .manifest.json in singles/ with filename field for songbook.

    Args:
        album_slug: Album slug (e.g., "my-album")
        dry_run: If true, show changes without modifying files
        xml_only: If true, only process XML files (skip PDF/MIDI)

    Returns:
        JSON with per-track results and manifest
    """
    err, audio_dir = _resolve_audio_dir(album_slug)
    if err:
        return err
    assert audio_dir is not None

    # Try new structure first, fall back to flat layout
    source_dir = audio_dir / "sheet-music" / "source"
    if not source_dir.is_dir():
        sheet_dir = audio_dir / "sheet-music"
        if sheet_dir.is_dir():
            source_dir = sheet_dir  # backward compat: flat layout
        else:
            return _safe_json({
                "error": f"Sheet music directory not found: {source_dir}",
                "suggestion": "Run transcribe_audio first to generate sheet music.",
            })

    singles_dir = audio_dir / "sheet-music" / "singles"

    prepare_mod = _import_sheet_music_module("prepare_singles")
    _prepare_singles = prepare_mod.prepare_singles

    musescore = None
    if not xml_only:
        musescore = prepare_mod.find_musescore()

    # Get artist, cover art, and footer URL for title pages
    songbook_mod = _import_sheet_music_module("create_songbook")
    auto_detect_cover_art = songbook_mod.auto_detect_cover_art
    get_footer_url_from_config = songbook_mod.get_footer_url_from_config

    state = _shared.cache.get_state()
    srv_config = state.get("config", {})
    artist = srv_config.get("artist_name", "Unknown Artist")
    cover_image = auto_detect_cover_art(str(source_dir))
    footer_url = get_footer_url_from_config()
    page_size_name = "letter"
    try:
        from tools.shared.config import load_config
        cfg = load_config()
        if cfg:
            page_size_name = cfg.get('sheet_music', {}).get('page_size', 'letter')
    except Exception:
        pass

    # Build title_map from state cache for legacy (no source manifest) fallback
    title_map = None
    albums = state.get("albums", {})
    album = albums.get(_normalize_slug(album_slug), {})
    cache_tracks = album.get("tracks", {})
    if cache_tracks:
        from tools.shared.text_utils import sanitize_filename
        from tools.shared.text_utils import slug_to_title as _s2t
        title_map = {}
        for slug, track in cache_tracks.items():
            title_map[slug] = sanitize_filename(track.get("title", _s2t(slug)))

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        lambda: _prepare_singles(
            source_dir=source_dir,
            singles_dir=singles_dir,
            musescore=musescore,
            dry_run=dry_run,
            xml_only=xml_only,
            artist=artist,
            cover_image=cover_image,
            footer_url=footer_url,
            page_size_name=page_size_name,
            title_map=title_map,
        ),
    )

    if "error" in result:
        return _safe_json({"error": result["error"]})

    tracks = result.get("tracks", [])
    return _safe_json({
        "tracks": tracks,
        "singles_dir": str(singles_dir),
        "track_count": len(tracks),
        "manifest": result.get("manifest", {}),
    })


async def create_songbook(
    album_slug: str,
    title: str,
    page_size: str = "letter",
) -> str:
    """Combine sheet music PDFs into a distribution-ready songbook.

    Creates a complete songbook with title page, copyright page, table
    of contents, and all track sheet music. Reads from singles/ directory
    (falls back to flat sheet-music/ layout for backward compatibility).

    Args:
        album_slug: Album slug (e.g., "my-album")
        title: Songbook title (e.g., "My Album Songbook")
        page_size: Page size - "letter", "9x12", or "6x9" (default: "letter")

    Returns:
        JSON with output path and metadata
    """
    dep_err = _check_songbook_deps()
    if dep_err:
        return _safe_json({"error": dep_err})

    err, audio_dir = _resolve_audio_dir(album_slug)
    if err:
        return err
    assert audio_dir is not None

    # Try new structure first (singles/), fall back to flat layout
    singles_dir = audio_dir / "sheet-music" / "singles"
    if singles_dir.is_dir():
        source_dir = singles_dir
    else:
        sheet_dir = audio_dir / "sheet-music"
        if sheet_dir.is_dir():
            source_dir = sheet_dir  # backward compat
        else:
            return _safe_json({
                "error": f"Sheet music directory not found: {singles_dir}",
                "suggestion": "Run transcribe_audio and prepare_singles first.",
            })

    songbook_mod = _import_sheet_music_module("create_songbook")
    _create_songbook = songbook_mod.create_songbook
    auto_detect_cover_art = songbook_mod.auto_detect_cover_art
    get_website_from_config = songbook_mod.get_website_from_config
    get_footer_url_from_config = songbook_mod.get_footer_url_from_config

    # Get artist from state
    state = _shared.cache.get_state()
    config = state.get("config", {})
    artist = config.get("artist_name", "Unknown Artist")

    # Auto-detect cover art, website, and footer URL
    cover = auto_detect_cover_art(str(source_dir))
    website = get_website_from_config()
    footer_url = get_footer_url_from_config()

    # Build output path in songbook/ subdirectory
    songbook_dir = audio_dir / "sheet-music" / "songbook"
    songbook_dir.mkdir(parents=True, exist_ok=True)
    safe_title = title.replace(" ", "_").replace("/", "-")
    output_path = songbook_dir / f"{safe_title}.pdf"

    loop = asyncio.get_running_loop()
    success = await loop.run_in_executor(
        None,
        lambda: _create_songbook(
            source_dir=str(source_dir),
            output_path=str(output_path),
            title=title,
            artist=artist,
            page_size_name=page_size,
            cover_image=cover,
            website=website,
            footer_url=footer_url,
        ),
    )

    if success:
        return _safe_json({
            "success": True,
            "output_path": str(output_path),
            "title": title,
            "artist": artist,
            "page_size": page_size,
        })
    else:
        return _safe_json({"error": "Songbook creation failed. Check sheet music directory."})


async def publish_sheet_music(
    album_slug: str,
    include_source: bool = False,
    dry_run: bool = False,
) -> str:
    """Upload sheet music files (PDFs, MusicXML, MIDI) to Cloudflare R2.

    Collects files from sheet-music/singles/ and sheet-music/songbook/,
    optionally including sheet-music/source/, and uploads them to R2
    for public download URLs.

    Args:
        album_slug: Album slug (e.g., "my-album")
        include_source: Include source/ transcription files (default: False)
        dry_run: List files and R2 keys without uploading (default: False)

    Returns:
        JSON with uploaded files, R2 keys, and summary
    """
    cloud_err = _check_cloud_enabled()
    if cloud_err:
        return _safe_json({"error": cloud_err})

    err, audio_dir = _resolve_audio_dir(album_slug)
    if err:
        return err
    assert audio_dir is not None

    sheet_music_dir = audio_dir / "sheet-music"
    if not sheet_music_dir.is_dir():
        return _safe_json({
            "error": f"Sheet music directory not found: {sheet_music_dir}",
            "suggestion": (
                "Run transcribe_audio first to generate source files, "
                "then prepare_singles to create distribution-ready PDFs."
            ),
        })

    # Collect files from each subdirectory
    subdirs_to_scan = ["singles", "songbook"]
    if include_source:
        subdirs_to_scan.append("source")

    files_to_upload = []  # list of (local_path, r2_subdir, filename)
    for subdir in subdirs_to_scan:
        subdir_path = sheet_music_dir / subdir
        if not subdir_path.is_dir():
            continue
        for f in sorted(subdir_path.iterdir()):
            if not f.is_file():
                continue
            # Skip internal metadata files
            if f.name == ".manifest.json":
                continue
            files_to_upload.append((f, subdir, f.name))

    if not files_to_upload:
        return _safe_json({
            "error": "No sheet music files found to upload.",
            "checked_dirs": [
                str(sheet_music_dir / s) for s in subdirs_to_scan
            ],
            "suggestion": "Run prepare_singles and/or create_songbook first.",
        })

    # Get artist name from state
    state = _shared.cache.get_state()
    config_data = state.get("config", {})
    artist = config_data.get("artist_name", "Unknown Artist")
    normalized_slug = _normalize_slug(album_slug)

    # Build R2 keys
    upload_plan: list[dict[str, Any]] = []
    for local_path, subdir, filename in files_to_upload:
        r2_key = f"{artist}/{normalized_slug}/sheet-music/{subdir}/{filename}"
        upload_plan.append({
            "local_path": str(local_path),
            "r2_key": r2_key,
            "size_bytes": local_path.stat().st_size,
            "subdir": subdir,
            "filename": filename,
        })

    if dry_run:
        return _safe_json({
            "dry_run": True,
            "album_slug": normalized_slug,
            "artist": artist,
            "files": upload_plan,
            "summary": {
                "total": len(upload_plan),
                "by_subdir": {
                    s: len([f for f in upload_plan if f["subdir"] == s])
                    for s in subdirs_to_scan
                    if any(f["subdir"] == s for f in upload_plan)
                },
            },
        })

    # Import cloud module and upload
    try:
        cloud_mod = _import_cloud_module("upload_to_cloud")
    except Exception as e:
        return _safe_json({
            "error": f"Failed to import cloud module: {e}",
            "suggestion": "Ensure boto3 is installed: pip install boto3",
        })

    from tools.shared.config import load_config
    config = load_config()
    assert config is not None

    try:
        s3_client = cloud_mod.get_s3_client(config)
    except SystemExit:
        return _safe_json({
            "error": "Cloud credentials not configured.",
            "suggestion": "Configure cloud.r2 or cloud.s3 credentials in ~/.bitwize-music/config.yaml",
        })

    try:
        bucket = cloud_mod.get_bucket_name(config)
    except SystemExit:
        return _safe_json({
            "error": "Bucket name not configured.",
            "suggestion": "Set cloud.r2.bucket or cloud.s3.bucket in ~/.bitwize-music/config.yaml",
        })

    public_read = config.get("cloud", {}).get("public_read", False)

    uploaded: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    for item in upload_plan:
        local_path = Path(item["local_path"])
        r2_key = item["r2_key"]
        success = cloud_mod.retry_upload(
            s3_client, bucket, local_path, r2_key,
            public_read=public_read, dry_run=False,
        )
        if success:
            uploaded.append({
                "r2_key": r2_key,
                "filename": item["filename"],
                "subdir": item["subdir"],
            })
        else:
            failed.append({"r2_key": r2_key, "filename": item["filename"]})

    # Build public URLs if available
    cloud_config = config.get("cloud", {})
    provider = cloud_config.get("provider", "r2")
    base_url = None
    if public_read:
        if provider == "r2":
            custom_domain = cloud_config.get("r2", {}).get("public_url")
            if custom_domain:
                base_url = custom_domain.rstrip("/")
        elif provider == "s3":
            region = cloud_config.get("s3", {}).get("region", "us-east-1")
            base_url = f"https://{bucket}.s3.{region}.amazonaws.com"

    urls = {}
    if base_url:
        for item in uploaded:
            urls[item["filename"]] = f"{base_url}/{item['r2_key']}"
    else:
        # Use relative R2 keys when no public_url is configured
        for item in uploaded:
            urls[item["filename"]] = item["r2_key"]

    # --- Persist URLs to track/album frontmatter ---
    frontmatter_updated = False
    tracks_updated = []
    album_updated = False
    fm_reason = None

    if not urls:
        fm_reason = "No files uploaded successfully"
    else:
        # Find album content path
        _, album_data, album_err = _find_album_or_error(normalized_slug)
        if album_err:
            fm_reason = f"Album not found in state: {normalized_slug}"
        else:
            assert album_data is not None
            album_content_path = album_data.get("path", "")
            state_tracks = album_data.get("tracks", {})

            # Group single URLs by track number
            # Singles are named like "01 - The Mountain.pdf"
            track_urls: dict[int, dict[str, str]] = {}  # {1: {"pdf": url, "musicxml": url, "midi": url}, ...}
            songbook_urls: dict[str, str] = {}  # {"songbook": url}
            ext_to_key = {".pdf": "pdf", ".xml": "musicxml", ".mid": "midi", ".midi": "midi"}

            for item in uploaded:
                filename = item["filename"]
                url = urls.get(filename)
                if not url:
                    continue

                if item["subdir"] == "singles":
                    m = re.match(r"^(\d+)\s*-\s*", filename)
                    if m:
                        track_num = int(m.group(1))
                        suffix = Path(filename).suffix.lower()
                        file_key = ext_to_key.get(suffix)
                        if file_key:
                            track_urls.setdefault(track_num, {})[file_key] = url
                elif item["subdir"] == "songbook":
                    suffix = Path(filename).suffix.lower()
                    if suffix == ".pdf":
                        songbook_urls["songbook"] = url

            # Update each track file's frontmatter
            for track_num, sm_values in track_urls.items():
                prefix = f"{track_num:02d}-"
                for slug, tdata in state_tracks.items():
                    if slug.startswith(prefix):
                        track_path = Path(tdata.get("path", ""))
                        if track_path.is_file():
                            ok, err = _update_frontmatter_block(
                                track_path, "sheet_music", sm_values,
                            )
                            if ok:
                                tracks_updated.append(slug)
                        break

            # Update album README.md frontmatter
            if songbook_urls and album_content_path:
                readme_path = Path(album_content_path) / "README.md"
                if readme_path.is_file():
                    ok, err = _update_frontmatter_block(
                        readme_path, "sheet_music", songbook_urls,
                    )
                    if ok:
                        album_updated = True

            frontmatter_updated = bool(tracks_updated) or album_updated

    result = {
        "album_slug": normalized_slug,
        "artist": artist,
        "uploaded": uploaded,
        "failed": failed,
        "summary": {
            "total": len(upload_plan),
            "success": len(uploaded),
            "failed": len(failed),
        },
        "urls": urls,
        "frontmatter_updated": frontmatter_updated,
    }
    if tracks_updated:
        result["tracks_updated"] = tracks_updated
    if album_updated:
        result["album_updated"] = True
    if fm_reason:
        result["frontmatter_reason"] = fm_reason

    return _safe_json(result)


async def generate_promo_videos(
    album_slug: str,
    style: str = "pulse",
    duration: int = 15,
    track_filename: str = "",
    color_hex: str = "",
    glow: float = 0.6,
    text_color: str = "",
) -> str:
    """Generate promo videos with waveform visualization for social media.

    Creates 15-second vertical videos (1080x1920) combining album artwork,
    audio waveform visualization, and track titles.

    Args:
        album_slug: Album slug (e.g., "my-album")
        style: Visualization style - "pulse", "mirror", "mountains", "colorwave",
               "neon", "dual", "bars", "line", "circular" (default: "pulse")
        duration: Video duration in seconds (default: 15)
        track_filename: Optional single track WAV filename (empty = batch all)
        color_hex: Wave color as hex (e.g. "#C9A96E"). Empty = auto-extract from artwork
        glow: Glow intensity 0.0 (none) to 1.0 (full). Default 0.6
        text_color: Text color as hex (e.g. "#FFD700"). Empty = white

    Returns:
        JSON with per-track results and summary
    """
    ffmpeg_err = _check_ffmpeg()
    if ffmpeg_err:
        return _safe_json({"error": ffmpeg_err})

    err, audio_dir = _resolve_audio_dir(album_slug)
    if err:
        return err
    assert audio_dir is not None

    # Find artwork
    artwork_patterns = [
        "album.png", "album.jpg", "album-art.png", "album-art.jpg",
        "artwork.png", "artwork.jpg", "cover.png", "cover.jpg",
    ]
    artwork = None
    for pattern in artwork_patterns:
        candidate = audio_dir / pattern
        if candidate.exists():
            artwork = candidate
            break
    if not artwork:
        return _safe_json({
            "error": "No album artwork found in audio directory.",
            "suggestion": "Place album.png in the audio directory or use /bitwize-music:import-art.",
            "looked_for": artwork_patterns,
        })

    from tools.promotion.generate_promo_video import (
        batch_process_album,
        generate_waveform_video,
    )
    from tools.shared.fonts import find_font

    # Get artist from state
    state = _shared.cache.get_state()
    config_data = state.get("config", {})
    artist = config_data.get("artist_name", "bitwize")

    font_path = find_font()

    output_dir = audio_dir / "promo_videos"
    output_dir.mkdir(exist_ok=True)

    loop = asyncio.get_running_loop()

    if track_filename:
        # Single track
        track_path = audio_dir / track_filename
        if not track_path.exists():
            # Also check originals/ and mastered/
            track_path = audio_dir / "originals" / track_filename
            if not track_path.exists():
                track_path = audio_dir / "mastered" / track_filename
            if not track_path.exists():
                return _safe_json({
                    "error": f"Track file not found: {track_filename}",
                    "available_files": [f.name for f in _find_wav_source_dir(audio_dir).glob("*.wav")],
                })

        # Resolve title: prefer markdown title from state cache over filename
        title = None
        albums = state.get("albums", {})
        normalized = _normalize_slug(album_slug)
        album_data = albums.get(normalized)
        if album_data:
            # Match track by stem (filename without extension)
            track_stem = track_path.stem
            track_slug = _normalize_slug(track_stem)
            tracks = album_data.get("tracks", {})
            track_data = tracks.get(track_slug)
            if track_data:
                title = track_data.get("title")

        if not title:
            # Fall back to cleaning up the filename
            title = track_path.stem
            if " - " in title:
                title = title.split(" - ", 1)[-1]
            else:
                title = re.sub(r"^\d{1,2}[\.\-_\s]+", "", title)
            title = title.replace("-", " ").replace("_", " ").title()

        output_path = output_dir / f"{track_path.stem}_promo.mp4"

        success = await loop.run_in_executor(
            None,
            lambda: generate_waveform_video(
                audio_path=track_path,
                artwork_path=artwork,
                title=title,
                output_path=output_path,
                duration=duration,
                style=style,
                artist_name=artist,
                font_path=font_path,
                color_hex=color_hex,
                glow=glow,
                text_color=text_color,
            ),
        )

        return _safe_json({
            "tracks": [{"filename": track_filename, "output": str(output_path), "success": success}],
            "summary": {"success": 1 if success else 0, "failed": 0 if success else 1},
        })
    else:
        # Batch all tracks
        # Resolve content dir for title lookup
        albums = state.get("albums", {})
        normalized = _normalize_slug(album_slug)
        content_dir = None
        album_data = albums.get(normalized)
        if album_data:
            content_dir_path = Path(album_data.get("path", ""))
            if content_dir_path.is_dir():
                content_dir = content_dir_path

        await loop.run_in_executor(
            None,
            lambda: batch_process_album(
                album_dir=audio_dir,
                artwork_path=artwork,
                output_dir=output_dir,
                duration=duration,
                style=style,
                artist_name=artist,
                font_path=font_path,
                content_dir=content_dir,
                color_hex=color_hex,
                glow=glow,
                text_color=text_color,
            ),
        )

        # Collect results from output dir
        output_files = sorted(output_dir.glob("*_promo.mp4"))
        results = [{"filename": f.name, "output": str(f), "success": True} for f in output_files]

        return _safe_json({
            "tracks": results,
            "summary": {
                "success": len(results),
                "output_dir": str(output_dir),
            },
        })


async def generate_album_sampler(
    album_slug: str,
    clip_duration: int = 12,
    crossfade: float = 0.5,
    style: str = "pulse",
    color_hex: str = "",
    glow: float = 0.6,
    text_color: str = "",
) -> str:
    """Generate an album sampler video cycling through all tracks.

    Creates a single promotional video with short clips from each track,
    designed to fit Twitter's 2:20 (140 second) limit.

    Args:
        album_slug: Album slug (e.g., "my-album")
        clip_duration: Duration per track clip in seconds (default: 12)
        crossfade: Crossfade duration between clips in seconds (default: 0.5)
        style: Visualization style - "pulse", "mirror", "mountains", "colorwave",
               "neon", "dual", "bars", "line", "circular" (default: "pulse")
        color_hex: Wave color as hex (e.g. "#C9A96E"). Empty = auto-extract from artwork
        glow: Glow intensity 0.0 (none) to 1.0 (full). Default 0.6
        text_color: Text color as hex (e.g. "#FFD700"). Empty = white

    Returns:
        JSON with output path, tracks included, and duration
    """
    ffmpeg_err = _check_ffmpeg()
    if ffmpeg_err:
        return _safe_json({"error": ffmpeg_err})

    err, audio_dir = _resolve_audio_dir(album_slug)
    if err:
        return err
    assert audio_dir is not None

    # Find artwork
    artwork_patterns = [
        "album.png", "album.jpg", "album-art.png", "album-art.jpg",
        "artwork.png", "artwork.jpg", "cover.png", "cover.jpg",
    ]
    artwork = None
    for pattern in artwork_patterns:
        candidate = audio_dir / pattern
        if candidate.exists():
            artwork = candidate
            break
    if not artwork:
        return _safe_json({
            "error": "No album artwork found in audio directory.",
            "suggestion": "Place album.png in the audio directory.",
        })

    from tools.promotion.generate_album_sampler import (
        generate_album_sampler as _gen_sampler,
    )

    # Get artist from state
    state = _shared.cache.get_state()
    config_data = state.get("config", {})
    artist = config_data.get("artist_name", "bitwize")

    # Pre-resolve titles from state cache (proper titles from markdown metadata)
    titles: dict[str, str] = {}
    albums = state.get("albums", {})
    normalized = _normalize_slug(album_slug)
    album_data = albums.get(normalized)
    if album_data:
        for track_slug, track_data in album_data.get("tracks", {}).items():
            title = track_data.get("title")
            if title:
                titles[track_slug] = title

    output_dir = audio_dir / "promo_videos"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "album_sampler.mp4"

    loop = asyncio.get_running_loop()
    success = await loop.run_in_executor(
        None,
        lambda: _gen_sampler(
            tracks_dir=audio_dir,
            artwork_path=artwork,
            output_path=output_path,
            clip_duration=clip_duration,
            crossfade=crossfade,
            artist_name=artist,
            titles=titles,
            style=style,
            color_hex=color_hex,
            glow=glow,
            text_color=text_color,
        ),
    )

    if success and output_path.exists():
        file_size = output_path.stat().st_size / (1024 * 1024)
        # Count audio files
        audio_extensions = {".wav", ".mp3", ".flac", ".m4a"}
        track_count = sum(
            1 for f in _find_wav_source_dir(audio_dir).iterdir()
            if f.suffix.lower() in audio_extensions
        )
        expected_duration = track_count * clip_duration - max(0, track_count - 1) * crossfade

        return _safe_json({
            "success": True,
            "output_path": str(output_path),
            "tracks_included": track_count,
            "clip_duration": clip_duration,
            "crossfade": crossfade,
            "expected_duration_seconds": expected_duration,
            "file_size_mb": round(file_size, 1),
            "twitter_limit_ok": expected_duration <= 140,
        })
    else:
        return _safe_json({"error": "Album sampler generation failed."})


async def master_album(
    album_slug: str,
    genre: str = "",
    target_lufs: float = -14.0,
    ceiling_db: float = -1.0,
    cut_highmid: float = 0.0,
    cut_highs: float = 0.0,
    source_subfolder: str = "",
) -> str:
    """End-to-end mastering pipeline: analyze, QC, master, verify, update status.

    Runs 7 sequential stages, stopping on failure:
        1. Pre-flight — resolve audio dir, check deps, find WAV files
        2. Analyze — measure LUFS, peaks, spectral balance on raw files
        3. Pre-QC — run technical QC checks on raw files (fails on FAIL verdict)
        4. Master — normalize loudness, apply EQ, limit peaks
        5. Verify — check mastered output meets targets (±0.5 dB LUFS, peak < ceiling)
        6. Post-QC — run technical QC on mastered files (fails on FAIL verdict)
        7. Update status — set tracks to Final, album to Complete

    Args:
        album_slug: Album slug (e.g., "my-album")
        genre: Genre preset to apply (overrides EQ/LUFS defaults if set)
        target_lufs: Target integrated loudness (default: -14.0)
        ceiling_db: True peak ceiling in dB (default: -1.0)
        cut_highmid: High-mid EQ cut in dB at 3.5kHz (e.g., -2.0)
        cut_highs: High shelf cut in dB at 8kHz
        source_subfolder: Read WAV files from this subfolder instead of the
            base audio dir (e.g., "polished" to master from mix-engineer output)

    Returns:
        JSON with per-stage results, settings, warnings, and failure info
    """
    from tools.state.indexer import write_state
    from tools.state.parsers import parse_track_file

    stages: dict[str, Any] = {}
    warnings: list[Any] = []

    # --- Stage 1: Pre-flight ---
    dep_err = _check_mastering_deps()
    if dep_err:
        return _safe_json({
            "album_slug": album_slug,
            "stage_reached": "pre_flight",
            "stages": {"pre_flight": {"status": "fail", "detail": dep_err}},
            "failed_stage": "pre_flight",
            "failure_detail": {"reason": dep_err},
        })

    err, audio_dir = _resolve_audio_dir(album_slug)
    if err:
        return _safe_json({
            "album_slug": album_slug,
            "stage_reached": "pre_flight",
            "stages": {"pre_flight": {"status": "fail", "detail": "Audio directory not found"}},
            "failed_stage": "pre_flight",
            "failure_detail": json.loads(err),
        })
    assert audio_dir is not None

    # If source_subfolder specified, read from that subfolder
    if source_subfolder:
        source_dir = audio_dir / source_subfolder
        if not source_dir.is_dir():
            return _safe_json({
                "album_slug": album_slug,
                "stage_reached": "pre_flight",
                "stages": {"pre_flight": {
                    "status": "fail",
                    "detail": f"Source subfolder not found: {source_dir}",
                }},
                "failed_stage": "pre_flight",
                "failure_detail": {
                    "reason": f"Source subfolder not found: {source_dir}",
                    "suggestion": f"Run polish_audio first to create {source_subfolder}/ output.",
                },
            })
    else:
        source_dir = _find_wav_source_dir(audio_dir)

    wav_files = sorted([
        f for f in source_dir.iterdir()
        if f.suffix.lower() == ".wav" and "venv" not in str(f)
    ])

    if not wav_files:
        return _safe_json({
            "album_slug": album_slug,
            "stage_reached": "pre_flight",
            "stages": {"pre_flight": {
                "status": "fail",
                "detail": f"No WAV files found in {source_dir}",
            }},
            "failed_stage": "pre_flight",
            "failure_detail": {"reason": f"No WAV files in {source_dir}"},
        })

    stages["pre_flight"] = {
        "status": "pass",
        "track_count": len(wav_files),
        "audio_dir": str(audio_dir),
        "source_dir": str(source_dir),
    }

    # Resolve genre presets and effective settings (same logic as master_audio)
    import numpy as np

    from tools.mastering.master_tracks import (
        load_genre_presets,
    )
    from tools.mastering.master_tracks import (
        master_track as _master_track,
    )

    effective_lufs = target_lufs
    effective_highmid = cut_highmid
    effective_highs = cut_highs
    effective_compress = 1.5
    genre_applied = None

    if genre:
        presets = load_genre_presets()
        genre_key = genre.lower()
        if genre_key not in presets:
            return _safe_json({
                "album_slug": album_slug,
                "stage_reached": "pre_flight",
                "stages": stages,
                "failed_stage": "pre_flight",
                "failure_detail": {
                    "reason": f"Unknown genre: {genre}",
                    "available_genres": sorted(presets.keys()),
                },
            })
        preset_lufs, preset_highmid, preset_highs, preset_compress = presets[genre_key]
        if target_lufs == -14.0:
            effective_lufs = preset_lufs
        if cut_highmid == 0.0:
            effective_highmid = preset_highmid
        if cut_highs == 0.0:
            effective_highs = preset_highs
        effective_compress = preset_compress
        genre_applied = genre_key

    settings = {
        "genre": genre_applied,
        "target_lufs": effective_lufs,
        "ceiling_db": ceiling_db,
        "cut_highmid": effective_highmid,
        "cut_highs": effective_highs,
    }

    loop = asyncio.get_running_loop()

    # --- Stage 2: Analysis ---
    from tools.mastering.analyze_tracks import analyze_track

    analysis_results = []
    for wav in wav_files:
        result = await loop.run_in_executor(None, analyze_track, str(wav))
        analysis_results.append(result)

    lufs_values = [r["lufs"] for r in analysis_results]
    avg_lufs = float(np.mean(lufs_values))
    lufs_range = float(max(lufs_values) - min(lufs_values))
    tinny_tracks = [r["filename"] for r in analysis_results if r["tinniness_ratio"] > 0.6]

    if tinny_tracks:
        for t in tinny_tracks:
            warnings.append(f"Pre-master: {t} — tinny (high-mid spike)")

    stages["analysis"] = {
        "status": "pass",
        "avg_lufs": round(avg_lufs, 1),
        "lufs_range": round(lufs_range, 1),
        "tinny_tracks": tinny_tracks,
    }

    # --- Stage 3: Pre-QC ---
    from tools.mastering.qc_tracks import qc_track

    pre_qc_results = []
    for wav in wav_files:
        result = await loop.run_in_executor(None, qc_track, str(wav), None)
        pre_qc_results.append(result)

    pre_passed = sum(1 for r in pre_qc_results if r["verdict"] == "PASS")
    pre_warned = sum(1 for r in pre_qc_results if r["verdict"] == "WARN")
    pre_failed = sum(1 for r in pre_qc_results if r["verdict"] == "FAIL")

    # Collect warnings
    for r in pre_qc_results:
        for check_name, check_info in r["checks"].items():
            if check_info["status"] == "WARN":
                warnings.append(f"Pre-QC {r['filename']}: {check_name} WARN — {check_info['detail']}")

    if pre_failed > 0:
        failed_tracks = [r for r in pre_qc_results if r["verdict"] == "FAIL"]
        fail_details = []
        for r in failed_tracks:
            for check_name, check_info in r["checks"].items():
                if check_info["status"] == "FAIL":
                    fail_details.append({
                        "filename": r["filename"],
                        "check": check_name,
                        "status": "FAIL",
                        "detail": check_info["detail"],
                    })

        stages["pre_qc"] = {
            "status": "fail",
            "passed": pre_passed,
            "warned": pre_warned,
            "failed": pre_failed,
            "verdict": "FAILURES FOUND",
        }
        return _safe_json({
            "album_slug": album_slug,
            "stage_reached": "pre_qc",
            "stages": stages,
            "settings": settings,
            "warnings": warnings,
            "failed_stage": "pre_qc",
            "failure_detail": {
                "tracks_failed": [r["filename"] for r in failed_tracks],
                "details": fail_details,
            },
        })

    stages["pre_qc"] = {
        "status": "pass",
        "passed": pre_passed,
        "warned": pre_warned,
        "failed": 0,
        "verdict": "ALL PASS" if pre_warned == 0 else "WARNINGS",
    }

    # --- Stage 4: Mastering ---
    eq_settings = []
    if effective_highmid != 0:
        eq_settings.append((3500.0, effective_highmid, 1.5))
    if effective_highs != 0:
        eq_settings.append((8000.0, effective_highs, 0.7))

    output_dir = audio_dir / "mastered"
    output_dir.mkdir(exist_ok=True)

    # Look up per-track metadata for fade_out values
    state = _shared.cache.get_state() or {}
    album_tracks = (state.get("albums", {})
                         .get(_normalize_slug(album_slug), {})
                         .get("tracks", {}))

    master_results = []
    for wav_file in wav_files:
        output_path = output_dir / wav_file.name

        # Derive track slug from WAV filename and look up fade_out
        track_stem = wav_file.stem
        track_slug = _normalize_slug(track_stem)
        track_meta = album_tracks.get(track_slug, {})
        fade_out_val = track_meta.get("fade_out")

        def _do_master(in_path: Path, out_path: Path, lufs: float, eq: list[tuple[float, float, float]], ceil: float, fade: float | None, comp: float) -> dict[str, Any]:
            return _master_track(
                str(in_path), str(out_path),
                target_lufs=lufs,
                eq_settings=eq if eq else None,
                ceiling_db=ceil,
                fade_out=fade,
                compress_ratio=comp,
            )

        result = await loop.run_in_executor(
            None, _do_master, wav_file, output_path,
            effective_lufs, eq_settings, ceiling_db, fade_out_val,
            effective_compress,
        )
        if result and not result.get("skipped"):
            result["filename"] = wav_file.name
            master_results.append(result)

    if not master_results:
        stages["mastering"] = {"status": "fail", "detail": "No tracks processed (all silent)"}
        return _safe_json({
            "album_slug": album_slug,
            "stage_reached": "mastering",
            "stages": stages,
            "settings": settings,
            "warnings": warnings,
            "failed_stage": "mastering",
            "failure_detail": {"reason": "No tracks processed (all silent or no WAV files)"},
        })

    stages["mastering"] = {
        "status": "pass",
        "tracks_processed": len(master_results),
        "settings": settings,
        "output_dir": str(output_dir),
    }

    # --- Stage 5: Verification ---
    mastered_files = sorted([
        f for f in output_dir.iterdir()
        if f.suffix.lower() == ".wav" and "venv" not in str(f)
    ])

    verify_results = []
    for wav in mastered_files:
        result = await loop.run_in_executor(None, analyze_track, str(wav))
        verify_results.append(result)

    verify_lufs = [r["lufs"] for r in verify_results]
    verify_avg = float(np.mean(verify_lufs))
    verify_range = float(max(verify_lufs) - min(verify_lufs))

    # Check thresholds
    out_of_spec = []
    for r in verify_results:
        issues = []
        if abs(r["lufs"] - effective_lufs) > 0.5:
            issues.append(f"LUFS {r['lufs']:.1f} outside ±0.5 dB of target {effective_lufs}")
        if r["peak_db"] > ceiling_db:
            issues.append(f"Peak {r['peak_db']:.1f} dB exceeds ceiling {ceiling_db} dB")
        if issues:
            out_of_spec.append({"filename": r["filename"], "issues": issues})

    album_range_fail = verify_range >= 1.0
    auto_recovered: list[dict[str, Any]] = []

    if out_of_spec or album_range_fail:
        # --- Auto-recovery: fix recoverable dynamic range issues ---
        # A track is recoverable when LUFS is too low (>0.5 dB below target)
        # AND peak is at ceiling (within 0.1 dB).  This specific pattern means
        # the limiter is clamping transients — compression will help.
        recoverable = []
        for spec in out_of_spec:
            has_peak_issue = any("Peak" in iss for iss in spec["issues"])
            vr = next(
                (r for r in verify_results if r["filename"] == spec["filename"]),
                None,
            )
            if not vr:
                continue
            lufs_too_low = vr["lufs"] < effective_lufs - 0.5
            peak_at_ceiling = vr["peak_db"] >= ceiling_db - 0.1
            if lufs_too_low and peak_at_ceiling and not has_peak_issue:
                recoverable.append(spec["filename"])

        if recoverable:
            from tools.mastering.fix_dynamic_track import fix_dynamic

            auto_recovered = []
            for fname in recoverable:
                raw_path = source_dir / fname
                if not raw_path.exists():
                    raw_path = _find_wav_source_dir(audio_dir) / fname
                if not raw_path.exists():
                    continue

                def _do_recovery(src: Path, dst: Path, lufs: float, eq: list[tuple[float, float, float]], ceil: float) -> dict[str, Any]:
                    import soundfile as sf
                    data, rate = sf.read(str(src))
                    if len(data.shape) == 1:
                        data = np.column_stack([data, data])
                    data, metrics = fix_dynamic(
                        data, rate,
                        target_lufs=lufs,
                        eq_settings=eq if eq else None,
                        ceiling_db=ceil,
                    )
                    sf.write(str(dst), data, rate, subtype="PCM_16")
                    return metrics

                mastered_path = output_dir / fname
                metrics = await loop.run_in_executor(
                    None, _do_recovery, raw_path, mastered_path,
                    effective_lufs, eq_settings, ceiling_db,
                )
                auto_recovered.append({
                    "filename": fname,
                    "original_lufs": metrics["original_lufs"],
                    "final_lufs": metrics["final_lufs"],
                    "final_peak_db": metrics["final_peak_db"],
                })

            if auto_recovered:
                warnings.append({
                    "type": "auto_recovery",
                    "tracks_fixed": [r["filename"] for r in auto_recovered],
                })

                # Re-verify ALL tracks (album range check needs all)
                verify_results = []
                for wav in mastered_files:
                    result = await loop.run_in_executor(
                        None, analyze_track, str(wav),
                    )
                    verify_results.append(result)

                verify_lufs = [r["lufs"] for r in verify_results]
                verify_avg = float(np.mean(verify_lufs))
                verify_range = float(max(verify_lufs) - min(verify_lufs))

                out_of_spec = []
                for r in verify_results:
                    issues = []
                    if abs(r["lufs"] - effective_lufs) > 0.5:
                        issues.append(
                            f"LUFS {r['lufs']:.1f} outside ±0.5 dB of target {effective_lufs}"
                        )
                    if r["peak_db"] > ceiling_db:
                        issues.append(
                            f"Peak {r['peak_db']:.1f} dB exceeds ceiling {ceiling_db} dB"
                        )
                    if issues:
                        out_of_spec.append({"filename": r["filename"], "issues": issues})

                album_range_fail = verify_range >= 1.0

        # If still failing after recovery attempt, return failure
        if out_of_spec or album_range_fail:
            fail_detail: dict[str, Any] = {}
            if out_of_spec:
                fail_detail["tracks_out_of_spec"] = out_of_spec
            if album_range_fail:
                fail_detail["album_lufs_range"] = round(verify_range, 2)
                fail_detail["album_range_limit"] = 1.0

            stages["verification"] = {
                "status": "fail",
                "avg_lufs": round(verify_avg, 1),
                "lufs_range": round(verify_range, 2),
                "all_within_spec": False,
            }
            return _safe_json({
                "album_slug": album_slug,
                "stage_reached": "verification",
                "stages": stages,
                "settings": settings,
                "warnings": warnings,
                "failed_stage": "verification",
                "failure_detail": fail_detail,
            })

    verification_stage = {
        "status": "pass",
        "avg_lufs": round(verify_avg, 1),
        "lufs_range": round(verify_range, 2),
        "all_within_spec": True,
    }
    # Include auto-recovery details when tracks were fixed
    if auto_recovered:
        verification_stage["auto_recovered"] = auto_recovered
    stages["verification"] = verification_stage

    # --- Stage 6: Post-QC ---
    post_qc_results = []
    for wav in mastered_files:
        result = await loop.run_in_executor(None, qc_track, str(wav), None)
        post_qc_results.append(result)

    post_passed = sum(1 for r in post_qc_results if r["verdict"] == "PASS")
    post_warned = sum(1 for r in post_qc_results if r["verdict"] == "WARN")
    post_failed = sum(1 for r in post_qc_results if r["verdict"] == "FAIL")

    for r in post_qc_results:
        for check_name, check_info in r["checks"].items():
            if check_info["status"] == "WARN":
                warnings.append(f"Post-QC {r['filename']}: {check_name} WARN — {check_info['detail']}")

    if post_failed > 0:
        failed_tracks = [r for r in post_qc_results if r["verdict"] == "FAIL"]
        fail_details = []
        for r in failed_tracks:
            for check_name, check_info in r["checks"].items():
                if check_info["status"] == "FAIL":
                    fail_details.append({
                        "filename": r["filename"],
                        "check": check_name,
                        "status": "FAIL",
                        "detail": check_info["detail"],
                    })

        stages["post_qc"] = {
            "status": "fail",
            "passed": post_passed,
            "warned": post_warned,
            "failed": post_failed,
            "verdict": "FAILURES FOUND",
        }
        return _safe_json({
            "album_slug": album_slug,
            "stage_reached": "post_qc",
            "stages": stages,
            "settings": settings,
            "warnings": warnings,
            "failed_stage": "post_qc",
            "failure_detail": {
                "tracks_failed": [r["filename"] for r in failed_tracks],
                "details": fail_details,
            },
        })

    stages["post_qc"] = {
        "status": "pass",
        "passed": post_passed,
        "warned": post_warned,
        "failed": 0,
        "verdict": "ALL PASS" if post_warned == 0 else "WARNINGS",
    }

    # --- Stage 7: Update statuses ---
    # Use the in-memory state directly rather than re-fetching via
    # cache.get_state(), which could reload from disk and lose any
    # concurrent modifications made during the lengthy processing stages.
    state = _shared.cache.get_state_ref()
    albums = state.get("albums", {})
    normalized_album = _normalize_slug(album_slug)
    album_data = albums.get(normalized_album)

    tracks_updated = 0
    status_errors = []

    if album_data:
        tracks = album_data.get("tracks", {})

        for track_slug, track_info in tracks.items():
            current_track_status = track_info.get("status", TRACK_NOT_STARTED)

            # Only transition Generated → Final; skip already-Final tracks
            if current_track_status.lower() == TRACK_FINAL.lower():
                continue  # already Final — nothing to do
            if current_track_status.lower() != TRACK_GENERATED.lower():
                status_errors.append(
                    f"Skipped '{track_slug}': status is '{current_track_status}' "
                    f"(expected '{TRACK_GENERATED}')"
                )
                continue

            track_path_str = track_info.get("path", "")
            if not track_path_str:
                status_errors.append(f"No path for track '{track_slug}'")
                continue

            track_path = Path(track_path_str)
            if not track_path.exists():
                status_errors.append(f"Track file not found: {track_path}")
                continue

            try:
                text = track_path.read_text(encoding="utf-8")
                pattern = re.compile(
                    r'^(\|\s*\*\*Status\*\*\s*\|)\s*.*?\s*\|',
                    re.MULTILINE,
                )
                match = pattern.search(text)
                if match:
                    new_row = f"{match.group(1)} {TRACK_FINAL} |"
                    updated_text = text[:match.start()] + new_row + text[match.end():]
                    track_path.write_text(updated_text, encoding="utf-8")

                    # Update cache
                    parsed = parse_track_file(track_path)
                    track_info.update({
                        "status": parsed.get("status", TRACK_FINAL),
                        "mtime": track_path.stat().st_mtime,
                    })
                    tracks_updated += 1
                else:
                    status_errors.append(f"Status field not found in {track_slug}")
            except Exception as e:
                status_errors.append(f"Error updating {track_slug}: {e}")

        # Update album status to Complete if all tracks are Final
        all_final = all(
            t.get("status", "").lower() == TRACK_FINAL.lower()
            for t in tracks.values()
        )
        album_status = None
        if all_final:
            album_path_str = album_data.get("path", "")
            if album_path_str:
                readme_path = Path(album_path_str) / "README.md"
                if readme_path.exists():
                    try:
                        text = readme_path.read_text(encoding="utf-8")
                        pattern = re.compile(
                            r'^(\|\s*\*\*Status\*\*\s*\|)\s*.*?\s*\|',
                            re.MULTILINE,
                        )
                        match = pattern.search(text)
                        if match:
                            new_row = f"{match.group(1)} {ALBUM_COMPLETE} |"
                            updated_text = text[:match.start()] + new_row + text[match.end():]
                            readme_path.write_text(updated_text, encoding="utf-8")
                            album_data["status"] = ALBUM_COMPLETE
                            album_status = ALBUM_COMPLETE
                    except Exception as e:
                        status_errors.append(f"Error updating album status: {e}")

        # Persist state cache
        try:
            write_state(state)
        except Exception as e:
            status_errors.append(f"Cache write failed: {e}")
    else:
        status_errors.append(f"Album '{album_slug}' not found in state cache")

    if status_errors:
        for err_msg in status_errors:
            warnings.append(f"Status update: {err_msg}")

    stages["status_update"] = {
        "status": "pass",
        "tracks_updated": tracks_updated,
        "album_status": album_status,
        "errors": status_errors if status_errors else None,
    }

    return _safe_json({
        "album_slug": album_slug,
        "stage_reached": "complete",
        "stages": stages,
        "settings": settings,
        "warnings": warnings,
        "failed_stage": None,
        "failure_detail": None,
    })


# =============================================================================
# Mix Polish Tools (per-stem audio cleanup before mastering)
# =============================================================================


async def polish_audio(
    album_slug: str,
    genre: str = "",
    use_stems: bool = True,
    dry_run: bool = False,
) -> str:
    """Polish audio tracks by processing stems or full mixes.

    When use_stems=True (default), looks for stem WAV files in a stems/
    subfolder with per-track directories (vocals.wav, drums.wav, bass.wav,
    other.wav). Processes each stem with targeted cleanup and remixes them.

    When use_stems=False, processes full mix WAV files directly.

    Writes polished output to a polished/ subfolder. Originals are preserved.

    Args:
        album_slug: Album slug (e.g., "my-album")
        genre: Genre preset for stem-specific settings (e.g., "hip-hop")
        use_stems: If true, process per-stem WAVs; if false, process full mixes
        dry_run: If true, analyze only without writing files

    Returns:
        JSON with per-track results, settings, and summary
    """
    dep_err = _check_mixing_deps()
    if dep_err:
        return _safe_json({"error": dep_err})

    err, audio_dir = _resolve_audio_dir(album_slug)
    if err:
        return err
    assert audio_dir is not None

    from tools.mixing.mix_tracks import (
        discover_stems,
        load_mix_presets,
        mix_track_full,
        mix_track_stems,
    )

    # Validate genre if specified
    if genre:
        presets = load_mix_presets()
        genre_key = genre.lower()
        if genre_key not in presets.get('genres', {}):
            return _safe_json({
                "error": f"Unknown genre: {genre}",
                "available_genres": sorted(presets.get('genres', {}).keys()),
            })

    output_dir = audio_dir / "polished"
    if not dry_run:
        output_dir.mkdir(exist_ok=True)

    loop = asyncio.get_running_loop()
    track_results = []

    if use_stems:
        # Stems mode: look for stems/ subdirectory with track folders
        stems_dir = audio_dir / "stems"
        if not stems_dir.is_dir():
            return _safe_json({
                "error": f"No stems/ directory found in {audio_dir}",
                "suggestion": "Import stems first, or use use_stems=false for full-mix mode.",
            })

        track_dirs = sorted([d for d in stems_dir.iterdir() if d.is_dir()])
        if not track_dirs:
            return _safe_json({"error": f"No track directories in {stems_dir}"})

        for track_dir in track_dirs:
            stem_paths = discover_stems(track_dir)

            if not stem_paths:
                continue

            out_path = str(output_dir / f"{track_dir.name}.wav")

            def _do_stems(sp: dict[str, str | list[str]], op: str, g: str | None, dr: bool) -> dict[str, Any]:
                return mix_track_stems(sp, op, genre=g, dry_run=dr)

            result = await loop.run_in_executor(
                None, _do_stems, stem_paths, out_path,
                genre or None, dry_run,
            )

            if result:
                result["track_name"] = track_dir.name
                track_results.append(result)

    else:
        # Full-mix mode: process WAV files directly
        source_dir = _find_wav_source_dir(audio_dir)
        wav_files = sorted([
            f for f in source_dir.iterdir()
            if f.suffix.lower() == ".wav" and "venv" not in str(f)
        ])

        if not wav_files:
            return _safe_json({"error": f"No WAV files found in {audio_dir}"})

        for wav_file in wav_files:
            out_path = str(output_dir / wav_file.name)

            def _do_full(ip: str, op: str, g: str | None, dr: bool) -> dict[str, Any]:
                return mix_track_full(ip, op, genre=g, dry_run=dr)

            result = await loop.run_in_executor(
                None, _do_full, str(wav_file), out_path,
                genre or None, dry_run,
            )

            if result:
                track_results.append(result)

    if not track_results:
        return _safe_json({"error": "No tracks were processed."})

    return _safe_json({
        "tracks": track_results,
        "settings": {
            "genre": genre or None,
            "use_stems": use_stems,
            "dry_run": dry_run,
        },
        "summary": {
            "tracks_processed": len(track_results),
            "mode": "stems" if use_stems else "full_mix",
            "output_dir": str(output_dir) if not dry_run else None,
        },
    })


async def analyze_mix_issues(
    album_slug: str,
) -> str:
    """Analyze audio files for common mix issues and recommend settings.

    Scans WAV files for noise floor, muddiness (low-mid energy), harshness
    (high-mid energy), clicks, and stereo issues. Returns per-track diagnostics
    with recommended mix-engineer settings.

    Args:
        album_slug: Album slug (e.g., "my-album")

    Returns:
        JSON with per-track analysis, detected issues, and recommendations
    """
    dep_err = _check_mixing_deps()
    if dep_err:
        return _safe_json({"error": dep_err})

    err, audio_dir = _resolve_audio_dir(album_slug)
    if err:
        return err
    assert audio_dir is not None

    import numpy as np
    import soundfile as sf

    loop = asyncio.get_running_loop()

    source_dir = _find_wav_source_dir(audio_dir)
    wav_files = sorted([
        f for f in source_dir.iterdir()
        if f.suffix.lower() == ".wav" and "venv" not in str(f)
    ])

    if not wav_files:
        return _safe_json({"error": f"No WAV files found in {audio_dir}"})

    def _analyze_one(wav_path: Path) -> dict[str, Any]:
        data, rate = sf.read(str(wav_path))
        if len(data.shape) == 1:
            data = np.column_stack([data, data])

        result: dict[str, Any] = {"filename": wav_path.name, "issues": [], "recommendations": {}}

        # Overall metrics
        peak = float(np.max(np.abs(data)))
        rms = float(np.sqrt(np.mean(data ** 2)))
        result["peak"] = peak
        result["rms"] = rms

        # Noise floor estimate (quietest 10% of signal)
        abs_signal = np.abs(data[:, 0])
        sorted_abs = np.sort(abs_signal)
        noise_floor = float(np.mean(sorted_abs[:len(sorted_abs) // 10]))
        result["noise_floor"] = noise_floor
        if noise_floor > 0.005:
            result["issues"].append("elevated_noise_floor")
            result["recommendations"]["noise_reduction"] = min(0.8, noise_floor * 100)

        # Spectral analysis (simplified: energy in frequency bands)
        from scipy import signal as sig
        freqs, psd = sig.welch(data[:, 0], rate, nperseg=min(4096, len(data)))

        # Low-mid energy (150-400 Hz) — muddiness indicator
        low_mid_mask = (freqs >= 150) & (freqs <= 400)
        total_energy = float(np.sum(psd))
        if total_energy > 0:
            low_mid_ratio = float(np.sum(psd[low_mid_mask])) / total_energy
            result["low_mid_ratio"] = low_mid_ratio
            if low_mid_ratio > 0.35:
                result["issues"].append("muddy_low_mids")
                result["recommendations"]["mud_cut_db"] = -3.0

        # High-mid energy (2-5 kHz) — harshness indicator
        high_mid_mask = (freqs >= 2000) & (freqs <= 5000)
        if total_energy > 0:
            high_mid_ratio = float(np.sum(psd[high_mid_mask])) / total_energy
            result["high_mid_ratio"] = high_mid_ratio
            if high_mid_ratio > 0.25:
                result["issues"].append("harsh_highmids")
                result["recommendations"]["high_tame_db"] = -2.0

        # Click detection (sudden amplitude spikes)
        diff = np.diff(data[:, 0])
        diff_std = float(np.std(diff))
        if diff_std > 0:
            click_count = int(np.sum(np.abs(diff) > 6 * diff_std))
            result["click_count"] = click_count
            if click_count > 10:
                result["issues"].append("clicks_detected")
                result["recommendations"]["click_removal"] = True

        # Sub-bass rumble (< 30 Hz)
        sub_mask = freqs < 30
        if total_energy > 0:
            sub_ratio = float(np.sum(psd[sub_mask])) / total_energy
            result["sub_ratio"] = sub_ratio
            if sub_ratio > 0.15:
                result["issues"].append("sub_rumble")
                result["recommendations"]["highpass_cutoff"] = 35

        if not result["issues"]:
            result["issues"].append("none_detected")

        return result

    track_analyses = []
    for wav_file in wav_files:
        analysis = await loop.run_in_executor(None, _analyze_one, wav_file)
        track_analyses.append(analysis)

    # Album-level summary
    all_issues: set[str] = set()
    for a in track_analyses:
        all_issues.update(i for i in a["issues"] if i != "none_detected")

    return _safe_json({
        "tracks": track_analyses,
        "album_summary": {
            "tracks_analyzed": len(track_analyses),
            "common_issues": sorted(all_issues),
            "audio_dir": str(audio_dir),
        },
    })


async def polish_album(
    album_slug: str,
    genre: str = "",
) -> str:
    """End-to-end mix polish pipeline: analyze, polish stems, verify.

    Runs 3 sequential stages:
        1. Analyze — scan for mix issues and recommend settings
        2. Polish — process stems (or full mixes) with appropriate settings
        3. Verify — check polished output quality

    Args:
        album_slug: Album slug (e.g., "my-album")
        genre: Genre preset for stem-specific settings

    Returns:
        JSON with per-stage results, settings, and recommendations
    """
    dep_err = _check_mixing_deps()
    if dep_err:
        return _safe_json({
            "album_slug": album_slug,
            "stage_reached": "pre_flight",
            "failed_stage": "pre_flight",
            "failure_detail": {"reason": dep_err},
        })

    err, audio_dir = _resolve_audio_dir(album_slug)
    if err:
        return _safe_json({
            "album_slug": album_slug,
            "stage_reached": "pre_flight",
            "failed_stage": "pre_flight",
            "failure_detail": json.loads(err),
        })
    assert audio_dir is not None

    stages: dict[str, Any] = {}

    # Determine mode: stems or full mix
    stems_dir = audio_dir / "stems"
    use_stems = stems_dir.is_dir() and any(stems_dir.iterdir())

    stages["pre_flight"] = {
        "status": "pass",
        "audio_dir": str(audio_dir),
        "mode": "stems" if use_stems else "full_mix",
        "stems_dir": str(stems_dir) if use_stems else None,
    }

    # --- Stage 1: Analysis ---
    analysis_json = await analyze_mix_issues(album_slug)
    analysis = json.loads(analysis_json)

    if "error" in analysis:
        stages["analysis"] = {"status": "fail", "detail": analysis["error"]}
        return _safe_json({
            "album_slug": album_slug,
            "stage_reached": "analysis",
            "stages": stages,
            "failed_stage": "analysis",
            "failure_detail": analysis,
        })

    stages["analysis"] = {
        "status": "pass",
        "tracks_analyzed": analysis["album_summary"]["tracks_analyzed"],
        "common_issues": analysis["album_summary"]["common_issues"],
    }

    # --- Stage 2: Polish ---
    polish_json = await polish_audio(
        album_slug=album_slug,
        genre=genre,
        use_stems=use_stems,
        dry_run=False,
    )
    polish = json.loads(polish_json)

    if "error" in polish:
        stages["polish"] = {"status": "fail", "detail": polish["error"]}
        return _safe_json({
            "album_slug": album_slug,
            "stage_reached": "polish",
            "stages": stages,
            "failed_stage": "polish",
            "failure_detail": polish,
        })

    stages["polish"] = {
        "status": "pass",
        "tracks_processed": polish["summary"]["tracks_processed"],
        "output_dir": polish["summary"]["output_dir"],
    }

    # --- Stage 3: Verify polished output ---
    import numpy as np
    import soundfile as sf

    polished_dir = audio_dir / "polished"
    if not polished_dir.is_dir():
        stages["verify"] = {"status": "fail", "detail": "polished/ directory not found"}
        return _safe_json({
            "album_slug": album_slug,
            "stage_reached": "verify",
            "stages": stages,
            "failed_stage": "verify",
        })

    polished_files = sorted([
        f for f in polished_dir.iterdir()
        if f.suffix.lower() == ".wav"
    ])

    loop = asyncio.get_running_loop()
    verify_results = []

    for wav in polished_files:
        def _verify(path: Path) -> dict[str, Any]:
            data, _rate = sf.read(str(path))
            peak = float(np.max(np.abs(data)))
            rms = float(np.sqrt(np.mean(data ** 2)))
            finite = bool(np.all(np.isfinite(data)))
            return {
                "filename": path.name,
                "peak": peak,
                "rms": rms,
                "all_finite": finite,
                "clipping": peak > 0.99,
            }

        result = await loop.run_in_executor(None, _verify, wav)
        verify_results.append(result)

    clipping = [r["filename"] for r in verify_results if r["clipping"]]
    non_finite = [r["filename"] for r in verify_results if not r["all_finite"]]

    verify_pass = not clipping and not non_finite
    stages["verify"] = {
        "status": "pass" if verify_pass else "warn",
        "tracks_verified": len(verify_results),
        "clipping_tracks": clipping,
        "non_finite_tracks": non_finite,
    }

    return _safe_json({
        "album_slug": album_slug,
        "stage_reached": "complete",
        "stages": stages,
        "analysis": analysis.get("tracks"),
        "polish": polish.get("tracks"),
        "next_step": f"master_audio('{album_slug}', source_subfolder='polished')",
    })


# =============================================================================
# Registration
# =============================================================================


def register(mcp: Any) -> None:
    """Register all processing tools with the MCP server."""
    # Mastering tools
    mcp.tool()(analyze_audio)
    mcp.tool()(qc_audio)
    mcp.tool()(master_audio)
    mcp.tool()(fix_dynamic_track)
    mcp.tool()(master_with_reference)
    mcp.tool()(master_album)

    # Sheet music tools
    mcp.tool()(transcribe_audio)
    mcp.tool()(prepare_singles)
    mcp.tool()(create_songbook)
    mcp.tool()(publish_sheet_music)

    # Promo video tools
    mcp.tool()(generate_promo_videos)
    mcp.tool()(generate_album_sampler)

    # Mix polish tools
    mcp.tool()(polish_audio)
    mcp.tool()(analyze_mix_issues)
    mcp.tool()(polish_album)
