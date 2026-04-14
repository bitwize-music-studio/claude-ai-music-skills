"""Audio mastering and analysis tools."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from pathlib import Path
from typing import Any

from handlers import _shared
from handlers._shared import (
    ALBUM_COMPLETE,
    TRACK_FINAL,
    TRACK_GENERATED,
    TRACK_NOT_STARTED,
    _find_wav_source_dir,
    _is_path_confined,
    _normalize_slug,
    # _resolve_audio_dir accessed via _helpers for patch compatibility
    _safe_json,
)
from handlers.processing import _helpers

logger = logging.getLogger("bitwize-music-state")


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
    dep_err = _helpers._check_mastering_deps()
    if dep_err:
        return _safe_json({"error": dep_err})

    err, audio_dir = _helpers._resolve_audio_dir(album_slug, subfolder)
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


async def qc_audio(
    album_slug: str,
    subfolder: str = "",
    checks: str = "",
    genre: str = "",
) -> str:
    """Run technical QC checks on audio tracks.

    Scans WAV files for mono compatibility, phase correlation, clipping,
    clicks/pops, silence issues, format validation, and spectral balance.

    Args:
        album_slug: Album slug (e.g., "my-album")
        subfolder: Optional subfolder within audio dir (e.g., "mastered")
        checks: Comma-separated checks to run (default: all).
                Options: mono, phase, clipping, clicks, silence, format, spectral
        genre: Optional genre preset name. When set, the click detector uses
                genre-tuned peak/RMS thresholds so intentional sharp transients
                in electronic/metal/IDM don't FAIL QC.

    Returns:
        JSON with per-track QC results, summary, and verdicts
    """
    dep_err = _helpers._check_mastering_deps()
    if dep_err:
        return _safe_json({"error": dep_err})

    err, audio_dir = _helpers._resolve_audio_dir(album_slug, subfolder)
    if err:
        return err
    assert audio_dir is not None

    from tools.mastering.qc_tracks import ALL_CHECKS, _resolve_click_thresholds, qc_track

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

    genre_arg = genre.strip() or None
    if genre_arg is not None:
        try:
            _resolve_click_thresholds(genre_arg)
        except ValueError as e:
            return _safe_json({"error": str(e)})

    loop = asyncio.get_running_loop()
    results = []
    for wav in wav_files:
        result = await loop.run_in_executor(
            None, qc_track, str(wav), active_checks, genre_arg
        )
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
    dep_err = _helpers._check_mastering_deps()
    if dep_err:
        return _safe_json({"error": dep_err})

    err, audio_dir = _helpers._resolve_audio_dir(album_slug)
    if err:
        return err
    assert audio_dir is not None

    # If source_subfolder specified, read from that subfolder
    if source_subfolder:
        if not _is_path_confined(audio_dir, source_subfolder):
            return _safe_json({
                "error": "Invalid source_subfolder: path must not escape the album directory",
                "source_subfolder": source_subfolder,
            })
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

    from tools.mastering.config import build_effective_preset
    from tools.mastering.master_tracks import (
        master_track as _master_track,
    )

    bundle = build_effective_preset(
        genre=genre,
        cut_highmid_arg=cut_highmid,
        cut_highs_arg=cut_highs,
        target_lufs_arg=target_lufs,
        ceiling_db_arg=ceiling_db,
    )
    if bundle["error"] is not None:
        return _safe_json({
            "error": bundle["error"]["reason"],
            "available_genres": bundle["error"]["available_genres"],
        })
    targets = bundle["targets"]
    settings = bundle["settings"]
    effective_preset = bundle["effective_preset"]
    effective_lufs = targets["target_lufs"]
    effective_ceiling = targets["ceiling_db"]
    effective_highmid = settings["cut_highmid"]
    effective_highs = settings["cut_highs"]
    effective_compress = effective_preset["compress_ratio"]
    genre_applied = bundle["genre_applied"]

    # EQ is applied inside master_track from preset.cut_highmid / cut_highs
    # below; no need to pre-build an eq_settings tuple list here.

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
                    eq_settings=None,  # built from preset inside master_track
                    ceiling_db=effective_ceiling,
                    fade_out=fo,
                    compress_ratio=effective_compress,
                    preset=effective_preset,
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
            "ceiling_db": effective_ceiling,
            "output_bits": targets["output_bits"],
            "output_sample_rate": targets["output_sample_rate"],
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
    dep_err = _helpers._check_mastering_deps()
    if dep_err:
        return _safe_json({"error": dep_err})

    err, audio_dir = _helpers._resolve_audio_dir(album_slug)
    if err:
        return err
    assert audio_dir is not None

    if not _is_path_confined(audio_dir, track_filename):
        return _safe_json({
            "error": "Invalid track_filename: path must not escape the album directory",
            "track_filename": track_filename,
        })

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
    output_path = output_dir / Path(track_filename).name

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
    dep_err = _helpers._check_matchering()
    if dep_err:
        return _safe_json({"error": dep_err})

    err, audio_dir = _helpers._resolve_audio_dir(album_slug)
    if err:
        return err
    assert audio_dir is not None

    if not _is_path_confined(audio_dir, reference_filename):
        return _safe_json({
            "error": "Invalid reference_filename: path must not escape the album directory",
            "reference_filename": reference_filename,
        })

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
        if not _is_path_confined(audio_dir, target_filename):
            return _safe_json({
                "error": "Invalid target_filename: path must not escape the album directory",
                "target_filename": target_filename,
            })
        # Single file
        target_path = audio_dir / target_filename
        if not target_path.exists():
            target_path = _find_wav_source_dir(audio_dir) / target_filename
        if not target_path.exists():
            return _safe_json({
                "error": f"Target file not found: {target_filename}",
                "available_files": [f.name for f in _find_wav_source_dir(audio_dir).glob("*.wav")],
            })
        output_path = output_dir / Path(target_filename).name

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
    dep_err = _helpers._check_mastering_deps()
    if dep_err:
        return _safe_json({
            "album_slug": album_slug,
            "stage_reached": "pre_flight",
            "stages": {"pre_flight": {"status": "fail", "detail": dep_err}},
            "failed_stage": "pre_flight",
            "failure_detail": {"reason": dep_err},
        })

    err, audio_dir = _helpers._resolve_audio_dir(album_slug)
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
        if not _is_path_confined(audio_dir, source_subfolder):
            return _safe_json({
                "album_slug": album_slug,
                "stage_reached": "pre_flight",
                "stages": {"pre_flight": {
                    "status": "fail",
                    "detail": "Invalid source_subfolder: path must not escape the album directory",
                }},
                "failed_stage": "pre_flight",
                "failure_detail": {
                    "reason": "Invalid source_subfolder: path escapes album directory",
                    "source_subfolder": source_subfolder,
                },
            })
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

    import numpy as np

    from tools.mastering.config import build_effective_preset
    from tools.mastering.master_tracks import (
        master_track as _master_track,
    )

    source_sample_rate: int | None = None
    try:
        import soundfile as _sf
        source_sample_rate = int(_sf.info(str(wav_files[0])).samplerate)
    except Exception as _probe_exc:  # pragma: no cover - probe is best-effort
        logger.debug(
            "Source sample rate probe failed for %s: %s — "
            "upsampling notice will be suppressed",
            wav_files[0],
            _probe_exc,
        )
        source_sample_rate = None

    bundle = build_effective_preset(
        genre=genre,
        cut_highmid_arg=cut_highmid,
        cut_highs_arg=cut_highs,
        target_lufs_arg=target_lufs,
        ceiling_db_arg=ceiling_db,
        source_sample_rate=source_sample_rate,
    )
    if bundle["error"] is not None:
        return _safe_json({
            "album_slug": album_slug,
            "stage_reached": "pre_flight",
            "stages": stages,
            "failed_stage": "pre_flight",
            "failure_detail": bundle["error"],
        })
    targets = bundle["targets"]
    settings = bundle["settings"]
    effective_preset = bundle["effective_preset"]
    preset_dict = bundle["preset_dict"]
    effective_lufs = targets["target_lufs"]
    effective_ceiling = targets["ceiling_db"]
    effective_highmid = settings["cut_highmid"]
    effective_highs = settings["cut_highs"]
    effective_compress = effective_preset["compress_ratio"]

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

    # --- Stage 2b: Anchor selection (#290 phase 2) ---
    from tools.mastering.anchor_selector import select_anchor

    # Read anchor_track override from state cache (parse_album_readme
    # surfaces it as an int or None).
    anchor_override: int | None = None
    state_albums = (_shared.cache.get_state() or {}).get("albums", {})
    album_state = state_albums.get(_normalize_slug(album_slug), {})
    raw_override = album_state.get("anchor_track")
    if isinstance(raw_override, int) and not isinstance(raw_override, bool):
        anchor_override = raw_override

    # Build anchor preset. load_genre_presets() filters through
    # _PRESET_DEFAULTS, so nested-dict defaults (spectral_reference_energy)
    # don't inherit into per-genre presets. select_anchor carries its own
    # pop-balanced defaults for `genre_ideal_lra_lu` and
    # `spectral_reference_energy` when the preset omits them.
    anchor_preset = preset_dict or {}

    anchor_result = select_anchor(
        analysis_results,
        anchor_preset,
        override_index=anchor_override,
    )

    # Phase 2 records the result but does not yet re-order the mastering
    # loop — coherence correction lands in a later phase.
    stages["anchor_selection"] = {
        "status": "pass" if anchor_result["selected_index"] is not None else "warn",
        "selected_index": anchor_result["selected_index"],
        "method": anchor_result["method"],
        "override_index": anchor_result["override_index"],
        "override_reason": anchor_result["override_reason"],
        "scores": anchor_result["scores"],
    }
    if anchor_result["selected_index"] is None:
        warnings.append(
            "Anchor selector: no eligible tracks (signature metrics missing). "
            "Mastering proceeds without an anchor; coherence correction disabled."
        )

    # --- Stage 3: Pre-QC ---
    # Skip `truepeak` and `clicks` on the raw/polished input:
    #   • truepeak: polished audio is pre-limiter — the mastering stage's
    #     limiter is what enforces the ceiling. Post-master verification
    #     (Stage 5) is the real ceiling gate.
    #   • clicks: polish already runs declick; residual transients here
    #     false-positive on legitimate percussive content (drum hits,
    #     electronic transients). A later pass with genre-aware thresholds
    #     could re-enable this.
    # The remaining checks catch issues mastering cannot fix.
    from tools.mastering.qc_tracks import qc_track

    PRE_QC_CHECKS = ["format", "mono", "phase", "clipping", "silence", "spectral"]

    pre_qc_results = []
    for wav in wav_files:
        result = await loop.run_in_executor(
            None, qc_track, str(wav), PRE_QC_CHECKS
        )
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

    # Use a staging directory so that a mid-batch crash never leaves
    # partial results in mastered/.  Files move atomically after all
    # tracks succeed; staging is cleaned up on any failure path.
    staging_dir = audio_dir / ".mastering_staging"
    if staging_dir.exists():
        import shutil as _shutil
        _shutil.rmtree(staging_dir)
    staging_dir.mkdir()

    # Look up per-track metadata for fade_out values
    state = _shared.cache.get_state() or {}
    album_tracks = (state.get("albums", {})
                         .get(_normalize_slug(album_slug), {})
                         .get("tracks", {}))

    try:
        master_results = []
        for wav_file in wav_files:
            output_path = staging_dir / wav_file.name

            # Derive track slug from WAV filename and look up fade_out
            track_stem = wav_file.stem
            track_slug = _normalize_slug(track_stem)
            track_meta = album_tracks.get(track_slug, {})
            fade_out_val = track_meta.get("fade_out")

            def _do_master(
                in_path: Path,
                out_path: Path,
                lufs: float,
                ceil: float,
                fade: float | None,
                comp: float,
                p: dict[str, Any],
            ) -> dict[str, Any]:
                return _master_track(
                    str(in_path), str(out_path),
                    target_lufs=lufs,
                    eq_settings=None,  # built from preset inside master_track
                    ceiling_db=ceil,
                    fade_out=fade,
                    compress_ratio=comp,
                    preset=p,
                )

            result = await loop.run_in_executor(
                None, _do_master, wav_file, output_path,
                effective_lufs, effective_ceiling, fade_out_val,
                effective_compress, effective_preset,
            )
            if result and not result.get("skipped"):
                result["filename"] = wav_file.name
                master_results.append(result)
    except Exception:
        if staging_dir.exists():
            import shutil as _shutil
            _shutil.rmtree(staging_dir)
        raise

    if not master_results:
        if staging_dir.exists():
            import shutil as _shutil
            _shutil.rmtree(staging_dir)
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

    # All tracks mastered successfully — move staging files to final output_dir
    output_dir.mkdir(exist_ok=True)
    for staged_file in staging_dir.iterdir():
        os.replace(str(staged_file), str(output_dir / staged_file.name))
    staging_dir.rmdir()

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
        if r["peak_db"] > effective_ceiling:
            issues.append(
                f"Peak {r['peak_db']:.1f} dB exceeds ceiling {effective_ceiling} dB"
            )
        if issues:
            out_of_spec.append({"filename": r["filename"], "issues": issues})

    album_range_fail = verify_range >= 1.0
    auto_recovered: list[dict[str, Any]] = []

    if out_of_spec or album_range_fail:
        # --- Auto-recovery: fix recoverable dynamic range issues ---
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
            peak_at_ceiling = vr["peak_db"] >= effective_ceiling - 0.1
            if lufs_too_low and peak_at_ceiling and not has_peak_issue:
                recoverable.append(spec["filename"])

        if recoverable:
            from tools.mastering.fix_dynamic_track import fix_dynamic

            # Recovery writes at source rate (fix_dynamic is a rescue path
            # that doesn't resample) but honors the configured output bit
            # depth from targets["output_bits"].
            recovery_subtype = (
                "PCM_24" if targets["output_bits"] > 16 else "PCM_16"
            )

            auto_recovered = []
            for fname in recoverable:
                raw_path = source_dir / fname
                if not raw_path.exists():
                    raw_path = _find_wav_source_dir(audio_dir) / fname
                if not raw_path.exists():
                    continue

                def _do_recovery(
                    src: Path,
                    dst: Path,
                    lufs: float,
                    eq: list[tuple[float, float, float]],
                    ceil: float,
                    subtype: str,
                ) -> dict[str, Any]:
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
                    sf.write(str(dst), data, rate, subtype=subtype)
                    return metrics

                mastered_path = output_dir / fname
                metrics = await loop.run_in_executor(
                    None, _do_recovery, raw_path, mastered_path,
                    effective_lufs, eq_settings, effective_ceiling,
                    recovery_subtype,
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
                    if r["peak_db"] > effective_ceiling:
                        issues.append(
                            f"Peak {r['peak_db']:.1f} dB exceeds ceiling {effective_ceiling} dB"
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

    # --- Stage 5.5: Mastering samples (codec preview + mono fold-down QC) ---
    # Issue #296. Writes .aac.m4a and .MONO_FOLD.md sidecars to the
    # mastering_samples/ sibling directory so mastered/ stays WAV-only. A
    # mono-fold hard-fail short-circuits the pipeline; codec preview never blocks.
    from tools.mastering.master_tracks import GENRE_PRESETS, _PRESET_DEFAULTS

    if genre and genre.lower() in GENRE_PRESETS:
        sample_cfg: dict[str, Any] = dict(GENRE_PRESETS[genre.lower()])
    else:
        sample_cfg = dict(_PRESET_DEFAULTS)

    codec_enabled = bool(int(sample_cfg.get("codec_preview_enabled", 1)))
    codec_bitrate = int(sample_cfg.get("codec_preview_bitrate_kbps", 128))
    monofold_enabled = bool(int(sample_cfg.get("mono_fold_enabled", 1)))
    monofold_write_audio = bool(int(sample_cfg.get("mono_fold_write_audio", 1)))
    monofold_thresholds = {
        "band_drop_fail_db": float(sample_cfg.get("mono_fold_band_drop_fail_db", 6.0)),
        "lufs_warn_db": float(sample_cfg.get("mono_fold_lufs_warn_db", 3.0)),
        "vocal_warn_db": float(sample_cfg.get("mono_fold_vocal_warn_db", 2.0)),
        "correlation_warn": float(sample_cfg.get("mono_fold_correlation_warn", 0.3)),
    }

    samples_dir = audio_dir / "mastering_samples"
    samples_stage: dict[str, Any] = {
        "status": "pass",
        "codec_preview_enabled": codec_enabled,
        "mono_fold_enabled": monofold_enabled,
        "output_dir": str(samples_dir),
    }

    if codec_enabled or monofold_enabled:
        samples_dir.mkdir(exist_ok=True)

    # Codec preview — never blocks
    if codec_enabled:
        from tools.mastering.codec_preview import (
            CodecPreviewError,
            render_aac_preview,
        )

        codec_results: list[dict[str, Any]] = []
        codec_errors: list[str] = []
        for wav in mastered_files:
            out_path = samples_dir / f"{wav.stem}.aac.m4a"
            try:
                info = await loop.run_in_executor(
                    None, render_aac_preview, wav, out_path, codec_bitrate
                )
                codec_results.append({
                    "track": wav.name,
                    "output_path": info["output_path"],
                    "bitrate_kbps": info["bitrate_kbps"],
                })
            except CodecPreviewError as e:
                codec_errors.append(f"{wav.name}: {e}")
                warnings.append(f"Codec preview {wav.name}: {e}")

        samples_stage["codec_previews"] = codec_results
        if codec_errors:
            samples_stage["codec_errors"] = codec_errors

    # Mono fold-down QC — hard-fails the pipeline on band drop
    if monofold_enabled:
        import soundfile as sf
        from tools.mastering.mono_fold import mono_fold_metrics
        from tools.mastering.mono_fold_report import render_mono_fold_markdown

        def _do_mono_fold(wav_path: Path) -> dict[str, Any]:
            data, rate = sf.read(str(wav_path))
            import numpy as _np
            if data.ndim == 1:
                data = _np.column_stack([data, data])
            metrics = mono_fold_metrics(data, rate, thresholds=monofold_thresholds)

            stem = wav_path.stem
            sample_filename = f"{stem}.mono.wav" if monofold_write_audio else None
            if sample_filename:
                sf.write(str(samples_dir / sample_filename), metrics["mono_audio"], rate, subtype="PCM_24")

            md = render_mono_fold_markdown(stem, metrics, sample_filename)
            (samples_dir / f"{stem}.MONO_FOLD.md").write_text(md, encoding="utf-8")

            return {
                "track": wav_path.name,
                "verdict": metrics["verdict"],
                "band_drop_fail": metrics["band_drop_fail"],
                "worst_band": metrics["worst_band"],
                "lufs_delta_db": metrics["lufs"]["delta_db"],
                "vocal_delta_db": metrics["vocal_rms"]["delta_db"],
                "stereo_correlation": metrics["stereo_correlation"],
                "report_path": str(samples_dir / f"{stem}.MONO_FOLD.md"),
            }

        mono_results = []
        for wav in mastered_files:
            mono_results.append(await loop.run_in_executor(None, _do_mono_fold, wav))

        mono_passed = sum(1 for r in mono_results if r["verdict"] == "PASS")
        mono_warned = sum(1 for r in mono_results if r["verdict"] == "WARN")
        mono_failed = sum(1 for r in mono_results if r["verdict"] == "FAIL")

        for r in mono_results:
            if r["verdict"] == "WARN":
                warnings.append(
                    f"Mono fold {r['track']}: WARN — see {Path(r['report_path']).name}"
                )

        samples_stage["mono_fold"] = {
            "tracks": mono_results,
            "passed": mono_passed,
            "warned": mono_warned,
            "failed": mono_failed,
        }

        if mono_failed > 0:
            failed_tracks = [r for r in mono_results if r["verdict"] == "FAIL"]
            samples_stage["status"] = "fail"
            stages["mastering_samples"] = samples_stage
            return _safe_json({
                "album_slug": album_slug,
                "stage_reached": "mastering_samples",
                "stages": stages,
                "settings": settings,
                "warnings": warnings,
                "failed_stage": "mastering_samples",
                "failure_detail": {
                    "reason": "Mono fold-down hard-fail (phase cancellation)",
                    "tracks_failed": [r["track"] for r in failed_tracks],
                    "details": [
                        {
                            "track": r["track"],
                            "worst_band": r["worst_band"],
                            "report": r["report_path"],
                        }
                        for r in failed_tracks
                    ],
                },
            })

    stages["mastering_samples"] = samples_stage

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

    # --- Stage 6.5: Archival (opt-in) ---
    # When mastering.archival_enabled is true, write a 32-bit float copy
    # of each mastered track to archival/. This is a bit-depth-expanded
    # copy of the delivery master (not a separate render), intended for
    # re-mastering without re-polishing stems.
    if targets.get("archival_enabled"):
        import soundfile as _sf_archival

        archival_dir = audio_dir / "archival"
        archival_dir.mkdir(exist_ok=True)
        archived = 0
        archive_errors: list[str] = []
        for mastered_path in mastered_files:
            arch_path = archival_dir / mastered_path.name
            try:
                data, rate = _sf_archival.read(str(mastered_path), dtype="float32")
                _sf_archival.write(str(arch_path), data, rate, subtype="FLOAT")
                archived += 1
            except Exception as exc:  # pragma: no cover - filesystem error path
                archive_errors.append(f"{mastered_path.name}: {exc}")

        stages["archival"] = {
            "status": "pass" if not archive_errors else "warn",
            "count": archived,
            "output_dir": str(archival_dir),
            "errors": archive_errors or None,
        }

    # --- Stage 7: Update statuses ---
    state = _shared.cache.get_state_ref()
    albums = state.get("albums", {})
    normalized_album = _normalize_slug(album_slug)
    album_data = albums.get(normalized_album)

    tracks_updated = 0
    status_errors: list[str] = []
    album_status: str | None = None

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

    # Build runtime notices (caveats worth surfacing to the user).
    notices: list[str] = []
    if targets.get("upsampled_from_source"):
        src_rate = targets.get("source_sample_rate") or 0
        dst_rate = targets["output_sample_rate"]
        notices.append(
            f"Delivery at {dst_rate // 1000} kHz "
            f"(upsampled from {src_rate / 1000:.1f} kHz source). "
            f"Badge-eligible for Apple Hi-Res Lossless and Tidal Max — "
            f"no additional audio information vs. source."
        )

    return _safe_json({
        "album_slug": album_slug,
        "stage_reached": "complete",
        "stages": stages,
        "settings": settings,
        "warnings": warnings,
        "notices": notices,
        "failed_stage": None,
        "failure_detail": None,
    })


async def render_codec_preview(
    album_slug: str,
    subfolder: str = "mastered",
    bitrate_kbps: int = 128,
) -> str:
    """Render a 128 kbps AAC preview of each mastered track.

    The `.aac.m4a` files are written to `mastering_samples/` next to
    (never inside) `mastered/`, so streaming uploads stay WAV-only. The
    previews exist so the operator can audition how the album sounds over
    Bluetooth before release (issue #296).

    Args:
        album_slug: Album slug (e.g., "my-album")
        subfolder: Source subfolder relative to the audio dir (default "mastered")
        bitrate_kbps: AAC bitrate in kbps (default 128)

    Returns:
        JSON with per-track preview info and a summary.
    """
    err, audio_dir = _helpers._resolve_audio_dir(album_slug)
    if err:
        return err
    assert audio_dir is not None

    source_dir = audio_dir / subfolder
    if not source_dir.is_dir():
        return _safe_json({
            "error": f"Source subfolder not found: {source_dir}",
            "hint": "Run master_audio or master_album first to populate mastered/.",
        })

    wav_files = sorted(
        f for f in source_dir.iterdir()
        if f.suffix.lower() == ".wav" and "venv" not in str(f)
    )
    if not wav_files:
        return _safe_json({"error": f"No WAV files in {source_dir}"})

    from tools.mastering.codec_preview import CodecPreviewError, render_aac_preview

    output_dir = audio_dir / "mastering_samples"
    output_dir.mkdir(exist_ok=True)

    loop = asyncio.get_running_loop()
    previews: list[dict[str, Any]] = []
    errors: list[str] = []

    for wav in wav_files:
        out_path = output_dir / f"{wav.stem}.aac.m4a"
        try:
            info = await loop.run_in_executor(
                None, render_aac_preview, wav, out_path, bitrate_kbps
            )
            previews.append({
                "input": wav.name,
                "output_path": info["output_path"],
                "bitrate_kbps": info["bitrate_kbps"],
                "output_bytes": info["output_bytes"],
            })
        except CodecPreviewError as e:
            errors.append(f"{wav.name}: {e}")

    if not previews and errors:
        return _safe_json({"error": "All previews failed", "details": errors})

    return _safe_json({
        "previews": previews,
        "summary": {
            "count": len(previews),
            "total_bytes": sum(p["output_bytes"] for p in previews),
            "output_dir": str(output_dir),
            "errors": errors or None,
        },
    })


async def mono_fold_check(
    album_slug: str,
    subfolder: str = "mastered",
    write_audio: bool = True,
) -> str:
    """Run the mono fold-down QC gate on every mastered track.

    For each WAV in `{audio_dir}/mastered/`, sum stereo to mono, measure
    per-band deltas, LUFS delta, vocal-band RMS delta, and stereo correlation,
    then write a `{track}.MONO_FOLD.md` report (and optionally a
    `{track}.mono.wav` listenable sample) to `mastering_samples/`. See
    issue #296.

    Args:
        album_slug: Album slug.
        subfolder: Source subfolder relative to the audio dir (default "mastered")
        write_audio: If True (default), write a .mono.wav sibling sample so
            the operator can audition cancellation on a phone speaker.

    Returns:
        JSON with per-track deltas, the offending band on any FAIL, and a
        summary verdict.
    """
    dep_err = _helpers._check_mastering_deps()
    if dep_err:
        return _safe_json({"error": dep_err})

    err, audio_dir = _helpers._resolve_audio_dir(album_slug)
    if err:
        return err
    assert audio_dir is not None

    source_dir = audio_dir / subfolder
    if not source_dir.is_dir():
        return _safe_json({
            "error": f"Source subfolder not found: {source_dir}",
            "hint": "Run master_audio or master_album first to populate mastered/.",
        })

    wav_files = sorted(
        f for f in source_dir.iterdir()
        if f.suffix.lower() == ".wav" and "venv" not in str(f)
    )
    if not wav_files:
        return _safe_json({"error": f"No WAV files in {source_dir}"})

    import soundfile as sf
    from tools.mastering.mono_fold import mono_fold_metrics
    from tools.mastering.mono_fold_report import render_mono_fold_markdown

    output_dir = audio_dir / "mastering_samples"
    output_dir.mkdir(exist_ok=True)

    loop = asyncio.get_running_loop()

    def _analyze(wav_path: Path) -> dict[str, Any]:
        data, rate = sf.read(str(wav_path))
        import numpy as _np
        if data.ndim == 1:
            data = _np.column_stack([data, data])
        metrics = mono_fold_metrics(data, rate)

        stem = wav_path.stem
        sample_filename: str | None = None
        if write_audio:
            sample_filename = f"{stem}.mono.wav"
            mono = metrics["mono_audio"]
            sf.write(str(output_dir / sample_filename), mono, rate, subtype="PCM_24")

        md = render_mono_fold_markdown(stem, metrics, sample_filename)
        (output_dir / f"{stem}.MONO_FOLD.md").write_text(md, encoding="utf-8")

        return {
            "track": wav_path.name,
            "verdict": metrics["verdict"],
            "band_drop_fail": metrics["band_drop_fail"],
            "worst_band": metrics["worst_band"],
            "lufs_delta_db": metrics["lufs"]["delta_db"],
            "vocal_delta_db": metrics["vocal_rms"]["delta_db"],
            "stereo_correlation": metrics["stereo_correlation"],
            "report_path": str(output_dir / f"{stem}.MONO_FOLD.md"),
            "sample_path": str(output_dir / sample_filename) if sample_filename else None,
        }

    tracks: list[dict[str, Any]] = []
    for wav in wav_files:
        tracks.append(await loop.run_in_executor(None, _analyze, wav))

    passed = sum(1 for t in tracks if t["verdict"] == "PASS")
    warned = sum(1 for t in tracks if t["verdict"] == "WARN")
    failed = sum(1 for t in tracks if t["verdict"] == "FAIL")

    if failed > 0:
        verdict = "FAIL"
    elif warned > 0:
        verdict = "WARN"
    else:
        verdict = "PASS"

    return _safe_json({
        "tracks": tracks,
        "summary": {
            "count": len(tracks),
            "passed": passed,
            "warned": warned,
            "failed": failed,
            "output_dir": str(output_dir),
        },
        "verdict": verdict,
    })


async def prune_archival(album_slug: str, keep: int = 3) -> str:
    """Prune the album's archival/ directory, keeping the N newest files.

    The archival/ directory holds 32-bit float pre-downconvert masters
    written by master_album when mastering.archival_enabled is true.
    Each re-master adds new files; this tool lets users cap disk usage
    by pruning older entries by modification time.

    Args:
        album_slug: Album slug (e.g., "my-album").
        keep: Number of most-recent files to keep (by mtime). Default: 3.
            0 removes everything. Negative values are treated as 0.

    Returns:
        JSON with {"kept": [names...], "removed": [names...]}. Includes
        "note" when the archival directory is absent.
    """
    err, audio_dir = _helpers._resolve_audio_dir(album_slug)
    if err:
        return err
    assert audio_dir is not None

    archival_dir = audio_dir / "archival"
    if not archival_dir.is_dir():
        return _safe_json({
            "kept": [],
            "removed": [],
            "note": "no archival directory",
        })

    files = sorted(
        (f for f in archival_dir.iterdir() if f.is_file()),
        key=lambda f: f.stat().st_mtime,
    )

    if keep < 0:
        keep = 0
    if keep >= len(files):
        return _safe_json({
            "kept": [f.name for f in files],
            "removed": [],
        })

    to_remove = files if keep == 0 else files[: len(files) - keep]
    to_keep = [] if keep == 0 else files[len(files) - keep:]

    removed_names: list[str] = []
    for f in to_remove:
        try:
            f.unlink()
            removed_names.append(f.name)
        except OSError as exc:  # pragma: no cover - filesystem edge case
            logger.warning("prune_archival: could not remove %s: %s", f, exc)

    return _safe_json({
        "kept": [f.name for f in to_keep],
        "removed": removed_names,
    })


def register(mcp: Any) -> None:
    """Register audio mastering tools."""
    mcp.tool()(analyze_audio)
    mcp.tool()(qc_audio)
    mcp.tool()(master_audio)
    mcp.tool()(fix_dynamic_track)
    mcp.tool()(master_with_reference)
    mcp.tool()(master_album)
    mcp.tool()(render_codec_preview)
    mcp.tool()(mono_fold_check)
    mcp.tool()(prune_archival)
