#!/usr/bin/env python3
"""Analyze audio tracks for mastering decisions."""
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

# Ensure project root is on sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.shared.logging_config import setup_logging
from tools.shared.progress import ProgressBar

logger = logging.getLogger(__name__)


def _bandpass_sos(data: np.ndarray, rate: int, low_hz: float, high_hz: float,
                  order: int = 4) -> np.ndarray:
    """Zero-phase Butterworth bandpass via SOS form (numerically stable)."""
    nyquist = rate / 2
    low = max(low_hz, 1.0) / nyquist
    high = min(high_hz, nyquist - 1.0) / nyquist
    sos = signal.butter(order, [low, high], btype='bandpass', output='sos')
    # scipy.signal.sosfiltfilt is typed to return Any; narrow explicitly.
    return np.asarray(signal.sosfiltfilt(sos, data))


def _rms_db(samples: np.ndarray) -> float:
    rms = float(np.sqrt(np.mean(samples ** 2)))
    return 20.0 * np.log10(rms) if rms > 0 else float('-inf')


def _read_vocal_stem(stem_path: Path | str, target_rate: int) -> np.ndarray | None:
    """Read a vocal stem, mono-mix, resample to target_rate.

    Returns None if the file cannot be read or resampled.
    """
    try:
        data, rate = sf.read(str(stem_path))
    except Exception as exc:
        logger.warning("Could not read vocal stem %s: %s", stem_path, exc)
        return None
    if data.ndim > 1:
        mono = np.mean(data, axis=1)
    else:
        mono = data
    if rate != target_rate:
        try:
            from math import gcd
            g = gcd(int(rate), int(target_rate))
            up = int(target_rate) // g
            down = int(rate) // g
            mono = signal.resample_poly(mono, up, down)
        except Exception as exc:
            logger.warning("Could not resample vocal stem %s: %s", stem_path, exc)
            return None
    return np.asarray(mono, dtype=np.float64)


def _auto_resolve_vocal_stem(input_path: Path) -> Path | None:
    """Find a matching polished vocal stem without explicit kwarg.

    Checks, in order:
      1. <input_dir>/polished/<input_stem>/vocals.wav  (album-root input)
      2. <input_dir>/../polished/<input_stem>/vocals.wav  (mastered/ or
         polished/ subfolder input)

    Returns the first existing path, or None.
    """
    stem_name = input_path.stem
    candidates = [
        input_path.parent / "polished" / stem_name / "vocals.wav",
        input_path.parent.parent / "polished" / stem_name / "vocals.wav",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def analyze_track(filepath: Path | str, *,
                  vocal_stem_path: Path | str | None = None) -> dict[str, Any]:
    """Analyze a single track and return metrics.

    Optional vocal_stem_path lets Phase 2 callers feed a known stem path
    directly; omitted calls auto-resolve via the polished/<name>/vocals.wav
    sibling convention (added in later tasks).
    """
    data, rate = sf.read(filepath)

    # Handle mono
    if len(data.shape) == 1:
        data = np.column_stack([data, data])

    # LUFS measurement
    meter = pyln.Meter(rate)
    loudness = meter.integrated_loudness(data)

    # Peak levels
    peak_linear = np.max(np.abs(data))
    peak_db = 20 * np.log10(peak_linear) if peak_linear > 0 else -np.inf

    # Dynamic range (difference between peak and RMS)
    rms = np.sqrt(np.mean(data**2))
    rms_db = 20 * np.log10(rms) if rms > 0 else -np.inf
    dynamic_range = peak_db - rms_db

    # Spectral analysis - energy in frequency bands
    # Combine channels for spectral analysis
    mono = np.mean(data, axis=1)

    # Compute power spectral density
    freqs, psd = signal.welch(mono, rate, nperseg=8192)

    # Define frequency bands
    bands = {
        'sub_bass': (20, 60),      # Sub bass
        'bass': (60, 250),          # Bass
        'low_mid': (250, 500),      # Low mids
        'mid': (500, 2000),         # Mids
        'high_mid': (2000, 6000),   # High mids (tinniness zone!)
        'high': (6000, 12000),      # Highs
        'air': (12000, 20000),      # Air
    }

    band_energy = {}
    total_energy = np.sum(psd)

    for band_name, (low, high) in bands.items():
        mask = (freqs >= low) & (freqs < high)
        energy = np.sum(psd[mask])
        band_energy[band_name] = (energy / total_energy) * 100 if total_energy > 0 else 0.0

    # Tinniness indicator: ratio of high_mid to mid energy
    tinniness_ratio = band_energy['high_mid'] / band_energy['mid'] if band_energy['mid'] > 0 else 0

    # Crest factor (peak to RMS as linear ratio)
    _crest_factor = peak_linear / rms if rms > 0 else 0.0

    # Short-term and momentary loudness dynamics
    max_short_term = float('-inf')
    min_short_term = float('inf')
    max_momentary = float('-inf')
    st_values: list[float] = []

    # Short-term: 3s window, 1s hop (EBU R128)
    st_window = int(3.0 * rate)
    st_hop = int(1.0 * rate)
    if data.shape[0] > st_window:
        for start in range(0, data.shape[0] - st_window, st_hop):
            chunk = data[start:start + st_window]
            st_lufs = pyln.Meter(rate).integrated_loudness(chunk)
            if np.isfinite(st_lufs):
                st_values.append(float(st_lufs))
                max_short_term = max(max_short_term, st_lufs)
                min_short_term = min(min_short_term, st_lufs)

    # STL-95: 95th percentile of finite short-term LUFS. Gated to ≥20 windows
    # (~23s audio) so the percentile has a meaningful spread; below that it
    # collapses to near-max. Top-5% indices retained for downstream low-RMS.
    stl_95: float | None
    stl_top_5pct_indices: np.ndarray
    if len(st_values) >= 20:
        stl_array = np.asarray(st_values, dtype=np.float64)
        stl_95 = float(np.percentile(stl_array, 95))
        top_k = max(1, int(round(0.05 * len(st_values))))
        order = np.argsort(-stl_array, kind='stable')
        stl_top_5pct_indices = order[:top_k]
    else:
        stl_95 = None
        stl_top_5pct_indices = np.array([], dtype=np.int64)

    # low-RMS: 20-200 Hz band, measured within top-5% STL windows only.
    # Whole-track measurement false-alarms on arrangements with quiet verses
    # and wall-of-bass choruses (see #290 spec footnote †).
    low_rms: float | None
    if stl_95 is not None and len(stl_top_5pct_indices) > 0:
        low_filtered = _bandpass_sos(mono, rate, 20.0, 200.0)
        window_rms_values: list[float] = []
        for window_idx in stl_top_5pct_indices:
            start = int(window_idx) * st_hop
            end = start + st_window
            chunk = low_filtered[start:end]
            rms_val = _rms_db(chunk)
            if np.isfinite(rms_val):
                window_rms_values.append(rms_val)
        low_rms = float(np.median(window_rms_values)) if window_rms_values else None
    else:
        low_rms = None

    # vocal-RMS: whole-stem RMS when stem path resolves; 1-4 kHz band of
    # full mix otherwise. See #290 spec footnote ‡.
    vocal_rms: float | None = None
    vocal_rms_source: str = "unavailable"

    resolved_stem: Path | None
    if vocal_stem_path is not None:
        resolved_stem = Path(vocal_stem_path)
    else:
        resolved_stem = _auto_resolve_vocal_stem(Path(filepath))
    if resolved_stem is not None and resolved_stem.is_file():
        stem_mono = _read_vocal_stem(resolved_stem, rate)
        if stem_mono is not None:
            rms_val = _rms_db(stem_mono)
            if np.isfinite(rms_val):
                vocal_rms = float(rms_val)
                vocal_rms_source = "stem"

    if vocal_rms is None:
        try:
            band_filtered = _bandpass_sos(mono, rate, 1000.0, 4000.0)
            rms_val = _rms_db(band_filtered)
            if np.isfinite(rms_val):
                vocal_rms = float(rms_val)
                vocal_rms_source = "band_fallback"
        except Exception as exc:
            logger.warning("1-4 kHz band fallback failed: %s", exc)

    # Momentary: 400ms window, 100ms hop
    mom_window = int(0.4 * rate)
    mom_hop = int(0.1 * rate)
    if data.shape[0] > mom_window:
        for start in range(0, data.shape[0] - mom_window, mom_hop):
            chunk = data[start:start + mom_window]
            mom_lufs = pyln.Meter(rate).integrated_loudness(chunk)
            if np.isfinite(mom_lufs):
                max_momentary = max(max_momentary, mom_lufs)

    short_term_range = (max_short_term - min_short_term
                        if np.isfinite(max_short_term) and np.isfinite(min_short_term)
                        else 0.0)

    # signature_meta records provenance for downstream consumers (anchor
    # selector in phase 2a, coherence check in phase 2b).
    signature_meta = {
        'stl_window_count': len(st_values),
        'stl_top_5pct_count': int(len(stl_top_5pct_indices)),
        'vocal_rms_source': vocal_rms_source,
    }

    return {
        'filename': os.path.basename(filepath),
        'duration': len(mono) / rate,
        'sample_rate': rate,
        'lufs': loudness,
        'peak_db': peak_db,
        'rms_db': rms_db,
        'dynamic_range': dynamic_range,
        'band_energy': band_energy,
        'is_dark': bool(band_energy.get('high_mid', 0.0) < 10.0),
        'tinniness_ratio': tinniness_ratio,
        'max_short_term_lufs': max_short_term if np.isfinite(max_short_term) else None,
        'max_momentary_lufs': max_momentary if np.isfinite(max_momentary) else None,
        'short_term_range': short_term_range,
        'stl_95': stl_95,
        'low_rms': low_rms,
        'vocal_rms': vocal_rms,
        'signature_meta': signature_meta,
    }

def main() -> None:
    parser = argparse.ArgumentParser(description='Analyze audio tracks for mastering.')
    parser.add_argument('path', nargs='?', default='.',
                        help='Path to directory containing WAV files (default: current directory)')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Show debug output')
    parser.add_argument('--quiet', '-q', action='store_true',
                        help='Show only warnings and errors')
    parser.add_argument('-j', '--jobs', type=int, default=1,
                        help='Parallel jobs (0=auto, default: 1)')
    args = parser.parse_args()

    setup_logging(__name__, verbose=args.verbose, quiet=args.quiet)

    # Find all wav files
    wav_dir = Path(args.path).expanduser().resolve()
    if not wav_dir.exists():
        logger.error("Directory not found: %s", wav_dir)
        sys.exit(1)

    wav_files = sorted(wav_dir.glob('*.wav'))

    print("=" * 80)
    print("TRACK ANALYSIS FOR MASTERING")
    print("=" * 80)
    print()

    filterable = [f for f in wav_files if 'venv' not in str(f)]
    workers = args.jobs if args.jobs > 0 else os.cpu_count()
    progress = ProgressBar(len(filterable), prefix="Analyzing")

    if workers == 1:
        results = []
        for wav_file in filterable:
            progress.update(wav_file.name)
            result = analyze_track(str(wav_file))
            results.append(result)
    else:
        logger.info("Using %d parallel workers", workers)
        ordered = {}
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(analyze_track, str(wf)): i
                for i, wf in enumerate(filterable)
            }
            for future in as_completed(futures):
                idx = futures[future]
                progress.update(filterable[idx].name)
                ordered[idx] = future.result()
        results = [ordered[i] for i in sorted(ordered)]

    print()
    print("=" * 80)
    print("LOUDNESS ANALYSIS (Target: -14 LUFS for streaming)")
    print("=" * 80)
    print(f"{'Track':<35} {'LUFS':>8} {'Peak dB':>8} {'Δ to -14':>10}")
    print("-" * 65)

    for r in results:
        delta = -14 - r['lufs']
        print(f"{r['filename'][:34]:<35} {r['lufs']:>8.1f} {r['peak_db']:>8.1f} {delta:>+10.1f}")

    avg_lufs = np.mean([r['lufs'] for r in results])
    print("-" * 65)
    print(f"{'Average':<35} {avg_lufs:>8.1f}")
    print()

    # Loudness dynamics table
    has_dynamics = any(r.get('max_short_term_lufs') is not None for r in results)
    if has_dynamics:
        print("=" * 80)
        print("LOUDNESS DYNAMICS (short-term=3s, momentary=400ms)")
        print("=" * 80)
        print(f"{'Track':<35} {'MaxST':>8} {'MaxMom':>8} {'STRange':>8}")
        print("-" * 65)
        for r in results:
            st = r.get('max_short_term_lufs')
            mom = r.get('max_momentary_lufs')
            st_range = r.get('short_term_range', 0)
            st_str = f"{st:.1f}" if st is not None else "N/A"
            mom_str = f"{mom:.1f}" if mom is not None else "N/A"
            print(f"{r['filename'][:34]:<35} {st_str:>8} {mom_str:>8} {st_range:>7.1f}dB")
        print()

    print("=" * 80)
    print("SPECTRAL BALANCE (% energy per band)")
    print("=" * 80)
    print(f"{'Track':<25} {'Bass':>7} {'Mid':>7} {'HiMid':>7} {'High':>7} {'Tinny?':>8}")
    print("-" * 65)

    for r in results:
        be = r['band_energy']
        bass = be['sub_bass'] + be['bass']
        mid = be['low_mid'] + be['mid']
        himid = be['high_mid']
        high = be['high'] + be['air']

        # Tinniness warning if high_mid is disproportionate
        tinny = "YES" if r['tinniness_ratio'] > 0.6 else "OK"

        name = r['filename'][:24]
        print(f"{name:<25} {bass:>6.1f}% {mid:>6.1f}% {himid:>6.1f}% {high:>6.1f}% {tinny:>8}")

    print()
    print("=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)

    # Find tracks that need attention
    tinny_tracks = [r for r in results if r['tinniness_ratio'] > 0.6]
    quiet_tracks = [r for r in results if r['lufs'] < avg_lufs - 2]
    loud_tracks = [r for r in results if r['lufs'] > avg_lufs + 2]

    if tinny_tracks:
        print("\nTINNINESS (need high-mid EQ cut 2-6kHz):")
        for t in tinny_tracks:
            cut_amount = min((t['tinniness_ratio'] - 0.5) * 6, 4)  # Max 4dB cut
            print(f"   - {t['filename']}: suggest -{cut_amount:.1f}dB at 3-5kHz")

    if quiet_tracks:
        print("\nQUIET TRACKS (below average):")
        for t in quiet_tracks:
            print(f"   - {t['filename']}: {t['lufs']:.1f} LUFS")

    if loud_tracks:
        print("\nLOUD TRACKS (above average):")
        for t in loud_tracks:
            print(f"   - {t['filename']}: {t['lufs']:.1f} LUFS")

    print()
    lufs_range = max(r['lufs'] for r in results) - min(r['lufs'] for r in results)
    print(f"LUFS range across album: {lufs_range:.1f} dB (should be < 2 dB ideally)")
    print("Target loudness: -14 LUFS (streaming standard)")
    print()

if __name__ == '__main__':
    main()
