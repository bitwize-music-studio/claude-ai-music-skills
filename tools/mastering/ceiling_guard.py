"""Album-ceiling guard for the mastering pipeline (#290 phase 5, step 8).

Pure-Python math + a small in-place gain writer. The ceiling guard compares
each mastered track's integrated LUFS to ``album_median + 2 LU`` (the
threshold below which album-mode streaming normalization keeps the album
cohesive). Tracks above the threshold are classified:

* ``in_spec``    — at or below threshold; no action.
* ``correctable`` — 0 < overshoot <= 0.5 LU; apply scalar pull-down.
* ``halt``       — overshoot > 0.5 LU; pipeline escalates.

The 0.5 LU bound mirrors Stage 5 verification tolerance — anything larger
is a mastering error, not a coherence drift, and coherence correction
(step 6) or a fresh master is the right recovery path.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

# Threshold bounds — see #290 section "[8] album-ceiling guard".
CEILING_MARGIN_LU = 2.0      # track must stay within album_median + MARGIN.
CORRECTABLE_MAX_LU = 0.5     # overshoot beyond MARGIN that can be silently pulled down.


class CeilingGuardError(RuntimeError):
    """Raised when the ceiling guard cannot operate (bad args, missing file)."""


def compute_overshoots(tracks: list[dict[str, Any]]) -> dict[str, Any]:
    """Classify each track against the album-mode loudness ceiling.

    Args:
        tracks: List of dicts with ``filename`` (str) and ``lufs`` (float).
            Input order is preserved in the output.

    Returns:
        Dict with:

        * ``median_lufs``  — median integrated LUFS across all tracks, or
          ``None`` if ``tracks`` is empty.
        * ``threshold_lu`` — ``median_lufs + CEILING_MARGIN_LU``, or ``None``.
        * ``tracks``       — list of classification rows in input order:

              ``{filename, lufs, overshoot_lu, classification, pull_down_db}``

          ``pull_down_db`` is the negative-or-zero dB scalar to apply for
          ``correctable`` rows; ``None`` for ``in_spec`` and ``halt``.
    """
    if not tracks:
        return {"median_lufs": None, "threshold_lu": None, "tracks": []}

    lufs_arr = np.asarray([float(t["lufs"]) for t in tracks], dtype=np.float64)
    median_lufs = float(np.median(lufs_arr))
    threshold_lu = median_lufs + CEILING_MARGIN_LU

    rows: list[dict[str, Any]] = []
    for track in tracks:
        lufs = float(track["lufs"])
        overshoot = lufs - threshold_lu
        if overshoot <= 0.0:
            classification = "in_spec"
            pull_down_db: float | None = None
        elif overshoot <= CORRECTABLE_MAX_LU:
            classification = "correctable"
            pull_down_db = -overshoot
        else:
            classification = "halt"
            pull_down_db = None

        rows.append({
            "filename":      track["filename"],
            "lufs":          lufs,
            "overshoot_lu":  overshoot,
            "classification": classification,
            "pull_down_db":  pull_down_db,
        })

    return {
        "median_lufs": median_lufs,
        "threshold_lu": threshold_lu,
        "tracks": rows,
    }


def apply_pull_down_db(
    path: Path | str,
    *,
    gain_db: float,
    output_bits: int,
) -> None:
    """Apply a scalar gain to *path* in-place.

    Writes to a temp file in the same directory, fsyncs, then atomically
    replaces the original. Caller guarantees *gain_db* <= 0; positive
    gains would raise peaks and require re-limiting (not supported here).

    Args:
        path:         WAV file path.
        gain_db:      Gain to apply, in dB. Must be <= 0.
        output_bits:  16 or 24. Selects PCM_16 vs. PCM_24 output subtype.

    Raises:
        CeilingGuardError: File missing, gain_db > 0, or write error.
    """
    path = Path(path)
    if gain_db > 0.0:
        raise CeilingGuardError(
            f"gain_db must be <= 0 (got {gain_db}); pull-down never raises peaks"
        )
    if not path.is_file():
        raise CeilingGuardError(f"Pull-down target not found: {path}")

    subtype = "PCM_24" if output_bits >= 24 else "PCM_16"
    scale = 10.0 ** (gain_db / 20.0)

    try:
        data, rate = sf.read(str(path))
    except Exception as exc:  # pragma: no cover - soundfile IO
        raise CeilingGuardError(f"read failed for {path}: {exc}") from exc

    data = data * scale

    # Atomic write: temp in same dir → fsync → os.replace.
    fd, tmp_str = tempfile.mkstemp(
        prefix=".ceiling_", suffix=".wav", dir=str(path.parent)
    )
    os.close(fd)
    tmp_path = Path(tmp_str)
    try:
        sf.write(str(tmp_path), data, rate, subtype=subtype)
        # fsync for durability before replace
        with open(tmp_path, "rb") as f:
            os.fsync(f.fileno())
        os.replace(str(tmp_path), str(path))
    except Exception as exc:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise CeilingGuardError(f"write failed for {path}: {exc}") from exc
