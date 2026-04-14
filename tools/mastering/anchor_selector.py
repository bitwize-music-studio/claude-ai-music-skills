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
