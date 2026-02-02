#!/usr/bin/env python3
"""
Automated Mastering Script for Album
- Normalizes to target LUFS (streaming: -14 LUFS)
- Optional high-mid EQ cut for tinniness
- True peak limiting to prevent clipping
- Preserves dynamics while ensuring consistency
"""

import logging
import os
import sys
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

import numpy as np
import soundfile as sf
import pyloudnorm as pyln
from scipy import signal

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
_BUILTIN_PRESETS_FILE = Path(__file__).parent / "genre-presets.yaml"

# User override location
_CONFIG_PATH = Path.home() / ".bitwize-music" / "config.yaml"


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


def load_genre_presets() -> dict:
    """Load genre presets from YAML, merging built-in with user overrides.

    Returns:
        Dict mapping genre name to (target_lufs, cut_highmid, cut_highs) tuples.
    """
    # Load built-in presets
    builtin = _load_yaml_file(_BUILTIN_PRESETS_FILE)
    builtin_genres = builtin.get('genres', {})
    defaults = builtin.get('defaults', {})

    # Load user overrides
    overrides_dir = _get_overrides_path()
    override_genres = {}
    if overrides_dir:
        override_file = overrides_dir / 'mastering-presets.yaml'
        override_data = _load_yaml_file(override_file)
        override_genres = override_data.get('genres', {})
        override_defaults = override_data.get('defaults', {})
        if override_defaults:
            defaults.update(override_defaults)

    default_lufs = float(defaults.get('target_lufs', -14.0))
    default_highmid = float(defaults.get('cut_highmid', 0))
    default_highs = float(defaults.get('cut_highs', 0))

    # Merge: built-in genres + override genres (override wins per-field)
    all_genre_names = set(builtin_genres.keys()) | set(override_genres.keys())
    presets = {}
    for genre in all_genre_names:
        base = builtin_genres.get(genre, {})
        over = override_genres.get(genre, {})
        merged = {**base, **over}
        presets[genre] = (
            float(merged.get('target_lufs', default_lufs)),
            float(merged.get('cut_highmid', default_highmid)),
            float(merged.get('cut_highs', default_highs)),
        )

    return presets


# Load presets at import time (fast — just two small YAML reads)
GENRE_PRESETS = load_genre_presets()

def apply_eq(data, rate, freq, gain_db, q=1.0):
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
        logger.warning("EQ freq %.1f Hz out of valid range (20–%.0f Hz), skipping", freq, nyquist)
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

def apply_high_shelf(data, rate, freq, gain_db):
    """Apply high shelf EQ."""
    nyquist = rate / 2
    if not (20 <= freq < nyquist):
        logger.warning("High shelf freq %.1f Hz out of valid range (20–%.0f Hz), skipping", freq, nyquist)
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

def soft_clip(data, threshold=0.95):
    """Soft clipping limiter to prevent harsh digital clipping."""
    # Soft knee limiter using tanh
    above_thresh = np.abs(data) > threshold
    if not np.any(above_thresh):
        return data

    result = data.copy()
    # Apply soft saturation above threshold
    mask = np.abs(data) > threshold
    result[mask] = np.sign(data[mask]) * (threshold + (1 - threshold) * np.tanh((np.abs(data[mask]) - threshold) / (1 - threshold)))
    return result

def limit_peaks(data, ceiling_db=-1.0):
    """Simple peak limiter to prevent clipping.

    Args:
        data: Audio data
        ceiling_db: Maximum peak level in dB (e.g., -1.0 for -1 dBTP)
    """
    ceiling_linear = 10 ** (ceiling_db / 20)
    peak = np.max(np.abs(data))

    if peak > ceiling_linear:
        # Calculate required gain reduction
        gain = ceiling_linear / peak
        data = data * gain

    return soft_clip(data, ceiling_linear)

def master_track(input_path, output_path, target_lufs=-14.0,
                 eq_settings=None, ceiling_db=-1.0):
    """Master a single track.

    Args:
        input_path: Path to input wav file
        output_path: Path for output wav file
        target_lufs: Target integrated loudness
        eq_settings: List of (freq, gain_db, q) tuples for EQ
        ceiling_db: True peak ceiling in dB
    """
    # Read audio
    data, rate = sf.read(input_path)

    # Handle mono
    was_mono = len(data.shape) == 1
    if was_mono:
        data = np.column_stack([data, data])

    # Apply EQ if specified
    if eq_settings:
        for freq, gain_db, q in eq_settings:
            data = apply_eq(data, rate, freq, gain_db, q)

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

    # Calculate required gain
    gain_db = target_lufs - current_lufs
    gain_linear = 10 ** (gain_db / 20)

    # Apply gain
    data = data * gain_linear

    # Apply limiter
    data = limit_peaks(data, ceiling_db)

    # Verify final loudness
    final_lufs = meter.integrated_loudness(data)
    peak_abs = np.max(np.abs(data))
    final_peak = 20 * np.log10(peak_abs) if peak_abs > 0 else float('-inf')

    # Convert back to mono if input was mono
    if was_mono:
        data = data[:, 0]

    # Write output (same format as input)
    sf.write(output_path, data, rate, subtype='PCM_16')

    return {
        'original_lufs': current_lufs,
        'final_lufs': final_lufs,
        'gain_applied': gain_db,
        'final_peak': final_peak,
    }

def _process_one_track(wav_file, output_path, target_lufs, eq_settings, ceiling_db, dry_run):
    """Process a single track (used by both sequential and parallel paths).

    Returns (wav_file_name, result_dict) or (wav_file_name, None) if skipped.
    """
    if dry_run:
        data, rate = sf.read(str(wav_file))
        if len(data.shape) == 1:
            data = np.column_stack([data, data])
        meter = pyln.Meter(rate)
        current_lufs = meter.integrated_loudness(data)
        if not np.isfinite(current_lufs):
            return (str(wav_file), None)
        gain = target_lufs - current_lufs
        result = {
            'original_lufs': current_lufs,
            'final_lufs': target_lufs,
            'gain_applied': gain,
            'final_peak': -1.0,
        }
    else:
        result = master_track(
            str(wav_file),
            str(output_path),
            target_lufs=target_lufs,
            eq_settings=eq_settings,
            ceiling_db=ceiling_db
        )

    if result.get('skipped'):
        return (str(wav_file), None)

    return (str(wav_file), result)


def main():
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
                       help='High-mid cut in dB at 3.5kHz (e.g., -2 for 2dB cut)')
    parser.add_argument('--cut-highs', type=float, default=None,
                       help='High shelf cut in dB at 8kHz')
    parser.add_argument('--output-dir', type=str, default='mastered',
                       help='Output directory (default: mastered)')
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

    # Apply genre preset if specified
    if args.genre:
        genre_key = args.genre.lower()
        if genre_key not in GENRE_PRESETS:
            logger.error("Unknown genre: %s", args.genre)
            logger.error("Available: %s", ', '.join(sorted(GENRE_PRESETS.keys())))
            return
        preset_lufs, preset_highmid, preset_highs = GENRE_PRESETS[genre_key]
        # Genre preset provides defaults, but explicit args override
        if args.target_lufs is None:
            args.target_lufs = preset_lufs
        if args.cut_highmid is None:
            args.cut_highmid = preset_highmid
        if args.cut_highs is None:
            args.cut_highs = preset_highs

    # Apply defaults if no genre and no explicit value
    if args.target_lufs is None:
        args.target_lufs = -14.0
    if args.cut_highmid is None:
        args.cut_highmid = 0
    if args.cut_highs is None:
        args.cut_highs = 0

    # Setup
    input_dir = Path(args.path).expanduser().resolve()
    if not input_dir.exists():
        logger.error("Directory not found: %s", input_dir)
        sys.exit(1)

    output_dir = input_dir / args.output_dir

    if not args.dry_run:
        output_dir.mkdir(exist_ok=True)

    # Find wav files (case-insensitive for cross-platform compatibility)
    wav_files = sorted([f for f in input_dir.iterdir()
                       if f.suffix.lower() == '.wav'
                       and 'mastering-env' not in str(f)])

    # Build EQ settings
    eq_settings = []
    if args.cut_highmid != 0:
        eq_settings.append((3500, args.cut_highmid, 1.5))  # 3.5kHz with moderate Q
    if args.cut_highs != 0:
        # For high shelf, we'd need different handling - simplified here
        eq_settings.append((8000, args.cut_highs, 0.7))

    print("=" * 70)
    print("MASTERING SESSION")
    print("=" * 70)
    if args.genre:
        print(f"Genre preset: {args.genre}")
    print(f"Target LUFS: {args.target_lufs}")
    print(f"Peak ceiling: {args.ceiling} dBTP")
    if args.cut_highmid != 0:
        print(f"EQ: High-mid cut: {args.cut_highmid}dB at 3.5kHz")
    if args.cut_highs != 0:
        print(f"EQ: High shelf cut: {args.cut_highs}dB at 8kHz")
    print(f"Output: {output_dir}/")
    print("=" * 70)
    print()

    if args.dry_run:
        logger.info("DRY RUN - No files will be written")
        print()

    print(f"{'Track':<35} {'Before':>8} {'After':>8} {'Gain':>8} {'Peak':>8}")
    print("-" * 70)

    workers = args.jobs if args.jobs > 0 else os.cpu_count()
    eq = eq_settings if eq_settings else None

    # Build list of (wav_file, output_path) pairs
    tasks = [(wf, output_dir / wf.name) for wf in wav_files]

    results = []
    progress = ProgressBar(len(tasks), prefix="Mastering")

    if workers == 1:
        # Sequential (existing behavior)
        for wav_file, output_path in tasks:
            progress.update(wav_file.name)
            _, result = _process_one_track(
                wav_file, output_path, args.target_lufs, eq, args.ceiling, args.dry_run
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
                    _process_one_track, wf, op, args.target_lufs, eq, args.ceiling, args.dry_run
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
    gains = [r['gain_applied'] for r in results]
    finals = [r['final_lufs'] for r in results]

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
