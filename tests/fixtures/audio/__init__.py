"""Realistic synthetic audio fixture generators for testing.

Each generator returns a tuple of (data, rate) where data is a stereo
numpy float64 array and rate is the sample rate (44100 Hz by default).

Signals are 1-3 seconds, deterministic, and copyright-free — no Git LFS
or licensing needed.
"""

from __future__ import annotations

import numpy as np
import soundfile as sf

DEFAULT_RATE = 44100
_RNG = np.random.default_rng(seed=42)


def _bandpass(data: np.ndarray, rate: int, low: float, high: float) -> np.ndarray:
    """Apply a 2nd-order Butterworth bandpass filter."""
    from scipy.signal import butter, lfilter

    nyq = rate / 2
    b, a = butter(2, [low / nyq, high / nyq], btype="band")
    return lfilter(b, a, data).astype(np.float64)


def _to_stereo(mono: np.ndarray, width: float = 0.1) -> np.ndarray:
    """Convert mono to stereo with slight decorrelation for realism."""
    shift = int(DEFAULT_RATE * 0.0003 * width)  # ~0.3ms offset
    right = np.roll(mono, shift)
    return np.column_stack([mono, right])


def write_wav(path: str, data: np.ndarray, rate: int = DEFAULT_RATE) -> str:
    """Write audio data to a WAV file and return the path."""
    sf.write(path, data, rate, subtype="PCM_16")
    return path


# ---------------------------------------------------------------------------
# Fixture generators
# ---------------------------------------------------------------------------


def make_vocal(duration: float = 2.0, rate: int = DEFAULT_RATE) -> tuple[np.ndarray, int]:
    """Formant-shaped bandpass noise with sibilant bursts (4-8 kHz spikes).

    Exercises: de-essing, vocal EQ, compression.
    """
    n = int(rate * duration)
    rng = np.random.default_rng(seed=100)

    # Base: bandpass noise shaped to vocal formants (300-3500 Hz)
    raw = rng.normal(0, 0.3, n)
    vocal_body = _bandpass(raw, rate, 300, 3500)

    # Add sibilant bursts every ~0.5s (4-8 kHz energy)
    sibilance = _bandpass(rng.normal(0, 0.6, n), rate, 4000, 8000)
    burst_env = np.zeros(n)
    burst_len = int(rate * 0.05)  # 50ms bursts
    for start in range(0, n, int(rate * 0.5)):
        end = min(start + burst_len, n)
        burst_env[start:end] = 1.0
    sibilance *= burst_env

    mono = (vocal_body + sibilance).astype(np.float64)
    mono /= np.max(np.abs(mono)) + 1e-10  # normalize
    mono *= 0.7  # headroom

    return _to_stereo(mono), rate


def make_drums(duration: float = 2.0, rate: int = DEFAULT_RATE) -> tuple[np.ndarray, int]:
    """Sharp transients with exponential decay.

    Exercises: click detection, transient shaping, compression.
    """
    n = int(rate * duration)
    mono = np.zeros(n, dtype=np.float64)

    # Place drum hits every ~0.25s
    hit_interval = int(rate * 0.25)
    for start in range(0, n, hit_interval):
        # Sharp attack + exponential decay
        hit_len = min(int(rate * 0.15), n - start)
        t = np.arange(hit_len, dtype=np.float64) / rate
        # Kick-like: low freq burst
        hit = 0.9 * np.sin(2 * np.pi * 80 * t) * np.exp(-t * 25)
        # Snap: high-freq click
        hit += 0.5 * np.sin(2 * np.pi * 5000 * t) * np.exp(-t * 80)
        mono[start : start + hit_len] += hit

    mono = np.clip(mono, -1.0, 1.0)
    return _to_stereo(mono, width=0.05), rate


def make_bass(duration: float = 2.0, rate: int = DEFAULT_RATE) -> tuple[np.ndarray, int]:
    """80 Hz fundamental + harmonics.

    Exercises: highpass filtering, low-end EQ.
    """
    n = int(rate * duration)
    t = np.linspace(0, duration, n, endpoint=False)

    mono = (
        0.6 * np.sin(2 * np.pi * 80 * t)
        + 0.25 * np.sin(2 * np.pi * 160 * t)
        + 0.1 * np.sin(2 * np.pi * 240 * t)
        + 0.05 * np.sin(2 * np.pi * 320 * t)
    )
    mono = mono.astype(np.float64)
    mono *= 0.8

    return _to_stereo(mono, width=0.02), rate


def make_full_mix(duration: float = 3.0, rate: int = DEFAULT_RATE) -> tuple[np.ndarray, int]:
    """Layered combination of all stem types.

    Exercises: remix, spectral balance, mastering pipeline.
    """
    vocal, _ = make_vocal(duration, rate)
    drums, _ = make_drums(duration, rate)
    bass, _ = make_bass(duration, rate)

    # Pad shorter arrays to match longest
    max_len = max(len(vocal), len(drums), len(bass))
    for arr_name in ("vocal", "drums", "bass"):
        arr = locals()[arr_name]
        if len(arr) < max_len:
            pad = np.zeros((max_len - len(arr), 2))
            locals()[arr_name] = np.vstack([arr, pad])

    vocal = vocal[:max_len]
    drums = drums[:max_len]
    bass = bass[:max_len]

    mixed = 0.4 * vocal + 0.35 * drums + 0.25 * bass
    # Normalize to -3 dBFS headroom
    peak = np.max(np.abs(mixed))
    if peak > 0:
        mixed = mixed / peak * 0.7

    return mixed.astype(np.float64), rate


def make_clipping(duration: float = 2.0, rate: int = DEFAULT_RATE) -> tuple[np.ndarray, int]:
    """Intentionally hard-clipped signal.

    Exercises: QC clipping detection, fix_dynamic_track().
    """
    n = int(rate * duration)
    t = np.linspace(0, duration, n, endpoint=False)

    # Over-driven sine that clips hard
    mono = 1.5 * np.sin(2 * np.pi * 300 * t)
    mono = np.clip(mono, -1.0, 1.0)

    return _to_stereo(mono.astype(np.float64)), rate


def make_phase_problem(duration: float = 2.0, rate: int = DEFAULT_RATE) -> tuple[np.ndarray, int]:
    """Inverted-phase stereo (left = -right).

    Exercises: QC mono compatibility / phase check.
    """
    n = int(rate * duration)
    t = np.linspace(0, duration, n, endpoint=False)

    left = 0.7 * np.sin(2 * np.pi * 440 * t)
    right = -left  # perfect phase inversion

    data = np.column_stack([left, right]).astype(np.float64)
    return data, rate


def make_bright(duration: float = 2.0, rate: int = DEFAULT_RATE) -> tuple[np.ndarray, int]:
    """Excessive high-frequency energy.

    Exercises: tinniness detection, high-shelf EQ correction.
    """
    n = int(rate * duration)
    t = np.linspace(0, duration, n, endpoint=False)

    # Weak low + very strong high-mid
    low = 0.08 * np.sin(2 * np.pi * 200 * t)
    mid = 0.05 * np.sin(2 * np.pi * 1000 * t)
    high_mid = 0.7 * np.sin(2 * np.pi * 4000 * t)
    air = 0.3 * np.sin(2 * np.pi * 10000 * t)

    mono = (low + mid + high_mid + air).astype(np.float64)
    mono *= 0.8

    return _to_stereo(mono), rate


def make_noisy(duration: float = 2.0, rate: int = DEFAULT_RATE) -> tuple[np.ndarray, int]:
    """Signal with elevated noise floor.

    Exercises: noise reduction, silence detection.
    """
    n = int(rate * duration)
    t = np.linspace(0, duration, n, endpoint=False)
    rng = np.random.default_rng(seed=200)

    # Musical content: simple chord
    signal = 0.4 * np.sin(2 * np.pi * 440 * t) + 0.2 * np.sin(2 * np.pi * 554 * t)
    # Heavy noise floor
    noise = rng.normal(0, 0.08, n)

    mono = (signal + noise).astype(np.float64)
    mono *= 0.7

    return _to_stereo(mono), rate


def make_clicks_and_pops(duration: float = 3.0, rate: int = DEFAULT_RATE) -> tuple[np.ndarray, int]:
    """Musical transients with sparse single-sample spikes (DC pops).

    Mixes a low-amplitude tonal bed with periodic kick-like transients,
    then injects single-sample spikes at irregular intervals to simulate
    digital clicks/pops from a bad encode or torn waveform.

    Exercises: click detection (peak_ratio), declicker behavior,
    genre-aware click thresholds.
    """
    n = int(rate * duration)
    t = np.linspace(0, duration, n, endpoint=False)

    # Low-amplitude tonal bed so RMS stays high enough for click detection
    bed = 0.15 * np.sin(2 * np.pi * 220 * t)

    # Musical transients (kick-ish) every 0.4s
    transient_env = np.zeros(n, dtype=np.float64)
    hit_interval = int(rate * 0.4)
    for start in range(0, n, hit_interval):
        hit_len = min(int(rate * 0.08), n - start)
        local_t = np.arange(hit_len, dtype=np.float64) / rate
        hit = 0.4 * np.sin(2 * np.pi * 70 * local_t) * np.exp(-local_t * 30)
        transient_env[start : start + hit_len] += hit

    mono = (bed + transient_env).astype(np.float64)

    # Inject 6 single-sample spikes at irregular offsets (not aligned with hits)
    spike_offsets = [0.13, 0.55, 0.92, 1.34, 1.71, 2.18]
    for offset_sec in spike_offsets:
        idx = int(offset_sec * rate)
        if idx < n:
            mono[idx] = 0.9 if mono[idx] >= 0 else -0.9

    return _to_stereo(mono, width=0.05), rate


def make_silent_gaps(rate: int = DEFAULT_RATE) -> tuple[np.ndarray, int]:
    """2s audio + 1s silence + 2s audio (5s total).

    Exercises: silence QC FAIL on internal gap detection.
    """
    seg_samples = int(rate * 2.0)
    gap_samples = int(rate * 1.0)
    t = np.linspace(0, 2.0, seg_samples, endpoint=False)

    seg = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float64)
    gap = np.zeros(gap_samples, dtype=np.float64)
    mono = np.concatenate([seg, gap, seg])

    return _to_stereo(mono, width=0.02), rate


def make_phase_partial(duration: float = 2.0, rate: int = DEFAULT_RATE) -> tuple[np.ndarray, int]:
    """Stereo with a partial phase shift on one channel (not full inversion).

    A 90-degree phase offset on the right channel produces measurable mono
    fold-down loss without the trivial cancellation of `make_phase_problem`.
    More representative of real-world stereo widening / mic-bleed problems.

    Exercises: realistic mono compatibility FAIL, phase correlation WARN.
    """
    n = int(rate * duration)
    t = np.linspace(0, duration, n, endpoint=False)

    # Mix two tones so cancellation patterns are non-trivial
    left = (0.5 * np.sin(2 * np.pi * 440 * t)
            + 0.3 * np.sin(2 * np.pi * 660 * t)).astype(np.float64)
    # Right: same tones but shifted 90 degrees (cosine instead of sine)
    right = (0.5 * np.cos(2 * np.pi * 440 * t)
             + 0.3 * np.cos(2 * np.pi * 660 * t)).astype(np.float64)

    return np.column_stack([left, right]), rate
