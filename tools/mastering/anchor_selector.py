"""Album-mastering anchor selector (#290 pipeline step 2).

Pure-Python scoring — no I/O, no MCP coupling. The handler in
``servers/bitwize-music-server/handlers/processing/audio.py`` calls
``select_anchor`` after Stage 2 (Analysis) with the list of
``analyze_track`` results plus the resolved genre preset.

Selection strategy (in order):
1. ``override_index`` supplied by caller (from album README
   frontmatter ``anchor_track``). Validated against the track list.
2. Composite scoring: ``0.4 * mix_quality + 0.4 * representativeness
   − 1.0 * ceiling_penalty`` (formula from issue #290).
3. Deterministic tie-breaker when top two scores differ by < 0.05:
   lowest 1-based index wins.

Tracks missing any of ``stl_95`` / ``low_rms`` / ``vocal_rms`` /
``short_term_range`` are considered ineligible and surface with
``eligible: False`` + a ``reason`` in the per-track score list.
"""

from __future__ import annotations

from typing import Any

import numpy as np

BANDS = ("sub_bass", "bass", "low_mid", "mid", "high_mid", "high", "air")
SIGNATURE_KEYS = ("stl_95", "short_term_range", "low_rms", "vocal_rms")
TIE_BREAKER_EPSILON = 0.05


def _spectral_match_score(band_energy: dict[str, float],
                          reference: dict[str, float]) -> float:
    """Euclidean distance between 7-band vectors, mapped to (0, 1].

    Bands are percentages of total spectral energy (sum ≈ 100). We divide
    by 100 so the distance lives in [0, √7], then map with 1/(1+d).
    """
    track_vec = np.array([band_energy[b] / 100.0 for b in BANDS])
    ref_vec   = np.array([reference[b]    / 100.0 for b in BANDS])
    distance = float(np.linalg.norm(track_vec - ref_vec))
    return 1.0 / (1.0 + distance)


def _album_medians(tracks: list[dict[str, Any]]) -> dict[str, float | None]:
    """Median of each signature key across tracks with finite values.

    Returns ``None`` for a key when every track's value is ``None``.
    """
    medians: dict[str, float | None] = {}
    for key in SIGNATURE_KEYS:
        values = [t[key] for t in tracks if t.get(key) is not None]
        medians[key] = float(np.median(values)) if values else None
    return medians


def _mix_quality_score(track: dict[str, Any],
                       spectral_reference: dict[str, float],
                       genre_ideal_lra: float) -> float:
    """Combined LRA-match × spectral-match score, ∈ (0, 1]."""
    lra = track.get("short_term_range")
    if lra is None:
        return 0.0
    lra_match = 1.0 / (1.0 + abs(float(lra) - float(genre_ideal_lra)))
    spectral = _spectral_match_score(track["band_energy"], spectral_reference)
    return lra_match * spectral


def _representativeness_score(track: dict[str, Any],
                              medians: dict[str, float | None]) -> float:
    """How close track's signature sits to the album median across SIGNATURE_KEYS."""
    total = 0.0
    for key in SIGNATURE_KEYS:
        median = medians.get(key)
        value = track.get(key)
        if median is None or value is None:
            continue
        denom = abs(median) if abs(median) > 1e-6 else 1.0
        total += abs(float(value) - float(median)) / denom
    return 1.0 / (1.0 + total)


def _ceiling_penalty_score(peak_db: float) -> float:
    """Penalty for tracks pinned near 0 dBFS. 0 at ≤ -3 dB, 1 at 0 dBFS."""
    return max(0.0, min(1.0, (float(peak_db) - (-3.0)) / 3.0))
