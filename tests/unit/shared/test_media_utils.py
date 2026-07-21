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


@pytest.mark.unit
class TestEscapeFilterPath:
    """Paths interpolated into an ffmpeg filtergraph.

    The expected Windows form is not guesswork: it was determined empirically on
    a real windows-latest runner by rendering one frame per candidate escaping.
    Only single-quoted + forward-slash + escaped-colon was accepted; bare,
    forward-slash-only, escaped-colon-unquoted, and quoted-without-colon-escape
    all died with "No option name near ...". These tests pin that finding so a
    future "simplification" cannot silently re-break promo video on Windows.
    """

    # The exact expression proved to render on windows-latest.
    PROVEN_WINDOWS_FONT = r"'C\:/Windows/Fonts/arialbd.ttf'"

    def test_windows_font_path_matches_the_form_proven_on_a_real_runner(self):
        assert mod.escape_filter_path(r"C:\Windows\Fonts\arialbd.ttf") == self.PROVEN_WINDOWS_FONT

    def test_windows_temp_textfile_path(self):
        result = mod.escape_filter_path(r"C:\Users\me\AppData\Local\Temp\t.txt")
        assert result == r"'C\:/Users/me/AppData/Local/Temp/t.txt'"

    def test_backslashes_become_forward_slashes(self):
        # '\' is the filtergraph escape character, so it must not survive.
        assert "\\W" not in mod.escape_filter_path(r"C:\Windows\x.ttf")

    def test_colon_is_escaped(self):
        # ':' separates filter options; an unescaped drive letter truncates it.
        assert mod.escape_filter_path(r"C:\x.ttf").startswith(r"'C\:")

    def test_result_is_single_quoted(self):
        r = mod.escape_filter_path(r"C:\Program Files\f.ttf")
        assert r.startswith("'") and r.endswith("'")

    def test_spaces_survive_via_quoting(self):
        assert mod.escape_filter_path(r"C:\Program Files\f.ttf") == r"'C\:/Program Files/f.ttf'"

    def test_posix_path_only_gains_quotes(self):
        # No backslashes and no colons on POSIX, so this is a near no-op —
        # macOS/Linux filtergraphs are unchanged apart from the quoting.
        p = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        assert mod.escape_filter_path(p) == f"'{p}'"

    def test_single_quote_in_path_is_escaped(self):
        # A bare ' would terminate the quoted token early.
        assert mod.escape_filter_path("/home/o'brien/f.ttf") == "'/home/o'\\''brien/f.ttf'"

    def test_accepts_a_path_object(self):
        assert mod.escape_filter_path(Path("/tmp/f.ttf")) == "'/tmp/f.ttf'"


@pytest.mark.unit
class TestPromoVideoFiltergraphEscaping:
    """The promo-video filtergraph must route every path through the escaper."""

    def test_filtergraph_source_uses_escaped_expressions_not_raw_paths(self):
        src = (
            Path(__file__).resolve().parents[3]
            / "tools" / "promotion" / "generate_promo_video.py"
        ).read_text(encoding="utf-8")

        # The escaper supplies its own quotes, so the old hand-quoted and
        # bare-interpolation forms must both be gone.
        assert "textfile='{title_file_path}'" not in src
        assert "textfile='{artist_file_path}'" not in src
        assert "fontfile={font_path}" not in src

        assert "textfile={title_file_expr}" in src
        assert "textfile={artist_file_expr}" in src
        assert "fontfile={font_expr}" in src
        assert "escape_filter_path" in src
