#!/usr/bin/env python3
"""
Automated Mix Polish Pipeline for Suno Stems

Processes per-stem audio (vocals, drums, bass, other) with targeted
cleanup and EQ, then remixes into a polished stereo WAV ready for mastering.

Falls back to full-mix processing when stems are not available.
"""

import argparse
import logging
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

import numpy as np
import soundfile as sf
from scipy import signal

try:
    import noisereduce as nr
except ImportError:
    nr = None

try:
    import yaml
except ImportError:
    yaml = None

# Ensure project root is on sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.shared.logging_config import setup_logging
from tools.shared.progress import ProgressBar

logger = logging.getLogger(__name__)

# Built-in presets file (ships with plugin)
_BUILTIN_PRESETS_FILE = Path(__file__).parent / "mix-presets.yaml"

# User override location
_CONFIG_PATH = Path.home() / ".bitwize-music" / "config.yaml"

# Stem names in processing order
STEM_NAMES = ("vocals", "drums", "bass", "other")

# Suno stem keyword → category mapping (case-insensitive, checked in order)
_STEM_KEYWORDS = {
    "vocals": ["vocal"],
    "drums": ["drum"],
    "bass": ["bass"],
    # "other" is the catch-all — anything not matching above
}


def discover_stems(track_dir):
    """Discover and categorize stem WAV files in a directory.

    Supports both standard naming (vocals.wav) and Suno naming
    (0 Lead Vocals.wav, 1 Backing Vocals.wav, etc.).

    When multiple files match one category (e.g., lead + backing vocals),
    all are returned so they can be combined during processing.

    Args:
        track_dir: Path to directory containing stem WAV files.

    Returns:
        Dict mapping stem category to path (str) or list of paths (list[str]).
        Single files are returned as strings for backward compatibility.
        Multiple files for one category are returned as a list.
    """
    track_dir = Path(track_dir)
    result = {}

    # Try standard names first (exact match — verify actual filename case
    # to avoid false positives on case-insensitive filesystems like macOS)
    for stem_name in STEM_NAMES:
        stem_file = track_dir / f"{stem_name}.wav"
        if stem_file.exists() and stem_file.name in os.listdir(track_dir):
            result[stem_name] = str(stem_file)

    if result:
        return result

    # Fall back to pattern matching on all WAV files
    wav_files = sorted([
        f for f in track_dir.iterdir()
        if f.suffix.lower() == ".wav"
    ])

    if not wav_files:
        return result

    categorized = {name: [] for name in STEM_NAMES}

    for wav_file in wav_files:
        name_lower = wav_file.stem.lower()
        matched = False
        for stem_cat, keywords in _STEM_KEYWORDS.items():
            if any(kw in name_lower for kw in keywords):
                categorized[stem_cat].append(str(wav_file))
                matched = True
                break
        if not matched:
            categorized["other"].append(str(wav_file))

    for stem_name, paths in categorized.items():
        if len(paths) == 1:
            result[stem_name] = paths[0]
        elif len(paths) > 1:
            result[stem_name] = paths

    return result


# ─── YAML / Config Helpers ───────────────────────────────────────────


def _load_yaml_file(path: Path) -> dict:
    """Load a YAML file, returning empty dict on failure."""
    if not path.exists():
        return {}
    if yaml is None:
        logger.debug("PyYAML not installed, cannot load %s", path)
        return {}
    try:
        with open(path) as f:
            return yaml.safe_load(f) or {}
    except (yaml.YAMLError, OSError) as e:
        logger.warning("Cannot read %s: %s", path, e)
        return {}


def _get_overrides_path() -> Optional[Path]:
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


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep-merge override dict into base dict (override wins).

    Skips None values from override to handle bare YAML keys gracefully.
    """
    merged = base.copy()
    for key, value in override.items():
        if value is None:
            continue
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_mix_presets() -> dict:
    """Load mix presets from YAML, merging built-in with user overrides.

    Returns:
        Dict with 'defaults' and 'genres' keys containing per-stem settings.
    """
    builtin = _load_yaml_file(_BUILTIN_PRESETS_FILE)
    defaults = builtin.get('defaults', {})
    genres = builtin.get('genres', {})

    # Load user overrides
    overrides_dir = _get_overrides_path()
    if overrides_dir:
        override_file = overrides_dir / 'mix-presets.yaml'
        override_data = _load_yaml_file(override_file)
        if override_data.get('defaults'):
            defaults = _deep_merge(defaults, override_data['defaults'])
        for genre_name, genre_overrides in override_data.get('genres', {}).items():
            if not isinstance(genre_overrides, dict):
                continue
            if genre_name in genres:
                genres[genre_name] = _deep_merge(genres[genre_name], genre_overrides)
            else:
                genres[genre_name] = genre_overrides

    return {'defaults': defaults, 'genres': genres}


# Load presets at import time (fast — just two small YAML reads)
MIX_PRESETS = load_mix_presets()


# ─── Audio Processing Functions ──────────────────────────────────────


def reduce_noise(data, rate, strength=0.5):
    """Apply spectral gating noise reduction for AI artifact cleanup.

    Args:
        data: Audio data (samples,) or (samples, channels)
        rate: Sample rate
        strength: Noise reduction strength (0.0-1.0). Higher = more aggressive.

    Returns:
        Noise-reduced audio data, same shape as input.
    """
    if nr is None:
        logger.warning("noisereduce not installed, skipping noise reduction")
        return data
    if strength <= 0:
        return data

    # Clamp strength
    strength = min(strength, 1.0)

    # prop_decrease maps strength to how much noise is removed
    prop_decrease = strength

    if len(data.shape) == 1:
        return nr.reduce_noise(
            y=data, sr=rate,
            prop_decrease=prop_decrease,
            stationary=True,
        )
    else:
        result = np.zeros_like(data)
        for ch in range(data.shape[1]):
            result[:, ch] = nr.reduce_noise(
                y=data[:, ch], sr=rate,
                prop_decrease=prop_decrease,
                stationary=True,
            )
        return result


def apply_highpass(data, rate, cutoff=30):
    """Apply Butterworth highpass filter for rumble removal.

    Args:
        data: Audio data
        rate: Sample rate
        cutoff: Cutoff frequency in Hz

    Returns:
        Highpass-filtered audio data.
    """
    nyquist = rate / 2
    if cutoff <= 0 or cutoff >= nyquist:
        if cutoff > 0:
            logger.warning("Highpass cutoff %d Hz out of range (0–%.0f Hz), skipping", cutoff, nyquist)
        return data

    normalized_cutoff = cutoff / nyquist
    # 2nd order Butterworth
    b, a = signal.butter(2, normalized_cutoff, btype='high')

    # Verify stability
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


def apply_eq(data, rate, freq, gain_db, q=1.0):
    """Apply parametric EQ (peaking filter) to audio data.

    Reuses the same biquad design as master_tracks.py.

    Args:
        data: Audio data (samples x channels)
        rate: Sample rate
        freq: Center frequency in Hz
        gain_db: Gain in dB (negative for cut)
        q: Q factor (higher = narrower)
    """
    nyquist = rate / 2
    if not (20 <= freq < nyquist):
        logger.warning("EQ freq %.1f Hz out of valid range (20–%.0f Hz), skipping", freq, nyquist)
        return data
    if q <= 0:
        logger.warning("EQ Q factor must be positive (got %.4f), skipping", q)
        return data
    if gain_db == 0:
        return data

    A = 10 ** (gain_db / 40)
    w0 = 2 * np.pi * freq / rate
    alpha = np.sin(w0) / (2 * q)

    b0 = 1 + alpha * A
    b1 = -2 * np.cos(w0)
    b2 = 1 - alpha * A
    a0 = 1 + alpha / A
    a1 = -2 * np.cos(w0)
    a2 = 1 - alpha / A

    b = np.array([b0/a0, b1/a0, b2/a0])
    a = np.array([1, a1/a0, a2/a0])

    poles = np.roots(a)
    if not np.all(np.abs(poles) < 1.0):
        logger.warning("Unstable EQ filter at %.1f Hz, skipping", freq)
        return data

    if len(data.shape) == 1:
        return signal.lfilter(b, a, data)
    else:
        result = np.zeros_like(data)
        for ch in range(data.shape[1]):
            result[:, ch] = signal.lfilter(b, a, data[:, ch])
        return result


def apply_high_shelf(data, rate, freq, gain_db):
    """Apply high shelf EQ for taming brightness/sibilance.

    Args:
        data: Audio data
        rate: Sample rate
        freq: Shelf corner frequency in Hz
        gain_db: Gain in dB (negative for cut)
    """
    nyquist = rate / 2
    if not (20 <= freq < nyquist):
        return data
    if gain_db == 0:
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

    poles = np.roots(a)
    if not np.all(np.abs(poles) < 1.0):
        logger.warning("Unstable high shelf at %.1f Hz, skipping", freq)
        return data

    if len(data.shape) == 1:
        return signal.lfilter(b, a, data)
    else:
        result = np.zeros_like(data)
        for ch in range(data.shape[1]):
            result[:, ch] = signal.lfilter(b, a, data[:, ch])
        return result


def gentle_compress(data, rate, threshold_db=-15.0, ratio=2.5, attack_ms=10.0,
                    release_ms=100.0):
    """Apply gentle dynamic compression using envelope following.

    Args:
        data: Audio data
        rate: Sample rate
        threshold_db: Compression threshold in dB
        ratio: Compression ratio (e.g., 2.5 = 2.5:1)
        attack_ms: Attack time in milliseconds
        release_ms: Release time in milliseconds

    Returns:
        Compressed audio data.
    """
    if ratio <= 1.0:
        return data

    threshold_linear = 10 ** (threshold_db / 20)

    # Time constants
    attack_coeff = np.exp(-1.0 / (rate * attack_ms / 1000.0))
    release_coeff = np.exp(-1.0 / (rate * release_ms / 1000.0))

    def _compress_channel(channel):
        envelope = np.zeros_like(channel)
        abs_signal = np.abs(channel)

        # Envelope follower
        env = 0.0
        for i in range(len(channel)):
            if abs_signal[i] > env:
                env = attack_coeff * env + (1.0 - attack_coeff) * abs_signal[i]
            else:
                env = release_coeff * env + (1.0 - release_coeff) * abs_signal[i]
            envelope[i] = env

        # Calculate gain reduction
        gain = np.ones_like(channel)
        above = envelope > threshold_linear
        if np.any(above):
            # dB domain compression
            env_db = np.where(above, 20 * np.log10(np.maximum(envelope, 1e-10)), 0)
            thresh_db = 20 * np.log10(max(threshold_linear, 1e-10))
            excess_db = np.where(above, env_db - thresh_db, 0)
            gain_reduction_db = excess_db * (1 - 1 / ratio)
            gain = np.where(above, 10 ** (-gain_reduction_db / 20), 1.0)

        return channel * gain

    if len(data.shape) == 1:
        return _compress_channel(data)
    else:
        result = np.zeros_like(data)
        for ch in range(data.shape[1]):
            result[:, ch] = _compress_channel(data[:, ch])
        return result


def remove_clicks(data, rate, threshold=6.0):
    """Detect and remove clicks/pops via interpolation.

    Looks for sudden amplitude spikes relative to local neighborhood
    and replaces them with linearly interpolated values.

    Args:
        data: Audio data
        rate: Sample rate
        threshold: Detection threshold in standard deviations

    Returns:
        Click-removed audio data.
    """
    if threshold <= 0:
        return data

    def _remove_clicks_channel(channel):
        # Calculate first-order difference
        diff = np.diff(channel, prepend=channel[0])

        # Guard against very short audio
        if len(channel) < 3:
            return channel

        local_std = np.std(diff)
        if local_std < 1e-10:
            return channel

        # Detect clicks: spikes above threshold * std
        click_mask = np.abs(diff) > threshold * local_std

        if not np.any(click_mask):
            return channel

        result = channel.copy()
        click_indices = np.where(click_mask)[0]

        # Interpolate over click regions
        for idx in click_indices:
            # Find clean samples on either side
            left = max(0, idx - 1)
            right = min(len(channel) - 1, idx + 1)
            while left > 0 and click_mask[left]:
                left -= 1
            while right < len(channel) - 1 and click_mask[right]:
                right += 1
            # Linear interpolation
            if left != right:
                result[idx] = channel[left] + (channel[right] - channel[left]) * (idx - left) / (right - left)

        return result

    if len(data.shape) == 1:
        return _remove_clicks_channel(data)
    else:
        result = np.zeros_like(data)
        for ch in range(data.shape[1]):
            result[:, ch] = _remove_clicks_channel(data[:, ch])
        return result


def apply_saturation(data, rate, drive=0.0, tone='warm'):
    """Apply soft harmonic distortion via tanh waveshaping.

    Args:
        data: Audio data (samples,) or (samples, channels)
        rate: Sample rate
        drive: Saturation amount (0.0 = bypass, 1.0 = heavy)
        tone: 'warm' applies gentle high-shelf rolloff after saturation;
              'neutral' skips the rolloff

    Returns:
        Saturated audio data, same shape as input.
    """
    if drive <= 0:
        return data

    drive = min(drive, 1.0)

    # Scale input by drive amount, apply tanh, scale back
    # Higher drive = more harmonics
    gain = 1.0 + drive * 4.0  # Maps 0-1 to 1-5x input gain
    result = np.tanh(data * gain) / np.tanh(gain)

    # Warm tone: gentle high-shelf rolloff to tame harshness from harmonics
    if tone == 'warm':
        result = apply_high_shelf(result, rate, freq=8000, gain_db=-1.5 * drive)

    return result


def apply_lowpass(data, rate, cutoff=20000):
    """Apply 2nd-order Butterworth lowpass filter.

    Args:
        data: Audio data (samples,) or (samples, channels)
        rate: Sample rate
        cutoff: Cutoff frequency in Hz (default 20000 = effectively off)

    Returns:
        Lowpass-filtered audio data.
    """
    nyquist = rate / 2
    if cutoff <= 0 or cutoff >= nyquist:
        return data

    normalized_cutoff = cutoff / nyquist
    b, a = signal.butter(2, normalized_cutoff, btype='low')

    # Verify stability
    poles = np.roots(a)
    if not np.all(np.abs(poles) < 1.0):
        logger.warning("Unstable lowpass filter at %d Hz, skipping", cutoff)
        return data

    if len(data.shape) == 1:
        return signal.lfilter(b, a, data)
    else:
        result = np.zeros_like(data)
        for ch in range(data.shape[1]):
            result[:, ch] = signal.lfilter(b, a, data[:, ch])
        return result


def apply_stereo_width(data, rate, width=1.0):
    """Adjust stereo width using mid-side processing.

    Args:
        data: Audio data (samples, 2) — stereo only
        rate: Sample rate (unused, kept for API consistency)
        width: Width multiplier.
            < 1.0 = narrower (more mono)
            1.0 = passthrough (no change)
            > 1.0 = wider (more side signal)

    Returns:
        Width-adjusted stereo audio data.
    """
    if len(data.shape) == 1 or data.shape[1] != 2:
        return data
    if width == 1.0:
        return data

    # Mid-side encoding
    mid = (data[:, 0] + data[:, 1]) / 2
    side = (data[:, 0] - data[:, 1]) / 2

    # Scale side signal by width factor
    side = side * width

    # Decode back to L/R
    result = np.zeros_like(data)
    result[:, 0] = mid + side
    result[:, 1] = mid - side

    return result


def enhance_stereo(data, rate, amount=0.2):
    """Enhance stereo width using mid-side processing.

    Args:
        data: Stereo audio data (samples, 2)
        rate: Sample rate (unused, kept for API consistency)
        amount: Width enhancement amount (0.0 = no change, 1.0 = max)

    Returns:
        Width-enhanced stereo audio data.
    """
    if len(data.shape) == 1 or data.shape[1] != 2:
        return data
    if amount <= 0:
        return data

    amount = min(amount, 1.0)

    # Mid-side encoding
    mid = (data[:, 0] + data[:, 1]) / 2
    side = (data[:, 0] - data[:, 1]) / 2

    # Enhance side signal
    side = side * (1 + amount)

    # Decode back to L/R
    result = np.zeros_like(data)
    result[:, 0] = mid + side
    result[:, 1] = mid - side

    return result


def remix_stems(stems_dict, gains_dict=None):
    """Combine processed stems into a stereo mix.

    Args:
        stems_dict: Dict mapping stem name to (data, rate) tuples
        gains_dict: Optional dict mapping stem name to gain in dB

    Returns:
        (mixed_data, rate) tuple.
    """
    if not stems_dict:
        raise ValueError("No stems to remix")

    gains_dict = gains_dict or {}

    # Get rate from first stem and verify all stems match
    first_stem = next(iter(stems_dict.values()))
    rate = first_stem[1]
    for stem_name, (_, stem_rate) in stems_dict.items():
        if stem_rate != rate:
            logger.warning(
                "Stem '%s' has sample rate %d (expected %d) — remix may be incorrect",
                stem_name, stem_rate, rate,
            )

    # Find max length
    max_len = max(data.shape[0] for data, _ in stems_dict.values())

    # Determine channel count (use 2 for stereo output)
    channels = 2
    mixed = np.zeros((max_len, channels), dtype=np.float64)

    for stem_name, (data, _) in stems_dict.items():
        gain_db = gains_dict.get(stem_name, 0.0)
        gain_linear = 10 ** (gain_db / 20)

        # Ensure stereo
        if len(data.shape) == 1:
            stem_stereo = np.column_stack([data, data])
        elif data.shape[1] == 1:
            stem_stereo = np.column_stack([data[:, 0], data[:, 0]])
        else:
            stem_stereo = data[:, :2]

        # Pad if needed
        if stem_stereo.shape[0] < max_len:
            padded = np.zeros((max_len, channels), dtype=np.float64)
            padded[:stem_stereo.shape[0]] = stem_stereo
            stem_stereo = padded

        mixed += stem_stereo * gain_linear

    # Prevent clipping
    peak = np.max(np.abs(mixed))
    if peak > 0.95:
        mixed = mixed * (0.95 / peak)

    return mixed, rate


# ─── Per-Stem Processing Chains ──────────────────────────────────────


def _get_stem_settings(stem_name, genre=None):
    """Get processing settings for a specific stem type.

    Args:
        stem_name: One of 'vocals', 'drums', 'bass', 'other'
        genre: Optional genre name for genre-specific overrides

    Returns:
        Dict of processing settings for this stem.
    """
    presets = MIX_PRESETS
    defaults = presets.get('defaults', {})
    stem_defaults = defaults.get(stem_name, {})

    if genre:
        genre_key = genre.lower()
        genre_presets = presets.get('genres', {}).get(genre_key, {})
        genre_stem = genre_presets.get(stem_name, {})
        return _deep_merge(stem_defaults, genre_stem)

    return stem_defaults.copy()


def _get_full_mix_settings(genre=None):
    """Get processing settings for full-mix fallback mode.

    Args:
        genre: Optional genre name for genre-specific overrides

    Returns:
        Dict of processing settings for full-mix mode.
    """
    presets = MIX_PRESETS
    defaults = presets.get('defaults', {})
    full_mix_defaults = defaults.get('full_mix', {})

    if genre:
        genre_key = genre.lower()
        genre_presets = presets.get('genres', {}).get(genre_key, {})
        genre_full_mix = genre_presets.get('full_mix', {})
        return _deep_merge(full_mix_defaults, genre_full_mix)

    return full_mix_defaults.copy()


def process_vocals(data, rate, settings=None):
    """Process vocal stem: noise reduction -> presence boost -> high tame -> compress.

    Args:
        data: Audio data
        rate: Sample rate
        settings: Dict of vocal processing settings

    Returns:
        Processed audio data.
    """
    settings = settings or _get_stem_settings('vocals')

    # Noise reduction
    nr_strength = settings.get('noise_reduction', 0.5)
    if nr_strength > 0:
        data = reduce_noise(data, rate, strength=nr_strength)

    # Presence boost (~3 kHz)
    presence_db = settings.get('presence_boost_db', 2.0)
    presence_freq = settings.get('presence_freq', 3000)
    if presence_db != 0:
        data = apply_eq(data, rate, freq=presence_freq, gain_db=presence_db, q=1.5)

    # Tame highs (~7 kHz)
    high_tame_db = settings.get('high_tame_db', -2.0)
    high_tame_freq = settings.get('high_tame_freq', 7000)
    if high_tame_db != 0:
        data = apply_high_shelf(data, rate, freq=high_tame_freq, gain_db=high_tame_db)

    # Gentle compression
    comp_threshold = settings.get('compress_threshold_db', -15.0)
    comp_ratio = settings.get('compress_ratio', 2.5)
    comp_attack = settings.get('compress_attack_ms', 10.0)
    if comp_ratio > 1.0:
        data = gentle_compress(data, rate, threshold_db=comp_threshold,
                               ratio=comp_ratio, attack_ms=comp_attack)

    # Saturation (genre character)
    sat_drive = settings.get('saturation_drive', 0)
    if sat_drive > 0:
        data = apply_saturation(data, rate, drive=sat_drive)

    # Lowpass (vintage/lo-fi character)
    lp_cutoff = settings.get('lowpass_cutoff', 20000)
    if lp_cutoff < 20000:
        data = apply_lowpass(data, rate, cutoff=lp_cutoff)

    return data


def process_drums(data, rate, settings=None):
    """Process drum stem: click removal -> compress (fast attack).

    Args:
        data: Audio data
        rate: Sample rate
        settings: Dict of drum processing settings

    Returns:
        Processed audio data.
    """
    settings = settings or _get_stem_settings('drums')

    # Click removal
    if settings.get('click_removal', True):
        click_threshold = settings.get('click_threshold', 6.0)
        data = remove_clicks(data, rate, threshold=click_threshold)

    # Compression with fast attack for transient preservation
    comp_threshold = settings.get('compress_threshold_db', -12.0)
    comp_ratio = settings.get('compress_ratio', 2.0)
    comp_attack = settings.get('compress_attack_ms', 5.0)
    if comp_ratio > 1.0:
        data = gentle_compress(data, rate, threshold_db=comp_threshold,
                               ratio=comp_ratio, attack_ms=comp_attack)

    # Saturation (genre character)
    sat_drive = settings.get('saturation_drive', 0)
    if sat_drive > 0:
        data = apply_saturation(data, rate, drive=sat_drive)

    return data


def process_bass(data, rate, settings=None):
    """Process bass stem: highpass -> mud cut -> compress.

    Args:
        data: Audio data
        rate: Sample rate
        settings: Dict of bass processing settings

    Returns:
        Processed audio data.
    """
    settings = settings or _get_stem_settings('bass')

    # Highpass for sub-rumble removal
    hp_cutoff = settings.get('highpass_cutoff', 30)
    if hp_cutoff > 0:
        data = apply_highpass(data, rate, cutoff=hp_cutoff)

    # Mud cut (~200 Hz)
    mud_cut_db = settings.get('mud_cut_db', -3.0)
    mud_freq = settings.get('mud_freq', 200)
    if mud_cut_db != 0:
        data = apply_eq(data, rate, freq=mud_freq, gain_db=mud_cut_db, q=1.0)

    # Compression
    comp_threshold = settings.get('compress_threshold_db', -15.0)
    comp_ratio = settings.get('compress_ratio', 3.0)
    comp_attack = settings.get('compress_attack_ms', 10.0)
    if comp_ratio > 1.0:
        data = gentle_compress(data, rate, threshold_db=comp_threshold,
                               ratio=comp_ratio, attack_ms=comp_attack)

    # Saturation (genre character)
    sat_drive = settings.get('saturation_drive', 0)
    if sat_drive > 0:
        data = apply_saturation(data, rate, drive=sat_drive)

    return data


def process_other(data, rate, settings=None):
    """Process 'other' stem (instruments, synths): noise reduction -> mud cut -> high tame.

    Args:
        data: Audio data
        rate: Sample rate
        settings: Dict of processing settings

    Returns:
        Processed audio data.
    """
    settings = settings or _get_stem_settings('other')

    # Noise reduction (lighter than vocals)
    nr_strength = settings.get('noise_reduction', 0.3)
    if nr_strength > 0:
        data = reduce_noise(data, rate, strength=nr_strength)

    # Mud cut (~300 Hz)
    mud_cut_db = settings.get('mud_cut_db', -2.0)
    mud_freq = settings.get('mud_freq', 300)
    if mud_cut_db != 0:
        data = apply_eq(data, rate, freq=mud_freq, gain_db=mud_cut_db, q=1.0)

    # Tame highs
    high_tame_db = settings.get('high_tame_db', -1.5)
    high_tame_freq = settings.get('high_tame_freq', 8000)
    if high_tame_db != 0:
        data = apply_high_shelf(data, rate, freq=high_tame_freq, gain_db=high_tame_db)

    # Lowpass (vintage/lo-fi character)
    lp_cutoff = settings.get('lowpass_cutoff', 20000)
    if lp_cutoff < 20000:
        data = apply_lowpass(data, rate, cutoff=lp_cutoff)

    return data


# Stem processor dispatch
STEM_PROCESSORS = {
    'vocals': process_vocals,
    'drums': process_drums,
    'bass': process_bass,
    'other': process_other,
}


# ─── Full Pipeline Functions ─────────────────────────────────────────


def mix_track_stems(stem_paths, output_path, genre=None, dry_run=False):
    """Full stems pipeline: load stems, process each, remix, write output.

    Args:
        stem_paths: Dict mapping stem name to file path
            e.g. {'vocals': '/path/vocals.wav', 'drums': '/path/drums.wav', ...}
        output_path: Path for polished output WAV
        genre: Optional genre name for preset selection
        dry_run: If True, analyze only without writing files

    Returns:
        Dict with processing results and metrics.
    """
    result = {
        'mode': 'stems',
        'stems_processed': [],
        'dry_run': dry_run,
    }

    # Load and process each stem
    processed_stems = {}
    gains = {}

    for stem_name in STEM_NAMES:
        if stem_name not in stem_paths:
            continue

        # Normalize to list of paths (supports single str or list of str)
        raw = stem_paths[stem_name]
        paths = [raw] if isinstance(raw, str) else list(raw)

        # Read and combine all files for this stem category
        data = None
        rate = None
        for p in paths:
            p = Path(p)
            if not p.exists():
                logger.warning("Stem file not found: %s", p)
                continue
            chunk, r = sf.read(str(p))
            if chunk.size == 0:
                logger.warning("Stem audio is empty, skipping: %s", p)
                continue
            if data is None:
                data = chunk.astype(np.float64)
                rate = r
            else:
                if r != rate:
                    logger.warning(
                        "Sample rate mismatch in %s (%d vs %d), skipping",
                        p, r, rate,
                    )
                    continue
                # Ensure same shape (mono→stereo promotion)
                if len(data.shape) == 1 and len(chunk.shape) == 2:
                    data = np.column_stack([data, data])
                elif len(data.shape) == 2 and len(chunk.shape) == 1:
                    chunk = np.column_stack([chunk, chunk])
                # Pad shorter to match longer
                max_len = max(data.shape[0], chunk.shape[0])
                if data.shape[0] < max_len:
                    padded = np.zeros((max_len,) + data.shape[1:], dtype=np.float64)
                    padded[:data.shape[0]] = data
                    data = padded
                if chunk.shape[0] < max_len:
                    padded = np.zeros((max_len,) + chunk.shape[1:], dtype=np.float64)
                    padded[:chunk.shape[0]] = chunk
                    chunk = padded
                data = data + chunk.astype(np.float64)

        if data is None:
            continue

        # Measure pre-processing level
        pre_peak = float(np.max(np.abs(data)))
        pre_rms = float(np.sqrt(np.mean(data ** 2)))

        if not dry_run:
            # Get settings and process
            settings = _get_stem_settings(stem_name, genre)
            processor = STEM_PROCESSORS[stem_name]
            data = processor(data, rate, settings)

            # Get remix gain
            gains[stem_name] = settings.get('gain_db', 0.0)

        # Measure post-processing level
        post_peak = float(np.max(np.abs(data)))
        post_rms = float(np.sqrt(np.mean(data ** 2)))

        processed_stems[stem_name] = (data, rate)
        result['stems_processed'].append({
            'stem': stem_name,
            'pre_peak': pre_peak,
            'pre_rms': pre_rms,
            'post_peak': post_peak,
            'post_rms': post_rms,
        })

    if not processed_stems:
        result['error'] = 'No stems could be loaded'
        return result

    # Remix
    if not dry_run:
        mixed, rate = remix_stems(processed_stems, gains)

        # Write output
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(output_path), mixed, rate, subtype='PCM_16')
        result['output_path'] = str(output_path)

        # Final metrics
        result['final_peak'] = float(np.max(np.abs(mixed)))
        result['final_rms'] = float(np.sqrt(np.mean(mixed ** 2)))

    return result


def mix_track_full(input_path, output_path, genre=None, dry_run=False):
    """Full-mix fallback: process a stereo mix directly (no stems).

    Args:
        input_path: Path to input WAV file
        output_path: Path for polished output WAV
        genre: Optional genre name for preset selection
        dry_run: If True, analyze only without writing files

    Returns:
        Dict with processing results and metrics.
    """
    input_path = Path(input_path)
    data, rate = sf.read(str(input_path))

    # Guard against empty/zero-length audio
    if data.size == 0:
        logger.warning("Audio is empty, skipping: %s", input_path)
        return {
            'mode': 'full_mix',
            'filename': input_path.name,
            'skipped': True,
            'dry_run': dry_run,
        }

    # Handle mono
    was_mono = len(data.shape) == 1
    if was_mono:
        data = np.column_stack([data, data])

    # Pre-processing metrics
    pre_peak = float(np.max(np.abs(data)))
    pre_rms = float(np.sqrt(np.mean(data ** 2)))

    result = {
        'mode': 'full_mix',
        'filename': input_path.name,
        'pre_peak': pre_peak,
        'pre_rms': pre_rms,
        'dry_run': dry_run,
    }

    if not dry_run:
        settings = _get_full_mix_settings(genre)

        # Noise reduction
        nr_strength = settings.get('noise_reduction', 0.3)
        if nr_strength > 0:
            data = reduce_noise(data, rate, strength=nr_strength)

        # Highpass
        hp_cutoff = settings.get('highpass_cutoff', 35)
        if hp_cutoff > 0:
            data = apply_highpass(data, rate, cutoff=hp_cutoff)

        # Click removal
        if settings.get('click_removal', True):
            data = remove_clicks(data, rate)

        # Mud cut
        mud_cut_db = settings.get('mud_cut_db', -2.0)
        mud_freq = settings.get('mud_freq', 250)
        if mud_cut_db != 0:
            data = apply_eq(data, rate, freq=mud_freq, gain_db=mud_cut_db, q=1.0)

        # Presence boost
        presence_db = settings.get('presence_boost_db', 1.5)
        presence_freq = settings.get('presence_freq', 3000)
        if presence_db != 0:
            data = apply_eq(data, rate, freq=presence_freq, gain_db=presence_db, q=1.5)

        # Tame highs
        high_tame_db = settings.get('high_tame_db', -1.5)
        high_tame_freq = settings.get('high_tame_freq', 7000)
        if high_tame_db != 0:
            data = apply_high_shelf(data, rate, freq=high_tame_freq, gain_db=high_tame_db)

        # Compression
        comp_threshold = settings.get('compress_threshold_db', -15.0)
        comp_ratio = settings.get('compress_ratio', 2.0)
        if comp_ratio > 1.0:
            data = gentle_compress(data, rate, threshold_db=comp_threshold,
                                   ratio=comp_ratio)

        # Saturation (genre character)
        sat_drive = settings.get('saturation_drive', 0)
        if sat_drive > 0:
            data = apply_saturation(data, rate, drive=sat_drive)

        # Lowpass (vintage/lo-fi character)
        lp_cutoff = settings.get('lowpass_cutoff', 20000)
        if lp_cutoff < 20000:
            data = apply_lowpass(data, rate, cutoff=lp_cutoff)

        # Stereo width (genre character)
        stereo_w = settings.get('stereo_width', 1.0)
        if stereo_w != 1.0 and not was_mono:
            data = apply_stereo_width(data, rate, width=stereo_w)

        # Convert back to mono if input was mono
        if was_mono:
            data = data[:, 0]

        # Write output
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(output_path), data, rate, subtype='PCM_16')
        result['output_path'] = str(output_path)

    # Post-processing metrics
    if not dry_run:
        post_peak = float(np.max(np.abs(data)))
        post_rms = float(np.sqrt(np.mean(data ** 2)))
        result['post_peak'] = post_peak
        result['post_rms'] = post_rms

    return result


def _process_one_track(track_dir, output_path, genre, dry_run):
    """Process a single track's stems (used by both sequential and parallel paths).

    Args:
        track_dir: Path to directory containing stem WAVs
        output_path: Path for output WAV
        genre: Genre preset name
        dry_run: Analyze only mode

    Returns:
        (track_name, result_dict) tuple.
    """
    track_dir = Path(track_dir)
    stem_paths = discover_stems(track_dir)

    if not stem_paths:
        return (track_dir.name, None)

    result = mix_track_stems(stem_paths, output_path, genre=genre, dry_run=dry_run)
    return (track_dir.name, result)


def _process_one_full_mix(wav_file, output_path, genre, dry_run):
    """Process a single full-mix WAV file.

    Returns:
        (filename, result_dict) tuple.
    """
    result = mix_track_full(wav_file, output_path, genre=genre, dry_run=dry_run)
    return (Path(wav_file).name, result)


# ─── CLI ─────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description='Polish audio tracks (stems or full mix)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modes:
  Stems mode (default): Looks for stems/ subdirectory with per-track
      stem folders (vocals.wav, drums.wav, bass.wav, other.wav).
  Full-mix mode (--full-mix): Processes WAV files directly from path.

Examples:
  python mix_tracks.py ~/music/album/             # Process stems
  python mix_tracks.py ~/music/album/ --full-mix   # Process full mixes
  python mix_tracks.py . --genre hip-hop --dry-run
        """
    )
    parser.add_argument('path', nargs='?', default='.',
                        help='Path to audio directory (default: current directory)')
    parser.add_argument('--genre', '-g', type=str, default=None,
                        help='Apply genre preset')
    parser.add_argument('--full-mix', action='store_true',
                        help='Process full mix WAVs instead of stems')
    parser.add_argument('--output-dir', type=str, default='polished',
                        help='Output directory (default: polished)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Analyze only, do not write files')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Show debug output')
    parser.add_argument('--quiet', '-q', action='store_true',
                        help='Show only warnings and errors')
    parser.add_argument('-j', '--jobs', type=int, default=1,
                        help='Parallel jobs (0=auto, default: 1)')

    args = parser.parse_args()

    setup_logging(__name__, verbose=args.verbose, quiet=args.quiet)

    input_dir = Path(args.path).expanduser().resolve()
    if not input_dir.exists():
        logger.error("Directory not found: %s", input_dir)
        sys.exit(1)

    output_dir = (input_dir / args.output_dir).resolve()

    # Prevent path traversal
    try:
        output_dir.relative_to(input_dir)
    except ValueError:
        logger.error("Output directory must be within input directory")
        sys.exit(1)

    if not args.dry_run:
        output_dir.mkdir(exist_ok=True)

    # Validate genre if specified
    if args.genre:
        presets = MIX_PRESETS.get('genres', {})
        genre_key = args.genre.lower()
        if genre_key not in presets:
            logger.error("Unknown genre: %s", args.genre)
            logger.error("Available: %s", ', '.join(sorted(presets.keys())))
            return

    print("=" * 70)
    print("MIX POLISH SESSION")
    print("=" * 70)
    if args.genre:
        print(f"Genre preset: {args.genre}")
    print(f"Mode: {'Full Mix' if args.full_mix else 'Stems'}")
    print(f"Output: {output_dir}/")
    print("=" * 70)
    print()

    if args.dry_run:
        logger.info("DRY RUN - No files will be written")
        print()

    if args.full_mix:
        # Full-mix mode: process WAV files directly
        # Check originals/ subdirectory first, fall back to album root
        originals = input_dir / "originals"
        source_dir = originals if originals.is_dir() else input_dir
        wav_files = sorted([f for f in source_dir.iterdir()
                           if f.suffix.lower() == '.wav'
                           and 'venv' not in str(f)])

        if not wav_files:
            print("No WAV files found.")
            return

        workers = args.jobs if args.jobs > 0 else os.cpu_count()
        progress = ProgressBar(len(wav_files), prefix="Polishing")
        results = []

        print(f"{'Track':<35} {'Pre Peak':>10} {'Post Peak':>10}")
        print("-" * 55)

        if workers == 1:
            for wav_file in wav_files:
                progress.update(wav_file.name)
                out_path = output_dir / wav_file.name
                name, result = _process_one_full_mix(
                    wav_file, out_path, args.genre, args.dry_run
                )
                if result:
                    results.append((name, result))
                    post_peak = result.get('post_peak', result.get('pre_peak', 0))
                    print(f"{name[:34]:<35} {result['pre_peak']:>9.4f} {post_peak:>9.4f}")
        else:
            logger.info("Using %d parallel workers", workers)
            ordered = {}
            tasks = list(enumerate(wav_files))
            with ProcessPoolExecutor(max_workers=workers) as executor:
                futures = {
                    executor.submit(
                        _process_one_full_mix, wf, output_dir / wf.name, args.genre, args.dry_run
                    ): i
                    for i, wf in tasks
                }
                for future in as_completed(futures):
                    idx = futures[future]
                    progress.update(wav_files[idx].name)
                    name, result = future.result()
                    if result:
                        ordered[idx] = (name, result)
            for idx in sorted(ordered):
                name, result = ordered[idx]
                results.append((name, result))
                post_peak = result.get('post_peak', result.get('pre_peak', 0))
                print(f"{name[:34]:<35} {result['pre_peak']:>9.4f} {post_peak:>9.4f}")

    else:
        # Stems mode: look for stems/ subdirectory
        stems_dir = input_dir / "stems"
        if not stems_dir.exists():
            logger.error("No stems/ directory found in %s", input_dir)
            logger.error("Use --full-mix to process WAV files directly")
            sys.exit(1)

        track_dirs = sorted([d for d in stems_dir.iterdir() if d.is_dir()])
        if not track_dirs:
            print("No track directories found in stems/")
            return

        workers = args.jobs if args.jobs > 0 else os.cpu_count()
        progress = ProgressBar(len(track_dirs), prefix="Polishing")
        results = []

        print(f"{'Track':<35} {'Stems':>6} {'Status':>10}")
        print("-" * 55)

        if workers == 1:
            for track_dir in track_dirs:
                progress.update(track_dir.name)
                out_path = output_dir / f"{track_dir.name}.wav"
                name, result = _process_one_track(
                    track_dir, out_path, args.genre, args.dry_run
                )
                if result:
                    results.append((name, result))
                    stems_count = len(result.get('stems_processed', []))
                    status = "dry-run" if args.dry_run else "polished"
                    print(f"{name[:34]:<35} {stems_count:>5} {status:>10}")
        else:
            logger.info("Using %d parallel workers", workers)
            ordered = {}
            tasks = list(enumerate(track_dirs))
            with ProcessPoolExecutor(max_workers=workers) as executor:
                futures = {
                    executor.submit(
                        _process_one_track, td, output_dir / f"{td.name}.wav",
                        args.genre, args.dry_run
                    ): i
                    for i, td in tasks
                }
                for future in as_completed(futures):
                    idx = futures[future]
                    progress.update(track_dirs[idx].name)
                    name, result = future.result()
                    if result:
                        ordered[idx] = (name, result)
            for idx in sorted(ordered):
                name, result = ordered[idx]
                results.append((name, result))
                stems_count = len(result.get('stems_processed', []))
                status = "dry-run" if args.dry_run else "polished"
                print(f"{name[:34]:<35} {stems_count:>5} {status:>10}")

    print("-" * 55)

    if not results:
        print("\nNo tracks were processed.")
        return

    print()
    print("SUMMARY:")
    print(f"  Tracks processed: {len(results)}")
    if not args.dry_run:
        print(f"  Polished files written to: {output_dir.absolute()}/")
    else:
        print("  Run without --dry-run to process files")


if __name__ == '__main__':
    main()
