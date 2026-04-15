"""Synthetic multi-track album fixtures for coherence testing (#290).

Generators return list of (data, rate) tuples. Each track is a stereo
1-second sine at the given amplitude. Use ``write_coherent_album`` to
write them to disk.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import soundfile as sf

_DEFAULT_RATE = 44100


def make_coherent_tracks(
    n_tracks: int = 4,
    amplitude: float = 0.25,
    rate: int = _DEFAULT_RATE,
) -> list[tuple[np.ndarray, int]]:
    """4 tracks at uniform amplitude — all should fall within coherence tolerance."""
    tracks = []
    for i in range(n_tracks):
        n = int(rate * 2.0)
        t = np.arange(n) / rate
        # Slightly different freq per track for realism
        freq = 220.0 * (2 ** (i / 12.0))
        mono = (amplitude * np.sin(2 * math.pi * freq * t)).astype(np.float64)
        stereo = np.column_stack([mono, mono])
        tracks.append((stereo, rate))
    return tracks


def make_outlier_track(
    amplitude: float = 0.70,  # ~-3 dBFS — much louder than the coherent tracks
    rate: int = _DEFAULT_RATE,
) -> tuple[np.ndarray, int]:
    """One loud track — should trip the coherence outlier detector."""
    n = int(rate * 2.0)
    t = np.arange(n) / rate
    mono = (amplitude * np.sin(2 * math.pi * 880.0 * t)).astype(np.float64)
    return np.column_stack([mono, mono]), rate


def write_coherent_album(
    directory: Path,
    *,
    n_coherent: int = 4,
    include_outlier: bool = True,
) -> list[Path]:
    """Write coherent (+ optional outlier) WAVs to directory. Returns paths."""
    directory.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for i, (data, rate) in enumerate(make_coherent_tracks(n_coherent), 1):
        p = directory / f"{i:02d}-coherent.wav"
        sf.write(str(p), data, rate, subtype="PCM_24")
        paths.append(p)
    if include_outlier:
        data, rate = make_outlier_track()
        p = directory / f"{n_coherent + 1:02d}-outlier.wav"
        sf.write(str(p), data, rate, subtype="PCM_24")
        paths.append(p)
    return paths
