"""Mix polish tools — per-stem audio cleanup before mastering."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from handlers._shared import _find_wav_source_dir, _safe_json
from handlers.processing import _helpers

logger = logging.getLogger("bitwize-music-state")


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
    dep_err = _helpers._check_mixing_deps()
    if dep_err:
        return _safe_json({"error": dep_err})

    err, audio_dir = _helpers._resolve_audio_dir(album_slug)
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
    dep_err = _helpers._check_mixing_deps()
    if dep_err:
        return _safe_json({"error": dep_err})

    err, audio_dir = _helpers._resolve_audio_dir(album_slug)
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
    dep_err = _helpers._check_mixing_deps()
    if dep_err:
        return _safe_json({
            "album_slug": album_slug,
            "stage_reached": "pre_flight",
            "failed_stage": "pre_flight",
            "failure_detail": {"reason": dep_err},
        })

    err, audio_dir = _helpers._resolve_audio_dir(album_slug)
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


def register(mcp: Any) -> None:
    """Register mix polish tools."""
    mcp.tool()(polish_audio)
    mcp.tool()(analyze_mix_issues)
    mcp.tool()(polish_album)
