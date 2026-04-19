"""Audio mastering and analysis tools."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from collections.abc import Awaitable, Callable
from typing import Any

# Progress log filename written at the album's audio_dir. Operators
# running long master_album calls (up to 30+ min with ADM enabled) can
# `tail -f` this during the run to see stage-level progress without
# waiting for the MCP tool call to return. Also survives crashes /
# MCP client disconnects so the forensics are on disk.
_PROGRESS_LOG_FILENAME = "MASTERING_PROGRESS.log"

from handlers import _shared
from handlers._shared import (
    _find_wav_source_dir,
    _is_path_confined,
    _normalize_slug,
    # _resolve_audio_dir accessed via _helpers for patch compatibility
    _safe_json,
)
from handlers.processing import _helpers
from handlers.processing import _album_stages
from tools.mastering.ceiling_guard import (
    compute_overshoots as _ceiling_guard_compute_overshoots,
)

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
    freeze_signature: bool = False,
    new_anchor: bool = False,
) -> str:
    """End-to-end mastering pipeline: analyze, QC, master, verify, update status.

    Runs in three phases, stopping on failure. See _album_stages.py for
    per-stage implementation. Stage order mirrors the #290 pipeline spec.

    **Expected duration:**
      - 3-5 min per track without ADM (ADM disabled by default).
      - +10-12 min per ADM retry cycle when ADM is enabled
        (`mastering.adm_validation_enabled: true`). Up to 5 cycles on
        pathological content → 30-60 min total for a 10-track album.

    MCP clients with per-tool-call timeouts should either raise the
    timeout for this tool, or disable ADM for routine runs and only
    enable when preparing for ADM / Apple Hi-Res Lossless submission.

    **Progress visibility:** stage-level progress is written to
    ``{audio_dir}/MASTERING_PROGRESS.log`` as it runs. Operators can
    ``tail -f`` that file during a long call to see which stage is
    active; the file also survives MCP disconnects for forensic use.

    Phase 1 (pre-loop): pre_flight → analysis → freeze_decision →
        anchor_selection → pre_qc  (run once)

    Phase 2 (ADM loop, max 1 or 5 cycles): mastering → verification →
        coherence_check → coherence_correct → ceiling_guard →
        adm_validation.  When ADM is enabled, inter-sample clip
        failures trigger adaptive ceiling tightening (slope-aware from
        cycle 2 onward). The loop halts early on divergence (slope ≤
        0) or ceiling floor (-6 dBTP), falling through to a
        warn-fallback so the album always completes.

    Phase 3 (post-loop): mastering_samples → post_qc → archival →
        metadata → layout → signature_persist → status_update  (run once)
    """
    if freeze_signature and new_anchor:
        return _safe_json({
            "album_slug": album_slug,
            "stage_reached": "pre_flight",
            "stages": {"pre_flight": {
                "status": "fail",
                "detail": "freeze_signature and new_anchor are mutually exclusive",
            }},
            "failed_stage": "pre_flight",
            "failure_detail": {
                "reason": "freeze_signature and new_anchor are mutually exclusive",
            },
        })

    loop = asyncio.get_running_loop()
    ctx = _album_stages.MasterAlbumCtx(
        album_slug=album_slug, genre=genre,
        target_lufs=target_lufs, ceiling_db=ceiling_db,
        cut_highmid=cut_highmid, cut_highs=cut_highs,
        source_subfolder=source_subfolder,
        freeze_signature=freeze_signature, new_anchor=new_anchor,
        loop=loop,
    )

    async def _ceiling_guard(c: _album_stages.MasterAlbumCtx) -> str | None:
        return await _album_stages._stage_ceiling_guard(
            c, _compute_overshoots=_ceiling_guard_compute_overshoots,
        )

    def _inject_notices_and_return(result: str) -> str:
        """Inject runtime notices into halt JSON on early exit."""
        _album_stages._build_notices(ctx)
        try:
            _d = json.loads(result)
            _d.setdefault("notices", ctx.notices)
            result = json.dumps(_d)
        except json.JSONDecodeError as exc:
            logger.warning(
                "master_album: halt result is not valid JSON, "
                "notices not injected: %s", exc,
            )
        return result

    # Explicit list type keeps mypy from narrowing stage_fn's type to the
    # first element's concrete function identity — the ADM-loop list below
    # mixes _stage_* with the local _ceiling_guard wrapper.
    _StageFn = Callable[[_album_stages.MasterAlbumCtx], Awaitable[str | None]]

    # ── Progress log sidecar ─────────────────────────────────────────────
    # Appends stage-boundary events to MASTERING_PROGRESS.log at the
    # album's audio_dir. `ctx.audio_dir` is only populated after
    # _stage_pre_flight runs, so pre_flight's own events are buffered
    # and flushed once the dir resolves.
    _progress_buffer: list[str] = []
    _progress_run_header_written = [False]

    def _progress_log_stage(
        stage_label: str, event: str,
        elapsed_ms: float | None = None,
        *, extra: str | None = None,
    ) -> None:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        parts = [ts, event, stage_label]
        if elapsed_ms is not None:
            parts.append(f"{elapsed_ms:.0f}ms")
        if ctx.adm_cycle > 0:
            parts.append(f"adm_cycle={ctx.adm_cycle}")
        if extra:
            parts.append(extra)
        line = " | ".join(parts)
        # Buffer until audio_dir is resolved, then flush.
        if ctx.audio_dir is None:
            _progress_buffer.append(line)
            return
        log_path = ctx.audio_dir / _PROGRESS_LOG_FILENAME
        try:
            # First write of this run starts with a RUN_START header so
            # `tail -f` viewers can visually separate runs. Use append
            # mode so cross-run history is preserved for forensics.
            with open(log_path, "a", encoding="utf-8") as f:
                if not _progress_run_header_written[0]:
                    f.write(
                        f"=== RUN START @ {ts} | album={ctx.album_slug} | "
                        f"genre={ctx.genre or '-'} ===\n"
                    )
                    _progress_run_header_written[0] = True
                    # Flush any pre-audio_dir buffered events.
                    for buffered in _progress_buffer:
                        f.write(buffered + "\n")
                    _progress_buffer.clear()
                f.write(line + "\n")
        except OSError as exc:
            # Never fail the pipeline on log-write errors.
            logger.warning("master_album: progress log write failed: %s", exc)

    def _stage_label(stage_fn: _StageFn) -> str:
        name = getattr(stage_fn, "__name__", "") or "unknown"
        return name.removeprefix("_stage_")

    async def _run_stage(stage_fn: _StageFn) -> str | None:
        label = _stage_label(stage_fn)
        _progress_log_stage(label, "ENTER")
        t0 = time.monotonic()
        try:
            stage_result = await stage_fn(ctx)
        except Exception as exc:
            elapsed_ms = (time.monotonic() - t0) * 1000
            _progress_log_stage(
                label, "ERROR", elapsed_ms=elapsed_ms,
                extra=f"exc={type(exc).__name__}",
            )
            raise
        elapsed_ms = (time.monotonic() - t0) * 1000
        event = "HALT" if stage_result else "EXIT"
        _progress_log_stage(label, event, elapsed_ms=elapsed_ms)
        return stage_result

    # ── Phase 1: pre-loop stages (run once) ──────────────────────────────
    pre_loop_stages: list[_StageFn] = [
        _album_stages._stage_pre_flight,
        _album_stages._stage_analysis,
        _album_stages._stage_freeze_decision,
        _album_stages._stage_anchor_selection,
        _album_stages._stage_pre_qc,
    ]
    for stage_fn in pre_loop_stages:
        if result := await _run_stage(stage_fn):
            return _inject_notices_and_return(result)

    # ── Phase 2: ADM loop (adaptive ceiling, max 3 cycles) ────────────────
    # Convergence: fixed 0.5 dB steps failed on dense-transient content
    # because AAC ripple only drops ~0.47 dB per 0.5 dB of ceiling — the
    # loop would exhaust its budget with overshoot still present. Adaptive
    # tightening uses the observed worst decoded peak to pick the next
    # ceiling in one shot, then backs that with a hard floor and a
    # warn-fallback so any album can complete without halting.
    #
    # ADM validation is OPT-IN via `mastering.adm_validation_enabled: true`
    # (default false) because each cycle re-masters every track and the
    # AAC encode/decode adds ~10-12 min per cycle on a 10-track album.
    # Most albums don't need the ADM loop; reserve it for Apple Hi-Res
    # Lossless / ADM submission prep.
    adm_enabled = bool(ctx.targets.get("adm_validation_enabled", False))
    # Bumped 3 → 5: dense-transient electronic content needs more cycles
    # because AAC ripple shrinks only ~0.6 dB per 1 dB of ceiling tighten,
    # not 1:1. Combined with slope-aware tightening below, 5 cycles
    # converges any album that isn't structurally divergent.
    _ADM_MAX_CYCLES = 5 if adm_enabled else 1
    _ADM_MIN_CEILING_DB = -6.0              # never tighten below this
    _ADM_SAFETY_DB = 0.3                    # extra headroom below observed peak
    _ADM_MIN_TIGHTEN_DB = 0.5               # preserves legacy step as floor
    _ADM_MIN_EFFECTIVE_RATIO = 0.4          # floor on slope efficacy
    adm_loop_stages: list[_StageFn] = [
        _album_stages._stage_mastering,
        _album_stages._stage_verification,
        _album_stages._stage_coherence_check,
        _album_stages._stage_coherence_correct,
        _ceiling_guard,
    ]
    if adm_enabled:
        adm_loop_stages.append(_album_stages._stage_adm_validation)
    else:
        ctx.stages["adm_validation"] = {
            "status": "skipped",
            "reason": "disabled_by_config",
        }
        ctx.notices.append(
            "ADM validation skipped — enable with "
            "`mastering.adm_validation_enabled: true` in config.yaml "
            "when preparing for Apple Hi-Res Lossless / ADM submission "
            "(adds ~10-12 min per cycle on a 10-track album)."
        )

    # Per-cycle (ceiling, worst_peak) observations. Used to estimate the
    # actual AAC-ripple-to-ceiling slope and pick a convergent tighten,
    # and to detect divergence (slope ≤ 0) where tightening the limiter
    # drives it harder and actually grows inter-sample ripple.
    adm_history: list[dict[str, float]] = []

    def _adm_adaptive_ceiling(
        failure_detail: dict[str, Any], current: float,
    ) -> tuple[float, bool, bool]:
        """Compute next ceiling from observed worst decoded peak + history.

        Returns ``(new_ceiling, hit_floor, diverging)``.

        - With no history yet: assumes 1:1 ripple-to-ceiling scaling
          (legacy formula).
        - With ≥2 history points: fits a slope from the last two cycles
          and scales the tighten by ``1/effective_ratio``, so material
          with a 0.6:1 ripple scaling gets a ~1.67× larger tighten than
          the legacy formula would apply.
        - When slope ≤ 0 (ripple growing as we tighten): flags
          ``diverging=True`` so the caller falls through to warn-fallback
          instead of looping forever with worsening decoded peaks.

        Clamped to ``_ADM_MIN_CEILING_DB``; ``hit_floor=True`` when the
        proposed ceiling would go below the floor.
        """
        tracks = failure_detail.get("tracks_with_clips") or []
        peaks = [
            float(t["peak_db_decoded"])
            for t in tracks if t.get("peak_db_decoded") is not None
        ]
        if not peaks:
            proposed = current - _ADM_MIN_TIGHTEN_DB
            floored = proposed < _ADM_MIN_CEILING_DB
            return (max(proposed, _ADM_MIN_CEILING_DB), floored, False)

        worst_peak = max(peaks)
        overshoot = worst_peak - current
        adm_history.append({"ceiling": current, "worst_peak": worst_peak})

        if len(adm_history) >= 2:
            prev, curr = adm_history[-2], adm_history[-1]
            # d_ceiling > 0 when we tightened between cycles; d_peak > 0
            # when the decoded peak dropped as a result.
            d_ceiling = prev["ceiling"] - curr["ceiling"]
            d_peak = prev["worst_peak"] - curr["worst_peak"]
            if d_ceiling > 1e-3:
                slope = d_peak / d_ceiling
                if slope <= 0:
                    # Ripple grew (or held) despite tightening — the
                    # limiter is contributing more inter-sample content
                    # than we're gaining headroom. Not convergent.
                    return (current, True, True)
                effective_ratio = max(slope, _ADM_MIN_EFFECTIVE_RATIO)
                tighten = (overshoot + _ADM_SAFETY_DB) / effective_ratio
                tighten = max(tighten, _ADM_MIN_TIGHTEN_DB)
            else:
                tighten = max(
                    overshoot + _ADM_SAFETY_DB, _ADM_MIN_TIGHTEN_DB,
                )
        else:
            # First retry — no slope yet, assume 1:1 scaling.
            tighten = max(
                overshoot + _ADM_SAFETY_DB, _ADM_MIN_TIGHTEN_DB,
            )

        proposed = current - tighten
        floored = proposed < _ADM_MIN_CEILING_DB
        return (max(proposed, _ADM_MIN_CEILING_DB), floored, False)

    adm_clip_failure_persisted = False
    adm_last_failure_detail: dict[str, Any] = {}
    adm_diverging = False

    for adm_cycle in range(_ADM_MAX_CYCLES):
        ctx.adm_cycle = adm_cycle
        adm_retry = False

        for stage_fn in adm_loop_stages:
            if result := await _run_stage(stage_fn):
                try:
                    _d = json.loads(result)
                except json.JSONDecodeError:
                    _d = {}
                is_adm_clip_failure = (
                    _d.get("failed_stage") == "adm_validation"
                    and _d.get("failure_detail", {}).get("clips_retry_eligible")
                )
                if is_adm_clip_failure:
                    adm_last_failure_detail = _d.get("failure_detail") or {}
                    if adm_cycle < _ADM_MAX_CYCLES - 1:
                        new_ceiling, hit_floor, diverging = (
                            _adm_adaptive_ceiling(
                                adm_last_failure_detail,
                                ctx.effective_ceiling,
                            )
                        )
                        if diverging:
                            # Ripple grew with tightening — any further
                            # tightening makes it worse. Bail to warn.
                            adm_diverging = True
                            adm_clip_failure_persisted = True
                            ctx.notices.append(
                                f"ADM cycle {adm_cycle + 1}: decoded peak "
                                f"grew despite ceiling tightening (slope "
                                f"≤ 0 between last two cycles). Material "
                                f"not convergent at current limiter "
                                f"settings — falling through to "
                                f"warn-fallback."
                            )
                            break
                        # If the adaptive pass can't move the ceiling any
                        # further (already at floor from a previous cycle)
                        # then another retry would just repeat the same
                        # re-master. Fall through to warn-fallback.
                        if new_ceiling >= ctx.effective_ceiling:
                            adm_clip_failure_persisted = True
                            break
                        ctx.effective_ceiling = new_ceiling
                        # Propagate the tightened ceiling everywhere the
                        # ADM stage and downstream consumers read it.
                        ctx.targets["ceiling_db"] = ctx.effective_ceiling
                        if isinstance(ctx.effective_preset, dict):
                            ctx.effective_preset["true_peak_ceiling"] = (
                                ctx.effective_ceiling
                            )
                        floor_note = " (floor reached)" if hit_floor else ""
                        ctx.notices.append(
                            f"ADM cycle {adm_cycle + 1}: inter-sample clips "
                            f"detected, tightening ceiling to "
                            f"{ctx.effective_ceiling:.2f} dBTP{floor_note} "
                            f"and re-mastering."
                        )
                        adm_retry = True
                        break
                    # Last cycle with clips → warn-fallback, don't halt.
                    adm_clip_failure_persisted = True
                    break
                # Non-ADM / non-retryable halt
                return _inject_notices_and_return(result)

        if adm_retry:
            continue
        break  # ADM passed, or warn-fallback break

    # Warn-fallback: ADM clips persist after all retries or at floor. The
    # album still finishes — operators get a flagged deliverable and the
    # ADM_VALIDATION.md sidecar with per-track peak data so they can make
    # the manual call on whether to republish.
    if adm_clip_failure_persisted:
        stage = ctx.stages.get("adm_validation")
        reason_suffix = (
            "; ripple growing with tightening (divergent)"
            if adm_diverging else ""
        )
        if isinstance(stage, dict):
            stage["status"] = "warn"
            stage["reason"] = (
                f"inter-sample clips persist at ceiling "
                f"{ctx.effective_ceiling:.2f} dBTP after "
                f"{_ADM_MAX_CYCLES} cycle(s); floor is "
                f"{_ADM_MIN_CEILING_DB:.1f} dBTP{reason_suffix}"
            )
            stage["clip_failure_persisted"] = True
            stage["diverging"] = adm_diverging
            stage["adm_history"] = list(adm_history)
        tracks_with_clips = adm_last_failure_detail.get("tracks_with_clips") or []
        clip_count = len(tracks_with_clips)
        ctx.warnings.append(
            f"ADM validation: {clip_count} track(s) retain inter-sample "
            f"clips after {_ADM_MAX_CYCLES} retry cycles (final ceiling "
            f"{ctx.effective_ceiling:.2f} dBTP, floor "
            f"{_ADM_MIN_CEILING_DB:.1f} dBTP). Album delivered with flag — "
            f"see ADM_VALIDATION.md for per-track detail."
        )
        # Terminal notice so operators reading the notice stream see the
        # final state immediately, without having to scan warnings. The
        # existing per-cycle tightening notices only cover cycles that
        # triggered a retry — this one names the exit condition.
        ctx.notices.append(
            f"ADM loop terminated without convergence after "
            f"{_ADM_MAX_CYCLES} cycle(s). Final ceiling: "
            f"{ctx.effective_ceiling:.2f} dBTP. Delivered with "
            f"{clip_count} track(s) flagged for inter-sample clips — "
            "inspect ADM_VALIDATION.md before republishing if AAC "
            "delivery matters."
        )

    # ── Phase 3: post-loop stages (run once) ─────────────────────────────
    post_loop_stages: list[_StageFn] = [
        _album_stages._stage_mastering_samples,
        _album_stages._stage_post_qc,
        _album_stages._stage_archival,
        _album_stages._stage_metadata,
        _album_stages._stage_layout,
        # signature_persist runs BEFORE status_update so the album never
        # advances to "Complete" without ALBUM_SIGNATURE.yaml on disk —
        # otherwise a release-without-re-master would halt the next master
        # at freeze_decision (Released + missing signature).
        _album_stages._stage_signature_persist,
        _album_stages._stage_status_update,
    ]
    for stage_fn in post_loop_stages:
        if result := await _run_stage(stage_fn):
            return _inject_notices_and_return(result)

    _progress_log_stage("pipeline", "COMPLETE")
    _album_stages._build_notices(ctx)
    return _safe_json({
        "album_slug": album_slug,
        "stage_reached": "complete",
        "stages": ctx.stages,
        "settings": ctx.settings,
        "warnings": ctx.warnings,
        "notices": ctx.notices,
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


async def measure_album_signature(
    album_slug: str,
    subfolder: str = "mastered",
    genre: str = "",
    anchor_track: int | None = None,
) -> str:
    """Measure an album's multi-metric signature from its WAV files.

    Runs analyze_track() on every WAV in the album's ``subfolder``
    directory, then aggregates the results into:
      • per-track signature metrics (LUFS, peak, STL-95, short-term
        range, low-RMS, vocal-RMS, spectral band energy);
      • album-level aggregates (median, p95, min, max, range);
      • an optional anchor block (when ``genre`` or ``anchor_track`` is
        given) with the selected-anchor index, the anchor-selector scores,
        and per-track deltas from the anchor.

    The tool is read-only — no files are written. It's intended for
    tuning genre tolerance presets from reference albums and for feeding
    the album_coherence_check / album_coherence_correct tools in phase 3b.

    Args:
        album_slug: Album slug (e.g., "my-album").
        subfolder: Subfolder under the album's audio directory to scan
            for WAVs. Default "mastered". Pass "" to scan the base audio
            dir, or any confined relative path.
        genre: Optional genre preset slug (e.g., "pop"). When set, the
            anchor selector runs with the resolved preset's
            ``genre_ideal_lra_lu`` and ``spectral_reference_energy``.
        anchor_track: Optional explicit 1-based track number to use as
            the anchor. Overrides both ``genre``-based selection and any
            album-README ``anchor_track:`` frontmatter value. Out-of-range
            values fall through to composite scoring (and are surfaced
            via ``anchor.override_reason``).

    Returns:
        JSON string. On success includes ``tracks``, ``album``, and —
        when an anchor was computed — an ``anchor`` block. On failure
        returns ``{"error": str, ...}``.
    """
    dep_err = _helpers._check_mastering_deps()
    if dep_err:
        return _safe_json({"error": dep_err})

    err, audio_dir = _helpers._resolve_audio_dir(album_slug)
    if err:
        return err
    assert audio_dir is not None

    # Resolve source directory (subfolder) with confinement guard.
    if subfolder:
        if not _is_path_confined(audio_dir, subfolder):
            return _safe_json({
                "error": (
                    f"Invalid subfolder: path must not escape the album "
                    f"directory (got {subfolder!r})"
                ),
            })
        source_dir = audio_dir / subfolder
        if not source_dir.is_dir():
            return _safe_json({
                "error": f"Subfolder not found: {source_dir}",
                "suggestion": (
                    f"Pass subfolder='' to scan the base audio dir, or "
                    f"verify {subfolder!r} exists under {audio_dir}."
                ),
            })
    else:
        source_dir = _find_wav_source_dir(audio_dir)

    wav_files = sorted([
        f for f in source_dir.iterdir()
        if f.suffix.lower() == ".wav" and "venv" not in str(f)
    ])
    if not wav_files:
        return _safe_json({
            "error": f"No WAV files found in {source_dir}",
        })

    # Resolve genre preset (only when caller gave a genre — otherwise
    # skip the preset step entirely so unknown-genre doesn't error a
    # signature-only measurement run).
    preset_dict: dict[str, Any] | None = None
    if genre:
        from tools.mastering.config import build_effective_preset
        bundle = build_effective_preset(
            genre=genre,
            cut_highmid_arg=0.0,
            cut_highs_arg=0.0,
            target_lufs_arg=-14.0,
            ceiling_db_arg=-1.0,
        )
        if bundle["error"] is not None:
            return _safe_json({
                "error": bundle["error"]["reason"],
                "available_genres": bundle["error"].get("available_genres", []),
            })
        preset_dict = bundle["preset_dict"]

    # Determine whether an anchor is requested and which override to use.
    # Precedence: explicit arg > README frontmatter > composite scoring > none.
    override_index: int | None = None
    if isinstance(anchor_track, int) and not isinstance(anchor_track, bool):
        override_index = anchor_track
    elif _shared.cache is not None:
        state_albums = (_shared.cache.get_state() or {}).get("albums", {})
        album_state = state_albums.get(_normalize_slug(album_slug), {})
        raw_override = album_state.get("anchor_track")
        if isinstance(raw_override, int) and not isinstance(raw_override, bool):
            override_index = raw_override

    anchor_requested = bool(genre) or override_index is not None

    # Run analyzer on every WAV. Block-executor keeps the event loop responsive.
    from tools.mastering.analyze_tracks import analyze_track
    from tools.mastering.album_signature import (
        build_signature,
        compute_anchor_deltas,
    )

    loop = asyncio.get_running_loop()
    analysis_results: list[dict[str, Any]] = []
    for wav in wav_files:
        result = await loop.run_in_executor(None, analyze_track, str(wav))
        analysis_results.append(result)

    signature = build_signature(analysis_results)
    response: dict[str, Any] = {
        "album_slug": album_slug,
        "source_dir": str(source_dir),
        "settings": {
            "genre": genre.lower() if genre else None,
            "subfolder": subfolder,
        },
        "tracks": signature["tracks"],
        "album":  signature["album"],
    }

    if anchor_requested:
        from tools.mastering.anchor_selector import select_anchor
        anchor_preset = preset_dict or {}
        anchor_result = select_anchor(
            analysis_results,
            anchor_preset,
            override_index=override_index,
        )
        anchor_block: dict[str, Any] = {
            "selected_index":  anchor_result["selected_index"],
            "method":          anchor_result["method"],
            "override_index":  anchor_result["override_index"],
            "override_reason": anchor_result["override_reason"],
            "scores":          anchor_result["scores"],
        }
        selected = anchor_result["selected_index"]
        if isinstance(selected, int) and 1 <= selected <= len(analysis_results):
            anchor_block["deltas"] = compute_anchor_deltas(
                analysis_results, anchor_index_1based=selected,
            )
        else:
            anchor_block["deltas"] = []
        response["anchor"] = anchor_block

    return _safe_json(response)


async def album_coherence_check(
    album_slug: str,
    subfolder: str = "mastered",
    genre: str = "",
    anchor_track: int | None = None,
) -> str:
    """Check an album's mastered tracks for coherence outliers vs. the anchor.

    Runs the same measurement pipeline as measure_album_signature, then
    classifies each non-anchor track against per-genre tolerance bands:
      • LUFS delta (±0.5 LU, correctable in MVP)
      • STL-95 delta (±coherence_stl_95_lu, reported)
      • LRA floor (short_term_range ≥ coherence_lra_floor_lu, reported)
      • low-RMS delta (±coherence_low_rms_db, reported)
      • vocal-RMS delta (±coherence_vocal_rms_db, reported)

    Read-only — no files modified. Use album_coherence_correct to
    actually re-master LUFS outliers.

    Args:
        album_slug: Album slug.
        subfolder: Directory to scan for WAVs (default "mastered").
        genre: Genre preset slug. Required unless anchor_track is given
            (in which case hardcoded default tolerances are used and a
            warning is emitted).
        anchor_track: Optional 1-based track number override for the
            anchor. Overrides genre-driven composite scoring + state-
            cache frontmatter.

    Returns:
        JSON string with settings, album aggregates, anchor block,
        per-track classifications, and summary counts.
    """
    dep_err = _helpers._check_mastering_deps()
    if dep_err:
        return _safe_json({"error": dep_err})

    err, audio_dir = _helpers._resolve_audio_dir(album_slug)
    if err:
        return err
    assert audio_dir is not None

    if subfolder:
        if not _is_path_confined(audio_dir, subfolder):
            return _safe_json({
                "error": (
                    f"Invalid subfolder: path must not escape the album "
                    f"directory (got {subfolder!r})"
                ),
            })
        source_dir = audio_dir / subfolder
        if not source_dir.is_dir():
            return _safe_json({
                "error": f"Subfolder not found: {source_dir}",
            })
    else:
        source_dir = _find_wav_source_dir(audio_dir)

    wav_files = sorted([
        f for f in source_dir.iterdir()
        if f.suffix.lower() == ".wav" and "venv" not in str(f)
    ])
    if not wav_files:
        return _safe_json({"error": f"No WAV files found in {source_dir}"})

    if not genre and anchor_track is None:
        return _safe_json({
            "error": (
                "album_coherence_check requires either a genre (for "
                "tolerances + anchor selection) or an explicit anchor_track "
                "(falls back to default tolerances with a warning)."
            ),
        })

    from tools.mastering.coherence import (
        classify_outliers,
        load_tolerances,
    )

    preset_dict: dict[str, Any] | None = None
    warnings: list[str] = []
    if genre:
        from tools.mastering.config import build_effective_preset
        bundle = build_effective_preset(
            genre=genre,
            cut_highmid_arg=0.0,
            cut_highs_arg=0.0,
            target_lufs_arg=-14.0,
            ceiling_db_arg=-1.0,
        )
        if bundle["error"] is not None:
            return _safe_json({
                "error": bundle["error"]["reason"],
                "available_genres": bundle["error"].get("available_genres", []),
            })
        preset_dict = bundle["preset_dict"]
    else:
        warnings.append(
            "No genre supplied — using default coherence tolerances. "
            "Pass genre= for per-genre-tuned tolerances when they become "
            "available."
        )

    tolerances = load_tolerances(preset_dict)

    override_index: int | None = None
    if isinstance(anchor_track, int) and not isinstance(anchor_track, bool):
        override_index = anchor_track
    elif _shared.cache is not None:
        state_albums = (_shared.cache.get_state() or {}).get("albums", {})
        album_state = state_albums.get(_normalize_slug(album_slug), {})
        raw_override = album_state.get("anchor_track")
        if isinstance(raw_override, int) and not isinstance(raw_override, bool):
            override_index = raw_override

    from tools.mastering.analyze_tracks import analyze_track
    from tools.mastering.album_signature import (
        build_signature,
        compute_anchor_deltas,
    )
    from tools.mastering.anchor_selector import select_anchor

    loop = asyncio.get_running_loop()
    analysis_results: list[dict[str, Any]] = []
    for wav in wav_files:
        result = await loop.run_in_executor(None, analyze_track, str(wav))
        analysis_results.append(result)

    signature = build_signature(analysis_results)

    anchor_result = select_anchor(
        analysis_results,
        preset_dict or {},
        override_index=override_index,
    )

    anchor_block: dict[str, Any] = {
        "selected_index":  anchor_result["selected_index"],
        "method":          anchor_result["method"],
        "override_index":  anchor_result["override_index"],
        "override_reason": anchor_result["override_reason"],
        "scores":          anchor_result["scores"],
    }

    classifications: list[dict[str, Any]] = []
    summary: dict[str, Any] = {
        "track_count":          len(analysis_results),
        "outlier_count":        0,
        "correctable_count":    0,
        "uncorrectable_count":  0,
        "metric_breakdown": {
            m: {"outliers": 0, "missing": 0}
            for m in ("lufs", "stl_95", "lra_floor", "low_rms", "vocal_rms")
        },
    }

    selected = anchor_result["selected_index"]
    if isinstance(selected, int) and 1 <= selected <= len(analysis_results):
        deltas = compute_anchor_deltas(analysis_results, anchor_index_1based=selected)
        anchor_block["deltas"] = deltas
        classifications = classify_outliers(
            deltas, analysis_results, tolerances, anchor_index_1based=selected,
        )
        for cls in classifications:
            has_lufs_correctable = any(
                v["metric"] == "lufs" and v["severity"] == "outlier"
                for v in cls["violations"]
            )
            has_non_lufs_outlier = any(
                v["metric"] != "lufs" and v["severity"] == "outlier"
                for v in cls["violations"]
            )
            if cls["is_outlier"]:
                summary["outlier_count"] += 1
                if has_lufs_correctable:
                    summary["correctable_count"] += 1
                elif has_non_lufs_outlier:
                    summary["uncorrectable_count"] += 1
            for v in cls["violations"]:
                metric = v["metric"]
                if v["severity"] == "outlier":
                    summary["metric_breakdown"][metric]["outliers"] += 1
                elif v["severity"] == "missing":
                    summary["metric_breakdown"][metric]["missing"] += 1
    else:
        anchor_block["deltas"] = []
        warnings.append(
            "Anchor selector returned no eligible tracks; classifications "
            "skipped. Check signature metrics — some tracks likely have "
            "stl_95=None or missing band_energy."
        )

    response = {
        "album_slug": album_slug,
        "source_dir": str(source_dir),
        "settings": {
            "genre":      genre.lower() if genre else None,
            "subfolder":  subfolder,
            "tolerances": tolerances,
        },
        "album":           signature["album"],
        "anchor":          anchor_block,
        "classifications": classifications,
        "summary":         summary,
    }
    if warnings:
        response["warnings"] = warnings
    return _safe_json(response)


async def album_coherence_correct(
    album_slug: str,
    genre: str,
    source_subfolder: str = "polished",
    check_subfolder: str = "mastered",
    target_lufs: float = -14.0,
    ceiling_db: float = -1.0,
    cut_highmid: float = 0.0,
    cut_highs: float = 0.0,
    anchor_track: int | None = None,
    dry_run: bool = False,
) -> str:
    """Re-master LUFS-outlier tracks from polished/ into mastered/.

    First runs the same logic as album_coherence_check to identify
    outliers, then — for each LUFS outlier — re-runs master_track on
    the corresponding polished/<track>.wav with target_lufs set to the
    anchor's measured LUFS. Outputs stage into a .coherence_staging/
    subfolder and atomically replace the originals in mastered/ on
    full success.

    Non-LUFS outliers (STL-95, LRA floor, low-RMS, vocal-RMS) are
    reported in the response but NOT corrected in MVP — fixing those
    requires per-track compression/EQ adjustment that this phase
    intentionally defers.

    Args:
        album_slug: Album slug.
        genre: Genre preset — required (tolerances + preset base).
        source_subfolder: Directory to re-master from (default "polished").
        check_subfolder: Directory to measure first (default "mastered").
        target_lufs / ceiling_db / cut_highmid / cut_highs: Mastering
            overrides — same semantics as master_album. Used only as
            the initial preset; per-track target_lufs is overridden
            with the anchor's measured LUFS during correction.
        anchor_track: Optional explicit anchor.
        dry_run: When True, build the correction plan and return it
            without writing any files.

    Returns:
        JSON with pre-correction measurement, plan, per-track
        correction results, post-correction re-measurement, and
        summary. On error, returns {"error": ...}.
    """
    if not genre:
        return _safe_json({
            "error": "album_coherence_correct requires a genre for tolerance + preset resolution.",
        })

    dep_err = _helpers._check_mastering_deps()
    if dep_err:
        return _safe_json({"error": dep_err})

    err, audio_dir = _helpers._resolve_audio_dir(album_slug)
    if err:
        return err
    assert audio_dir is not None

    if not _is_path_confined(audio_dir, source_subfolder) \
            or not _is_path_confined(audio_dir, check_subfolder):
        return _safe_json({
            "error": "Invalid subfolder: path must not escape album directory.",
        })
    polished_dir = audio_dir / source_subfolder
    mastered_dir = audio_dir / check_subfolder
    if not polished_dir.is_dir():
        return _safe_json({
            "error": (
                f"Source subfolder not found: {polished_dir}. "
                f"Run polish_audio first, then master_album, then retry."
            ),
        })
    if not mastered_dir.is_dir():
        return _safe_json({
            "error": f"Check subfolder not found: {mastered_dir}",
        })

    polished_names = {
        f.name for f in polished_dir.iterdir()
        if f.suffix.lower() == ".wav" and "venv" not in str(f)
    }
    mastered_names = {
        f.name for f in mastered_dir.iterdir()
        if f.suffix.lower() == ".wav" and "venv" not in str(f)
    }
    missing_in_polished = sorted(mastered_names - polished_names)
    if missing_in_polished:
        return _safe_json({
            "error": (
                f"Tracks present in {check_subfolder}/ but missing from "
                f"{source_subfolder}/: {missing_in_polished}. Cannot re-master "
                f"without pre-limiter source."
            ),
        })

    pre_json = await album_coherence_check(
        album_slug=album_slug,
        subfolder=check_subfolder,
        genre=genre,
        anchor_track=anchor_track,
    )
    pre = json.loads(pre_json)
    if "error" in pre:
        return _safe_json({"error": pre["error"], **pre})

    from tools.mastering.coherence import build_correction_plan
    classifications = pre["classifications"]
    anchor_idx = pre["anchor"]["selected_index"]
    if anchor_idx is None:
        return _safe_json({
            "error": "Anchor selector returned no eligible tracks — cannot correct.",
            "pre_correction": pre,
        })

    from tools.mastering.analyze_tracks import analyze_track
    loop = asyncio.get_running_loop()
    mastered_wavs = sorted([
        f for f in mastered_dir.iterdir()
        if f.suffix.lower() == ".wav" and "venv" not in str(f)
    ])
    pre_analysis: list[dict[str, Any]] = []
    for wav in mastered_wavs:
        result = await loop.run_in_executor(None, analyze_track, str(wav))
        pre_analysis.append(result)

    plan = build_correction_plan(
        classifications, pre_analysis, anchor_index_1based=anchor_idx,
    )

    response: dict[str, Any] = {
        "album_slug": album_slug,
        "dry_run":    dry_run,
        "settings": {
            "genre":             genre,
            "source_subfolder":  source_subfolder,
            "check_subfolder":   check_subfolder,
        },
        "pre_correction": pre,
        "plan":           plan,
        "corrections":    [],
    }

    if dry_run:
        response["summary"] = {
            "corrected":       0,
            "skipped":         len(plan["skipped"]),
            "failed":          0,
            "anchor_lufs":     plan["anchor_lufs"],
            "outliers_before": pre["summary"]["outlier_count"],
            "outliers_after":  pre["summary"]["outlier_count"],
        }
        return _safe_json(response)

    from tools.mastering.config import build_effective_preset
    from tools.mastering.master_tracks import master_track

    import soundfile as _sf
    try:
        source_sample_rate = int(_sf.info(str(mastered_wavs[0])).samplerate)
    except Exception:
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
            "error": bundle["error"]["reason"],
            "available_genres": bundle["error"].get("available_genres", []),
        })
    effective_preset = bundle["effective_preset"]

    staging_dir = mastered_dir.parent / ".coherence_staging"
    staging_dir.mkdir(exist_ok=True)

    failed = 0
    try:
        for entry in plan["corrections"]:
            if not entry["correctable"]:
                continue
            filename = entry["filename"]
            # Spectral-only outliers have no LUFS target — re-master at the
            # anchor LUFS so the tilt nudge passes through the limiter chain
            # without an incidental gain move.
            applied_target = entry.get(
                "corrected_target_lufs", plan["anchor_lufs"]
            )
            applied_tilt_db = float(entry.get("corrected_tilt_db", 0.0))
            src = polished_dir / filename
            if not src.is_file():
                response["corrections"].append({
                    "filename":           filename,
                    "status":             "failed",
                    "failure_reason":     f"Polished source missing: {src}",
                    "applied_target_lufs": applied_target,
                    "applied_tilt_db":    applied_tilt_db,
                })
                failed += 1
                continue
            modified_preset = dict(effective_preset)
            modified_preset["target_lufs"] = applied_target
            staged = staging_dir / filename
            try:
                from functools import partial
                await loop.run_in_executor(
                    None,
                    partial(
                        master_track, src, staged,
                        preset=modified_preset, tilt_db=applied_tilt_db,
                    ),
                )
            except Exception as exc:  # pragma: no cover - defensive
                response["corrections"].append({
                    "filename":           filename,
                    "status":             "failed",
                    "failure_reason":     f"master_track raised: {exc}",
                    "applied_target_lufs": applied_target,
                    "applied_tilt_db":    applied_tilt_db,
                })
                failed += 1
                continue

            staged_result = await loop.run_in_executor(
                None, analyze_track, str(staged),
            )
            delta = staged_result["lufs"] - plan["anchor_lufs"]
            response["corrections"].append({
                "filename":             filename,
                "original_lufs":        next(
                    (t["lufs"] for t in pre_analysis if t["filename"] == filename),
                    None,
                ),
                "applied_target_lufs":  applied_target,
                "applied_tilt_db":      applied_tilt_db,
                "result_lufs":          staged_result["lufs"],
                "status":               "ok",
                "delta_from_anchor":    delta,
                "within_tolerance":     abs(delta) <= 0.5,
            })

        if failed == 0 and response["corrections"]:
            for entry in response["corrections"]:
                if entry["status"] != "ok":
                    continue
                staged = staging_dir / entry["filename"]
                final = mastered_dir / entry["filename"]
                staged.replace(final)
    finally:
        for f in staging_dir.iterdir():
            try:
                f.unlink()
            except OSError:
                pass
        try:
            staging_dir.rmdir()
        except OSError:
            pass

    post_json = await album_coherence_check(
        album_slug=album_slug,
        subfolder=check_subfolder,
        genre=genre,
        anchor_track=anchor_track,
    )
    post = json.loads(post_json)
    response["post_correction"] = post

    response["summary"] = {
        "corrected":       sum(1 for c in response["corrections"] if c["status"] == "ok"),
        "skipped":         len(plan["skipped"])
                          + sum(1 for c in plan["corrections"] if not c["correctable"]),
        "failed":          failed,
        "anchor_lufs":     plan["anchor_lufs"],
        "outliers_before": pre["summary"]["outlier_count"],
        "outliers_after":  post.get("summary", {}).get("outlier_count", -1),
    }
    return _safe_json(response)


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
    mcp.tool()(measure_album_signature)
    mcp.tool()(album_coherence_check)
    mcp.tool()(album_coherence_correct)
