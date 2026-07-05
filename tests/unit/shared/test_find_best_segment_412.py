"""Regression tests for find_best_segment window-range off-by-one (issue #412).

find_best_segment scans overlapping ``window_samples``-long windows across the
RMS energy envelope to locate the most energetic segment. The valid starting
frame indices span ``0 .. len(rms) - window_samples`` inclusive. A loop of
``range(len(rms) - window_samples)`` never evaluates that final window, so when
the peak-energy segment is the last window of the track it is silently skipped;
in the degenerate ``len(rms) == window_samples`` case the loop never runs at all
and the start defaults to 0.0.

These tests mock librosa so the RMS / times arrays are fully controlled while
numpy stays real. find_best_segment wraps its analysis in a broad
``except Exception`` that falls back to "20% into the track", so each test
asserts the *exact* expected start time: an off-by-one (wrong window) or a
swallowed IndexError (fallback value) both produce a different number and fail.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# Ensure project root on sys.path (conftest normally handles this).
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.shared import media_utils as mod

# With duration=15, sr=120 and the internal hop_length=512:
#   window_samples = int(15 * 120 / 512) = int(3.515625) = 3
_SR = 120
_DURATION = 15
_TOTAL_DURATION = 1000.0  # >> any window time, so the max_start clamp never bites
# Value returned by the internal fallback path (librosa error / swallowed exc).
_FALLBACK = min(_TOTAL_DURATION * 0.2, _TOTAL_DURATION - _DURATION)  # 200.0


def _run(rms, times):
    """Invoke find_best_segment with librosa mocked to yield the given arrays."""
    rms_arr = np.asarray(rms, dtype=float)
    fake_librosa = MagicMock()
    fake_librosa.load.return_value = (np.zeros(8, dtype=float), _SR)
    # librosa.feature.rms(...) returns shape (1, n_frames); the code takes [0].
    fake_librosa.feature.rms.return_value = np.array([rms_arr])
    fake_librosa.times_like.return_value = np.asarray(times, dtype=float)
    with patch.object(mod, "get_audio_duration", return_value=_TOTAL_DURATION), \
            patch.dict(sys.modules, {"librosa": fake_librosa}):
        return mod.find_best_segment(Path("/fake.wav"), duration=_DURATION)


@pytest.mark.unit
class TestFindBestSegmentLastWindow:
    """The final valid analysis window must be considered."""

    def test_selects_last_valid_window(self):
        # 6 RMS frames, window_samples=3 -> valid start indices 0,1,2,3.
        # Energy climbs toward the end so the window starting at index 3 (the
        # LAST valid window) has the highest mean. Buggy range(3) stops at 2.
        rms = [0.1, 0.1, 0.1, 1.0, 1.0, 1.0]
        times = [0.0, 10.0, 20.0, 30.0, 40.0, 50.0]
        # window means: [0:3]=0.1  [1:4]=0.4  [2:5]=0.7  [3:6]=1.0 (max)
        result = _run(rms, times)
        assert result == pytest.approx(30.0)  # times[3]; pre-fix -> 20.0

    def test_normal_case_middle_window_unchanged(self):
        # Peak window sits in the middle (index 1); pre- and post-fix agree,
        # confirming the range change does not disturb the normal path.
        rms = [0.1, 0.9, 0.9, 0.9, 0.1, 0.1]
        times = [0.0, 10.0, 20.0, 30.0, 40.0, 50.0]
        # window means: [0:3]=0.633  [1:4]=0.9 (max)  [2:5]=0.633  [3:6]=0.367
        result = _run(rms, times)
        assert result == pytest.approx(10.0)  # times[1], unchanged by the fix

    def test_boundary_single_window_no_index_error(self):
        # len(rms) == window_samples (3): exactly one valid window at index 0.
        # Pre-fix range(0) never runs -> start defaults to 0.0. The fix must
        # evaluate index 0 and pick times[0] WITHOUT raising IndexError (a raised
        # IndexError would be swallowed and return the 200.0 fallback instead).
        rms = [0.2, 0.3, 0.4]
        times = [5.0, 6.0, 7.0]
        result = _run(rms, times)
        assert result != pytest.approx(_FALLBACK)  # no swallowed IndexError
        assert result == pytest.approx(5.0)  # times[0]; pre-fix -> 0.0
