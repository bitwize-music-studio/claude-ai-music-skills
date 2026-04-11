#!/usr/bin/env python3
"""
Automated Mastering Script for Album
- Normalizes to target LUFS (streaming: -14 LUFS)
- Optional high-mid EQ cut for tinniness
- True peak limiting to prevent clipping
- Preserves dynamics while ensuring consistency
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import numpy as np
import pyloudnorm as pyln
import soundfile as sf
from scipy import signal

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]

# Ensure project root is on sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.mixing.mix_tracks import gentle_compress
from tools.shared.logging_config import setup_logging
from tools.shared.progress import ProgressBar

logger = logging.getLogger(__name__)

# Built-in presets file (ships with plugin)
_BUILTIN_PRESETS_FILE = Path(__file__).parent / "genre-presets.yaml"

# User override location
_CONFIG_PATH = Path.home() / ".bitwize-music" / "config.yaml"


def _load_yaml_file(path: Path) -> dict[str, Any]:
    """Load a YAML file, returning empty dict on failure."""
    if not path.exists():
        return {}
    if yaml is None:
        logger.debug("PyYAML not installed, cannot load %s", path)  # type: ignore[unreachable]
        return {}
    try:
        with open(path) as f:
            return yaml.safe_load(f) or {}
    except (yaml.YAMLError, OSError) as e:
        logger.warning("Cannot read %s: %s", path, e)
        return {}


def _get_overrides_path() -> Path | None:
    """Resolve the user's overrides directory from config."""
    config = _load_yaml_file(_CONFIG_PATH)
    if not config:
        return None
    overrides_raw = config.get('paths', {}).get('overrides', '')
    if overrides_raw:
        return Path(os.path.expanduser(overrides_raw))
    content_root = config.get('paths', {}).get('content_root', '')
    if content_root:
        return Path(os.path.expanduser(content_root)) / 'overrides'
    return None


# All recognized preset keys and their defaults
_PRESET_DEFAULTS: dict[str, float] = {
    'target_lufs': -14.0,
    'cut_highmid': 0.0,
    'cut_highs': 0.0,
    'compress_ratio': 1.5,
    'compress_threshold': -18.0,
    'compress_attack': 30.0,
    'compress_release': 200.0,
    'eq_highmid_freq': 3500.0,
    'eq_highmid_q': 1.5,
    'eq_highs_freq': 8000.0,
    'eq_highs_q': 0.7,
    'eq_low_freq': 80.0,
    'eq_low_gain': 0.0,
    'eq_low_q': 0.7,
    'eq_sub_cut_freq': 0.0,
    'stereo_width': 1.0,
    'stereo_bass_mono_freq': 0.0,
    'output_bits': 16,
    'dither_bits': 16,
    'limiter_lookahead_ms': 5.0,
    'limiter_release_ms': 50.0,
    'compress_mix': 1.0,
    'compress_makeup': 0.0,
    'processing_oversample': 1,
    'target_lra': 0.0,
    'dc_filter_freq': 5.0,
    'output_sample_rate': 0,
    'deess_enabled': 0,
    'deess_freq': 6500.0,
    'deess_bandwidth': 4000.0,
    'deess_threshold': -20.0,
    'deess_ratio': 4.0,
    'track_gap': 0.0,
}


def load_genre_presets() -> dict[str, dict[str, float]]:
    """Load genre presets from YAML, merging built-in with user overrides.

    Returns:
        Dict mapping genre name to a dict of preset parameters.
    """
    # Load built-in presets
    builtin = _load_yaml_file(_BUILTIN_PRESETS_FILE)
    builtin_genres = builtin.get('genres', {})
    defaults = {**_PRESET_DEFAULTS}

    # Merge YAML defaults on top of hardcoded defaults
    yaml_defaults = builtin.get('defaults', {})
    for key in defaults:
        if key in yaml_defaults:
            defaults[key] = float(yaml_defaults[key])

    # Load user overrides
    overrides_dir = _get_overrides_path()
    override_genres = {}
    if overrides_dir:
        override_file = overrides_dir / 'mastering-presets.yaml'
        override_data = _load_yaml_file(override_file)
        override_genres = override_data.get('genres', {})
        override_defaults = override_data.get('defaults', {})
        if override_defaults:
            for key in defaults:
                if key in override_defaults:
                    defaults[key] = float(override_defaults[key])

    # Merge: built-in genres + override genres (override wins per-field)
    all_genre_names = set(builtin_genres.keys()) | set(override_genres.keys())
    presets: dict[str, dict[str, float]] = {}
    for genre in all_genre_names:
        base = builtin_genres.get(genre, {})
        over = override_genres.get(genre, {})
        merged = {**base, **over}
        presets[genre] = {
            key: float(merged.get(key, default))
            for key, default in defaults.items()
        }

    return presets


# Load presets at import time (fast — just two small YAML reads)
GENRE_PRESETS = load_genre_presets()

def apply_eq(data: Any, rate: int, freq: float, gain_db: float, q: float = 1.0) -> Any:
    """Apply parametric EQ to audio data.

    Args:
        data: Audio data (samples x channels)
        rate: Sample rate
        freq: Center frequency in Hz
        gain_db: Gain in dB (negative for cut)
        q: Q factor (higher = narrower)
    """
    nyquist = rate / 2
    if not (20 <= freq < nyquist):
        logger.warning("EQ freq %.1f Hz out of valid range (20\u2013%.0f Hz), skipping", freq, nyquist)
        return data
    if q <= 0:
        logger.warning("EQ Q factor must be positive (got %.4f), skipping", q)
        return data

    # Convert to filter parameters
    A = 10 ** (gain_db / 40)
    w0 = 2 * np.pi * freq / rate
    alpha = np.sin(w0) / (2 * q)

    # Peaking EQ coefficients
    b0 = 1 + alpha * A
    b1 = -2 * np.cos(w0)
    b2 = 1 - alpha * A
    a0 = 1 + alpha / A
    a1 = -2 * np.cos(w0)
    a2 = 1 - alpha / A

    # Normalize
    b = np.array([b0/a0, b1/a0, b2/a0])
    a = np.array([1, a1/a0, a2/a0])

    # Verify filter stability (all poles inside unit circle)
    poles = np.roots(a)
    if not np.all(np.abs(poles) < 1.0):
        logger.warning("Unstable EQ filter at %.1f Hz (gain=%.1f dB, Q=%.2f), skipping", freq, gain_db, q)
        return data

    # Apply filter to each channel
    if len(data.shape) == 1:
        return signal.lfilter(b, a, data)
    else:
        result = np.zeros_like(data)
        for ch in range(data.shape[1]):
            result[:, ch] = signal.lfilter(b, a, data[:, ch])
        return result

def apply_high_shelf(data: Any, rate: int, freq: float, gain_db: float) -> Any:
    """Apply high shelf EQ."""
    nyquist = rate / 2
    if not (20 <= freq < nyquist):
        logger.warning("High shelf freq %.1f Hz out of valid range (20\u2013%.0f Hz), skipping", freq, nyquist)
        return data

    A = 10 ** (gain_db / 40)
    w0 = 2 * np.pi * freq / rate
    alpha = np.sin(w0) / 2 * np.sqrt(2)

    cos_w0 = np.cos(w0)
    sqrt_A = np.sqrt(A)

    b0 = A * ((A + 1) + (A - 1) * cos_w0 + 2 * sqrt_A * alpha)
    b1 = -2 * A * ((A - 1) + (A + 1) * cos_w0)
    b2 = A * ((A + 1) + (A - 1) * cos_w0 - 2 * sqrt_A * alpha)
    a0 = (A + 1) - (A - 1) * cos_w0 + 2 * sqrt_A * alpha
    a1 = 2 * ((A - 1) - (A + 1) * cos_w0)
    a2 = (A + 1) - (A - 1) * cos_w0 - 2 * sqrt_A * alpha

    b = np.array([b0/a0, b1/a0, b2/a0])
    a = np.array([1, a1/a0, a2/a0])

    # Verify filter stability (all poles inside unit circle)
    poles = np.roots(a)
    if not np.all(np.abs(poles) < 1.0):
        logger.warning("Unstable high shelf filter at %.1f Hz (gain=%.1f dB), skipping", freq, gain_db)
        return data

    if len(data.shape) == 1:
        return signal.lfilter(b, a, data)
    else:
        result = np.zeros_like(data)
        for ch in range(data.shape[1]):
            result[:, ch] = signal.lfilter(b, a, data[:, ch])
        return result

def apply_low_shelf(data: Any, rate: int, freq: float, gain_db: float) -> Any:
    """Apply low shelf EQ for bass shaping.

    Args:
        data: Audio data
        rate: Sample rate
        freq: Shelf corner frequency in Hz
        gain_db: Gain in dB (positive = boost, negative = cut, 0 = bypass)
    """
    if gain_db == 0:
        return data
    nyquist = rate / 2
    if not (20 <= freq < nyquist):
        logger.warning("Low shelf freq %.1f Hz out of valid range (20–%.0f Hz), skipping", freq, nyquist)
        return data

    A = 10 ** (gain_db / 40)
    w0 = 2 * np.pi * freq / rate
    alpha = np.sin(w0) / 2 * np.sqrt(2)

    cos_w0 = np.cos(w0)
    sqrt_A = np.sqrt(A)

    # Low shelf coefficients (Audio EQ Cookbook)
    b0 = A * ((A + 1) - (A - 1) * cos_w0 + 2 * sqrt_A * alpha)
    b1 = 2 * A * ((A - 1) - (A + 1) * cos_w0)
    b2 = A * ((A + 1) - (A - 1) * cos_w0 - 2 * sqrt_A * alpha)
    a0 = (A + 1) + (A - 1) * cos_w0 + 2 * sqrt_A * alpha
    a1 = -2 * ((A - 1) + (A + 1) * cos_w0)
    a2 = (A + 1) + (A - 1) * cos_w0 - 2 * sqrt_A * alpha

    b = np.array([b0/a0, b1/a0, b2/a0])
    a = np.array([1, a1/a0, a2/a0])

    poles = np.roots(a)
    if not np.all(np.abs(poles) < 1.0):
        logger.warning("Unstable low shelf filter at %.1f Hz (gain=%.1f dB), skipping", freq, gain_db)
        return data

    if len(data.shape) == 1:
        return signal.lfilter(b, a, data)
    else:
        result = np.zeros_like(data)
        for ch in range(data.shape[1]):
            result[:, ch] = signal.lfilter(b, a, data[:, ch])
        return result


def apply_highpass(data: Any, rate: int, cutoff: int = 30) -> Any:
    """Apply Butterworth highpass filter for sub-bass rumble removal.

    Args:
        data: Audio data
        rate: Sample rate
        cutoff: Cutoff frequency in Hz (0 = bypass)
    """
    if cutoff <= 0:
        return data
    nyquist = rate / 2
    if cutoff >= nyquist:
        logger.warning("Highpass cutoff %d Hz >= Nyquist (%.0f Hz), skipping", cutoff, nyquist)
        return data

    normalized_cutoff = cutoff / nyquist
    b, a = signal.butter(2, normalized_cutoff, btype='high')

    poles = np.roots(a)
    if not np.all(np.abs(poles) < 1.0):
        logger.warning("Unstable highpass filter at %d Hz, skipping", cutoff)
        return data

    if len(data.shape) == 1:
        return signal.lfilter(b, a, data)
    else:
        result = np.zeros_like(data)
        for ch in range(data.shape[1]):
            result[:, ch] = signal.lfilter(b, a, data[:, ch])
        return result


def apply_stereo_width(data: Any, rate: int, width: float = 1.0,
                       bass_mono_freq: int = 0) -> Any:
    """Adjust stereo width with optional low-frequency mono fold.

    Args:
        data: Stereo audio data (samples, 2)
        rate: Sample rate
        width: Width multiplier (0.0 = mono, 1.0 = unchanged, >1.0 = wider)
        bass_mono_freq: Mono-sum frequencies below this (0 = bypass).
            Ensures bass coherence on club/PA systems.
    """
    if len(data.shape) == 1 or data.shape[1] != 2:
        return data
    if width == 1.0 and bass_mono_freq <= 0:
        return data

    # Mid-side encoding
    mid = (data[:, 0] + data[:, 1]) / 2
    side = (data[:, 0] - data[:, 1]) / 2

    # Apply width scaling
    if width != 1.0:
        side = side * max(width, 0.0)

    # Bass mono fold: filter side channel to remove low frequencies
    if bass_mono_freq > 0:
        nyquist = rate / 2
        if bass_mono_freq < nyquist:
            normalized = bass_mono_freq / nyquist
            b, a = signal.butter(2, normalized, btype='high')
            poles = np.roots(a)
            if np.all(np.abs(poles) < 1.0):
                side = signal.lfilter(b, a, side)

    # Decode back to L/R
    result = np.zeros_like(data)
    result[:, 0] = mid + side
    result[:, 1] = mid - side

    return result


def apply_fade_out(data: Any, rate: int, duration: float = 5.0, curve: str = 'exponential') -> Any:
    """Apply a fade-out to the end of audio data.

    Args:
        data: Audio data (samples,) for mono or (samples, channels) for stereo
        rate: Sample rate
        duration: Fade duration in seconds (default: 5.0).
            If <= 0, returns data unchanged (passthrough).
            If > audio length, fades the entire track.
        curve: 'exponential' for (1-t)**3, 'linear' for 1-t

    Returns:
        Audio data with fade-out applied.
    """
    if duration <= 0:
        return data

    total_samples = data.shape[0]
    fade_samples = int(rate * duration)

    # If fade is longer than audio, fade the entire track
    if fade_samples > total_samples:
        fade_samples = total_samples

    # Build the fade envelope
    t = np.linspace(0, 1, fade_samples, endpoint=True)
    if curve == 'exponential':
        envelope = (1 - t) ** 3
    else:
        envelope = 1 - t

    result = data.copy()
    if len(data.shape) == 1:
        # Mono
        result[-fade_samples:] *= envelope
    else:
        # Stereo / multichannel — broadcast envelope across channels
        result[-fade_samples:] *= envelope[:, np.newaxis]

    return result


def soft_clip(data: Any, threshold: float = 0.95) -> Any:
    """Soft clipping limiter to prevent harsh digital clipping."""
    # Soft knee limiter using tanh
    above_thresh = np.abs(data) > threshold
    if not np.any(above_thresh):
        return data

    result = data.copy()
    # Apply soft saturation above threshold
    result[above_thresh] = np.sign(data[above_thresh]) * (threshold + (1 - threshold) * np.tanh((np.abs(data[above_thresh]) - threshold) / (1 - threshold)))
    return result

def measure_true_peak(data: Any, rate: int = 44100) -> float:
    """Measure true peak level using 4x oversampling per ITU-R BS.1770-4.

    Inter-sample peaks can exceed the highest sample value. This function
    upsamples 4x with sinc interpolation to detect those peaks.

    Args:
        data: Audio data (samples,) or (samples, channels).
        rate: Sample rate (unused, kept for API consistency).

    Returns:
        True peak as a linear amplitude value.
    """
    if data.size == 0:
        return 0.0

    # Upsample 4x using polyphase FIR (sinc interpolation)
    if data.ndim == 1:
        upsampled = signal.resample_poly(data, up=4, down=1)
        return float(np.max(np.abs(upsampled)))

    # Multichannel: measure each channel, return the worst
    peak = 0.0
    for ch in range(data.shape[1]):
        upsampled = signal.resample_poly(data[:, ch], up=4, down=1)
        ch_peak = float(np.max(np.abs(upsampled)))
        if ch_peak > peak:
            peak = ch_peak
    return peak


def limit_peaks(data: Any, ceiling_db: float = -1.0) -> Any:
    """True peak limiter using 4x oversampled peak detection.

    Measures inter-sample peaks via ITU-R BS.1770-4 oversampling, then
    applies gain reduction so the true peak stays below the ceiling.

    Args:
        data: Audio data
        ceiling_db: Maximum true peak level in dB (e.g., -1.0 for -1 dBTP)
    """
    ceiling_linear = 10 ** (ceiling_db / 20)
    true_peak = measure_true_peak(data)

    if true_peak > ceiling_linear:
        gain = ceiling_linear / true_peak
        data = data * gain

    return soft_clip(data, ceiling_linear)


def limit_peaks_lookahead(data: Any, ceiling_db: float = -1.0,
                          lookahead_ms: float = 5.0,
                          release_ms: float = 50.0,
                          rate: int = 44100) -> Any:
    """Look-ahead limiter with smooth gain reduction envelope.

    Delays the audio while a sidechain detects upcoming peaks and
    pre-applies gain reduction, producing transparent limiting
    instead of reactive distortion.

    Args:
        data: Audio data
        ceiling_db: Maximum true peak level in dB
        lookahead_ms: Look-ahead buffer in ms
        release_ms: Limiter release time in ms
        rate: Sample rate
    """
    ceiling_linear = 10 ** (ceiling_db / 20)
    lookahead_samples = int(rate * lookahead_ms / 1000.0)

    if lookahead_samples <= 0:
        return limit_peaks(data, ceiling_db)

    # Work per-channel, combine max gain reduction
    if data.ndim == 1:
        channels = data.reshape(-1, 1)
    else:
        channels = data

    n_samples = channels.shape[0]

    # Compute instantaneous gain reduction needed across all channels
    peak_env = np.max(np.abs(channels), axis=1)
    gain_needed = np.where(
        peak_env > ceiling_linear,
        ceiling_linear / np.maximum(peak_env, 1e-10),
        1.0,
    )

    # Smooth the gain envelope with release coefficient
    release_coeff = np.exp(-1.0 / (rate * release_ms / 1000.0))
    smoothed = np.ones(n_samples, dtype=np.float64)
    env = 1.0
    for i in range(n_samples):
        target = gain_needed[i]
        if target < env:
            # Attack: instant (look-ahead handles the transition)
            env = target
        else:
            # Release: smooth recovery
            env = release_coeff * env + (1.0 - release_coeff) * target
        smoothed[i] = env

    # Shift gain envelope backward by lookahead_samples (pre-apply reduction)
    shifted = np.ones(n_samples, dtype=np.float64)
    if lookahead_samples < n_samples:
        shifted[:n_samples - lookahead_samples] = smoothed[lookahead_samples:]
        shifted[n_samples - lookahead_samples:] = smoothed[-1]
    else:
        shifted[:] = np.min(smoothed)

    # Apply gain reduction
    if data.ndim == 1:
        result = data * shifted
    else:
        result = data * shifted[:, np.newaxis]

    # Final soft clip as safety net
    return soft_clip(result, ceiling_linear)


def apply_deesser(data: Any, rate: int, freq: float = 6500.0,
                  bandwidth: float = 4000.0, threshold_db: float = -20.0,
                  ratio: float = 4.0) -> Any:
    """Frequency-selective de-esser for sibilance reduction.

    Isolates a sibilance band, detects energy exceeding threshold,
    and applies gain reduction only to that band.

    Args:
        data: Audio data
        rate: Sample rate
        freq: Center frequency for sibilance detection (Hz)
        bandwidth: Detection bandwidth in Hz
        threshold_db: Threshold for sibilance reduction (dB)
        ratio: Compression ratio for sibilant regions
    """
    if ratio <= 1.0:
        return data

    nyquist = rate / 2
    low_freq = max(20, freq - bandwidth / 2)
    high_freq = min(nyquist - 1, freq + bandwidth / 2)

    if low_freq >= high_freq or high_freq >= nyquist:
        return data

    # Design bandpass filter for sibilance detection
    low_norm = low_freq / nyquist
    high_norm = high_freq / nyquist
    b_bp, a_bp = signal.butter(2, [low_norm, high_norm], btype='band')

    poles = np.roots(a_bp)
    if not np.all(np.abs(poles) < 1.0):
        logger.warning("Unstable de-esser bandpass at %.0f Hz, skipping", freq)
        return data

    threshold_linear = 10 ** (threshold_db / 20)

    def _deess_channel(channel: Any) -> Any:
        # Extract sibilance band
        sibilance = signal.lfilter(b_bp, a_bp, channel)
        # Envelope of sibilance band
        env = np.abs(sibilance)
        # Smooth envelope (fast attack, medium release)
        attack_coeff = np.exp(-1.0 / (rate * 0.001))  # 1ms attack
        release_coeff = np.exp(-1.0 / (rate * 0.020))  # 20ms release
        smoothed = np.empty_like(env)
        val = 0.0
        for i in range(len(env)):
            if env[i] > val:
                val = attack_coeff * val + (1.0 - attack_coeff) * env[i]
            else:
                val = release_coeff * val + (1.0 - release_coeff) * env[i]
            smoothed[i] = val
        # Gain reduction only where sibilance exceeds threshold
        gain = np.ones_like(channel)
        above = smoothed > threshold_linear
        if np.any(above):
            env_db = np.where(above, 20 * np.log10(np.maximum(smoothed, 1e-10)), 0)
            thresh_db_val = 20 * np.log10(max(threshold_linear, 1e-10))
            excess_db = np.where(above, env_db - thresh_db_val, 0)
            gain_reduction_db = excess_db * (1 - 1 / ratio)
            gain = np.where(above, 10 ** (-gain_reduction_db / 20), 1.0)
        # Apply gain reduction only to sibilance band, keep rest unchanged
        return channel - sibilance + sibilance * gain

    if len(data.shape) == 1:
        return _deess_channel(data)
    else:
        result = np.zeros_like(data)
        for ch in range(data.shape[1]):
            result[:, ch] = _deess_channel(data[:, ch])
        return result


def apply_tpdf_dither(data: Any, target_bits: int = 16, seed: int | None = None) -> Any:
    """Apply TPDF (Triangular Probability Density Function) dithering.

    Must be the *last* processing step before integer quantization.
    Converts correlated truncation distortion into uncorrelated noise,
    which is perceptually far less objectionable on quiet passages and fades.

    Args:
        data: Audio data as float (−1.0 to 1.0).
        target_bits: Output bit depth (default 16).
        seed: Optional RNG seed for reproducible output (testing).

    Returns:
        Dithered float data ready for integer quantization by soundfile.
    """
    rng = np.random.default_rng(seed)

    # 1 LSB at the target bit depth (e.g. 16-bit → 1/32768)
    max_val = 2 ** (target_bits - 1)
    one_lsb = 1.0 / max_val

    # TPDF noise = sum of two independent uniform ±0.5 LSB distributions
    # Result: triangular distribution with range ±1 LSB, variance = LSB²/6
    noise = rng.uniform(-0.5, 0.5, size=data.shape) + rng.uniform(-0.5, 0.5, size=data.shape)
    noise *= one_lsb

    return data + noise

def master_track(input_path: Path | str, output_path: Path | str,
                 target_lufs: float = -14.0,
                 eq_settings: list[tuple[float, float, float]] | None = None,
                 ceiling_db: float = -1.0, fade_out: float | None = None,
                 compress_ratio: float = 1.5,
                 preset: dict[str, float] | None = None) -> dict[str, Any]:
    """Master a single track.

    Args:
        input_path: Path to input wav file
        output_path: Path for output wav file
        target_lufs: Target integrated loudness (ignored if preset provided)
        eq_settings: List of (freq, gain_db, q) tuples for EQ (ignored if preset provided)
        ceiling_db: True peak ceiling in dB
        fade_out: Optional fade-out duration in seconds.
            None or <= 0 disables fade-out.
        compress_ratio: Compression ratio (ignored if preset provided)
        preset: Full preset dict. When provided, target_lufs, eq_settings,
            and compress_ratio are read from the preset instead.
    """
    # Resolve parameters from preset or legacy args
    p = {**_PRESET_DEFAULTS}
    if preset is not None:
        p.update(preset)
        target_lufs = p['target_lufs']
        compress_ratio = p['compress_ratio']
        # Build EQ settings from preset
        eq_settings = []
        if p['cut_highmid'] != 0:
            eq_settings.append((p['eq_highmid_freq'], p['cut_highmid'], p['eq_highmid_q']))
        if p['cut_highs'] != 0:
            eq_settings.append((p['eq_highs_freq'], p['cut_highs'], p['eq_highs_q']))
        eq_settings = eq_settings or None

    # Read audio
    data, rate = sf.read(input_path)

    # Handle mono
    was_mono = len(data.shape) == 1
    if was_mono:
        data = np.column_stack([data, data])

    # DC offset removal (first processing stage)
    dc_freq = p.get('dc_filter_freq', 5.0)
    if dc_freq > 0:
        data = apply_highpass(data, rate, cutoff=int(dc_freq))

    # Sub-bass rumble removal (before any EQ)
    sub_cut = int(p.get('eq_sub_cut_freq', 0))
    if sub_cut > 0:
        data = apply_highpass(data, rate, cutoff=sub_cut)

    # Low shelf EQ (bass shaping)
    low_gain = p.get('eq_low_gain', 0.0)
    if low_gain != 0:
        data = apply_low_shelf(data, rate, freq=p['eq_low_freq'], gain_db=low_gain)

    # Apply high-mid/highs EQ if specified
    if eq_settings:
        for freq, gain_db, q in eq_settings:
            data = apply_eq(data, rate, freq, gain_db, q)

    # De-essing (after EQ, before dynamics)
    if p.get('deess_enabled', 0) > 0:
        data = apply_deesser(
            data, rate,
            freq=p.get('deess_freq', 6500.0),
            bandwidth=p.get('deess_bandwidth', 4000.0),
            threshold_db=p.get('deess_threshold', -20.0),
            ratio=p.get('deess_ratio', 4.0),
        )

    # Stereo width adjustment (after EQ, before compression)
    stereo_w = p.get('stereo_width', 1.0)
    bass_mono = int(p.get('stereo_bass_mono_freq', 0))
    if stereo_w != 1.0 or bass_mono > 0:
        data = apply_stereo_width(data, rate, width=stereo_w, bass_mono_freq=bass_mono)

    # Apply fade-out if specified (before loudness measurement so LUFS
    # is measured correctly with the fade included)
    if fade_out is not None and fade_out > 0:
        data = apply_fade_out(data, rate, duration=fade_out)

    # Oversampling for nonlinear stages (compression + limiting)
    oversample = int(p.get('processing_oversample', 1))
    original_rate = rate
    if oversample > 1:
        data = signal.resample_poly(data, up=oversample, down=1, axis=0)
        rate = original_rate * oversample

    # Mastering compression — gentle safety net with parallel blend
    compress_mix = p.get('compress_mix', 1.0)
    if compress_ratio > 1.0:
        dry = data.copy() if compress_mix < 1.0 else None
        data = gentle_compress(
            data, rate,
            threshold_db=p['compress_threshold'],
            ratio=compress_ratio,
            attack_ms=p['compress_attack'],
            release_ms=p['compress_release'],
        )
        # Makeup gain: compensate for compression gain reduction
        makeup = p.get('compress_makeup', 0.0)
        if makeup != 0:
            data = data * (10 ** (makeup / 20))
        # Parallel compression: blend wet/dry
        if dry is not None and compress_mix < 1.0:
            data = dry * (1.0 - compress_mix) + data * compress_mix

    # Downsample back if oversampled
    if oversample > 1:
        data = signal.resample_poly(data, up=1, down=oversample, axis=0)
        rate = original_rate

    # Measure current loudness
    meter = pyln.Meter(rate)
    current_lufs = meter.integrated_loudness(data)

    # Guard against silent or near-silent audio (loudness returns -inf)
    if not np.isfinite(current_lufs):
        logger.warning("Audio is silent or near-silent, skipping: %s", input_path)
        return {
            'original_lufs': float('-inf'),
            'final_lufs': float('-inf'),
            'gain_applied': 0.0,
            'final_peak': float('-inf'),
            'skipped': True,
        }

    # LRA targeting: if LRA exceeds target, increase compression
    target_lra = p.get('target_lra', 0.0)
    measured_lra = None
    if target_lra > 0:
        try:
            measured_lra = pyln.Meter(rate).integrated_loudness(data)
            # pyloudnorm doesn't have LRA, so compute from short-term loudness
            # Use 3-second windows with 2-second overlap per EBU R128
            window_samples = int(3.0 * rate)
            hop_samples = int(1.0 * rate)
            if data.shape[0] > window_samples:
                short_term = []
                for start in range(0, data.shape[0] - window_samples, hop_samples):
                    chunk = data[start:start + window_samples]
                    st_lufs = pyln.Meter(rate).integrated_loudness(chunk)
                    if np.isfinite(st_lufs):
                        short_term.append(st_lufs)
                if len(short_term) >= 2:
                    # LRA = difference between 95th and 10th percentile
                    measured_lra = float(np.percentile(short_term, 95) - np.percentile(short_term, 10))
        except Exception:
            measured_lra = None

    # Calculate required gain
    gain_db = target_lufs - current_lufs
    gain_linear = 10 ** (gain_db / 20)

    # Apply gain
    data = data * gain_linear

    # Oversample for limiting if requested
    if oversample > 1:
        data = signal.resample_poly(data, up=oversample, down=1, axis=0)
        rate = original_rate * oversample

    # Apply limiter (look-ahead or reactive)
    lookahead_ms = p.get('limiter_lookahead_ms', 5.0)
    if lookahead_ms > 0:
        data = limit_peaks_lookahead(
            data, ceiling_db,
            lookahead_ms=lookahead_ms,
            release_ms=p.get('limiter_release_ms', 50.0),
            rate=rate,
        )
    else:
        data = limit_peaks(data, ceiling_db)

    # Downsample after limiting if oversampled
    if oversample > 1:
        data = signal.resample_poly(data, up=1, down=oversample, axis=0)
        rate = original_rate

    # Verify final loudness and measure true peak
    final_lufs = meter.integrated_loudness(data)
    true_peak_linear = measure_true_peak(data, rate)
    final_peak = 20 * np.log10(true_peak_linear) if true_peak_linear > 0 else float('-inf')

    # Convert back to mono if input was mono
    if was_mono:
        data = data[:, 0]

    # Sample rate conversion (after processing, before dither)
    output_sr = int(p.get('output_sample_rate', 0))
    if output_sr > 0 and output_sr != rate:
        # Use rational resampling via polyphase FIR
        from math import gcd
        g = gcd(output_sr, rate)
        data = signal.resample_poly(data, up=output_sr // g, down=rate // g, axis=0)
        rate = output_sr

    # Resolve output bit depth: output_bits controls the format,
    # dither_bits follows output_bits by default but can be overridden
    output_bits = int(p.get('output_bits', 16))
    dither_bits = int(p.get('dither_bits', output_bits))
    data = apply_tpdf_dither(data, target_bits=dither_bits)

    # Inter-track gap insertion (after dither, before write)
    track_gap = p.get('track_gap', 0.0)
    if track_gap > 0:
        gap_samples = int(rate * track_gap)
        if data.ndim == 1:
            silence = np.zeros(gap_samples, dtype=data.dtype)
        else:
            silence = np.zeros((gap_samples, data.shape[1]), dtype=data.dtype)
        data = np.concatenate([silence, data], axis=0)

    # Write output
    subtype = 'PCM_16' if output_bits <= 16 else 'PCM_24'
    sf.write(output_path, data, rate, subtype=subtype)

    result = {
        'original_lufs': current_lufs,
        'final_lufs': final_lufs,
        'gain_applied': gain_db,
        'final_peak': final_peak,
    }
    if measured_lra is not None:
        result['lra'] = measured_lra

    return result

def _process_one_track(wav_file: Path | str, output_path: Path | str,
                       target_lufs: float = -14.0,
                       eq_settings: list[tuple[float, float, float]] | None = None,
                       ceiling_db: float = -1.0, dry_run: bool = False,
                       compress_ratio: float = 1.5,
                       preset: dict[str, float] | None = None,
                       ) -> tuple[str, dict[str, Any] | None]:
    """Process a single track (used by both sequential and parallel paths).

    Returns (wav_file_name, result_dict) or (wav_file_name, None) if skipped.
    """
    if dry_run:
        data, rate = sf.read(str(wav_file))
        if len(data.shape) == 1:
            data = np.column_stack([data, data])
        meter = pyln.Meter(rate)
        effective_lufs = target_lufs
        if preset is not None:
            effective_lufs = preset.get('target_lufs', target_lufs)
        current_lufs = meter.integrated_loudness(data)
        if not np.isfinite(current_lufs):
            return (str(wav_file), None)
        gain = effective_lufs - current_lufs
        result = {
            'original_lufs': current_lufs,
            'final_lufs': effective_lufs,
            'gain_applied': gain,
            'final_peak': -1.0,
        }
    else:
        result = master_track(
            str(wav_file),
            str(output_path),
            target_lufs=target_lufs,
            eq_settings=eq_settings,
            ceiling_db=ceiling_db,
            compress_ratio=compress_ratio,
            preset=preset,
        )

    if result.get('skipped'):
        return (str(wav_file), None)

    return (str(wav_file), result)


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Master audio tracks for streaming',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Genre presets available: {', '.join(sorted(GENRE_PRESETS.keys()))}

Examples:
  python master_tracks.py ~/music/album/ --genre country
  python master_tracks.py . --cut-highmid -2
  python master_tracks.py /path/to/tracks --dry-run --genre rock
        """
    )
    parser.add_argument('path', nargs='?', default='.',
                       help='Path to directory containing WAV files (default: current directory)')
    parser.add_argument('--genre', '-g', type=str,
                       help=f'Apply genre preset ({", ".join(sorted(set(GENRE_PRESETS.keys())))})')
    parser.add_argument('--target-lufs', type=float, default=None,
                       help='Target loudness in LUFS (default: -14 for streaming)')
    parser.add_argument('--ceiling', type=float, default=-1.0,
                       help='True peak ceiling in dB (default: -1.0)')
    parser.add_argument('--cut-highmid', type=float, default=None,
                       help='High-mid cut in dB at eq_highmid_freq (e.g., -2 for 2dB cut)')
    parser.add_argument('--cut-highs', type=float, default=None,
                       help='High shelf cut in dB at eq_highs_freq')
    parser.add_argument('--output-dir', type=str, default='mastered',
                       help='Output directory (default: mastered)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Analyze only, do not write files')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Show debug output')
    parser.add_argument('--quiet', '-q', action='store_true',
                       help='Show only warnings and errors')
    parser.add_argument('--compress-ratio', type=float, default=None,
                       help='Mastering compression ratio (1.0=bypass, default: genre preset or 1.5)')
    parser.add_argument('--compress-threshold', type=float, default=None,
                       help='Compression threshold in dB (default: -18.0)')
    parser.add_argument('--compress-attack', type=float, default=None,
                       help='Compression attack in ms (default: 30.0)')
    parser.add_argument('--compress-release', type=float, default=None,
                       help='Compression release in ms (default: 200.0)')
    parser.add_argument('--eq-highmid-freq', type=float, default=None,
                       help='High-mid EQ center frequency in Hz (default: 3500.0)')
    parser.add_argument('--eq-highmid-q', type=float, default=None,
                       help='High-mid EQ Q factor (default: 1.5)')
    parser.add_argument('--eq-highs-freq', type=float, default=None,
                       help='High shelf frequency in Hz (default: 8000.0)')
    parser.add_argument('--eq-highs-q', type=float, default=None,
                       help='High shelf Q factor (default: 0.7)')
    parser.add_argument('--eq-low-gain', type=float, default=None,
                       help='Low shelf gain in dB at eq-low-freq (default: 0 = bypass)')
    parser.add_argument('--eq-low-freq', type=float, default=None,
                       help='Low shelf frequency in Hz (default: 80.0)')
    parser.add_argument('--sub-cut', type=float, default=None,
                       help='High-pass filter frequency in Hz to remove sub-bass rumble (default: 0 = bypass)')
    parser.add_argument('--stereo-width', type=float, default=None,
                       help='Stereo width multiplier (0.0=mono, 1.0=unchanged, >1.0=wider)')
    parser.add_argument('--bass-mono-freq', type=float, default=None,
                       help='Mono-sum frequencies below this in Hz (default: 0 = bypass)')
    parser.add_argument('--output-bits', type=int, default=None,
                       help='Output bit depth (16 or 24, default: 16)')
    parser.add_argument('--dither-bits', type=int, default=None,
                       help='Dither bit depth (default: follows --output-bits)')
    parser.add_argument('--limiter-lookahead', type=float, default=None,
                       help='Look-ahead buffer in ms (0 = reactive, default: 5.0)')
    parser.add_argument('--limiter-release', type=float, default=None,
                       help='Limiter release time in ms (default: 50.0)')
    parser.add_argument('--compress-mix', type=float, default=None,
                       help='Compression wet/dry blend (0.0=dry, 1.0=wet, default: 1.0)')
    parser.add_argument('--compress-makeup', type=float, default=None,
                       help='Compression makeup gain in dB (0 = off, default: 0)')
    parser.add_argument('--processing-oversample', type=int, default=None,
                       help='Oversample factor for nonlinear stages (1/2/4, default: 1)')
    parser.add_argument('--target-lra', type=float, default=None,
                       help='Target loudness range in LU (0 = disable, default: 0)')
    parser.add_argument('--dc-filter-freq', type=float, default=None,
                       help='DC offset removal HPF frequency in Hz (0 = bypass, default: 5.0)')
    parser.add_argument('--output-sample-rate', type=int, default=None,
                       help='Target sample rate (0 = preserve input, e.g., 44100)')
    parser.add_argument('--deess', action='store_true', default=None,
                       help='Enable de-esser')
    parser.add_argument('--deess-freq', type=float, default=None,
                       help='De-esser center frequency in Hz (default: 6500)')
    parser.add_argument('--deess-threshold', type=float, default=None,
                       help='De-esser threshold in dB (default: -20.0)')
    parser.add_argument('--deess-ratio', type=float, default=None,
                       help='De-esser compression ratio (default: 4.0)')
    parser.add_argument('--track-gap', type=float, default=None,
                       help='Silence to prepend to each track in seconds (default: 0)')
    parser.add_argument('-j', '--jobs', type=int, default=1,
                       help='Parallel jobs (0=auto, default: 1)')

    args = parser.parse_args()

    setup_logging(__name__, verbose=args.verbose, quiet=args.quiet)

    # Build preset dict: start with defaults, layer genre preset, then CLI overrides
    preset = {**_PRESET_DEFAULTS}

    if args.genre:
        genre_key = args.genre.lower()
        if genre_key not in GENRE_PRESETS:
            logger.error("Unknown genre: %s", args.genre)
            logger.error("Available: %s", ', '.join(sorted(GENRE_PRESETS.keys())))
            return
        preset.update(GENRE_PRESETS[genre_key])

    # CLI overrides (only apply if explicitly set)
    cli_overrides = {
        'target_lufs': args.target_lufs,
        'cut_highmid': args.cut_highmid,
        'cut_highs': args.cut_highs,
        'compress_ratio': args.compress_ratio,
        'compress_threshold': args.compress_threshold,
        'compress_attack': args.compress_attack,
        'compress_release': args.compress_release,
        'eq_highmid_freq': args.eq_highmid_freq,
        'eq_highmid_q': args.eq_highmid_q,
        'eq_highs_freq': args.eq_highs_freq,
        'eq_highs_q': args.eq_highs_q,
        'eq_low_gain': args.eq_low_gain,
        'eq_low_freq': args.eq_low_freq,
        'eq_sub_cut_freq': float(args.sub_cut) if args.sub_cut is not None else None,
        'stereo_width': args.stereo_width,
        'stereo_bass_mono_freq': float(args.bass_mono_freq) if args.bass_mono_freq is not None else None,
        'output_bits': float(args.output_bits) if args.output_bits is not None else None,
        'dither_bits': float(args.dither_bits) if args.dither_bits is not None else None,
        'limiter_lookahead_ms': args.limiter_lookahead,
        'limiter_release_ms': args.limiter_release,
        'compress_mix': args.compress_mix,
        'compress_makeup': args.compress_makeup,
        'processing_oversample': float(args.processing_oversample) if args.processing_oversample is not None else None,
        'target_lra': args.target_lra,
        'dc_filter_freq': args.dc_filter_freq,
        'output_sample_rate': float(args.output_sample_rate) if args.output_sample_rate is not None else None,
        'deess_enabled': 1.0 if args.deess else None,
        'deess_freq': args.deess_freq,
        'deess_threshold': args.deess_threshold,
        'deess_ratio': args.deess_ratio,
        'track_gap': args.track_gap,
    }
    for key, value in cli_overrides.items():
        if value is not None:
            preset[key] = float(value)

    # Setup
    input_dir = Path(args.path).expanduser().resolve()
    if not input_dir.exists():
        logger.error("Directory not found: %s", input_dir)
        sys.exit(1)

    output_dir = (input_dir / args.output_dir).resolve()

    # Prevent path traversal: output must stay within input directory
    try:
        output_dir.relative_to(input_dir)
    except ValueError:
        logger.error("Output directory must be within input directory")
        logger.error("  Output: %s", output_dir)
        logger.error("  Input:  %s", input_dir)
        sys.exit(1)

    if not args.dry_run:
        output_dir.mkdir(exist_ok=True)

    # Find wav files (case-insensitive for cross-platform compatibility)
    # Check originals/ subdirectory first, fall back to album root
    originals = input_dir / "originals"
    source_dir = originals if originals.is_dir() else input_dir
    wav_files = sorted([f for f in source_dir.iterdir()
                       if f.suffix.lower() == '.wav'
                       and 'venv' not in str(f)])

    print("=" * 70)
    print("MASTERING SESSION")
    print("=" * 70)
    if args.genre:
        print(f"Genre preset: {args.genre}")
    print(f"Target LUFS: {preset['target_lufs']}")
    print(f"Peak ceiling: {args.ceiling} dBTP")
    if preset['cut_highmid'] != 0:
        print(f"EQ: High-mid cut: {preset['cut_highmid']}dB at {preset['eq_highmid_freq']}Hz (Q={preset['eq_highmid_q']})")
    if preset['cut_highs'] != 0:
        print(f"EQ: High shelf cut: {preset['cut_highs']}dB at {preset['eq_highs_freq']}Hz (Q={preset['eq_highs_q']})")
    if preset['compress_ratio'] > 1.0:
        print(f"Compression: {preset['compress_ratio']}:1 (threshold={preset['compress_threshold']}dB, attack={preset['compress_attack']}ms, release={preset['compress_release']}ms)")
    else:
        print("Compression: bypass")
    if preset.get('eq_sub_cut_freq', 0) > 0:
        print(f"EQ: Sub cut HPF: {int(preset['eq_sub_cut_freq'])}Hz")
    if preset.get('eq_low_gain', 0) != 0:
        print(f"EQ: Low shelf: {preset['eq_low_gain']}dB at {preset['eq_low_freq']}Hz")
    if preset.get('stereo_width', 1.0) != 1.0:
        print(f"Stereo width: {preset['stereo_width']}x")
    if preset.get('stereo_bass_mono_freq', 0) > 0:
        print(f"Bass mono below: {int(preset['stereo_bass_mono_freq'])}Hz")
    out_bits = int(preset.get('output_bits', 16))
    if out_bits != 16:
        print(f"Output: {out_bits}-bit")
    print(f"Output: {output_dir}/")
    print("=" * 70)
    print()

    if args.dry_run:
        logger.info("DRY RUN - No files will be written")
        print()

    print(f"{'Track':<35} {'Before':>8} {'After':>8} {'Gain':>8} {'Peak':>8}")
    print("-" * 70)

    workers = args.jobs if args.jobs > 0 else os.cpu_count()

    # Build list of (wav_file, output_path) pairs
    tasks = [(wf, output_dir / wf.name) for wf in wav_files]

    results = []
    progress = ProgressBar(len(tasks), prefix="Mastering")

    if workers == 1:
        # Sequential (existing behavior)
        for wav_file, output_path in tasks:
            progress.update(wav_file.name)
            _, result = _process_one_track(
                wav_file, output_path,
                ceiling_db=args.ceiling,
                dry_run=args.dry_run,
                preset=preset,
            )
            if result is None:
                continue
            results.append((wav_file.name, result))
            name = wav_file.name[:34]
            print(f"{name:<35} {result['original_lufs']:>7.1f} {result['final_lufs']:>7.1f} "
                  f"{result['gain_applied']:>+7.1f} {result['final_peak']:>7.1f}")
    else:
        # Parallel
        logger.info("Using %d parallel workers", workers)
        ordered_results = {}
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(
                    _process_one_track, wf, op,
                    ceiling_db=args.ceiling,
                    dry_run=args.dry_run,
                    preset=preset,
                ): i
                for i, (wf, op) in enumerate(tasks)
            }
            for future in as_completed(futures):
                idx = futures[future]
                progress.update(tasks[idx][0].name)
                wav_name, result = future.result()
                if result is not None:
                    ordered_results[idx] = (Path(wav_name).name, result)
        # Print table in original order
        for idx in sorted(ordered_results):
            name, result = ordered_results[idx]
            results.append((name, result))
            display = name[:34]
            print(f"{display:<35} {result['original_lufs']:>7.1f} {result['final_lufs']:>7.1f} "
                  f"{result['gain_applied']:>+7.1f} {result['final_peak']:>7.1f}")

    print("-" * 70)

    if not results:
        print("\nNo tracks were processed (all silent or no WAV files found).")
        return

    # Summary
    gains = [result['gain_applied'] for _, result in results]
    finals = [result['final_lufs'] for _, result in results]

    print()
    print("SUMMARY:")
    print(f"  Gain range applied: {min(gains):+.1f} to {max(gains):+.1f} dB")
    print(f"  Final LUFS range: {max(finals) - min(finals):.2f} dB (target: < 0.5 dB)")
    print()

    if not args.dry_run:
        print(f"Mastered files written to: {output_dir.absolute()}/")
    else:
        print("Run without --dry-run to process files")

if __name__ == '__main__':
    main()
