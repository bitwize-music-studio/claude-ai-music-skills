"""Tests for tools/promotion/generate_album_sampler.py."""

import re
import shutil
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Import the module under test
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Force-mock heavy optional deps before import so tests behave consistently
# regardless of whether the deps are installed on this machine.
# Save originals and restore after import to prevent MagicMock pollution
# leaking into later test files (e.g. PIL.__version__ becomes MagicMock).
_MOCK_DEPS = ["librosa", "PIL", "PIL.Image", "PIL.ImageDraw", "PIL.ImageFont"]
_SAVED_DEPS = {dep: sys.modules.get(dep) for dep in _MOCK_DEPS}
for dep in _MOCK_DEPS:
    sys.modules[dep] = MagicMock()

from tools.promotion import generate_album_sampler as mod
from tools.promotion.generate_album_sampler import get_track_title

# Restore original modules to avoid polluting later tests
for dep, original in _SAVED_DEPS.items():
    if original is None:
        sys.modules.pop(dep, None)
    else:
        sys.modules[dep] = original


# ---------------------------------------------------------------------------
# get_track_title
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestGetTrackTitle:
    """Tests for track title extraction from filenames."""

    def test_dash_separator(self):
        assert get_track_title("08 - 116 Cadets.wav") == "116 Cadets"

    def test_number_prefix_removed(self):
        assert get_track_title("01_my-great-track.wav") == "My Great Track"

    def test_slug_converted(self):
        assert get_track_title("03-fire-in-the-sky.wav") == "Fire In The Sky"

    def test_no_prefix(self):
        assert get_track_title("song-name.wav") == "Song Name"

    def test_two_digit_prefix(self):
        assert get_track_title("12.my_song.mp3") == "My Song"

    def test_three_digit_number_preserved(self):
        """Track numbers with 3+ digits (like '116') should NOT be stripped."""
        result = get_track_title("116-cadets.wav")
        # "116" has 3 digits so the regex shouldn't strip it
        assert "116" in result

    def test_underscore_to_space(self):
        assert get_track_title("01_hello_world.wav") == "Hello World"

    def test_title_case(self):
        result = get_track_title("05 - all lowercase words.wav")
        assert result == "All Lowercase Words"

    def test_single_word(self):
        assert get_track_title("01-anthem.wav") == "Anthem"

    def test_extension_removed(self):
        result = get_track_title("01-track.mp4")
        assert ".mp4" not in result


# ---------------------------------------------------------------------------
# generate_clip
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestGenerateClip:
    """Tests for single clip generation (delegates to generate_waveform_video)."""

    @patch.object(mod, "generate_waveform_video", return_value=True)
    def test_delegates_to_waveform_video(self, mock_gen, tmp_path):
        audio = tmp_path / "track.wav"
        audio.write_bytes(b"audio")
        art = tmp_path / "art.png"
        art.write_bytes(b"image")
        output = tmp_path / "clip.mp4"

        result = mod.generate_clip(
            audio_path=audio,
            artwork_path=art,
            title="Test",
            output_path=output,
            duration=12,
            start_time=5.0,
            color_hex="#FF0000",
            artist_name="artist",
            font_path="/tmp/font.ttf",
        )
        assert result is True
        mock_gen.assert_called_once()

    @patch.object(mod, "generate_waveform_video", return_value=False)
    def test_returns_false_on_failure(self, mock_gen, tmp_path):
        result = mod.generate_clip(
            audio_path=tmp_path / "track.wav",
            artwork_path=tmp_path / "art.png",
            title="Test",
            output_path=tmp_path / "clip.mp4",
            duration=12,
            start_time=0.0,
            color_hex="",
            artist_name="artist",
            font_path="/tmp/font.ttf",
        )
        assert result is False


# ---------------------------------------------------------------------------
# concatenate_with_crossfade
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestConcatenateWithCrossfade:
    """Tests for clip concatenation via ffmpeg."""

    def test_single_clip_copies(self, tmp_path):
        clip = tmp_path / "clip.mp4"
        clip.write_bytes(b"video data")
        output = tmp_path / "output.mp4"

        result = mod.concatenate_with_crossfade([clip], output)
        assert result is True
        assert output.read_bytes() == b"video data"

    @patch.object(mod, "subprocess")
    def test_multiple_clips_calls_ffmpeg(self, mock_sub, tmp_path):
        mock_sub.run.return_value = MagicMock(returncode=0, stderr="")
        clips = [tmp_path / f"clip_{i}.mp4" for i in range(3)]
        for c in clips:
            c.write_bytes(b"video")
        output = tmp_path / "output.mp4"

        result = mod.concatenate_with_crossfade(clips, output)
        assert result is True
        mock_sub.run.assert_called_once()

    @patch.object(mod, "subprocess")
    def test_ffmpeg_failure(self, mock_sub, tmp_path):
        mock_sub.run.return_value = MagicMock(returncode=1, stderr="error")
        clips = [tmp_path / f"clip_{i}.mp4" for i in range(2)]
        for c in clips:
            c.write_bytes(b"video")

        result = mod.concatenate_with_crossfade(clips, tmp_path / "out.mp4")
        assert result is False


# ---------------------------------------------------------------------------
# generate_album_sampler
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestGenerateAlbumSampler:
    """Tests for the full album sampler generation pipeline."""

    @patch.object(mod, "get_audio_duration", return_value=60.0)
    @patch.object(mod, "concatenate_with_crossfade", return_value=True)
    @patch.object(mod, "generate_clip", return_value=True)
    @patch.object(mod, "find_best_segment", return_value=5.0)
    @patch.object(mod, "extract_dominant_color", return_value=(128, 128, 128))
    def test_happy_path(self, _color, _seg, mock_clip, mock_concat, _dur, tmp_path):
        tracks = tmp_path / "tracks"
        tracks.mkdir()
        (tracks / "01-track.wav").write_bytes(b"audio")
        (tracks / "02-track.wav").write_bytes(b"audio")
        art = tmp_path / "art.png"
        art.write_bytes(b"img")
        output = tmp_path / "sampler.mp4"
        output.write_bytes(b"final video")  # concat mock doesn't create file

        result = mod.generate_album_sampler(
            tracks_dir=tracks,
            artwork_path=art,
            output_path=output,
            font_path="/tmp/font.ttf",
        )
        assert result is True
        assert mock_clip.call_count == 2
        mock_concat.assert_called_once()

    def test_no_audio_files(self, tmp_path):
        tracks = tmp_path / "empty"
        tracks.mkdir()
        result = mod.generate_album_sampler(
            tracks_dir=tracks,
            artwork_path=tmp_path / "art.png",
            output_path=tmp_path / "out.mp4",
            font_path="/tmp/font.ttf",
        )
        assert result is False

    @patch.object(mod, "concatenate_with_crossfade", return_value=False)
    @patch.object(mod, "generate_clip", return_value=True)
    @patch.object(mod, "find_best_segment", return_value=0.0)
    @patch.object(mod, "extract_dominant_color", return_value=(128, 128, 128))
    def test_concat_failure(self, _color, _seg, _clip, _concat, tmp_path):
        tracks = tmp_path / "tracks"
        tracks.mkdir()
        (tracks / "01-track.wav").write_bytes(b"audio")
        result = mod.generate_album_sampler(
            tracks_dir=tracks,
            artwork_path=tmp_path / "art.png",
            output_path=tmp_path / "out.mp4",
            font_path="/tmp/font.ttf",
        )
        assert result is False

    @patch.object(mod, "generate_clip", return_value=False)
    @patch.object(mod, "find_best_segment", return_value=0.0)
    @patch.object(mod, "extract_dominant_color", return_value=(128, 128, 128))
    def test_all_clips_fail(self, _color, _seg, _clip, tmp_path):
        tracks = tmp_path / "tracks"
        tracks.mkdir()
        (tracks / "01-track.wav").write_bytes(b"audio")
        result = mod.generate_album_sampler(
            tracks_dir=tracks,
            artwork_path=tmp_path / "art.png",
            output_path=tmp_path / "out.mp4",
            font_path="/tmp/font.ttf",
        )
        assert result is False

    @patch.object(mod, "get_audio_duration", return_value=60.0)
    @patch.object(mod, "concatenate_with_crossfade", return_value=True)
    @patch.object(mod, "generate_clip", return_value=True)
    @patch.object(mod, "find_best_segment", return_value=5.0)
    @patch.object(mod, "extract_dominant_color", return_value=(201, 169, 110))
    def test_auto_extracted_color_passes_downstream_validation(
        self, _color, _seg, mock_clip, _concat, _dur, tmp_path
    ):
        """Auto-extracted wave color (no color_hex given) must be a format that
        generate_waveform_video's validation accepts. Regression for #369:
        rgb_to_hex returns ffmpeg-style '0x...', which the '^#?[0-9a-fA-F]{3,8}$'
        validator rejects, failing every clip."""
        # Same validation regex generate_waveform_video applies to color_hex.
        validator = re.compile(r"^#?[0-9a-fA-F]{3,8}$")

        tracks = tmp_path / "tracks"
        tracks.mkdir()
        (tracks / "01-track.wav").write_bytes(b"audio")
        output = tmp_path / "out.mp4"
        output.write_bytes(b"video")

        mod.generate_album_sampler(
            tracks_dir=tracks,
            artwork_path=tmp_path / "art.png",
            output_path=output,
            font_path="/tmp/font.ttf",
            # color_hex omitted -> auto-extract path
        )

        passed_color = mock_clip.call_args[1]["color_hex"]
        assert not passed_color.startswith("0x"), (
            f"auto-extracted color {passed_color!r} uses ffmpeg '0x' format that "
            "downstream validation rejects"
        )
        assert validator.match(passed_color), (
            f"auto-extracted color {passed_color!r} fails generate_waveform_video "
            "validation, so every clip would be rejected"
        )

    @patch.object(mod, "get_audio_duration", return_value=60.0)
    @patch.object(mod, "concatenate_with_crossfade", return_value=True)
    @patch.object(mod, "generate_clip", return_value=True)
    @patch.object(mod, "find_best_segment", return_value=0.0)
    @patch.object(mod, "extract_dominant_color", return_value=(128, 128, 128))
    def test_custom_titles(self, _color, _seg, mock_clip, _concat, _dur, tmp_path):
        tracks = tmp_path / "tracks"
        tracks.mkdir()
        (tracks / "01-track.wav").write_bytes(b"audio")
        output = tmp_path / "out.mp4"
        output.write_bytes(b"video")

        mod.generate_album_sampler(
            tracks_dir=tracks,
            artwork_path=tmp_path / "art.png",
            output_path=output,
            font_path="/tmp/font.ttf",
            titles={"01-track": "Custom Title"},
        )
        # Verify the custom title was passed
        call_kwargs = mock_clip.call_args[1]
        assert call_kwargs["title"] == "Custom Title"
