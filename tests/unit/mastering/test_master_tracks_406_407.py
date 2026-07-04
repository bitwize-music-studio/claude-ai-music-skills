#!/usr/bin/env python3
"""Regression tests for master_tracks.py bugs #406 and #407.

#406 — apply_fade_out must not raise (nor corrupt audio) when the fade
       duration is so small it rounds to zero samples.
#407 — result['original_lufs'] must report the loudness of the SOURCE audio
       (measured right after read), not the loudness measured after the
       EQ/compression/fade processing chain.
"""

import sys
from pathlib import Path

import numpy as np
import pyloudnorm as pyln
import pytest
import soundfile as sf

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.mastering import master_tracks
from tools.mastering.master_tracks import apply_fade_out, master_track


def _stereo_sine(freq=440.0, duration=3.0, rate=44100, amplitude=0.5):
    t = np.linspace(0, duration, int(rate * duration), endpoint=False)
    mono = (amplitude * np.sin(2 * np.pi * freq * t)).astype(np.float64)
    return np.column_stack([mono, mono]), rate


# ─── #406: sub-sample fade-out must be a safe no-op ───────────────────────


class TestFadeOutSubSample:
    def test_tiny_duration_does_not_raise_stereo(self):
        """0 < duration < 1/rate => int(rate*duration) == 0 must not crash."""
        data, rate = _stereo_sine(duration=1.0)
        # 0.5 sample worth of fade -> int(rate * duration) == 0
        tiny = 0.5 / rate
        assert int(rate * tiny) == 0  # precondition that triggered the bug
        result = apply_fade_out(data, rate, duration=tiny)  # must not raise
        # A sub-sample fade is effectively nothing: audio stays unchanged.
        assert np.array_equal(result, data)

    def test_tiny_duration_does_not_raise_mono(self):
        data, rate = _stereo_sine(duration=1.0)
        mono = data[:, 0].copy()
        tiny = 0.5 / rate
        result = apply_fade_out(mono, rate, duration=tiny)  # must not raise
        assert np.array_equal(result, mono)

    def test_tiny_duration_linear_curve(self):
        data, rate = _stereo_sine(duration=1.0)
        tiny = 0.5 / rate
        result = apply_fade_out(data, rate, duration=tiny, curve='linear')
        assert np.array_equal(result, data)


# ─── #407: original_lufs must reflect the SOURCE, not processed audio ──────


class TestOriginalLufsIsSource:
    def test_original_lufs_is_source_not_processed(self, tmp_path, monkeypatch):
        """A processing stage that changes loudness must not leak into
        the reported 'original_lufs' — it should stay the source value."""
        data, rate = _stereo_sine(duration=3.0, amplitude=0.5)
        in_path = tmp_path / "src.wav"
        out_path = tmp_path / "out.wav"
        sf.write(str(in_path), data, rate, subtype='PCM_16')

        # Independently measure the true SOURCE loudness the same way the
        # fix does — read the file back and meter the raw samples.
        src_data, src_rate = sf.read(str(in_path))
        src_lufs = pyln.Meter(src_rate).integrated_loudness(src_data)
        assert np.isfinite(src_lufs)

        # Force a large, deterministic loudness drop *during* processing:
        # replace the fade stage with a -20 dB (x0.1) attenuation. The old
        # code measured loudness after this stage and reported it as
        # 'original_lufs'; the fix measures the source before it.
        def loudness_dropping_fade(d, r, duration=5.0, curve='exponential'):
            return d * 0.1

        monkeypatch.setattr(master_tracks, "apply_fade_out",
                            loudness_dropping_fade)

        result = master_track(str(in_path), str(out_path),
                              target_lufs=-14.0, fade_out=2.0)

        assert not result.get('skipped', False)
        # original_lufs must equal the SOURCE loudness...
        assert result['original_lufs'] == pytest.approx(src_lufs, abs=0.5)
        # ...and must NOT be the post-processing (~20 dB quieter) value the
        # buggy code reported.
        processed_lufs = src_lufs - 20.0
        assert abs(result['original_lufs'] - processed_lufs) > 10.0
