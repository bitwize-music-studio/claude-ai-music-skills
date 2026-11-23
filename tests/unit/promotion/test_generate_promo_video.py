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

    def test_title_after_bom(self, tmp_path):
        """A UTF-8 byte order mark ahead of the "---" is skipped (#669)."""
        md = tmp_path / "track.md"
        md.write_text("\ufeff---\ntitle: Boot Sequence\n---\n", encoding="utf-8")
        assert mod.get_title_from_markdown(md) == "Boot Sequence"

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

def _album_with_tracks(tmp_path, names=("01-track.wav", "02-track.wav")):
    album_dir = tmp_path / "album"
    album_dir.mkdir()
    for name in names:
        (album_dir / name).write_bytes(b"audio")
    return album_dir


def _fail_for(*failing):
    """A generate_waveform_video stand-in that fails for the named tracks."""
    def _fake(**kwargs):
        return kwargs["audio_path"].name not in failing
    return _fake


@pytest.mark.unit
class TestBatchProcessAlbum:
    """Tests for batch album promo video generation.

    The batch returns one (audio, output, success) row per track, and the
    success is the track's own outcome (#382): asserting call counts let a
    batch where every video failed report all successes (#682).
    """

    @patch.object(mod, "generate_waveform_video", return_value=True)
    def test_processes_audio_files(self, mock_gen, tmp_path):
        album_dir = _album_with_tracks(tmp_path)
        output_dir = tmp_path / "output"
        results = mod.batch_process_album(
            album_dir=album_dir,
            artwork_path=tmp_path / "art.png",
            output_dir=output_dir,
        )
        assert results == [
            ("01-track.wav", "01-track_promo.mp4", True),
            ("02-track.wav", "02-track_promo.mp4", True),
        ]
        assert sorted(c.kwargs["output_path"] for c in mock_gen.call_args_list) == [
            output_dir / "01-track_promo.mp4", output_dir / "02-track_promo.mp4",
        ]

    @patch.object(mod, "generate_waveform_video", return_value=True)
    def test_skips_non_audio_files(self, mock_gen, tmp_path):
        album_dir = _album_with_tracks(tmp_path, names=("01-track.wav",))
        (album_dir / "notes.txt").write_text("not audio", encoding="utf-8")
        (album_dir / "cover.png").write_bytes(b"image")
        output_dir = tmp_path / "output"
        results = mod.batch_process_album(
            album_dir=album_dir,
            artwork_path=tmp_path / "art.png",
            output_dir=output_dir,
        )
        assert results == [("01-track.wav", "01-track_promo.mp4", True)]
        assert mock_gen.call_count == 1

    @patch.object(mod, "generate_waveform_video", return_value=True)
    def test_empty_directory(self, mock_gen, tmp_path):
        album_dir = tmp_path / "empty"
        album_dir.mkdir()
        output_dir = tmp_path / "output"
        results = mod.batch_process_album(
            album_dir=album_dir,
            artwork_path=tmp_path / "art.png",
            output_dir=output_dir,
        )
        assert results == []
        mock_gen.assert_not_called()

    @pytest.mark.parametrize("jobs", [1, 2])
    def test_failed_track_is_reported_failed(self, tmp_path, jobs):
        """A video that fails comes back as a failed row, sequential or parallel."""
        album_dir = _album_with_tracks(tmp_path, names=("01-a.wav", "02-b.wav", "03-c.wav"))
        with patch.object(mod, "generate_waveform_video", side_effect=_fail_for("02-b.wav")):
            results = mod.batch_process_album(
                album_dir=album_dir, artwork_path=tmp_path / "art.png",
                output_dir=tmp_path / "output", jobs=jobs,
            )
        assert results == [
            ("01-a.wav", "01-a_promo.mp4", True),
            ("02-b.wav", "02-b_promo.mp4", False),
            ("03-c.wav", "03-c_promo.mp4", True),
        ]

    def test_every_track_failing_is_all_failures(self, tmp_path):
        album_dir = _album_with_tracks(tmp_path)
        with patch.object(mod, "generate_waveform_video", return_value=False):
            results = mod.batch_process_album(
                album_dir=album_dir, artwork_path=tmp_path / "art.png",
                output_dir=tmp_path / "output",
            )
        assert [ok for _name, _out, ok in results] == [False, False]


@pytest.mark.unit
class TestBatchFailuresReachTheCaller:
    """A failed video in the real batch reaches the MCP tool and the CLI (#382, #682)."""

    def test_handler_reports_failed_track_and_counts(self, tmp_path, monkeypatch):
        import asyncio
        import json

        server_dir = _PROJECT_ROOT / "servers" / "bitwize-music-server"
        if str(server_dir) not in sys.path:
            monkeypatch.syspath_prepend(str(server_dir))
        from handlers import _shared
        from handlers.processing import _helpers as processing_helpers
        from handlers.processing import video as video_mod

        class _Cache:
            def get_state(self):
                return {"config": {"artist_name": "bitwize"}, "albums": {}}

        album_dir = _album_with_tracks(tmp_path)
        (album_dir / "album.png").write_bytes(b"png")
        monkeypatch.setattr(_shared, "cache", _Cache())
        monkeypatch.setattr(processing_helpers, "_check_ffmpeg", lambda: None)
        monkeypatch.setattr(processing_helpers, "_resolve_audio_dir",
                            lambda *_a, **_k: (None, album_dir))
        with patch.object(mod, "generate_waveform_video", side_effect=_fail_for("02-track.wav")), \
             patch("tools.shared.fonts.find_font", return_value=None):
            result = json.loads(asyncio.run(video_mod.generate_promo_videos("album")))

        assert [(t["filename"], t["success"]) for t in result["tracks"]] == [
            ("01-track.wav", True), ("02-track.wav", False),
        ]
        assert result["summary"]["success"] == 1
        assert result["summary"]["failed"] == 1
        assert result["summary"]["failed_tracks"] == ["02-track.wav"]

    def test_cli_batch_exits_nonzero_and_names_the_failure(self, tmp_path, monkeypatch, caplog):
        album_dir = _album_with_tracks(tmp_path)
        art = tmp_path / "album.png"
        art.write_bytes(b"")
        monkeypatch.setattr(
            "sys.argv",
            ["generate_promo_video.py", "--batch", str(album_dir), "--batch-artwork", str(art)],
        )
        monkeypatch.setattr(mod, "check_ffmpeg", lambda: True)
        monkeypatch.setattr(mod, "find_font", lambda: str(tmp_path / "font.ttf"))
        with patch.object(mod, "generate_waveform_video", side_effect=_fail_for("02-track.wav")), \
             pytest.raises(SystemExit) as exc_info:
            mod.main()
        assert exc_info.value.code == 1
        assert "1 of 2 tracks failed: 02-track.wav" in caplog.text


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
        calls: list[dict] = []
        monkeypatch.setattr(gpv, "batch_process_album", lambda **kw: calls.append(kw) or results)
        # main() probes the environment (real ffmpeg binary, system font)
        # before batching; neutralize both so the exit-code contract is
        # tested on runners without them (Windows CI) and their absence
        # can't mask — or fake — the batch-result exit path.
        monkeypatch.setattr(gpv, "check_ffmpeg", lambda: True)
        monkeypatch.setattr(gpv, "find_font", lambda: str(tmp_path / "font.ttf"))
        assert gpv.main() is None
        return album, art, calls

    def test_failure_exits_nonzero(self, tmp_path, monkeypatch):
        with pytest.raises(SystemExit) as exc_info:
            self._run_main(
                tmp_path, monkeypatch,
                [("01-track.wav", "01-track_promo.mp4", True),
                 ("02-track.wav", "02-track_promo.mp4", False)],
            )
        assert exc_info.value.code == 1

    def test_all_success_exits_zero(self, tmp_path, monkeypatch, caplog):
        # main() returns normally (no SystemExit) when every track succeeds
        album, art, calls = self._run_main(
            tmp_path, monkeypatch,
            [("01-track.wav", "01-track_promo.mp4", True)],
        )
        assert len(calls) == 1
        assert calls[0]["album_dir"] == album
        assert calls[0]["artwork_path"] == art
        assert calls[0]["output_dir"] == album / "promo_videos"
        assert "failed" not in caplog.text
