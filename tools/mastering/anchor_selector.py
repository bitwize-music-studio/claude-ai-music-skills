"""Album-mastering anchor selector (#290 pipeline step 2).

Pure-Python scoring — no I/O, no MCP coupling. The handler in
``servers/bitwize-music-server/handlers/processing/audio.py`` calls
``select_anchor`` after Stage 2 (Analysis) with the list of
``analyze_track`` results plus the resolved genre preset.

Selection strategy (in order):
1. ``override_index`` supplied by caller (from album README
   frontmatter ``anchor_track``). It is a track number, so it is matched
   to the file whose leading digits carry that number (``03-x.wav`` is
   track 3), wherever that file sits in the list: a leftover file such
   as ``02-old-title.wav`` beside ``02-new-title.wav`` shifts the
   positions but not the numbers (#668). A number no file carries, or
   one two files share, falls through to composite scoring and says why
   in ``override_reason``. Only when no file is numbered is the number
   read as a position in the list.
2. Composite scoring: ``0.4 * mix_quality + 0.4 * representativeness
   - 1.0 * ceiling_penalty`` (formula from issue #290).
3. Deterministic tie-breaker when top two scores differ by < 0.05:
   lowest 1-based index wins.

Tracks missing any of ``stl_95`` / ``low_rms`` / ``vocal_rms`` /
``short_term_range`` are considered ineligible and surface with
``eligible: False`` + a ``reason`` in the per-track score list.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import numpy as np

BANDS = ("sub_bass", "bass", "low_mid", "mid", "high_mid", "high", "air")
SIGNATURE_KEYS = ("stl_95", "short_term_range", "low_rms", "vocal_rms")
TIE_BREAKER_EPSILON = 0.05
_TRACK_NUMBER_RE = re.compile(r"^(\d+)")


def _track_number(filename: Any) -> int | None:
    """The track number in a file name's leading digits (``03-x.wav`` → 3)."""
    if not isinstance(filename, str):
        return None
    match = _TRACK_NUMBER_RE.match(Path(filename).name)
    return int(match.group(1)) if match else None


def resolve_track_number(
    tracks: list[dict[str, Any]], number: int,
) -> tuple[int | None, str | None]:
    """The 1-based position in ``tracks`` of the file numbered ``number``.

    Returns ``(position, None)``, or ``(None, reason)`` when no file carries
    that number or more than one does. When no file in ``tracks`` is
    numbered at all, the number is read as a position, as it always was.
    """
    numbers = [_track_number(t.get("filename")) for t in tracks]
    if all(n is None for n in numbers):
        if 1 <= number <= len(tracks):
            return number, None
        return None, f"out of range [1, {len(tracks)}]"
    matches = [i + 1 for i, n in enumerate(numbers) if n == number]
    if len(matches) == 1:
        return matches[0], None
    if matches:
        names = ", ".join(str(tracks[i - 1].get("filename")) for i in matches)
        return None, f"track {number} is ambiguous: {len(matches)} files carry it ({names})"
    reason = f"no file is numbered {number}"
    if not 1 <= number <= len(tracks):
        reason += f" (out of range [1, {len(tracks)}])"
    return None, reason


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
        # Walrus-filter so mypy sees the narrowed (non-None) value in the
        # comprehension result — the double-call form left it as Any | None.
        values: list[float] = [
            float(v) for t in tracks if (v := t.get(key)) is not None
        ]
        medians[key] = float(np.median(values)) if values else None
    return medians


def _mix_quality_score(track: dict[str, Any],
                       spectral_reference: dict[str, float],
                       genre_ideal_lra: float) -> float:
    """Combined LRA-match x spectral-match score, ∈ (0, 1]."""
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


def _is_eligible(track: dict[str, Any]) -> tuple[bool, str | None]:
    for key in SIGNATURE_KEYS:
        if track.get(key) is None:
            return False, f"{key} is None (analyzer could not compute it)"
    band_energy = track.get("band_energy")
    if not band_energy:
        return False, "band_energy missing"
    missing_bands = [b for b in BANDS if b not in band_energy]
    if missing_bands:
        return False, f"band_energy missing bands: {missing_bands}"
    return True, None


def select_anchor(
    tracks: list[dict[str, Any]],
    preset: dict[str, Any],
    override_index: int | None = None,
) -> dict[str, Any]:
    """Select the anchor track for album mastering.

    Args:
        tracks: List of ``analyze_track`` result dicts, in track order
                (index 0 == track #1). Must include ``filename``,
                ``stl_95``, ``short_term_range``, ``low_rms``,
                ``vocal_rms``, ``peak_db``, ``band_energy``.
        preset: Genre preset dict; must include
                ``genre_ideal_lra_lu`` and ``spectral_reference_energy``
                (fall back to defaults.yaml shape when missing).
        override_index: Optional track number from album README
                frontmatter ``anchor_track``, matched to the file whose
                leading digits carry it (see ``resolve_track_number``).
                Values ≤ 0, and numbers no file or several files carry,
                fall through to composite scoring with ``override_reason``
                saying why.

    Returns:
        Dict — see module docstring + plan design section for shape.
        ``selected_index`` is always the 1-based position in ``tracks``;
        ``override_index`` echoes the track number the caller passed.
    """
    ideal_lra = float(preset.get("genre_ideal_lra_lu", 8.0))
    spectral_ref = preset.get("spectral_reference_energy") or {
        "sub_bass": 8.0, "bass": 18.0, "low_mid": 20.0, "mid": 25.0,
        "high_mid": 14.0, "high": 10.0, "air": 5.0,
    }
    missing_ref_bands = [b for b in BANDS if b not in spectral_ref]
    if missing_ref_bands:
        raise ValueError(
            f"spectral_reference_energy missing bands: {missing_ref_bands}"
        )

    # Normalize override: reject anything that isn't a plain int.
    # (bool is an int subclass in Python; callers should not pass True/False.)
    # Preserve the original caller-supplied value for the result dict so
    # diagnostics can show what was passed.
    original_override = override_index
    override_reason: str | None = None
    if override_index is not None and (
        not isinstance(override_index, int) or isinstance(override_index, bool)
    ):
        override_reason = (
            f"non-integer override ({override_index!r}) — treated as no override"
        )
        override_index = None

    # Override path
    if override_index is not None and override_index > 0:
        position, unresolved = resolve_track_number(tracks, override_index)
        if position is not None:
            return {
                "selected_index": position,
                "method": "override",
                "scores": [
                    {"index": i + 1,
                     "filename": t.get("filename"),
                     "score": None,
                     "eligible": None,
                     "reason": "skipped — override in effect"}
                    for i, t in enumerate(tracks)
                ],
                "override_index": override_index,
                "override_reason": None,
            }
        override_reason = f"{unresolved} — fell through to composite scoring"
    elif override_index is not None and override_index <= 0:
        override_reason = "non-positive — treated as no override"

    # Composite scoring
    eligible_tracks: list[tuple[int, dict[str, Any]]] = []
    scores: list[dict[str, Any]] = []
    for i, track in enumerate(tracks):
        ok, reason = _is_eligible(track)
        entry: dict[str, Any] = {
            "index": i + 1,
            "filename": track.get("filename"),
            "eligible": ok,
        }
        if not ok:
            entry["score"] = None
            entry["reason"] = reason
            scores.append(entry)
            continue
        eligible_tracks.append((i + 1, track))
        entry["reason"] = None
        scores.append(entry)

    if not eligible_tracks:
        return {
            "selected_index": None,
            "method": "no_eligible_tracks",
            "scores": scores,
            "override_index": original_override,
            "override_reason": override_reason,
        }

    medians = _album_medians([t for _, t in eligible_tracks])
    for entry in scores:
        if not entry["eligible"]:
            continue
        idx = entry["index"]
        track = tracks[idx - 1]
        mq = _mix_quality_score(track, spectral_ref, ideal_lra)
        rp = _representativeness_score(track, medians)
        cp = _ceiling_penalty_score(float(track.get("peak_db", 0.0)))
        composite = 0.4 * mq + 0.4 * rp - 1.0 * cp
        entry["mix_quality"] = mq
        entry["representativeness"] = rp
        entry["ceiling_penalty"] = cp
        entry["score"] = composite

    ranked = sorted(
        (e for e in scores if e["eligible"]),
        key=lambda e: (-e["score"], e["index"]),
    )
    top = ranked[0]
    method = "composite"
    if len(ranked) >= 2 and abs(ranked[0]["score"] - ranked[1]["score"]) < TIE_BREAKER_EPSILON:
        method = "tie_breaker"

    return {
        "selected_index": top["index"],
        "method": method,
        "scores": scores,
        "override_index": original_override,
        "override_reason": override_reason,
    }
