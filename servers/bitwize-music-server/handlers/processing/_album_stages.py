"""Per-stage implementations for master_album (#290 D5 — stage extraction).

Each public function in this module implements exactly one stage of the
master_album pipeline. Stages communicate through MasterAlbumCtx — a
dataclass that holds all shared mutable state. Each stage function has
the signature::

    async def _stage_NAME(ctx: MasterAlbumCtx) -> str | None

returning ``None`` on success (ctx mutated in-place) or a failure JSON
string when the stage halts the pipeline.

Stage functions are called in sequence by the master_album orchestrator
in handlers/processing/audio.py. Import nothing from audio.py here —
stages import directly from tools.* and handlers.* as needed.
"""

from __future__ import annotations

import asyncio
import functools
import json
import logging
import os
import tempfile
from dataclasses import dataclass, field
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
    _safe_json,
    get_plugin_version as _read_plugin_version,
)
from handlers._atomic import atomic_write_text
from handlers.processing import _helpers
from tools.mastering.album_signature import build_signature
from tools.mastering.ceiling_guard import (
    CeilingGuardError,
    apply_pull_down_db,
    compute_overshoots as _ceiling_guard_compute_overshoots,
)
from tools.mastering.config import build_effective_preset
from tools.mastering.layout import (
    LayoutError,
    compute_transitions as _layout_compute_transitions,
    render_layout_markdown as _layout_render_markdown,
)
from tools.mastering.signature_persistence import (
    SIGNATURE_FILENAME,
    SignaturePersistenceError,
    read_signature_file,
    write_signature_file,
)

logger = logging.getLogger("bitwize-music-state")


# ---------------------------------------------------------------------------
# Pipeline context
# ---------------------------------------------------------------------------

@dataclass
class MasterAlbumCtx:
    """All shared mutable state for a single master_album pipeline run.

    Inputs are set at construction. Each stage function reads from and
    writes to this object. Fields are grouped by the stage that first
    populates them.
    """

    # ── inputs (set at construction) ─────────────────────────────────────────
    album_slug: str
    genre: str
    target_lufs: float
    ceiling_db: float
    cut_highmid: float
    cut_highs: float
    source_subfolder: str
    freeze_signature: bool
    new_anchor: bool
    loop: asyncio.AbstractEventLoop

    # ── accumulated outputs ───────────────────────────────────────────────────
    stages: dict[str, Any] = field(default_factory=dict)
    warnings: list[Any] = field(default_factory=list)
    notices: list[str] = field(default_factory=list)

    # ── stage 1 (pre-flight) ─────────────────────────────────────────────────
    audio_dir: Path | None = None
    source_dir: Path | None = None
    wav_files: list[Path] = field(default_factory=list)
    targets: dict[str, Any] = field(default_factory=dict)
    settings: dict[str, Any] = field(default_factory=dict)
    effective_preset: dict[str, Any] = field(default_factory=dict)
    preset_dict: dict[str, Any] | None = None
    # None means "no genre preset was loaded" (distinct from {} = empty preset).
    # Stage functions must null-check before use.
    effective_lufs: float = -14.0
    effective_ceiling: float = -1.0
    effective_highmid: float = 0.0
    effective_highs: float = 0.0
    effective_compress: float = 1.0

    # ── stage 2 (analysis) ───────────────────────────────────────────────────
    analysis_results: list[dict[str, Any]] = field(default_factory=list)

    # ── stage 2a (freeze decision) ───────────────────────────────────────────
    freeze_mode: str = "fresh"
    freeze_reason: str = "default"
    frozen_signature: dict[str, Any] | None = None

    # ── stage 2b (anchor selection) ──────────────────────────────────────────
    anchor_result: dict[str, Any] = field(default_factory=dict)

    # ── stage 3 (pre-QC) — produces no new ctx fields ────────────────────────
    # Stage 3 reads wav_files + loop and writes QC results only to ctx.stages
    # and ctx.warnings. No persistent fields are needed for downstream stages.

    # ── stage 4 (mastering) ──────────────────────────────────────────────────
    output_dir: Path | None = None
    mastered_files: list[Path] = field(default_factory=list)

    # ── stage 5 (verification) ───────────────────────────────────────────────
    verify_results: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Runtime notices
# ---------------------------------------------------------------------------

def _build_notices(ctx: MasterAlbumCtx) -> None:
    """Compute runtime caveats and append to ctx.notices.

    Called once by the orchestrator after all stages succeed. Not idempotent
    by design — the orchestrator must call it exactly once.
    """
    if ctx.targets.get("upsampled_from_source"):
        src_rate = ctx.targets.get("source_sample_rate")
        dst_rate = ctx.targets.get("output_sample_rate")
        if src_rate is not None and dst_rate is not None:
            ctx.notices.append(
                f"Delivery at {dst_rate // 1000} kHz "
                f"(upsampled from {src_rate / 1000:.1f} kHz source). "
                f"Badge-eligible for Apple Hi-Res Lossless and Tidal Max — "
                f"no additional audio information vs. source."
            )


# ---------------------------------------------------------------------------
# Stage functions (populated in subsequent tasks)
# ---------------------------------------------------------------------------


async def _stage_pre_flight(ctx: MasterAlbumCtx) -> str | None:
    """Stage 1: Resolve audio dir, find WAV files, build effective preset.

    Reads ctx: album_slug, genre, target_lufs, ceiling_db, cut_highmid,
               cut_highs, source_subfolder
    Sets ctx:  audio_dir, source_dir, wav_files, targets, settings,
               effective_preset, preset_dict, effective_lufs,
               effective_ceiling, effective_highmid, effective_highs,
               effective_compress
    Returns: None on success, failure JSON on halt.
    """
    dep_err = _helpers._check_mastering_deps()
    if dep_err:
        ctx.stages["pre_flight"] = {"status": "fail", "detail": dep_err}
        return _safe_json({
            "album_slug": ctx.album_slug,
            "stage_reached": "pre_flight",
            "stages": ctx.stages,
            "failed_stage": "pre_flight",
            "failure_detail": {"reason": dep_err},
        })

    err, audio_dir = _helpers._resolve_audio_dir(ctx.album_slug)
    if err:
        ctx.stages["pre_flight"] = {
            "status": "fail",
            "detail": "Audio directory not found",
        }
        return _safe_json({
            "album_slug": ctx.album_slug,
            "stage_reached": "pre_flight",
            "stages": ctx.stages,
            "failed_stage": "pre_flight",
            "failure_detail": json.loads(err),
        })
    assert audio_dir is not None

    if ctx.source_subfolder:
        if not _is_path_confined(audio_dir, ctx.source_subfolder):
            ctx.stages["pre_flight"] = {
                "status": "fail",
                "detail": "Invalid source_subfolder: path must not escape the album directory",
            }
            return _safe_json({
                "album_slug": ctx.album_slug,
                "stage_reached": "pre_flight",
                "stages": ctx.stages,
                "failed_stage": "pre_flight",
                "failure_detail": {
                    "reason": "Invalid source_subfolder: path escapes album directory",
                    "source_subfolder": ctx.source_subfolder,
                },
            })
        source_dir = audio_dir / ctx.source_subfolder
        if not source_dir.is_dir():
            ctx.stages["pre_flight"] = {
                "status": "fail",
                "detail": f"Source subfolder not found: {source_dir}",
            }
            return _safe_json({
                "album_slug": ctx.album_slug,
                "stage_reached": "pre_flight",
                "stages": ctx.stages,
                "failed_stage": "pre_flight",
                "failure_detail": {
                    "reason": f"Source subfolder not found: {source_dir}",
                    "suggestion": (
                        f"Run polish_audio first to create "
                        f"{ctx.source_subfolder}/ output."
                    ),
                },
            })
    else:
        source_dir = _find_wav_source_dir(audio_dir)

    wav_files = sorted([
        f for f in source_dir.iterdir()
        if f.suffix.lower() == ".wav" and "venv" not in str(f)
    ])

    if not wav_files:
        ctx.stages["pre_flight"] = {
            "status": "fail",
            "detail": f"No WAV files found in {source_dir}",
        }
        return _safe_json({
            "album_slug": ctx.album_slug,
            "stage_reached": "pre_flight",
            "stages": ctx.stages,
            "failed_stage": "pre_flight",
            "failure_detail": {"reason": f"No WAV files in {source_dir}"},
        })

    ctx.stages["pre_flight"] = {
        "status": "pass",
        "track_count": len(wav_files),
        "audio_dir": str(audio_dir),
        "source_dir": str(source_dir),
    }
    ctx.audio_dir = audio_dir
    ctx.source_dir = source_dir
    ctx.wav_files = wav_files

    source_sample_rate: int | None = None
    try:
        import soundfile as _sf
        source_sample_rate = int(_sf.info(str(wav_files[0])).samplerate)
    except Exception as _probe_exc:
        logger.debug(
            "Source sample rate probe failed for %s: %s",
            wav_files[0], _probe_exc,
        )

    bundle = build_effective_preset(
        genre=ctx.genre,
        cut_highmid_arg=ctx.cut_highmid,
        cut_highs_arg=ctx.cut_highs,
        target_lufs_arg=ctx.target_lufs,
        ceiling_db_arg=ctx.ceiling_db,
        source_sample_rate=source_sample_rate,
    )
    if bundle["error"] is not None:
        ctx.stages["pre_flight"] = {
            "status": "fail",
            "detail": "Failed to build effective preset",
        }
        return _safe_json({
            "album_slug": ctx.album_slug,
            "stage_reached": "pre_flight",
            "stages": ctx.stages,
            "failed_stage": "pre_flight",
            "failure_detail": bundle["error"],
        })

    ctx.targets = bundle["targets"]
    ctx.settings = bundle["settings"]
    ctx.effective_preset = bundle["effective_preset"]
    ctx.preset_dict = bundle["preset_dict"]
    ctx.effective_lufs = ctx.targets["target_lufs"]
    ctx.effective_ceiling = ctx.targets["ceiling_db"]
    ctx.effective_highmid = ctx.settings["cut_highmid"]
    ctx.effective_highs = ctx.settings["cut_highs"]
    ctx.effective_compress = ctx.effective_preset["compress_ratio"]
    return None


async def _stage_analysis(ctx: MasterAlbumCtx) -> str | None:
    """Stage 2: Measure LUFS, peaks, spectral balance on raw source files.

    Reads ctx: wav_files, loop
    Sets ctx:  analysis_results (also appends to ctx.warnings for tinny tracks)
    Returns: None always (analysis never halts the pipeline).
    """
    import numpy as np
    from tools.mastering.analyze_tracks import analyze_track

    analysis_results = []
    for wav in ctx.wav_files:
        result = await ctx.loop.run_in_executor(None, analyze_track, str(wav))
        analysis_results.append(result)

    lufs_values = [r["lufs"] for r in analysis_results]
    avg_lufs = float(np.mean(lufs_values))
    lufs_range = float(max(lufs_values) - min(lufs_values))
    tinny_tracks = [r["filename"] for r in analysis_results if r["tinniness_ratio"] > 0.6]

    for t in tinny_tracks:
        ctx.warnings.append(f"Pre-master: {t} — tinny (high-mid spike)")

    ctx.stages["analysis"] = {
        "status": "pass",
        "avg_lufs": round(avg_lufs, 1),
        "lufs_range": round(lufs_range, 1),
        "tinny_tracks": tinny_tracks,
    }
    ctx.analysis_results = analysis_results
    return None


async def _stage_freeze_decision(ctx: MasterAlbumCtx) -> str | None:
    """Stage 2a: Decide frozen vs fresh mastering mode.

    Reads ctx: album_slug, audio_dir, freeze_signature (param), new_anchor (param)
    Sets ctx:  freeze_mode, freeze_reason, frozen_signature
    Returns: None on success, failure JSON if ALBUM_SIGNATURE.yaml is missing
             when frozen mode is required.
    """
    if ctx.freeze_signature:
        freeze_mode = "frozen"
        freeze_reason = "freeze_signature_override"
    elif ctx.new_anchor:
        freeze_mode = "fresh"
        freeze_reason = "new_anchor_override"
    elif _shared.is_album_released(ctx.album_slug):
        freeze_mode = "frozen"
        freeze_reason = "album_released"
    else:
        freeze_mode = "fresh"
        freeze_reason = "default"

    frozen_signature: dict[str, Any] | None = None
    if freeze_mode == "frozen":
        assert ctx.audio_dir is not None
        try:
            frozen_signature = read_signature_file(ctx.audio_dir)
        except SignaturePersistenceError as exc:
            reason_text = f"Corrupt {SIGNATURE_FILENAME}: {exc}"
            ctx.stages["freeze_decision"] = {
                "status": "fail",
                "mode": freeze_mode,
                "reason": reason_text,
            }
            return _safe_json({
                "album_slug": ctx.album_slug,
                "stage_reached": "freeze_decision",
                "stages": ctx.stages,
                "settings": ctx.settings,
                "warnings": ctx.warnings,
                "failed_stage": "freeze_decision",
                "failure_detail": {"reason": reason_text},
            })
        if frozen_signature is None:
            if ctx.freeze_signature:
                reason_text = (
                    f"freeze_signature requested but {SIGNATURE_FILENAME} is absent "
                    f"in {ctx.audio_dir}"
                )
            else:
                reason_text = (
                    f"Album is Released but {SIGNATURE_FILENAME} is absent in "
                    f"{ctx.audio_dir}. Halt + escalate — cannot safely re-master "
                    f"without a frozen signature."
                )
            ctx.stages["freeze_decision"] = {
                "status": "fail",
                "mode": freeze_mode,
                "reason": reason_text,
            }
            return _safe_json({
                "album_slug": ctx.album_slug,
                "stage_reached": "freeze_decision",
                "stages": ctx.stages,
                "settings": ctx.settings,
                "warnings": ctx.warnings,
                "failed_stage": "freeze_decision",
                "failure_detail": {"reason": reason_text},
            })

    ctx.stages["freeze_decision"] = {
        "status": "pass",
        "mode": freeze_mode,
        "reason": freeze_reason,
    }
    ctx.freeze_mode = freeze_mode
    ctx.freeze_reason = freeze_reason
    ctx.frozen_signature = frozen_signature
    return None


async def _stage_anchor_selection(ctx: MasterAlbumCtx) -> str | None:
    """Stage 2b: Select mastering anchor track (or reuse frozen).

    Reads ctx: album_slug, analysis_results, preset_dict, freeze_mode,
               frozen_signature, targets, settings, effective_preset,
               effective_lufs, effective_ceiling, effective_compress
    Sets ctx:  anchor_result (also mutates targets, settings, effective_preset,
               effective_lufs, effective_ceiling, effective_compress in frozen path)
    Returns: None always (warnings issued on scoring failure, not halts).
    """
    if ctx.frozen_signature is not None:
        frozen_anchor = ctx.frozen_signature.get("anchor") or {}
        frozen_targets = ctx.frozen_signature.get("delivery_targets") or {}

        ctx.anchor_result = {
            "selected_index": frozen_anchor.get("index"),
            "method": "frozen_signature",
            "override_index": None,
            "override_reason": None,
            "scores": [],
        }
        ctx.stages["anchor_selection"] = {
            "status": "pass" if ctx.anchor_result["selected_index"] is not None else "warn",
            "selected_index": ctx.anchor_result["selected_index"],
            "method": "frozen_signature",
            "override_index": None,
            "override_reason": None,
            "scores": [],
            "frozen_from": frozen_anchor.get("filename"),
        }

        for k, sig_key in (
            ("target_lufs",        "target_lufs"),
            ("ceiling_db",         "tp_ceiling_db"),
            ("output_bits",        "output_bits"),
            ("output_sample_rate", "output_sample_rate"),
        ):
            val = frozen_targets.get(sig_key)
            if val is not None:
                ctx.targets[k] = val

        _src_sr = ctx.targets.get("source_sample_rate")
        _out_sr = ctx.targets.get("output_sample_rate")
        if _src_sr is not None and _out_sr is not None:
            ctx.targets["upsampled_from_source"] = _out_sr > _src_sr

        ctx.settings["target_lufs"] = ctx.targets.get("target_lufs")
        ctx.settings["ceiling_db"] = ctx.targets.get("ceiling_db")
        ctx.settings["output_bits"] = ctx.targets.get("output_bits")
        ctx.settings["output_sample_rate"] = ctx.targets.get("output_sample_rate")
        ctx.settings["upsampled_from_source"] = ctx.targets.get("upsampled_from_source")

        _frozen_preset_overrides: dict[str, Any] = {}
        for _pkey, _fkey in (
            ("target_lufs",        "target_lufs"),
            ("ceiling_db",         "tp_ceiling_db"),
            ("output_bits",        "output_bits"),
            ("output_sample_rate", "output_sample_rate"),
            ("genre_ideal_lra_lu", "lra_target_lu"),
        ):
            _val = frozen_targets.get(_fkey)
            if _val is not None:
                _frozen_preset_overrides[_pkey] = _val
        ctx.effective_preset.update(_frozen_preset_overrides)

        for _tol_key in (
            "coherence_stl_95_lu",
            "coherence_lra_floor_lu",
            "coherence_low_rms_db",
            "coherence_vocal_rms_db",
        ):
            _tol_val = (ctx.frozen_signature.get("tolerances") or {}).get(_tol_key)
            if _tol_val is not None:
                ctx.effective_preset[_tol_key] = _tol_val

        ctx.effective_lufs = ctx.targets["target_lufs"]
        ctx.effective_ceiling = ctx.targets["ceiling_db"]
        ctx.effective_compress = ctx.effective_preset.get(
            "compress_ratio", ctx.effective_compress
        )
    else:
        from tools.mastering.anchor_selector import select_anchor

        anchor_override: int | None = None
        state_albums = (_shared.cache.get_state() or {}).get("albums", {})
        album_state = state_albums.get(_normalize_slug(ctx.album_slug), {})
        raw_override = album_state.get("anchor_track")
        if isinstance(raw_override, int) and not isinstance(raw_override, bool):
            anchor_override = raw_override

        anchor_preset = ctx.preset_dict or {}
        ctx.anchor_result = select_anchor(
            ctx.analysis_results, anchor_preset, override_index=anchor_override,
        )
        ctx.stages["anchor_selection"] = {
            "status": "pass" if ctx.anchor_result["selected_index"] is not None else "warn",
            "selected_index": ctx.anchor_result["selected_index"],
            "method": ctx.anchor_result["method"],
            "override_index": ctx.anchor_result["override_index"],
            "override_reason": ctx.anchor_result["override_reason"],
            "scores": ctx.anchor_result["scores"],
        }
        if ctx.anchor_result["selected_index"] is None:
            ctx.warnings.append(
                "Anchor selector: no eligible tracks (signature metrics missing). "
                "Mastering proceeds without an anchor; coherence correction disabled."
            )
    return None


async def _stage_pre_qc(ctx: MasterAlbumCtx) -> str | None:
    """Stage 3: Technical QC on source files (truepeak/clicks excluded).

    Reads ctx: wav_files, loop
    Sets ctx:  (appends to ctx.warnings for WARN checks)
    Returns: None on pass/warn, failure JSON if any track FAILs.
    """
    from tools.mastering.qc_tracks import qc_track

    PRE_QC_CHECKS = ["format", "mono", "phase", "clipping", "silence", "spectral"]

    pre_qc_results = []
    for wav in ctx.wav_files:
        result = await ctx.loop.run_in_executor(
            None, qc_track, str(wav), PRE_QC_CHECKS
        )
        pre_qc_results.append(result)

    pre_passed = sum(1 for r in pre_qc_results if r["verdict"] == "PASS")
    pre_warned = sum(1 for r in pre_qc_results if r["verdict"] == "WARN")
    pre_failed = sum(1 for r in pre_qc_results if r["verdict"] == "FAIL")

    for r in pre_qc_results:
        for check_name, check_info in r["checks"].items():
            if check_info["status"] == "WARN":
                ctx.warnings.append(
                    f"Pre-QC {r['filename']}: {check_name} WARN — {check_info['detail']}"
                )

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
        ctx.stages["pre_qc"] = {
            "status": "fail",
            "passed": pre_passed,
            "warned": pre_warned,
            "failed": pre_failed,
            "verdict": "FAILURES FOUND",
        }
        return _safe_json({
            "album_slug": ctx.album_slug,
            "stage_reached": "pre_qc",
            "stages": ctx.stages,
            "settings": ctx.settings,
            "warnings": ctx.warnings,
            "failed_stage": "pre_qc",
            "failure_detail": {
                "tracks_failed": [r["filename"] for r in failed_tracks],
                "details": fail_details,
            },
        })

    ctx.stages["pre_qc"] = {
        "status": "pass",
        "passed": pre_passed,
        "warned": pre_warned,
        "failed": 0,
        "verdict": "ALL PASS" if pre_warned == 0 else "WARNINGS",
    }
    return None


async def _stage_mastering(ctx: MasterAlbumCtx) -> str | None:
    """Stage 4: Normalize loudness, apply EQ, limit peaks for all tracks.

    Reads ctx: album_slug, audio_dir, wav_files, effective_lufs,
               effective_ceiling, effective_highmid, effective_highs,
               effective_compress, effective_preset, source_dir, targets, loop
    Sets ctx:  output_dir, mastered_files
    Returns: None on success, failure JSON if no tracks processed.
    """
    import shutil as _shutil

    from tools.mastering.master_tracks import master_track as _master_track

    eq_settings = []
    if ctx.effective_highmid != 0:
        eq_settings.append((3500.0, ctx.effective_highmid, 1.5))
    if ctx.effective_highs != 0:
        eq_settings.append((8000.0, ctx.effective_highs, 0.7))

    assert ctx.audio_dir is not None
    output_dir = ctx.audio_dir / "mastered"
    staging_dir = ctx.audio_dir / ".mastering_staging"
    if staging_dir.exists():
        _shutil.rmtree(staging_dir)
    staging_dir.mkdir()

    state = _shared.cache.get_state() or {}
    album_tracks = (
        state.get("albums", {})
        .get(_normalize_slug(ctx.album_slug), {})
        .get("tracks", {})
    )

    try:
        master_results = []
        for wav_file in ctx.wav_files:
            output_path = staging_dir / wav_file.name
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
                    eq_settings=None,
                    ceiling_db=ceil,
                    fade_out=fade,
                    compress_ratio=comp,
                    preset=p,
                )

            result = await ctx.loop.run_in_executor(
                None, _do_master, wav_file, output_path,
                ctx.effective_lufs, ctx.effective_ceiling, fade_out_val,
                ctx.effective_compress, ctx.effective_preset,
            )
            if result and not result.get("skipped"):
                result["filename"] = wav_file.name
                master_results.append(result)
    except Exception:
        if staging_dir.exists():
            _shutil.rmtree(staging_dir)
        raise

    if not master_results:
        if staging_dir.exists():
            _shutil.rmtree(staging_dir)
        ctx.stages["mastering"] = {
            "status": "fail",
            "detail": "No tracks processed (all silent)",
        }
        return _safe_json({
            "album_slug": ctx.album_slug,
            "stage_reached": "mastering",
            "stages": ctx.stages,
            "settings": ctx.settings,
            "warnings": ctx.warnings,
            "failed_stage": "mastering",
            "failure_detail": {
                "reason": "No tracks processed (all silent or no WAV files)",
            },
        })

    output_dir.mkdir(exist_ok=True)
    for staged_file in staging_dir.iterdir():
        os.replace(str(staged_file), str(output_dir / staged_file.name))
    staging_dir.rmdir()

    ctx.stages["mastering"] = {
        "status": "pass",
        "tracks_processed": len(master_results),
        "settings": ctx.settings,
        "output_dir": str(output_dir),
    }
    ctx.output_dir = output_dir
    ctx.mastered_files = sorted([
        f for f in output_dir.iterdir()
        if f.suffix.lower() == ".wav" and "venv" not in str(f)
    ])
    return None


async def _stage_verification(ctx: MasterAlbumCtx) -> str | None:
    """Stage 5: Check mastered output meets targets; auto-recover dynamic tracks.

    Reads ctx: mastered_files, output_dir, source_dir, audio_dir,
               effective_lufs, effective_ceiling, effective_highmid,
               effective_highs, targets, settings, warnings, loop
    Sets ctx:  verify_results
    Returns: None on pass (all within spec), failure JSON otherwise.
    """
    import numpy as np
    from tools.mastering.analyze_tracks import analyze_track
    from tools.mastering.fix_dynamic_track import fix_dynamic

    assert ctx.output_dir is not None and ctx.source_dir is not None

    verify_results = []
    for wav in ctx.mastered_files:
        result = await ctx.loop.run_in_executor(None, analyze_track, str(wav))
        verify_results.append(result)

    verify_lufs = [r["lufs"] for r in verify_results]
    verify_avg = float(np.mean(verify_lufs))
    verify_range = float(max(verify_lufs) - min(verify_lufs))
    effective_lufs = ctx.effective_lufs
    effective_ceiling = ctx.effective_ceiling

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
    auto_recovered: list[dict[str, Any]] = []

    if out_of_spec or album_range_fail:
        recoverable = []
        for spec in out_of_spec:
            has_peak_issue = any("Peak" in iss for iss in spec["issues"])
            vr = next(
                (r for r in verify_results if r["filename"] == spec["filename"]), None
            )
            if not vr:
                continue
            lufs_too_low = vr["lufs"] < effective_lufs - 0.5
            peak_at_ceiling = vr["peak_db"] >= effective_ceiling - 0.1
            if lufs_too_low and peak_at_ceiling and not has_peak_issue:
                recoverable.append(spec["filename"])

        if recoverable:
            import soundfile as sf
            import numpy as _np

            eq_settings = []
            if ctx.effective_highmid != 0:
                eq_settings.append((3500.0, ctx.effective_highmid, 1.5))
            if ctx.effective_highs != 0:
                eq_settings.append((8000.0, ctx.effective_highs, 0.7))

            recovery_subtype = (
                "PCM_24" if ctx.targets["output_bits"] > 16 else "PCM_16"
            )

            for fname in recoverable:
                raw_path = ctx.source_dir / fname
                if not raw_path.exists():
                    raw_path = _find_wav_source_dir(ctx.audio_dir) / fname
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
                    data, rate = sf.read(str(src))
                    if len(data.shape) == 1:
                        data = _np.column_stack([data, data])
                    data, metrics = fix_dynamic(
                        data, rate,
                        target_lufs=lufs,
                        eq_settings=eq if eq else None,
                        ceiling_db=ceil,
                    )
                    sf.write(str(dst), data, rate, subtype=subtype)
                    return metrics

                mastered_path = ctx.output_dir / fname
                metrics = await ctx.loop.run_in_executor(
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
                ctx.warnings.append({
                    "type": "auto_recovery",
                    "tracks_fixed": [r["filename"] for r in auto_recovered],
                })
                verify_results = []
                for wav in ctx.mastered_files:
                    result = await ctx.loop.run_in_executor(
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
                            f"LUFS {r['lufs']:.1f} outside ±0.5 dB "
                            f"of target {effective_lufs}"
                        )
                    if r["peak_db"] > effective_ceiling:
                        issues.append(
                            f"Peak {r['peak_db']:.1f} dB exceeds ceiling "
                            f"{effective_ceiling} dB"
                        )
                    if issues:
                        out_of_spec.append(
                            {"filename": r["filename"], "issues": issues}
                        )
                album_range_fail = verify_range >= 1.0

        if out_of_spec or album_range_fail:
            fail_detail: dict[str, Any] = {}
            if out_of_spec:
                fail_detail["tracks_out_of_spec"] = out_of_spec
            if album_range_fail:
                fail_detail["album_lufs_range"] = round(verify_range, 2)
                fail_detail["album_range_limit"] = 1.0
            ctx.stages["verification"] = {
                "status": "fail",
                "avg_lufs": round(verify_avg, 1),
                "lufs_range": round(verify_range, 2),
                "all_within_spec": False,
            }
            return _safe_json({
                "album_slug": ctx.album_slug,
                "stage_reached": "verification",
                "stages": ctx.stages,
                "settings": ctx.settings,
                "warnings": ctx.warnings,
                "failed_stage": "verification",
                "failure_detail": fail_detail,
            })

    verification_stage: dict[str, Any] = {
        "status": "pass",
        "avg_lufs": round(verify_avg, 1),
        "lufs_range": round(verify_range, 2),
        "all_within_spec": True,
    }
    if auto_recovered:
        verification_stage["auto_recovered"] = auto_recovered
    ctx.stages["verification"] = verification_stage
    ctx.verify_results = verify_results
    return None


async def _stage_ceiling_guard(
    ctx: MasterAlbumCtx,
    _compute_overshoots: Any = None,
) -> str | None:
    """Stage 5.4: Album-ceiling guard — enforce album_median + 2 LU (#290 step 8).

    Reads ctx: verify_results, output_dir, targets, loop
    Sets ctx:  (mutates verify_results on pull-down; updates stages["verification"])
    Returns: None on pass/pull-down, failure JSON on halt (>0.5 LU overshoot).

    _compute_overshoots: injectable for testing (defaults to the module-level
        _ceiling_guard_compute_overshoots). Callers that need monkeypatching
        should pass their patched version explicitly.
    """
    import numpy as np
    from tools.mastering.analyze_tracks import analyze_track

    compute_fn = _compute_overshoots if _compute_overshoots is not None else _ceiling_guard_compute_overshoots

    assert ctx.output_dir is not None

    ceiling_tracks_input = [
        {"filename": r["filename"], "lufs": r["lufs"]}
        for r in ctx.verify_results
    ]
    ceiling_result = compute_fn(ceiling_tracks_input)

    ceiling_stage: dict[str, Any] = {
        "status": "pass",
        "action": "no_op",
        "median_lufs": (
            None if ceiling_result["median_lufs"] is None
            else round(ceiling_result["median_lufs"], 2)
        ),
        "threshold_lu": (
            None if ceiling_result["threshold_lu"] is None
            else round(ceiling_result["threshold_lu"], 2)
        ),
        "tracks": ceiling_result["tracks"],
        "pulled_down": [],
    }

    halt_rows = [r for r in ceiling_result["tracks"] if r["classification"] == "halt"]
    if halt_rows:
        ceiling_stage["status"] = "fail"
        ceiling_stage["action"] = "halt"
        ctx.stages["ceiling_guard"] = ceiling_stage
        return _safe_json({
            "album_slug": ctx.album_slug,
            "stage_reached": "ceiling_guard",
            "stages": ctx.stages,
            "settings": ctx.settings,
            "warnings": ctx.warnings,
            "failed_stage": "ceiling_guard",
            "failure_detail": {
                "reason": (
                    f"Album-ceiling guard: {len(halt_rows)} track(s) with "
                    f"overshoot > 0.5 LU. Coherence correction (step 6) did not "
                    f"converge on LUFS-I; re-run master_album with coherence "
                    f"corrections or adjust per-track mastering."
                ),
                "tracks": [
                    {
                        "filename": r["filename"],
                        "lufs": round(r["lufs"], 2),
                        "overshoot_lu": round(r["overshoot_lu"], 2),
                    }
                    for r in halt_rows
                ],
                "threshold_lu": ceiling_stage["threshold_lu"],
                "median_lufs": ceiling_stage["median_lufs"],
            },
        })

    correctable_rows = [
        r for r in ceiling_result["tracks"] if r["classification"] == "correctable"
    ]
    if correctable_rows:
        output_bits = int(ctx.targets.get("output_bits") or 24)
        pull_down_errors: list[str] = []
        pulled_files: list[str] = []
        for row in correctable_rows:
            target_path = ctx.output_dir / row["filename"]
            try:
                await ctx.loop.run_in_executor(
                    None,
                    functools.partial(
                        apply_pull_down_db,
                        target_path,
                        gain_db=row["pull_down_db"],
                        output_bits=output_bits,
                    ),
                )
                pulled_files.append(row["filename"])
            except CeilingGuardError as exc:
                pull_down_errors.append(f"{row['filename']}: {exc}")

        if pull_down_errors:
            ceiling_stage["status"] = "warn"
            ceiling_stage["pull_down_errors"] = pull_down_errors
            ctx.warnings.append(
                "Ceiling guard: pull-down failed for "
                f"{len(pull_down_errors)} track(s); see stage output"
            )
        ceiling_stage["action"] = "pull_down"
        ceiling_stage["pulled_down"] = pulled_files

        filename_to_index = {
            r["filename"]: i for i, r in enumerate(ctx.verify_results)
        }
        for fname in pulled_files:
            wav_path = ctx.output_dir / fname
            fresh = await ctx.loop.run_in_executor(
                None, analyze_track, str(wav_path),
            )
            idx = filename_to_index.get(fname)
            if idx is not None:
                ctx.verify_results[idx] = fresh

        verify_lufs = [r["lufs"] for r in ctx.verify_results]
        ctx.stages["verification"]["avg_lufs"] = round(float(np.mean(verify_lufs)), 1)
        ctx.stages["verification"]["lufs_range"] = round(
            float(max(verify_lufs) - min(verify_lufs)), 2
        )

    ctx.stages["ceiling_guard"] = ceiling_stage
    return None
