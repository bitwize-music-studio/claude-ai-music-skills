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
