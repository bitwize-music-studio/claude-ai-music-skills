#!/usr/bin/env python3
"""Analyze audio tracks for mastering decisions."""

import os
import sys
import argparse
import numpy as np
import soundfile as sf
import pyloudnorm as pyln
from scipy import signal
from pathlib import Path

def analyze_track(filepath):
    """Analyze a single track and return metrics."""
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

    # True peak (oversampled)
    true_peak_db = peak_db  # Simplified; proper true peak needs oversampling

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
        band_energy[band_name] = (energy / total_energy) * 100  # Percentage

    # Tinniness indicator: ratio of high_mid to mid energy
    tinniness_ratio = band_energy['high_mid'] / band_energy['mid'] if band_energy['mid'] > 0 else 0

    # Crest factor (peak to RMS ratio in dB)
    crest_factor = dynamic_range

    return {
        'filename': os.path.basename(filepath),
        'duration': len(mono) / rate,
        'sample_rate': rate,
        'lufs': loudness,
        'peak_db': peak_db,
        'rms_db': rms_db,
        'dynamic_range': dynamic_range,
        'band_energy': band_energy,
        'tinniness_ratio': tinniness_ratio,
    }

def main():
    parser = argparse.ArgumentParser(description='Analyze audio tracks for mastering.')
    parser.add_argument('path', nargs='?', default='.',
                        help='Path to directory containing WAV files (default: current directory)')
    args = parser.parse_args()

    # Find all wav files
    wav_dir = Path(args.path).expanduser().resolve()
    if not wav_dir.exists():
        print(f"Error: Directory not found: {wav_dir}")
        sys.exit(1)

    wav_files = sorted(wav_dir.glob('*.wav'))

    print("=" * 80)
    print("TRACK ANALYSIS FOR MASTERING")
    print("=" * 80)
    print()

    results = []
    for wav_file in wav_files:
        if 'mastering-env' in str(wav_file):
            continue
        print(f"Analyzing: {wav_file.name}...")
        result = analyze_track(str(wav_file))
        results.append(result)

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
    print(f"Target loudness: -14 LUFS (streaming standard)")
    print()

if __name__ == '__main__':
    main()
