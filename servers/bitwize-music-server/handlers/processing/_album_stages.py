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
import re
import os
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
from tools.mastering.album_signature import build_signature, compute_anchor_deltas
from tools.mastering.coherence import (
    build_correction_plan as _coherence_build_plan,
    classify_outliers as _coherence_classify,
    load_tolerances as _coherence_load_tolerances,
)
from tools.mastering.ceiling_guard import (
    CeilingGuardError,
    apply_pull_down_db,
    compute_overshoots as _ceiling_guard_compute_overshoots,
)
from tools.mastering.config import build_effective_preset
from tools.mastering.layout import (
    LayoutError,
    compute_transitions as _layout_compute_transitions,
    parse_layout_yaml as _parse_layout_yaml,
    render_layout_markdown as _layout_render_markdown,
)
from tools.mastering.signature_persistence import (
    SIGNATURE_FILENAME,
    SignaturePersistenceError,
    read_signature_file,
    write_signature_file,
)
from tools.mastering.adm_validation import (
    ADMValidationError,
    check_aac_intersample_clips as _adm_check_fn_default,
    render_adm_validation_markdown,
)
from tools.mastering.metadata import (
    MetadataEmbedError,
    embed_wav_metadata as _embed_wav_metadata_fn_default,
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

    # ── stage 5.1 (coherence check) ───────────────────────────────────────────
    coherence_classifications: list[dict[str, Any]] = field(default_factory=list)
    # ── stage 5.2 (coherence correct) ─────────────────────────────────────────
    coherence_corrected_tracks: list[str] = field(default_factory=list)

    # ── stage 5.5 (ADM validation) ────────────────────────────────────────────
    adm_validation_results: list[dict[str, Any]] = field(default_factory=list)

    # ── ADM retry tracking ────────────────────────────────────────────────
    adm_cycle: int = 0


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


# Injectable for test monkeypatching (tests patch this module-level name).
_adm_check_fn = _adm_check_fn_default
_embed_wav_metadata_fn = _embed_wav_metadata_fn_default


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
    PRE_QC_DEFERRED = ["truepeak", "clicks"]

    pre_qc_results = []
    qc_genre = ctx.genre or None
    for wav in ctx.wav_files:
        result = await ctx.loop.run_in_executor(
            None, qc_track, str(wav), PRE_QC_CHECKS, qc_genre
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
            "checks_run": PRE_QC_CHECKS,
            "checks_deferred_to_post_master": PRE_QC_DEFERRED,
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
        "checks_run": PRE_QC_CHECKS,
        "checks_deferred_to_post_master": PRE_QC_DEFERRED,
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

    assert ctx.output_dir is not None and ctx.source_dir is not None and ctx.audio_dir is not None

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


_COHERENCE_MAX_CORRECTION_DB = 1.5
_COHERENCE_MAX_ITERATIONS = 2


async def _stage_coherence_check(ctx: MasterAlbumCtx) -> str | None:
    """Stage 5.1: Classify tracks against coherence tolerance bands (#290 step 5).

    Reads ctx: anchor_result, verify_results, preset_dict
    Sets ctx:  coherence_classifications, stages["coherence_check"]
    Returns: None always (outliers are warnings, not pipeline halts).
    """
    anchor_idx = ctx.anchor_result.get("selected_index")
    if not isinstance(anchor_idx, int) or anchor_idx < 1:
        ctx.stages["coherence_check"] = {
            "status": "warn",
            "reason": "no_anchor",
            "outlier_count": 0,
            "correctable_count": 0,
            "anchor_index": None,
        }
        return None

    if not ctx.verify_results:
        ctx.stages["coherence_check"] = {
            "status": "warn",
            "reason": "no_verify_results",
            "outlier_count": 0,
            "correctable_count": 0,
            "anchor_index": anchor_idx,
        }
        return None

    tolerances = _coherence_load_tolerances(ctx.preset_dict)
    deltas = compute_anchor_deltas(ctx.verify_results, anchor_index_1based=anchor_idx)
    classifications = _coherence_classify(
        deltas, ctx.verify_results, tolerances, anchor_index_1based=anchor_idx
    )
    ctx.coherence_classifications = classifications

    outlier_count = sum(1 for c in classifications if c.get("is_outlier"))

    # correctable_count must match what _stage_coherence_correct actually
    # acts on. Delegate to build_correction_plan so both stages share one
    # definition of "correctable" (LUFS outliers OR spectral outliers with
    # bounded tilt-EQ correction). Previously this counted LUFS-only,
    # hiding spectral corrections and misreporting 0 while the correct
    # stage still ran iterations.
    from tools.mastering.coherence import build_correction_plan
    plan = build_correction_plan(
        classifications, ctx.verify_results, anchor_index_1based=anchor_idx
    )
    correctable_count = sum(1 for c in plan["corrections"] if c["correctable"])

    ctx.stages["coherence_check"] = {
        "status": "pass" if outlier_count == 0 else "warn",
        "outlier_count": outlier_count,
        "correctable_count": correctable_count,
        "anchor_index": anchor_idx,
    }
    return None


async def _stage_coherence_correct(ctx: MasterAlbumCtx) -> str | None:
    """Stage 5.2: Re-master LUFS outliers within ±1.5 dB of anchor (#290 step 6).

    Reads ctx: anchor_result, coherence_classifications, verify_results,
               source_dir, output_dir, mastered_files, effective_ceiling,
               effective_compress, effective_preset, preset_dict, loop
    Sets ctx:  verify_results (updated), coherence_classifications (updated),
               coherence_corrected_tracks, stages["coherence_correct"]
    Returns: None always (unconverged outliers go to warnings).
    """
    from tools.mastering.analyze_tracks import analyze_track
    from tools.mastering.master_tracks import master_track as _master_track

    anchor_idx = ctx.anchor_result.get("selected_index")
    if not isinstance(anchor_idx, int) or anchor_idx < 1:
        ctx.stages["coherence_correct"] = {
            "status": "warn",
            "reason": "no_anchor",
            "iterations": 0,
            "corrections": [],
        }
        return None

    if not ctx.coherence_classifications:
        ctx.stages["coherence_correct"] = {
            "status": "pass",
            "iterations": 0,
            "corrections": [],
        }
        return None

    assert ctx.source_dir is not None
    assert ctx.output_dir is not None

    tolerances = _coherence_load_tolerances(ctx.preset_dict)
    all_corrections: list[dict[str, Any]] = []
    iterations_run = 0

    current_verify = list(ctx.verify_results)
    classifications = list(ctx.coherence_classifications)

    # Freeze anchor LUFS from step-5 verification — spec #290 step 6 requires
    # the album median (anchor-based here) be captured once and held constant
    # across inner iterations to prevent correction feedback loops.
    frozen_anchor_lufs = float(
        current_verify[anchor_idx - 1].get("lufs", 0.0)
    ) if 1 <= anchor_idx <= len(current_verify) else 0.0

    prev_plan_signature: tuple[tuple[str, float, float], ...] | None = None

    for _iter in range(_COHERENCE_MAX_ITERATIONS):
        plan = _coherence_build_plan(classifications, current_verify, anchor_idx)
        correctable = [c for c in plan["corrections"] if c["correctable"]]
        if not correctable:
            break

        # Fixed-point detection (#323 comment): when consecutive iterations
        # produce identical correction plans AND at least one entry has
        # tilt clamped, re-mastering from the same polished source with
        # the same clamped tilt will yield the same output. Flag each
        # unconvergent track and break the loop rather than burning the
        # remaining iteration budget on a known-futile repeat.
        plan_signature = tuple(
            (
                str(c["filename"]),
                round(float(c.get("corrected_target_lufs", 0.0)), 3),
                round(float(c.get("corrected_tilt_db", 0.0)), 3),
            )
            for c in correctable
        )
        any_tilt_clamped = any(c.get("tilt_clamped") for c in correctable)
        if plan_signature == prev_plan_signature and any_tilt_clamped:
            for entry in correctable:
                all_corrections.append({
                    "filename": entry["filename"],
                    "status": "unconvergent",
                    "reason": "fixed_point_tilt_clamp",
                    "applied_target_lufs": entry.get("corrected_target_lufs"),
                    "applied_tilt_db": entry.get("corrected_tilt_db"),
                    "tilt_clamped": entry.get("tilt_clamped", False),
                    "iteration": _iter + 1,
                })
            break
        prev_plan_signature = plan_signature

        anchor_lufs = frozen_anchor_lufs
        iterations_run += 1

        for entry in correctable:
            filename = entry["filename"]
            # Spectral-only outliers have no LUFS target; re-master at the
            # anchor LUFS so the tilt-EQ nudge passes through the full
            # limiter chain without a separate gain move.
            raw_target = entry.get("corrected_target_lufs", anchor_lufs)
            tilt_db = float(entry.get("corrected_tilt_db", 0.0))
            tilt_clamped = bool(entry.get("tilt_clamped", False))
            clamped = False

            # Clamp to ±1.5 dB window around the FROZEN step-5 anchor, not
            # the plan's fresh recomputation — prevents clamp bounds from
            # drifting if the anchor's post-limit LUFS measurement shifts
            # slightly between iterations.
            if raw_target < anchor_lufs - _COHERENCE_MAX_CORRECTION_DB:
                raw_target = anchor_lufs - _COHERENCE_MAX_CORRECTION_DB
                clamped = True
            elif raw_target > anchor_lufs + _COHERENCE_MAX_CORRECTION_DB:
                raw_target = anchor_lufs + _COHERENCE_MAX_CORRECTION_DB
                clamped = True

            src = ctx.source_dir / filename
            if not src.exists():
                all_corrections.append({
                    "filename": filename,
                    "status": "skipped",
                    "reason": "source_not_found",
                    "applied_target_lufs": None,
                    "applied_tilt_db": None,
                    "clamped": clamped,
                    "tilt_clamped": tilt_clamped,
                    "iteration": _iter + 1,
                })
                continue

            dst = ctx.output_dir / filename
            try:
                await ctx.loop.run_in_executor(
                    None,
                    functools.partial(
                        _master_track,
                        str(src),
                        str(dst),
                        target_lufs=raw_target,
                        ceiling_db=ctx.effective_ceiling,
                        compress_ratio=ctx.effective_compress,
                        preset=ctx.effective_preset,
                        tilt_db=tilt_db,
                    ),
                )
                all_corrections.append({
                    "filename": filename,
                    "status": "corrected",
                    "applied_target_lufs": raw_target,
                    "applied_tilt_db": tilt_db,
                    "clamped": clamped,
                    "tilt_clamped": tilt_clamped,
                    "iteration": _iter + 1,
                })
                if filename not in ctx.coherence_corrected_tracks:
                    ctx.coherence_corrected_tracks.append(filename)
            except Exception as exc:
                all_corrections.append({
                    "filename": filename,
                    "status": "error",
                    "reason": str(exc),
                    "applied_target_lufs": raw_target,
                    "applied_tilt_db": tilt_db,
                    "clamped": clamped,
                    "tilt_clamped": tilt_clamped,
                    "iteration": _iter + 1,
                })

        # Re-analyze all mastered files after this iteration's corrections
        fresh_results: list[dict[str, Any]] = []
        for wav in ctx.mastered_files:
            result = await ctx.loop.run_in_executor(None, analyze_track, str(wav))
            fresh_results.append(result)

        # Re-classify with fresh analysis
        fresh_deltas = compute_anchor_deltas(
            fresh_results, anchor_index_1based=anchor_idx
        )
        classifications = _coherence_classify(
            fresh_deltas, fresh_results, tolerances, anchor_index_1based=anchor_idx
        )
        current_verify = fresh_results

    # Commit updated state back to ctx
    ctx.verify_results = current_verify
    ctx.coherence_classifications = classifications

    remaining_outliers = sum(1 for c in classifications if c.get("is_outlier"))
    if remaining_outliers > 0:
        ctx.stages["coherence_correct"] = {
            "status": "warn",
            "reason": f"{remaining_outliers} outlier(s) remain after {_COHERENCE_MAX_ITERATIONS} iteration(s)",
            "iterations": iterations_run,
            "corrections": all_corrections,
            "remaining_outliers": remaining_outliers,
        }
        # Tag with ADM cycle so retry-loop runs produce distinguishable
        # warnings instead of silently conflating cycle-1 and cycle-2 state.
        ctx.warnings.append(
            f"Coherence correct (ADM cycle {ctx.adm_cycle + 1}): "
            f"{remaining_outliers} outlier(s) remain after "
            f"{iterations_run} iteration(s); ceiling_guard may apply pull-down."
        )
    else:
        ctx.stages["coherence_correct"] = {
            "status": "pass",
            "iterations": iterations_run,
            "corrections": all_corrections,
        }
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
                f"Ceiling guard (ADM cycle {ctx.adm_cycle + 1}): "
                f"pull-down failed for {len(pull_down_errors)} track(s); "
                "see stage output"
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


async def _stage_mastering_samples(ctx: MasterAlbumCtx) -> str | None:
    """Stage 5.5: Codec preview (.aac.m4a) + mono fold-down QC.

    Reads ctx: audio_dir, mastered_files, genre, loop, warnings
    Sets ctx:  (appends to ctx.warnings; never sets new ctx fields)
    Returns: None on pass/warn, failure JSON on mono fold hard-fail.
    """
    from tools.mastering.master_tracks import GENRE_PRESETS, _PRESET_DEFAULTS

    assert ctx.audio_dir is not None

    if ctx.genre and ctx.genre.lower() in GENRE_PRESETS:
        sample_cfg: dict[str, Any] = dict(GENRE_PRESETS[ctx.genre.lower()])
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

    samples_dir = ctx.audio_dir / "mastering_samples"
    samples_stage: dict[str, Any] = {
        "status": "pass",
        "codec_preview_enabled": codec_enabled,
        "mono_fold_enabled": monofold_enabled,
        "output_dir": str(samples_dir),
    }

    if codec_enabled or monofold_enabled:
        samples_dir.mkdir(exist_ok=True)

    if codec_enabled:
        from tools.mastering.codec_preview import CodecPreviewError, render_aac_preview

        codec_results: list[dict[str, Any]] = []
        codec_errors: list[str] = []
        for wav in ctx.mastered_files:
            out_path = samples_dir / f"{wav.stem}.aac.m4a"
            try:
                info = await ctx.loop.run_in_executor(
                    None, render_aac_preview, wav, out_path, codec_bitrate
                )
                codec_results.append({
                    "track": wav.name,
                    "output_path": info["output_path"],
                    "bitrate_kbps": info["bitrate_kbps"],
                })
            except CodecPreviewError as e:
                codec_errors.append(f"{wav.name}: {e}")
                ctx.warnings.append(f"Codec preview {wav.name}: {e}")
        samples_stage["codec_previews"] = codec_results
        if codec_errors:
            samples_stage["codec_errors"] = codec_errors

    if monofold_enabled:
        import soundfile as sf
        from tools.mastering.mono_fold import mono_fold_metrics
        from tools.mastering.mono_fold_report import render_mono_fold_markdown

        def _do_mono_fold(wav_path: Path) -> dict[str, Any]:
            import numpy as _np
            data, rate = sf.read(str(wav_path))
            if data.ndim == 1:
                data = _np.column_stack([data, data])
            metrics = mono_fold_metrics(data, rate, thresholds=monofold_thresholds)
            stem = wav_path.stem
            sample_filename = f"{stem}.mono.wav" if monofold_write_audio else None
            if sample_filename:
                sf.write(
                    str(samples_dir / sample_filename),
                    metrics["mono_audio"], rate, subtype="PCM_24",
                )
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
        for wav in ctx.mastered_files:
            mono_results.append(
                await ctx.loop.run_in_executor(None, _do_mono_fold, wav)
            )

        mono_passed = sum(1 for r in mono_results if r["verdict"] == "PASS")
        mono_warned = sum(1 for r in mono_results if r["verdict"] == "WARN")
        mono_failed = sum(1 for r in mono_results if r["verdict"] == "FAIL")

        for r in mono_results:
            if r["verdict"] == "WARN":
                ctx.warnings.append(
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
            ctx.stages["mastering_samples"] = samples_stage
            return _safe_json({
                "album_slug": ctx.album_slug,
                "stage_reached": "mastering_samples",
                "stages": ctx.stages,
                "settings": ctx.settings,
                "warnings": ctx.warnings,
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

    ctx.stages["mastering_samples"] = samples_stage
    return None


async def _stage_post_qc(ctx: MasterAlbumCtx) -> str | None:
    """Stage 6: Technical QC on mastered files (all checks enabled).

    Reads ctx: mastered_files, loop
    Sets ctx:  (appends to ctx.warnings)
    Returns: None on pass/warn, failure JSON if any track FAILs.
    """
    from tools.mastering.qc_tracks import qc_track

    post_qc_results = []
    for wav in ctx.mastered_files:
        result = await ctx.loop.run_in_executor(None, qc_track, str(wav), None)
        post_qc_results.append(result)

    post_passed = sum(1 for r in post_qc_results if r["verdict"] == "PASS")
    post_warned = sum(1 for r in post_qc_results if r["verdict"] == "WARN")
    post_failed = sum(1 for r in post_qc_results if r["verdict"] == "FAIL")

    for r in post_qc_results:
        for check_name, check_info in r["checks"].items():
            if check_info["status"] == "WARN":
                ctx.warnings.append(
                    f"Post-QC {r['filename']}: {check_name} WARN — {check_info['detail']}"
                )

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
        ctx.stages["post_qc"] = {
            "status": "fail",
            "passed": post_passed,
            "warned": post_warned,
            "failed": post_failed,
            "verdict": "FAILURES FOUND",
        }
        return _safe_json({
            "album_slug": ctx.album_slug,
            "stage_reached": "post_qc",
            "stages": ctx.stages,
            "settings": ctx.settings,
            "warnings": ctx.warnings,
            "failed_stage": "post_qc",
            "failure_detail": {
                "tracks_failed": [r["filename"] for r in failed_tracks],
                "details": fail_details,
            },
        })

    # ── LRA floor check (spec step 10: LRA ≥ genre floor, hard fail) ─────────
    lra_floor = (
        ctx.preset_dict.get("coherence_lra_floor_lu")
        if ctx.preset_dict is not None
        else None
    )
    if lra_floor is not None:
        lra_violations = [
            {
                "filename": r["filename"],
                "lra_lu": r.get("short_term_range", float("inf")),
                "floor_lu": lra_floor,
            }
            for r in ctx.verify_results
            if r.get("short_term_range", float("inf")) < lra_floor
        ]
        if lra_violations:
            ctx.stages["post_qc"] = {
                "status": "fail",
                "passed": post_passed,
                "warned": post_warned,
                "failed": post_failed,
                "verdict": "LRA FLOOR VIOLATION",
            }
            return _safe_json({
                "album_slug": ctx.album_slug,
                "stage_reached": "post_qc",
                "stages": ctx.stages,
                "settings": ctx.settings,
                "warnings": ctx.warnings,
                "failed_stage": "post_qc",
                "failure_detail": {
                    "reason": (
                        f"LRA floor violation: {len(lra_violations)} track(s) "
                        f"below floor of {lra_floor} LU"
                    ),
                    "lra_floor_violations": lra_violations,
                },
            })

    ctx.stages["post_qc"] = {
        "status": "pass",
        "passed": post_passed,
        "warned": post_warned,
        "failed": 0,
        "verdict": "ALL PASS" if post_warned == 0 else "WARNINGS",
    }
    return None


async def _stage_archival(ctx: MasterAlbumCtx) -> str | None:
    """Stage 6.5: Write 32-bit float archival copies (opt-in).

    Reads ctx: audio_dir, mastered_files, targets
    Sets ctx:  (nothing — archival output is filesystem-side only)
    Returns: None always (archival errors go to warnings, never halt).
    """
    if not ctx.targets.get("archival_enabled"):
        return None

    import soundfile as _sf_archival
    from tools.mastering.archival import prune_archival_orphans

    assert ctx.audio_dir is not None
    archival_dir = ctx.audio_dir / "archival"
    archival_dir.mkdir(exist_ok=True)
    mastered_names = {p.name for p in ctx.mastered_files}
    pruned = prune_archival_orphans(archival_dir, mastered_names)

    archived = 0
    archive_errors: list[str] = []
    for mastered_path in ctx.mastered_files:
        arch_path = archival_dir / mastered_path.name
        try:
            data, rate = _sf_archival.read(str(mastered_path), dtype="float32")
            _sf_archival.write(str(arch_path), data, rate, subtype="FLOAT")
            archived += 1
        except Exception as exc:
            archive_errors.append(f"{mastered_path.name}: {exc}")

    ctx.stages["archival"] = {
        "status": "pass" if not archive_errors else "warn",
        "count": archived,
        "pruned": pruned or None,
        "output_dir": str(archival_dir),
        "errors": archive_errors or None,
    }
    return None


async def _stage_layout(ctx: MasterAlbumCtx) -> str | None:
    """Stage 6.7: Write LAYOUT.md with per-transition defaults (#290 step 7).

    Reads ctx: album_slug, audio_dir, mastered_files, warnings
    Sets ctx:  (nothing — layout output is filesystem-side only)
    Returns: None always (write errors go to warnings, never halt).
    """
    assert ctx.audio_dir is not None

    layout_frontmatter = None
    try:
        _state_albums = (_shared.cache.get_state() or {}).get("albums", {})
        _album_state = _state_albums.get(_normalize_slug(ctx.album_slug), {})
        layout_frontmatter = _album_state.get("layout")
    except Exception as _layout_state_exc:
        logger.debug(
            "Layout: could not read state.albums[%s].layout — %s.",
            ctx.album_slug, _layout_state_exc,
        )

    default_transition = "gap"
    if isinstance(layout_frontmatter, dict):
        dt = layout_frontmatter.get("default_transition")
        if dt in ("gap", "gapless"):
            default_transition = dt

    prior_transitions: list[dict[str, Any]] | None = None
    layout_path = ctx.audio_dir / "LAYOUT.md"
    if layout_path.is_file():
        prior_transitions = _parse_layout_yaml(
            layout_path.read_text(encoding="utf-8")
        )

    layout_stage: dict[str, Any] = {
        "status": "pass",
        "path": str(ctx.audio_dir / "LAYOUT.md"),
        "default_transition": default_transition,
        "transition_count": 0,
    }
    try:
        track_filenames = [p.name for p in ctx.mastered_files]
        transitions = _layout_compute_transitions(
            track_filenames,
            default_transition=default_transition,
            prior_transitions=prior_transitions,
        )
        layout_md = _layout_render_markdown(ctx.album_slug, transitions)
        atomic_write_text(ctx.audio_dir / "LAYOUT.md", layout_md)
        layout_stage["transition_count"] = len(transitions)
    except (LayoutError, OSError) as exc:
        layout_stage["status"] = "warn"
        layout_stage["error"] = str(exc)
        ctx.warnings.append(f"Layout emitter: {exc}")

    ctx.stages["layout"] = layout_stage
    return None


async def _stage_status_update(ctx: MasterAlbumCtx) -> str | None:
    """Stage 7: Transition Generated → Final tracks; advance album to Complete.

    Reads ctx: album_slug, warnings
    Sets ctx:  (appends to ctx.warnings on errors; no new ctx fields)
    Returns: None always (status errors go to warnings, never halt).
    """
    from tools.state.indexer import write_state
    from tools.state.parsers import parse_track_file

    state = _shared.cache.get_state_ref()
    albums = state.get("albums", {})
    normalized_album = _normalize_slug(ctx.album_slug)
    album_data = albums.get(normalized_album)

    tracks_updated = 0
    status_errors: list[str] = []
    album_status: str | None = None

    if album_data:
        tracks = album_data.get("tracks", {})
        for track_slug, track_info in tracks.items():
            current_track_status = track_info.get("status", TRACK_NOT_STARTED)
            if current_track_status.lower() == TRACK_FINAL.lower():
                continue
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
                    updated_text = (
                        text[:match.start()] + new_row + text[match.end():]
                    )
                    track_path.write_text(updated_text, encoding="utf-8")
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

        all_final = all(
            t.get("status", "").lower() == TRACK_FINAL.lower()
            for t in tracks.values()
        )
        # Gate album → Complete on ALBUM_SIGNATURE.yaml existing — otherwise a
        # later "Released" mark would halt the next master_album run at
        # freeze_decision (Released + missing signature). signature_persist
        # runs BEFORE this stage in the orchestrator, so the file is on disk
        # by the time we get here on the happy path.
        signature_present = (
            ctx.audio_dir is not None
            and (ctx.audio_dir / SIGNATURE_FILENAME).is_file()
        )
        if all_final and not signature_present:
            status_errors.append(
                f"Album not advanced to {ALBUM_COMPLETE}: "
                f"{SIGNATURE_FILENAME} is missing — see signature_persist warnings"
            )
        if all_final and signature_present:
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
                            updated_text = (
                                text[:match.start()] + new_row + text[match.end():]
                            )
                            readme_path.write_text(updated_text, encoding="utf-8")
                            album_data["status"] = ALBUM_COMPLETE
                            album_status = ALBUM_COMPLETE
                    except Exception as e:
                        status_errors.append(f"Error updating album status: {e}")

        try:
            write_state(state)
        except Exception as e:
            status_errors.append(f"Cache write failed: {e}")
    else:
        status_errors.append(f"Album '{ctx.album_slug}' not found in state cache")

    for err_msg in status_errors:
        ctx.warnings.append(f"Status update: {err_msg}")

    ctx.stages["status_update"] = {
        "status": "pass",
        "tracks_updated": tracks_updated,
        "album_status": album_status,
        "errors": status_errors if status_errors else None,
    }
    return None


async def _stage_signature_persist(ctx: MasterAlbumCtx) -> str | None:
    """Stage 7.5: Write ALBUM_SIGNATURE.yaml (#290 phase 4).

    Reads ctx: album_slug, audio_dir, analysis_results, anchor_result,
               frozen_signature, targets, preset_dict, source_subfolder,
               warnings
    Sets ctx:  (appends to ctx.warnings on error; no new ctx fields)
    Returns: None always (errors go to warnings, never halt).
    """
    try:
        _plugin_version = _read_plugin_version()

        assert ctx.audio_dir is not None

        if ctx.frozen_signature is not None:
            _frozen_targets = ctx.frozen_signature.get("delivery_targets") or {}
            _frozen_tolerances = ctx.frozen_signature.get("tolerances") or {}
            _lra_target_lu = _frozen_targets.get("lra_target_lu")
            if _lra_target_lu is None:
                _lra_target_lu = (
                    ctx.preset_dict.get("genre_ideal_lra_lu")
                    if ctx.preset_dict else None
                )
            _tolerances = {
                k: _frozen_tolerances.get(k)
                for k in (
                    "coherence_stl_95_lu", "coherence_lra_floor_lu",
                    "coherence_low_rms_db", "coherence_vocal_rms_db",
                )
                if _frozen_tolerances.get(k) is not None
            }
            if not _tolerances:
                _tolerances = {
                    k: ctx.preset_dict.get(k)
                    for k in (
                        "coherence_stl_95_lu", "coherence_lra_floor_lu",
                        "coherence_low_rms_db", "coherence_vocal_rms_db",
                    )
                    if ctx.preset_dict is not None and ctx.preset_dict.get(k) is not None
                }
        else:
            _lra_target_lu = (
                ctx.preset_dict.get("genre_ideal_lra_lu")
                if ctx.preset_dict else None
            )
            _tolerances = {
                k: ctx.preset_dict.get(k)
                for k in (
                    "coherence_stl_95_lu", "coherence_lra_floor_lu",
                    "coherence_low_rms_db", "coherence_vocal_rms_db",
                )
                if ctx.preset_dict is not None and ctx.preset_dict.get(k) is not None
            }

        sig = build_signature(
            ctx.analysis_results,
            delivery_targets={
                "target_lufs":        ctx.targets.get("target_lufs"),
                "tp_ceiling_db":      ctx.targets.get("ceiling_db"),
                "lra_target_lu":      _lra_target_lu,
                "output_bits":        ctx.targets.get("output_bits"),
                "output_sample_rate": ctx.targets.get("output_sample_rate"),
            },
            tolerances=_tolerances,
        )
        anchor_idx = ctx.anchor_result.get("selected_index")
        anchor_track_sig: dict[str, Any] | None = None
        anchor_filename: str | None = None
        if anchor_idx is not None and 1 <= anchor_idx <= len(sig["tracks"]):
            row = sig["tracks"][anchor_idx - 1]
            anchor_filename = row.get("filename")
            anchor_track_sig = {
                k: row.get(k)
                for k in ("stl_95", "low_rms", "vocal_rms",
                          "short_term_range", "lufs", "peak_db")
            }

        if ctx.frozen_signature is not None:
            frozen_anchor_block = ctx.frozen_signature.get("anchor") or {}
            payload: dict[str, Any] = {
                "album_slug":       ctx.album_slug,
                "anchor":           dict(frozen_anchor_block),
                "album_median":     sig["album"]["median"],
                "delivery_targets": sig["album"].get("delivery_targets", {}),
                "tolerances":       sig["album"].get("tolerances", {}),
                "pipeline": {
                    "polish_subfolder":      ctx.source_subfolder or None,
                    "source_sample_rate":    ctx.targets.get("source_sample_rate"),
                    "upsampled_from_source": bool(ctx.targets.get("upsampled_from_source")),
                },
            }
        else:
            payload = {
                "album_slug":       ctx.album_slug,
                "anchor": {
                    "index":     anchor_idx,
                    "filename":  anchor_filename,
                    "method":    ctx.anchor_result.get("method"),
                    "score":     None,
                    "signature": anchor_track_sig,
                },
                "album_median":     sig["album"]["median"],
                "delivery_targets": sig["album"].get("delivery_targets", {}),
                "tolerances":       sig["album"].get("tolerances", {}),
                "pipeline": {
                    "polish_subfolder":      ctx.source_subfolder or None,
                    "source_sample_rate":    ctx.targets.get("source_sample_rate"),
                    "upsampled_from_source": bool(ctx.targets.get("upsampled_from_source")),
                },
            }
            if anchor_idx is not None:
                for s in ctx.anchor_result.get("scores", []) or []:
                    if s.get("index") == anchor_idx:
                        payload["anchor"]["score"] = s.get("score")
                        break

        def _coerce_numeric(v: Any) -> Any:
            if hasattr(v, "item"):
                return v.item()
            raise TypeError(
                f"signature payload contains unserializable "
                f"{type(v).__name__}: {v!r}"
            )

        payload = json.loads(json.dumps(payload, default=_coerce_numeric))
        sig_path = write_signature_file(
            ctx.audio_dir, payload, plugin_version=_plugin_version,
        )
        ctx.stages["signature_persist"] = {"status": "pass", "path": str(sig_path)}
    except (SignaturePersistenceError, OSError, TypeError) as exc:
        ctx.warnings.append(f"Signature persist: {exc}")
        ctx.stages["signature_persist"] = {"status": "warn", "error": str(exc)}
    return None


async def _stage_adm_validation(ctx: MasterAlbumCtx) -> str | None:
    """Stage 5.5: ADM inter-sample clip check via AAC encode+decode (#290 step 9).

    Encodes each mastered WAV to AAC, decodes back, scans decoded PCM for
    samples above the true-peak ceiling. Halts if clips found; warns (never
    halts) if the encoder subprocess fails.

    Reads ctx: mastered_files, audio_dir, targets (ceiling_db, adm_aac_encoder),
               album_slug, warnings
    Sets ctx:  adm_validation_results, stages["adm_validation"]
    Returns: None on pass/warn, failure JSON if clips found.
    """
    assert ctx.audio_dir is not None

    ceiling_db = float(ctx.targets.get("ceiling_db", -1.0))
    encoder = str(ctx.targets.get("adm_aac_encoder", "aac"))

    results: list[dict[str, Any]] = []
    encoder_errors: list[str] = []

    for wav in ctx.mastered_files:
        try:
            r = await ctx.loop.run_in_executor(
                None,
                functools.partial(
                    _adm_check_fn, wav,
                    encoder=encoder, ceiling_db=ceiling_db, bitrate_kbps=256,
                ),
            )
            results.append(r)
        except ADMValidationError as exc:
            encoder_errors.append(f"{wav.name}: {exc}")

    ctx.adm_validation_results = results

    # Write ADM_VALIDATION.md regardless of outcome (even partial)
    encoder_used = encoder
    if results:
        encoder_used = results[0].get("encoder_used", encoder)
    if not results:
        ctx.notices.append("ADM validation skipped — no results to write")
    else:
        try:
            md = render_adm_validation_markdown(
                ctx.album_slug, results,
                encoder_used=encoder_used, ceiling_db=ceiling_db,
            )
            atomic_write_text(ctx.audio_dir / "ADM_VALIDATION.md", md)
        except Exception as exc:
            ctx.warnings.append(f"ADM sidecar write: {exc}")

    # Encoder errors → warn but never halt (ffmpeg may not be installed)
    if encoder_errors:
        for e in encoder_errors:
            ctx.notices.append(f"ADM validation skipped: {e}")
        ctx.stages["adm_validation"] = {
            "status": "warn",
            "reason": "encoder errors — see notices",
            "errors": encoder_errors,
            "clips_found": False,
        }
        return None

    clips_found = [r for r in results if r.get("clips_found")]
    if clips_found:
        ctx.stages["adm_validation"] = {
            "status": "fail",
            "clips_found": True,
            "tracks_checked": len(results),
            "tracks_with_clips": len(clips_found),
            "encoder_used": encoder_used,
        }
        return _safe_json({
            "album_slug": ctx.album_slug,
            "stage_reached": "adm_validation",
            "stages": ctx.stages,
            "settings": ctx.settings,
            "warnings": ctx.warnings,
            "failed_stage": "adm_validation",
            "failure_detail": {
                "reason": "inter-sample peaks detected after AAC encode/decode",
                "encoder_used": encoder_used,
                "ceiling_db": ceiling_db,
                "clips_retry_eligible": True,
                "adm_cycles": ctx.adm_cycle + 1,
                "tracks_with_clips": [
                    {"filename": r["filename"], "clip_count": r["clip_count"],
                     "peak_db_decoded": r["peak_db_decoded"]}
                    for r in clips_found
                ],
                "suggestion": (
                    "Tighten true-peak ceiling by 0.5 dB and re-master, "
                    "or set mastering.true_peak_ceiling: -1.5 in config.yaml."
                ),
            },
        })

    ctx.stages["adm_validation"] = {
        "status": "pass",
        "clips_found": False,
        "tracks_checked": len(results),
        "encoder_used": encoder_used,
        "ceiling_db": ceiling_db,
    }
    return None


async def _stage_metadata(ctx: MasterAlbumCtx) -> str | None:
    """Stage 6.6: Embed ID3v2.4 metadata into mastered WAV delivery files (#290).

    Reads artist, copyright, and label from config. Reads album name and
    track titles from state cache. All fields optional — missing fields are
    silently skipped. Errors go to ctx.warnings; this stage never halts.

    Reads ctx: album_slug, mastered_files, warnings
    Sets ctx:  stages["metadata"]
    Returns: None always.
    """
    from tools.shared.config import load_config

    # --- resolve config metadata ---
    config = load_config() or {}
    artist_cfg = config.get("artist") or {}
    artist_name = str(artist_cfg.get("name") or "")
    copyright_text = str(artist_cfg.get("copyright_holder") or artist_name)
    label = str(artist_cfg.get("label") or artist_name)

    # --- resolve track titles from state cache ---
    state_albums = (_shared.cache.get_state() or {}).get("albums", {})
    album_data = state_albums.get(_normalize_slug(ctx.album_slug)) or {}
    album_name = album_data.get("name") or ctx.album_slug
    release_date = str(album_data.get("release_date") or "")
    # TDRC requires YYYY; reject malformed values ("15/06/2026", "unknown").
    year = ""
    year_match = re.match(r"^(\d{4})", release_date)
    if year_match:
        year = year_match.group(1)
    # TCON: spec (#290 metadata table) sources genre from the album path
    # segment (albums/[genre]/[album]). ctx.genre (the master_album arg) acts
    # as a user override when explicitly passed.
    genre = ctx.genre or ""
    if not genre:
        album_path = album_data.get("path") or ""
        if album_path:
            genre = Path(album_path).parent.name
    album_upc = str(album_data.get("upc") or "")
    state_tracks: dict[str, Any] = album_data.get("tracks") or {}

    embed_count = 0
    embed_errors: list[str] = []

    for wav in ctx.mastered_files:
        stem = wav.stem
        track_info = state_tracks.get(stem) or {}
        title = str(track_info.get("title") or stem)
        track_number = ""
        match = re.match(r"^(\d+)", stem)
        if match:
            track_number = str(int(match.group(1)))
        isrc = str(track_info.get("isrc") or "")

        try:
            await ctx.loop.run_in_executor(
                None,
                functools.partial(
                    _embed_wav_metadata_fn,
                    wav,
                    title=title,
                    artist=artist_name,
                    album=album_name,
                    track_number=track_number,
                    year=year,
                    genre=genre,
                    copyright_text=copyright_text,
                    label=label,
                    isrc=isrc,
                    upc=album_upc,
                ),
            )
            embed_count += 1
        except (MetadataEmbedError, OSError) as exc:
            embed_errors.append(f"{wav.name}: {exc}")

    for e in embed_errors:
        ctx.warnings.append(f"Metadata embed: {e}")

    ctx.stages["metadata"] = {
        "status": "warn" if embed_errors else "pass",
        "embedded": embed_count,
        "errors": embed_errors or None,
    }
    return None
