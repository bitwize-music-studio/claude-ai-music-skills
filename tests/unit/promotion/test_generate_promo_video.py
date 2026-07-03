"""Tests for tools/promotion/generate_promo_video.py."""

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
_MOCK_DEPS = ["librosa", "PIL", "PIL.Image", "PIL.ImageDraw", "PIL.ImageFont"]
_SAVED_DEPS = {dep: sys.modules.get(dep) for dep in _MOCK_DEPS}
for dep in _MOCK_DEPS:
    sys.modules[dep] = MagicMock()

from tools.promotion import generate_promo_video as mod

# Restore original modules to avoid polluting later tests
for dep, original in _SAVED_DEPS.items():
    if original is None:
        sys.modules.pop(dep, None)
    else:
        sys.modules[dep] = original


# ---------------------------------------------------------------------------
# get_title_from_markdown
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestGetTitleFromMarkdown:
    """Tests for extracting title from track markdown frontmatter."""

    def test_valid_frontmatter(self, tmp_path):
        md = tmp_path / "track.md"
        md.write_text("---\ntitle: Boot Sequence\nstatus: Final\n---\n# Lyrics\n")
        assert mod.get_title_from_markdown(md) == "Boot Sequence"

    def test_double_quoted_title(self, tmp_path):
        md = tmp_path / "track.md"
        md.write_text('---\ntitle: "Hello World"\n---\n')
        assert mod.get_title_from_markdown(md) == "Hello World"

    def test_single_quoted_title(self, tmp_path):
        md = tmp_path / "track.md"
        md.write_text("---\ntitle: 'Hello World'\n---\n")
        assert mod.get_title_from_markdown(md) == "Hello World"

    def test_no_frontmatter(self, tmp_path):
        md = tmp_path / "track.md"
        md.write_text("# Just a heading\nSome content\n")
        assert mod.get_title_from_markdown(md) is None

    def test_missing_title_field(self, tmp_path):
        md = tmp_path / "track.md"
        md.write_text("---\nstatus: Final\n---\n")
        assert mod.get_title_from_markdown(md) is None

    def test_nonexistent_file(self, tmp_path):
        md = tmp_path / "missing.md"
        assert mod.get_title_from_markdown(md) is None


# ---------------------------------------------------------------------------
# generate_waveform_video
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestGenerateWaveformVideo:
    """Tests for promo video generation with mocked subprocess/ffmpeg."""

    @pytest.fixture()
    def audio_file(self, tmp_path):
        f = tmp_path / "track.wav"
        f.write_bytes(b"fake audio")
        return f

    @pytest.fixture()
    def artwork_file(self, tmp_path):
        f = tmp_path / "artwork.png"
        f.write_bytes(b"fake image")
        return f

    @patch.object(mod, "subprocess")
    @patch.object(mod, "find_best_segment", return_value=0.0)
    @patch.object(mod, "extract_dominant_color", return_value=(128, 128, 128))
    def test_happy_path(self, _mock_color, _mock_seg, mock_sub, audio_file, artwork_file, tmp_path):
        mock_sub.run.return_value = MagicMock(returncode=0, stderr="")
        output = tmp_path / "out.mp4"
        result = mod.generate_waveform_video(
            audio_path=audio_file,
            artwork_path=artwork_file,
            title="Test Track",
            output_path=output,
            font_path="/tmp/fake-font.ttf",
        )
        assert result is True
        mock_sub.run.assert_called_once()

    @patch.object(mod, "subprocess")
    @patch.object(mod, "find_best_segment", return_value=0.0)
    @patch.object(mod, "extract_dominant_color", return_value=(128, 128, 128))
    def test_ffmpeg_failure(self, _mock_color, _mock_seg, mock_sub, audio_file, artwork_file, tmp_path):
        mock_sub.run.return_value = MagicMock(returncode=1, stderr="encoder error")
        output = tmp_path / "out.mp4"
        result = mod.generate_waveform_video(
            audio_path=audio_file,
            artwork_path=artwork_file,
            title="Test Track",
            output_path=output,
            font_path="/tmp/fake-font.ttf",
        )
        assert result is False

    @patch.object(mod, "subprocess")
    @patch.object(mod, "find_best_segment", return_value=0.0)
    @patch.object(mod, "extract_dominant_color", return_value=(128, 128, 128))
    def test_subprocess_exception(self, _mock_color, _mock_seg, mock_sub, audio_file, artwork_file, tmp_path):
        mock_sub.run.side_effect = OSError("ffmpeg not found")
        output = tmp_path / "out.mp4"
        result = mod.generate_waveform_video(
            audio_path=audio_file,
            artwork_path=artwork_file,
            title="Test Track",
            output_path=output,
            font_path="/tmp/fake-font.ttf",
        )
        assert result is False

    @patch.object(mod, "subprocess")
    @patch.object(mod, "find_best_segment", return_value=0.0)
    @patch.object(mod, "extract_dominant_color", return_value=(128, 128, 128))
    def test_custom_color_hex(self, mock_color, _mock_seg, mock_sub, audio_file, artwork_file, tmp_path):
        mock_sub.run.return_value = MagicMock(returncode=0, stderr="")
        output = tmp_path / "out.mp4"
        # Use "pulse" style which embeds color2 in the filter (bars uses white)
        mod.generate_waveform_video(
            audio_path=audio_file,
            artwork_path=artwork_file,
            title="Test",
            output_path=output,
            font_path="/tmp/fake-font.ttf",
            color_hex="#C9A96E",
            style="pulse",
        )
        cmd_args = mock_sub.run.call_args[0][0]
        filter_str = " ".join(str(a) for a in cmd_args)
        assert "#C9A96E" in filter_str or "C9A96E" in filter_str

    @patch.object(mod, "subprocess")
    @patch.object(mod, "find_best_segment", return_value=0.0)
    @patch.object(mod, "extract_dominant_color", return_value=(128, 128, 128))
    def test_custom_text_color(self, _mock_color, _mock_seg, mock_sub, audio_file, artwork_file, tmp_path):
        mock_sub.run.return_value = MagicMock(returncode=0, stderr="")
        output = tmp_path / "out.mp4"
        mod.generate_waveform_video(
            audio_path=audio_file,
            artwork_path=artwork_file,
            title="Test",
            output_path=output,
            font_path="/tmp/fake-font.ttf",
            text_color="#FFD700",
        )
        cmd_args = mock_sub.run.call_args[0][0]
        filter_str = " ".join(str(a) for a in cmd_args)
        assert "#FFD700" in filter_str


# ---------------------------------------------------------------------------
# batch_process_album
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestBatchProcessAlbum:
    """Tests for batch album promo video generation."""

    @patch.object(mod, "generate_waveform_video", return_value=True)
    def test_processes_audio_files(self, mock_gen, tmp_path):
        album_dir = tmp_path / "album"
        album_dir.mkdir()
        (album_dir / "01-track.wav").write_bytes(b"audio")
        (album_dir / "02-track.wav").write_bytes(b"audio")
        output_dir = tmp_path / "output"
        mod.batch_process_album(
            album_dir=album_dir,
            artwork_path=tmp_path / "art.png",
            output_dir=output_dir,
        )
        assert mock_gen.call_count == 2

    @patch.object(mod, "generate_waveform_video", return_value=True)
    def test_skips_non_audio_files(self, mock_gen, tmp_path):
        album_dir = tmp_path / "album"
        album_dir.mkdir()
        (album_dir / "01-track.wav").write_bytes(b"audio")
        (album_dir / "notes.txt").write_text("not audio")
        (album_dir / "cover.png").write_bytes(b"image")
        output_dir = tmp_path / "output"
        mod.batch_process_album(
            album_dir=album_dir,
            artwork_path=tmp_path / "art.png",
            output_dir=output_dir,
        )
        assert mock_gen.call_count == 1

    @patch.object(mod, "generate_waveform_video", return_value=True)
    def test_empty_directory(self, mock_gen, tmp_path):
        album_dir = tmp_path / "empty"
        album_dir.mkdir()
        output_dir = tmp_path / "output"
        mod.batch_process_album(
            album_dir=album_dir,
            artwork_path=tmp_path / "art.png",
            output_dir=output_dir,
        )
        mock_gen.assert_not_called()


class TestBatchCliExitCode:
    """CLI --batch mode exits non-zero when any track fails (#382)."""

    def _run_main(self, tmp_path, monkeypatch, results):
        import tools.promotion.generate_promo_video as gpv
        album = tmp_path / "album"
        album.mkdir()
        (album / "01-track.wav").write_bytes(b"")
        art = tmp_path / "album.png"
        art.write_bytes(b"")
        monkeypatch.setattr(
            "sys.argv",
            ["generate_promo_video.py", "--batch", str(album),
             "--batch-artwork", str(art)],
        )
        monkeypatch.setattr(gpv, "batch_process_album", lambda **kw: results)
        gpv.main()

    def test_failure_exits_nonzero(self, tmp_path, monkeypatch):
        with pytest.raises(SystemExit) as exc_info:
            self._run_main(
                tmp_path, monkeypatch,
                [("01-track.wav", "01-track_promo.mp4", True),
                 ("02-track.wav", "02-track_promo.mp4", False)],
            )
        assert exc_info.value.code == 1

    def test_all_success_exits_zero(self, tmp_path, monkeypatch):
        # main() returns normally (no SystemExit) when every track succeeds
        self._run_main(
            tmp_path, monkeypatch,
            [("01-track.wav", "01-track_promo.mp4", True)],
        )
