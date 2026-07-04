"""Tests for tools/shared/media_utils.py."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Import the module under test
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Force-mock heavy optional deps before import
_MOCK_DEPS = ["librosa", "PIL", "PIL.Image", "PIL.ImageDraw", "PIL.ImageFont"]
_SAVED_DEPS = {dep: sys.modules.get(dep) for dep in _MOCK_DEPS}
for dep in _MOCK_DEPS:
    sys.modules[dep] = MagicMock()

from tools.shared import media_utils as mod

# Restore original modules
for dep, original in _SAVED_DEPS.items():
    if original is None:
        sys.modules.pop(dep, None)
    else:
        sys.modules[dep] = original


# ---------------------------------------------------------------------------
# rgb_to_hex
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestRgbToHex:
    """Tests for RGB to hex conversion."""

    def test_white(self):
        assert mod.rgb_to_hex((255, 255, 255)) == "0xffffff"

    def test_black(self):
        assert mod.rgb_to_hex((0, 0, 0)) == "0x000000"

    def test_red(self):
        assert mod.rgb_to_hex((255, 0, 0)) == "0xff0000"


# ---------------------------------------------------------------------------
# get_complementary_color
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestGetComplementaryColor:
    """Tests for complementary color calculation."""

    def test_returns_tuple(self):
        result = mod.get_complementary_color((128, 64, 32))
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_values_in_range(self):
        result = mod.get_complementary_color((200, 100, 50))
        for v in result:
            assert 0 <= v <= 255


# ---------------------------------------------------------------------------
# get_analogous_colors
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestGetAnalogousColors:
    """Tests for analogous color calculation."""

    def test_returns_two_tuples(self):
        c1, c2 = mod.get_analogous_colors((128, 64, 32))
        assert len(c1) == 3
        assert len(c2) == 3


# ---------------------------------------------------------------------------
# check_ffmpeg
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestCheckFfmpeg:
    """Tests for ffmpeg availability check."""

    @patch.object(mod, "subprocess")
    def test_ffmpeg_available(self, mock_sub):
        mock_sub.run.return_value = MagicMock(stdout="showwaves", returncode=0)
        result = mod.check_ffmpeg()
        assert result is True

    @patch.object(mod, "subprocess")
    def test_showwaves_missing(self, mock_sub):
        mock_sub.run.return_value = MagicMock(stdout="no relevant filters", returncode=0)
        result = mod.check_ffmpeg(require_showwaves=True)
        assert result is False

    @patch.object(mod, "subprocess")
    def test_ffmpeg_not_installed(self, mock_sub):
        mock_sub.run.side_effect = FileNotFoundError()
        with pytest.raises(SystemExit):
            mod.check_ffmpeg()


# ---------------------------------------------------------------------------
# get_audio_duration
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestGetAudioDuration:
    """Tests for audio duration via ffprobe."""

    @patch.object(mod, "subprocess")
    def test_returns_duration(self, mock_sub):
        mock_sub.run.return_value = MagicMock(returncode=0, stdout="123.45\n", stderr="")
        result = mod.get_audio_duration(Path("/fake/audio.wav"))
        assert result == pytest.approx(123.45)

    @patch.object(mod, "subprocess")
    def test_ffprobe_failure(self, mock_sub):
        mock_sub.run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
        with pytest.raises(RuntimeError):
            mod.get_audio_duration(Path("/fake/audio.wav"))


# ---------------------------------------------------------------------------
# find_best_segment
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestFindBestSegment:
    """Tests for best audio segment detection."""

    @patch.object(mod, "get_audio_duration", return_value=10.0)
    def test_short_audio_returns_zero(self, _mock_dur):
        """If audio is shorter than duration, start at 0."""
        result = mod.find_best_segment(Path("/fake.wav"), duration=15)
        assert result == 0

    @patch.object(mod, "get_audio_duration", return_value=120.0)
    def test_fallback_without_librosa(self, _mock_dur):
        """Without librosa, falls back to 20% into track."""
        # Force ImportError for librosa inside the function
        with patch.dict(sys.modules, {"librosa": None}):
            # The function catches ImportError internally
            result = mod.find_best_segment(Path("/fake.wav"), duration=15)
            # Fallback: min(120 * 0.2, 120 - 15) = min(24, 105) = 24
            assert result == pytest.approx(24.0)

    @patch.object(mod, "get_audio_duration", return_value=20.0)
    def test_last_window_is_considered(self, _mock_dur):
        """#412: the highest-energy window at the very end must not be skipped.

        window_samples=2 over a 5-sample rms track: valid start indices are
        0..3 inclusive (range(5 - 2 + 1)). The off-by-one bug stopped at
        range(5 - 2) = range(3), silently excluding the last (highest-energy)
        window and returning a worse start time.
        """
        import numpy as np

        fake_librosa = MagicMock()
        fake_librosa.load.return_value = (np.zeros(10), 512)  # y, sr=512
        fake_librosa.feature.rms.return_value = np.array([[0, 0, 0, 10, 10]])
        fake_librosa.times_like.return_value = np.array([0.0, 1.0, 2.0, 3.0, 4.0])

        with patch.dict(sys.modules, {"librosa": fake_librosa}):
            # duration=2, hop_length=512 (hardcoded) -> window_samples = int(2*512/512) = 2
            result = mod.find_best_segment(Path("/fake.wav"), duration=2)

        assert result == pytest.approx(3.0)
