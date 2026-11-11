"""find_best_segment starts the promo passage on a beat when one is close by.

librosa is mocked, as in test_find_best_segment_412.py, so the energy envelope
and the beat grid are fully controlled.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.shared import media_utils as mod

_SR = 120
_DURATION = 15
_TOTAL = 1000.0


def _run(rms, times, beat_times=None, beat_error=None):
    fake = MagicMock()
    fake.load.return_value = (np.zeros(8, dtype=float), _SR)
    fake.feature.rms.return_value = np.array([np.asarray(rms, dtype=float)])
    fake.times_like.return_value = np.asarray(times, dtype=float)
    if beat_error is not None:
        fake.beat.beat_track.side_effect = beat_error
    elif beat_times is not None:
        fake.beat.beat_track.return_value = (120.0, np.arange(len(beat_times)))
        fake.frames_to_time.return_value = np.asarray(beat_times, dtype=float)
    with patch.object(mod, "get_audio_duration", return_value=_TOTAL), \
            patch.dict(sys.modules, {"librosa": fake}):
        return mod.find_best_segment(Path("/fake.wav"), duration=_DURATION)


# Energy peaks in the window that starts at index 3 -> time 30.4 s.
_RMS = [0.1, 0.1, 0.1, 0.9, 0.9, 0.9]
_TIMES = [0.0, 10.0, 20.0, 30.4, 40.0, 50.0]


@pytest.mark.unit
class TestBeatSnap:
    def test_snaps_to_the_nearest_beat(self):
        assert _run(_RMS, _TIMES, beat_times=[29.0, 29.5, 30.0, 30.5, 31.0]) == 30.5

    def test_a_beat_further_than_a_second_away_is_ignored(self):
        assert _run(_RMS, _TIMES, beat_times=[10.0, 20.0, 45.0]) == 30.4

    def test_no_beats_found(self):
        assert _run(_RMS, _TIMES, beat_times=[]) == 30.4

    def test_a_beat_tracker_failure_keeps_the_energy_pick(self):
        assert _run(_RMS, _TIMES, beat_error=RuntimeError("no onset envelope")) == 30.4

    def test_without_a_beat_grid_nothing_changes(self):
        """The mock returns a MagicMock for beat_track: unusable, so the pick stands."""
        assert _run(_RMS, _TIMES) == 30.4
