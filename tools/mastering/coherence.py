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
    """Classify each track against the coherence tolerance bands.

    Args:
        deltas: Output of ``album_signature.compute_anchor_deltas``.
        analysis_results: Original ``analyze_track`` dicts (for
            absolute-value checks like ``lra_floor`` that don't fit
            the delta-from-anchor pattern).
        tolerances: Output of ``load_tolerances``.
        anchor_index_1based: 1-based track number of the anchor.
            Anchor's own row is returned with empty violations.

    Returns:
        List of classification dicts — one per track, in track-number
        order. See the phase-3b plan for the full shape.
    """
    if len(deltas) != len(analysis_results):
        raise ValueError(
            f"deltas length ({len(deltas)}) != analysis_results length "
            f"({len(analysis_results)})"
        )

    out: list[dict[str, Any]] = []
    for delta, track in zip(deltas, analysis_results):
        idx = delta["index"]
        is_anchor = (idx == anchor_index_1based)
        row: dict[str, Any] = {
            "index":       idx,
            "filename":    delta.get("filename") or track.get("filename"),
            "is_anchor":   is_anchor,
            "is_outlier":  False,
            "violations":  [],
        }

        if is_anchor:
            out.append(row)
            continue

        # LUFS — correctable in MVP
        row["violations"].append(_delta_check(
            metric="lufs",
            delta=delta.get("delta_lufs"),
            tolerance=tolerances["lufs_tolerance_lu"],
            correctable=True,
        ))
        # STL-95 — not correctable
        row["violations"].append(_delta_check(
            metric="stl_95",
            delta=delta.get("delta_stl_95"),
            tolerance=tolerances["coherence_stl_95_lu"],
            correctable=False,
        ))
        # LRA floor — absolute value check, not delta
        row["violations"].append(_floor_check(
            metric="lra_floor",
            value=track.get("short_term_range"),
            floor=tolerances["coherence_lra_floor_lu"],
        ))
        # low-RMS — not correctable
        row["violations"].append(_delta_check(
            metric="low_rms",
            delta=delta.get("delta_low_rms"),
            tolerance=tolerances["coherence_low_rms_db"],
            correctable=False,
        ))
        # vocal-RMS — not correctable
        row["violations"].append(_delta_check(
            metric="vocal_rms",
            delta=delta.get("delta_vocal_rms"),
            tolerance=tolerances["coherence_vocal_rms_db"],
            correctable=False,
        ))

        row["is_outlier"] = any(
            v["severity"] == "outlier" for v in row["violations"]
        )
        out.append(row)
    return out


def _delta_check(*, metric: str, delta: float | None, tolerance: float,
                 correctable: bool) -> dict[str, Any]:
    if delta is None:
        return {
            "metric":      metric,
            "delta":       None,
            "tolerance":   tolerance,
            "severity":    "missing",
            "correctable": False,
        }
    severity = "outlier" if abs(float(delta)) > float(tolerance) else "ok"
    return {
        "metric":      metric,
        "delta":       float(delta),
        "tolerance":   tolerance,
        "severity":    severity,
        "correctable": correctable if severity == "outlier" else False,
    }


def _floor_check(*, metric: str, value: float | None, floor: float) -> dict[str, Any]:
    if value is None:
        return {
            "metric":      metric,
            "value":       None,
            "floor":       floor,
            "severity":    "missing",
            "correctable": False,
        }
    severity = "outlier" if float(value) < float(floor) else "ok"
    return {
        "metric":      metric,
        "value":       float(value),
        "floor":       floor,
        "severity":    severity,
        "correctable": False,
    }


def build_correction_plan(
    classifications: list[dict[str, Any]],
    analysis_results: list[dict[str, Any]],
    anchor_index_1based: int,
) -> dict[str, Any]:
    """Build a per-track correction plan targeting LUFS outliers.

    Args:
        classifications: Output of ``classify_outliers``.
        analysis_results: Original ``analyze_track`` dicts (used for
            anchor LUFS lookup).
        anchor_index_1based: 1-based track number of the anchor.

    Returns:
        Dict with:
          anchor_index: 1-based anchor index
          anchor_lufs:  measured LUFS of the anchor (ground truth)
          corrections:  list of per-track correction dicts
          skipped:      list of {index, filename, reason} for the
                        anchor + clean tracks
    """
    if not (1 <= anchor_index_1based <= len(analysis_results)):
        raise ValueError(
            f"anchor_index_1based={anchor_index_1based} out of range "
            f"[1, {len(analysis_results)}]"
        )

    anchor_analysis = analysis_results[anchor_index_1based - 1]
    anchor_lufs = float(anchor_analysis.get("lufs", 0.0))

    corrections: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for cls in classifications:
        if cls["is_anchor"]:
            skipped.append({
                "index":    cls["index"],
                "filename": cls.get("filename"),
                "reason":   "is_anchor",
            })
            continue

        lufs_violation = next(
            (v for v in cls["violations"]
             if v["metric"] == "lufs" and v["severity"] == "outlier"),
            None,
        )
        non_lufs_outliers = [
            v for v in cls["violations"]
            if v["metric"] != "lufs" and v["severity"] == "outlier"
        ]

        if lufs_violation is not None:
            corrections.append({
                "index":                cls["index"],
                "filename":             cls.get("filename"),
                "correctable":          True,
                "corrected_target_lufs": anchor_lufs,
                "reason": (
                    f"LUFS outlier: delta={lufs_violation['delta']:+.2f}, "
                    f"tolerance=±{lufs_violation['tolerance']:.2f}"
                ),
            })
        elif non_lufs_outliers:
            metrics = ", ".join(sorted({v["metric"] for v in non_lufs_outliers}))
            corrections.append({
                "index":       cls["index"],
                "filename":    cls.get("filename"),
                "correctable": False,
                "reason": (
                    f"Only non-LUFS violations ({metrics}) — MVP scope "
                    f"skips; revisit when compression-ratio correction lands."
                ),
            })
        else:
            skipped.append({
                "index":    cls["index"],
                "filename": cls.get("filename"),
                "reason":   "no_violations",
            })

    return {
        "anchor_index":  anchor_index_1based,
        "anchor_lufs":   anchor_lufs,
        "corrections":   corrections,
        "skipped":       skipped,
    }
