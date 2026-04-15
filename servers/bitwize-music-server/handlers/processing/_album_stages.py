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
import logging
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
