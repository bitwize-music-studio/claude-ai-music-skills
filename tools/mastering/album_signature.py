"""Album signature aggregation and anchor-delta computation (#290 phase 3a).

Pure-Python module — no I/O, no MCP coupling. The
``measure_album_signature`` handler in
``servers/bitwize-music-server/handlers/processing/audio.py`` calls
``build_signature`` on a list of ``analyze_track`` results, then
(optionally) ``compute_anchor_deltas`` once an anchor index is known.

Phase 3b (``album_coherence_check`` / ``album_coherence_correct``) will
consume the same signature dict, so this module is intentionally free
of handler-layer concerns.
"""

from __future__ import annotations

from typing import Any

import numpy as np

# Metrics that get aggregated across tracks (median/p95/min/max/range).
# ``band_energy`` is surfaced per-track only — aggregating 7-band vectors
# as independent medians loses the correlation structure that matters.
AGGREGATE_KEYS = (
    "lufs",
    "peak_db",
    "stl_95",
    "short_term_range",
    "low_rms",
    "vocal_rms",
)

# Subset required for signature-eligibility (same four keys the anchor
# selector uses — see ``tools/mastering/anchor_selector.py::SIGNATURE_KEYS``).
ELIGIBILITY_KEYS = ("stl_95", "short_term_range", "low_rms", "vocal_rms")


def _finite_values(tracks: list[dict[str, Any]], key: str) -> list[float]:
    """Collect finite, non-None values for ``key`` across all tracks."""
    out: list[float] = []
    for t in tracks:
        v = t.get(key)
        if v is None:
            continue
        try:
            vf = float(v)
        except (TypeError, ValueError):
            continue
        if not np.isfinite(vf):
            continue
        out.append(vf)
    return out


def _aggregate(values: list[float]) -> dict[str, float | None]:
    """Return median / p95 / min / max for a list of values.

    Returns a dict of ``None``s when the input is empty — callers can
    propagate "no data" without special-casing missing keys.
    """
    if not values:
        return {"median": None, "p95": None, "min": None, "max": None}
    arr = np.asarray(values, dtype=float)
    return {
        "median": float(np.median(arr)),
        "p95":    float(np.percentile(arr, 95)),
        "min":    float(arr.min()),
        "max":    float(arr.max()),
    }


def build_signature(
    analysis_results: list[dict[str, Any]],
    *,
    delivery_targets: dict[str, Any] | None = None,
    tolerances: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build per-track + album-level signature summary.

    Args:
        analysis_results: List of ``analyze_track()`` result dicts, in
            track-number order (index 0 == track #1). Dicts may have
            ``None`` values for ``stl_95`` / ``low_rms`` / ``vocal_rms``.
        delivery_targets: Optional dict of mastering delivery targets
            (``target_lufs``, ``tp_ceiling_db``, ``lra_target_lu``,
            ``output_bits``, ``output_sample_rate``). When provided, gets
            embedded under ``album.delivery_targets`` for downstream
            persistence. Only the keys present in the input dict are
            forwarded — unknown keys pass through.
        tolerances: Optional dict of coherence tolerances (e.g.
            ``coherence_stl_95_lu``). Embedded under ``album.tolerances``.

    Returns:
        Dict with ``tracks`` (per-track signature list) and ``album``
        (aggregates, plus optional ``delivery_targets`` / ``tolerances``).
    """
    tracks: list[dict[str, Any]] = []
    for i, t in enumerate(analysis_results):
        tracks.append({
            "index":              i + 1,
            "filename":           t.get("filename"),
            "duration":           t.get("duration"),
            "sample_rate":        t.get("sample_rate"),
            "lufs":               t.get("lufs"),
            "peak_db":            t.get("peak_db"),
            "stl_95":             t.get("stl_95"),
            "short_term_range":   t.get("short_term_range"),
            "low_rms":            t.get("low_rms"),
            "vocal_rms":          t.get("vocal_rms"),
            "band_energy":        t.get("band_energy"),
            "signature_meta":     t.get("signature_meta"),
        })

    album: dict[str, Any] = {
        "track_count":     len(analysis_results),
        "median":          {},
        "p95":             {},
        "min":             {},
        "max":             {},
        "range":           {},
        "eligible_count":  {},
    }
    for key in AGGREGATE_KEYS:
        vals = _finite_values(analysis_results, key)
        agg = _aggregate(vals)
        album["median"][key] = agg["median"]
        album["p95"][key]    = agg["p95"]
        album["min"][key]    = agg["min"]
        album["max"][key]    = agg["max"]
        if agg["min"] is None or agg["max"] is None:
            album["range"][key] = None
        else:
            album["range"][key] = agg["max"] - agg["min"]
    for key in ELIGIBILITY_KEYS:
        album["eligible_count"][key] = len(_finite_values(analysis_results, key))

    if delivery_targets is not None:
        album["delivery_targets"] = dict(delivery_targets)
    if tolerances is not None:
        album["tolerances"] = dict(tolerances)

    return {"tracks": tracks, "album": album}


def compute_anchor_deltas(
    analysis_results: list[dict[str, Any]],
    anchor_index_1based: int,
) -> list[dict[str, Any]]:
    """Compute per-track deltas from the anchor for every aggregate metric.

    Args:
        analysis_results: Same list of ``analyze_track`` dicts passed to
            ``build_signature``.
        anchor_index_1based: 1-based track number of the anchor. Must be
            in ``[1, len(analysis_results)]``.

    Returns:
        List of per-track delta dicts (length == len(analysis_results)).
        Anchor's own row has ``is_anchor: True`` and zeros for every delta.

    Raises:
        ValueError: if ``anchor_index_1based`` is out of range or the
            list is empty.
    """
    if not analysis_results:
        raise ValueError("analysis_results is empty")
    if not (1 <= anchor_index_1based <= len(analysis_results)):
        raise ValueError(
            f"anchor_index_1based={anchor_index_1based} out of range "
            f"[1, {len(analysis_results)}]"
        )

    anchor = analysis_results[anchor_index_1based - 1]
    out: list[dict[str, Any]] = []
    for i, t in enumerate(analysis_results):
        is_anchor = (i + 1) == anchor_index_1based
        row: dict[str, Any] = {
            "index":     i + 1,
            "filename":  t.get("filename"),
            "is_anchor": is_anchor,
        }
        for key in AGGREGATE_KEYS:
            a_val = anchor.get(key)
            t_val = t.get(key)
            if a_val is None or t_val is None:
                row[f"delta_{key}"] = None
                continue
            try:
                row[f"delta_{key}"] = float(t_val) - float(a_val)
            except (TypeError, ValueError):
                row[f"delta_{key}"] = None
        out.append(row)
    return out
