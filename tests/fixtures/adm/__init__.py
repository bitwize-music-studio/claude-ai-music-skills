"""Synthetic ADM test fixtures — PCM-clean and near-clip WAVs (#290 step 9).

``make_near_clip_wav`` generates a 440 Hz sine at -0.1 dBFS. After 256 kbps
AAC encode+decode, AAC codec ringing typically introduces samples that exceed
-1.0 dBTP, making this useful to verify the ADM clip detector fires.

``make_safe_wav`` generates the same signal at -12 dBFS. Survives AAC safely.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import soundfile as sf

_DEFAULT_RATE = 44100


def make_near_clip_wav(path: Path, *, rate: int = _DEFAULT_RATE) -> Path:
    """Write a 440 Hz sine at -0.1 dBFS — near-clipping, will trip ADM validator."""
    amplitude = 10.0 ** (-0.1 / 20.0)  # -0.1 dBFS
    n = int(rate * 2.0)
    t = np.arange(n) / rate
    mono = (amplitude * np.sin(2 * math.pi * 440.0 * t)).astype(np.float32)
    stereo = np.column_stack([mono, mono])
    sf.write(str(path), stereo, rate, subtype="PCM_24")
    return path


def make_safe_wav(path: Path, *, rate: int = _DEFAULT_RATE) -> Path:
    """Write a 440 Hz sine at -12 dBFS — quiet, survives AAC encoding safely."""
    amplitude = 10.0 ** (-12.0 / 20.0)  # -12 dBFS
    n = int(rate * 2.0)
    t = np.arange(n) / rate
    mono = (amplitude * np.sin(2 * math.pi * 440.0 * t)).astype(np.float32)
    stereo = np.column_stack([mono, mono])
    sf.write(str(path), stereo, rate, subtype="PCM_24")
    return path
