"""Album coherence classification + correction planning (#290 phase 3b).

Pure-Python module — no I/O, no MCP coupling. Consumed by the
``album_coherence_check`` / ``album_coherence_correct`` handlers in
``servers/bitwize-music-server/handlers/processing/audio.py``.

Depends only on phase 3a's ``album_signature.AGGREGATE_KEYS`` /
``compute_anchor_deltas`` output shape and the phase 1b analyzer fields.

Correction coverage:
 - LUFS deltas                → bounded gain re-master (±1.5 dB)
 - low-RMS / vocal-RMS deltas → bounded tilt-EQ (±0.5 dB) applied
   during the re-master (per #290 step 6 "≤1.5 dB gain, ≤0.5 dB tilt-EQ")
 - STL-95 / LRA violations    → surfaced by ``classify_outliers`` but
   not directly correctable (needs per-track compression changes that
   this phase intentionally does not ship)
"""

from __future__ import annotations

from typing import Any

DEFAULTS: dict[str, float] = {
    "coherence_stl_95_lu":    0.5,
    "coherence_lra_floor_lu": 1.0,
    "coherence_low_rms_db":   2.0,
    "coherence_vocal_rms_db": 2.0,
    "coherence_tilt_max_db":  0.5,
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
            "coherence_tilt_max_db",
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
        # low-RMS — correctable via tilt-EQ (spec step 6, ±0.5 dB)
        row["violations"].append(_delta_check(
            metric="low_rms",
            delta=delta.get("delta_low_rms"),
            tolerance=tolerances["coherence_low_rms_db"],
            correctable=True,
        ))
        # vocal-RMS — correctable via tilt-EQ fallback when low-RMS is clean
        row["violations"].append(_delta_check(
            metric="vocal_rms",
            delta=delta.get("delta_vocal_rms"),
            tolerance=tolerances["coherence_vocal_rms_db"],
            correctable=True,
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


# Spec #290 step 6: tilt-EQ correction bounded to ±0.5 dB.
TILT_CORRECTION_MAX_DB: float = 0.5


def _compute_tilt_db(
    violations: list[dict[str, Any]],
    max_tilt_db: float = TILT_CORRECTION_MAX_DB,
) -> tuple[float, bool, float, str | None, float | None]:
    """Derive a bounded tilt-EQ correction from spectral violations.

    Returns ``(tilt_db, clamped, raw_tilt_db, limiting_metric, delta_db)``.
    ``clamped`` is True when the raw tilt exceeded ``max_tilt_db`` and was
    capped — the stage-level coherence loop uses this to detect
    structurally unconvergent corrections (tilt can't close the gap
    regardless of how many iterations run).

    ``limiting_metric`` identifies which spectral band drove the tilt
    request (``"low_rms_db"`` or ``"vocal_rms_db"``); ``delta_db`` is the
    signed anchor-relative delta on that metric. Both are ``None`` when
    no spectral outlier fires.

    ``max_tilt_db`` is loaded from the ``coherence_tilt_max_db`` preset
    (default 0.5). Callers that don't pass it fall back to the module
    constant for backward compatibility.

    Tilt sign convention (matches ``master_tracks.apply_tilt_eq``):
      - positive tilt → cut lows, boost highs (brighter)
      - negative tilt → boost lows, cut highs (warmer)

    ``delta_low_rms`` is the primary signal (#290 calls low-end RMS the
    #1 inter-track variance source). A track with too much bass has
    ``delta_low_rms > 0`` and wants positive tilt (cut bass). Vocal-RMS
    is used as a fallback when low-RMS is clean; since the vocal band
    (1-4 kHz) sits above the 650 Hz pivot, its sign is inverted.
    """
    low = next(
        (v for v in violations
         if v["metric"] == "low_rms" and v["severity"] == "outlier"),
        None,
    )
    if low is not None and low.get("delta") is not None:
        delta = float(low["delta"])
        raw = delta
        clamped = abs(raw) > max_tilt_db
        return (
            max(-max_tilt_db, min(max_tilt_db, raw)),
            clamped,
            raw,
            "low_rms_db",
            delta,
        )

    vocal = next(
        (v for v in violations
         if v["metric"] == "vocal_rms" and v["severity"] == "outlier"),
        None,
    )
    if vocal is not None and vocal.get("delta") is not None:
        delta = float(vocal["delta"])
        raw = -delta
        clamped = abs(raw) > max_tilt_db
        return (
            max(-max_tilt_db, min(max_tilt_db, raw)),
            clamped,
            raw,
            "vocal_rms_db",
            delta,
        )

    return 0.0, False, 0.0, None, None


def build_correction_plan(
    classifications: list[dict[str, Any]],
    analysis_results: list[dict[str, Any]],
    anchor_index_1based: int,
    max_tilt_db: float | None = None,
) -> dict[str, Any]:
    """Build a per-track correction plan for LUFS + spectral outliers.

    Args:
        classifications: Output of ``classify_outliers``.
        analysis_results: Original ``analyze_track`` dicts (used for
            anchor LUFS lookup).
        anchor_index_1based: 1-based track number of the anchor.
        max_tilt_db: Clamp magnitude for tilt-EQ corrections. ``None``
            falls back to ``TILT_CORRECTION_MAX_DB`` (0.5) so direct
            callers keep working without threading the preset through.

    Returns:
        Dict with:
          anchor_index: 1-based anchor index
          anchor_lufs:  measured LUFS of the anchor (ground truth)
          corrections:  list of per-track correction dicts. Each dict
                        has ``correctable``, ``corrected_target_lufs``
                        (present when gain correction applies),
                        ``corrected_tilt_db`` (non-zero when spectral
                        correction applies, clamped to ±max_tilt_db),
                        and — when a spectral violation fires —
                        ``intended_tilt_db`` (pre-clamp raw tilt),
                        ``limiting_metric`` (``"low_rms_db"`` or
                        ``"vocal_rms_db"``), and ``spectral_delta_db``
                        (signed anchor-relative delta).
          skipped:      list of {index, filename, reason} for the
                        anchor + clean tracks
    """
    if not (1 <= anchor_index_1based <= len(analysis_results)):
        raise ValueError(
            f"anchor_index_1based={anchor_index_1based} out of range "
            f"[1, {len(analysis_results)}]"
        )

    effective_max_tilt = (
        TILT_CORRECTION_MAX_DB if max_tilt_db is None else float(max_tilt_db)
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

        violations = cls["violations"]
        lufs_violation = next(
            (v for v in violations
             if v["metric"] == "lufs" and v["severity"] == "outlier"),
            None,
        )
        spectral_violations = [
            v for v in violations
            if v["metric"] in ("low_rms", "vocal_rms")
            and v["severity"] == "outlier"
        ]
        uncorrectable_outliers = [
            v for v in violations
            if v["metric"] in ("stl_95", "lra_floor")
            and v["severity"] == "outlier"
        ]

        tilt_db = 0.0
        tilt_clamped = False
        raw_tilt_db = 0.0
        limiting_metric: str | None = None
        spectral_delta: float | None = None
        if spectral_violations:
            (
                tilt_db,
                tilt_clamped,
                raw_tilt_db,
                limiting_metric,
                spectral_delta,
            ) = _compute_tilt_db(violations, max_tilt_db=effective_max_tilt)

        if lufs_violation is not None or spectral_violations:
            reason_parts: list[str] = []
            entry: dict[str, Any] = {
                "index":        cls["index"],
                "filename":     cls.get("filename"),
                "correctable":  True,
                "tilt_clamped": tilt_clamped,
            }
            if lufs_violation is not None:
                entry["corrected_target_lufs"] = anchor_lufs
                reason_parts.append(
                    f"LUFS outlier: delta={lufs_violation['delta']:+.2f}, "
                    f"tolerance=±{lufs_violation['tolerance']:.2f}"
                )
            if spectral_violations:
                entry["corrected_tilt_db"] = tilt_db
                entry["intended_tilt_db"] = raw_tilt_db
                entry["limiting_metric"] = limiting_metric
                entry["spectral_delta_db"] = spectral_delta
                metrics = ", ".join(sorted({v["metric"] for v in spectral_violations}))
                clamp_note = " (clamped)" if tilt_clamped else ""
                reason_parts.append(
                    f"Spectral outlier ({metrics}) → tilt_db={tilt_db:+.2f}{clamp_note}"
                )
            entry["reason"] = "; ".join(reason_parts)
            corrections.append(entry)
        elif uncorrectable_outliers:
            metrics = ", ".join(sorted({v["metric"] for v in uncorrectable_outliers}))
            corrections.append({
                "index":       cls["index"],
                "filename":    cls.get("filename"),
                "correctable": False,
                "reason": (
                    f"Only uncorrectable violations ({metrics}) — "
                    f"requires per-track compression changes."
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
