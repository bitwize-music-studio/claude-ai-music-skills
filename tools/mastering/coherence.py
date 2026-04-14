"""Album coherence classification + correction planning (#290 phase 3b).

Pure-Python module — no I/O, no MCP coupling. Consumed by the
``album_coherence_check`` / ``album_coherence_correct`` handlers in
``servers/bitwize-music-server/handlers/processing/audio.py``.

Depends only on phase 3a's ``album_signature.AGGREGATE_KEYS`` /
``compute_anchor_deltas`` output shape and the phase 1b analyzer fields.

Scope limit (MVP): ``build_correction_plan`` marks only LUFS outliers
as correctable. STL-95 / LRA / RMS violations are reported by
``classify_outliers`` but deferred for correction to a later phase —
fixing those requires per-track compression/EQ adjustment that this
phase intentionally doesn't ship.
"""

from __future__ import annotations

from typing import Any

DEFAULTS: dict[str, float] = {
    "coherence_stl_95_lu":    0.5,
    "coherence_lra_floor_lu": 1.0,
    "coherence_low_rms_db":   2.0,
    "coherence_vocal_rms_db": 2.0,
    # Hardcoded — matches master_album Stage 5 verify spec. Not a preset field.
    "lufs_tolerance_lu":      0.5,
}


def load_tolerances(preset: dict[str, Any] | None) -> dict[str, float]:
    """Return effective tolerance-band dict, merging preset on top of defaults.

    ``lufs_tolerance_lu`` is always the hardcoded default (0.5) — preset
    values for that key are ignored. All other keys honor preset overrides.
    """
    out = dict(DEFAULTS)
    if preset:
        for key in (
            "coherence_stl_95_lu",
            "coherence_lra_floor_lu",
            "coherence_low_rms_db",
            "coherence_vocal_rms_db",
        ):
            if key in preset and preset[key] is not None:
                out[key] = float(preset[key])
    return out


def classify_outliers(
    deltas: list[dict[str, Any]],
    analysis_results: list[dict[str, Any]],
    tolerances: dict[str, float],
    anchor_index_1based: int,
) -> list[dict[str, Any]]:
    """Classify each track as outlier / ok / missing per metric.

    Implementation lands in Task 3.
    """
    raise NotImplementedError


def build_correction_plan(
    classifications: list[dict[str, Any]],
    analysis_results: list[dict[str, Any]],
    anchor_index_1based: int,
) -> dict[str, Any]:
    """Build per-track correction plan targeting LUFS outliers.

    Implementation lands in Task 4.
    """
    raise NotImplementedError
