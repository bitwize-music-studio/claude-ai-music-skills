"""Tests for tools/sheet-music/prepare_singles.py."""

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Import the module under test via importlib (hyphenated directory)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Force-mock heavy optional deps before import
_MOCK_MODULES = {
    "pypdf": MagicMock(),
    "reportlab": MagicMock(),
    "reportlab.lib": MagicMock(),
    "reportlab.lib.pagesizes": MagicMock(),
    "reportlab.lib.units": MagicMock(inch=72),
    "reportlab.pdfgen": MagicMock(),
    "reportlab.pdfgen.canvas": MagicMock(),
}
_SAVED_MODULES = {name: sys.modules.get(name) for name in _MOCK_MODULES}
for name, mock in _MOCK_MODULES.items():
    sys.modules[name] = mock

_module_path = _PROJECT_ROOT / "tools" / "sheet-music" / "prepare_singles.py"
_spec = importlib.util.spec_from_file_location("prepare_singles", _module_path)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

# Restore original modules
for name, original in _SAVED_MODULES.items():
    if original is None:
        sys.modules.pop(name, None)
    else:
        sys.modules[name] = original


# ---------------------------------------------------------------------------
# _extract_track_number
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestExtractTrackNumber:
    """Tests for numeric track number extraction from filename stems."""

    def test_two_digit_prefix(self):
        assert mod._extract_track_number("01-ocean-of-tears") == 1

    def test_double_digit(self):
        assert mod._extract_track_number("12-beyond-the-stars") == 12

    def test_single_digit(self):
        assert mod._extract_track_number("3-hello") == 3

    def test_no_number(self):
        assert mod._extract_track_number("ocean-of-tears") is None

    def test_empty_string(self):
        assert mod._extract_track_number("") is None

    def test_number_only(self):
        assert mod._extract_track_number("07") == 7


# ---------------------------------------------------------------------------
# resolve_source_dir
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestResolveSourceDir:
    """Tests for source directory resolution with backward compatibility."""

    def test_given_source_dir_directly(self, tmp_path):
        source = tmp_path / "source"
        source.mkdir()
        src, singles = mod.resolve_source_dir(source)
        assert src == source
        assert singles == tmp_path / "singles"

    def test_parent_with_source_subdir(self, tmp_path):
        sheet_music = tmp_path / "sheet-music"
        source = sheet_music / "source"
        source.mkdir(parents=True)
        src, singles = mod.resolve_source_dir(sheet_music)
        assert src == source
        assert singles == sheet_music / "singles"

    def test_flat_layout_with_numbered_xml(self, tmp_path):
        flat = tmp_path / "sheet-music"
        flat.mkdir()
        (flat / "01-track.xml").write_text("<score/>")
        src, singles = mod.resolve_source_dir(flat)
        assert src == flat
        assert singles == flat / "singles"

    def test_flat_layout_with_musicxml(self, tmp_path):
        flat = tmp_path / "sheet-music"
        flat.mkdir()
        (flat / "01-track.musicxml").write_text("<score/>")
        src, singles = mod.resolve_source_dir(flat)
        assert src == flat

    def test_empty_directory(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        src, singles = mod.resolve_source_dir(empty)
        assert src == empty
        assert singles == empty / "singles"


# ---------------------------------------------------------------------------
# _read_source_manifest
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestReadSourceManifest:
    """Tests for reading .manifest.json from source directory."""

    def test_reads_valid_manifest(self, tmp_path):
        manifest = {"tracks": [{"number": 1, "title": "First Pour"}]}
        (tmp_path / ".manifest.json").write_text(json.dumps(manifest))
        result = mod._read_source_manifest(tmp_path)
        assert result == manifest

    def test_returns_none_when_missing(self, tmp_path):
        result = mod._read_source_manifest(tmp_path)
        assert result is None

    def test_returns_none_on_invalid_json(self, tmp_path):
        (tmp_path / ".manifest.json").write_text("not json at all {{{")
        result = mod._read_source_manifest(tmp_path)
        assert result is None


# ---------------------------------------------------------------------------
# prepare_xml
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestPrepareXml:
    """Tests for MusicXML work-title update and file writing."""

    def test_updates_work_title(self, tmp_path):
        source = tmp_path / "source"
        source.mkdir()
        xml_content = '<score><work-title>01-ocean-of-tears</work-title></score>'
        xml_file = source / "01-ocean-of-tears.xml"
        xml_file.write_text(xml_content)

        singles = tmp_path / "singles"
        singles.mkdir()

        out = mod.prepare_xml(xml_file, singles, "Ocean of Tears")
        assert out is not None
        written = (singles / "Ocean of Tears.xml").read_text()
        assert "<work-title>Ocean of Tears</work-title>" in written
        assert "01-ocean-of-tears" not in written

    def test_custom_output_name(self, tmp_path):
        source = tmp_path / "source"
        source.mkdir()
        xml_file = source / "01-track.xml"
        xml_file.write_text('<score><work-title>01-track</work-title></score>')

        singles = tmp_path / "singles"
        singles.mkdir()

        out = mod.prepare_xml(xml_file, singles, "Track", output_name="01 - Track")
        assert out.name == "01 - Track.xml"

    def test_dry_run_does_not_write(self, tmp_path):
        source = tmp_path / "source"
        source.mkdir()
        xml_file = source / "01-track.xml"
        xml_file.write_text('<score><work-title>old</work-title></score>')

        singles = tmp_path / "singles"
        singles.mkdir()

        out = mod.prepare_xml(xml_file, singles, "New Title", dry_run=True)
        assert out is not None
        # File should NOT be written in dry run
        assert not (singles / "New Title.xml").exists()

    def test_no_work_title_tag(self, tmp_path):
        source = tmp_path / "source"
        source.mkdir()
        xml_file = source / "track.xml"
        xml_file.write_text('<score><part>notes</part></score>')

        singles = tmp_path / "singles"
        singles.mkdir()

        out = mod.prepare_xml(xml_file, singles, "Title")
        assert out is not None
        written = (singles / "Title.xml").read_text()
        assert "<score><part>notes</part></score>" == written


# ---------------------------------------------------------------------------
# prepare_singles (main function) — legacy flow
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestPrepareSinglesLegacy:
    """Tests for prepare_singles with numbered source files (no manifest)."""

    def _make_source(self, tmp_path, files):
        """Create source dir with given filenames."""
        source = tmp_path / "source"
        source.mkdir()
        for name in files:
            (source / name).write_text(f"content of {name}")
        return source

    @patch.object(mod, "_add_title_page_and_footer")
    def test_processes_xml_and_pdf(self, mock_title_page, tmp_path):
        source = self._make_source(tmp_path, [
            "01-first-pour.xml",
            "01-first-pour.pdf",
        ])
        singles = tmp_path / "singles"

        result = mod.prepare_singles(source, singles)
        assert "error" not in result
        assert len(result["tracks"]) == 1
        assert result["tracks"][0]["title"] == "First Pour"
        assert (singles / ".manifest.json").exists()

    @patch.object(mod, "_add_title_page_and_footer")
    def test_processes_multiple_tracks(self, mock_title_page, tmp_path):
        source = self._make_source(tmp_path, [
            "01-first.xml", "01-first.pdf",
            "02-second.xml", "02-second.pdf",
        ])
        singles = tmp_path / "singles"

        result = mod.prepare_singles(source, singles)
        assert len(result["tracks"]) == 2
        manifest = result["manifest"]
        assert manifest["tracks"][0]["title"] == "First"
        assert manifest["tracks"][1]["title"] == "Second"

    @patch.object(mod, "_add_title_page_and_footer")
    def test_copies_midi(self, mock_title_page, tmp_path):
        source = self._make_source(tmp_path, [
            "01-track.xml",
            "01-track.mid",
        ])
        singles = tmp_path / "singles"

        result = mod.prepare_singles(source, singles)
        assert (singles / "01 - Track.mid").exists()

    def test_no_files_returns_error(self, tmp_path):
        source = tmp_path / "source"
        source.mkdir()
        singles = tmp_path / "singles"

        result = mod.prepare_singles(source, singles)
        assert "error" in result

    @patch.object(mod, "_add_title_page_and_footer")
    def test_dry_run_no_directory_created(self, mock_title_page, tmp_path):
        source = self._make_source(tmp_path, ["01-track.xml"])
        singles = tmp_path / "singles"

        result = mod.prepare_singles(source, singles, dry_run=True)
        assert "error" not in result
        assert not singles.exists()

    @patch.object(mod, "_add_title_page_and_footer")
    def test_manifest_written(self, mock_title_page, tmp_path):
        source = self._make_source(tmp_path, [
            "01-alpha.xml", "02-beta.xml",
        ])
        singles = tmp_path / "singles"

        mod.prepare_singles(source, singles)
        manifest_path = singles / ".manifest.json"
        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text())
        assert len(manifest["tracks"]) == 2
        assert manifest["tracks"][0]["number"] == 1
        assert manifest["tracks"][0]["filename"] == "01 - Alpha"
        assert manifest["tracks"][1]["number"] == 2

    @patch.object(mod, "_add_title_page_and_footer")
    def test_title_map_override(self, mock_title_page, tmp_path):
        source = self._make_source(tmp_path, ["01-my-track.xml"])
        singles = tmp_path / "singles"

        result = mod.prepare_singles(
            source, singles,
            title_map={"01-my-track": "Custom Title Here"}
        )
        assert result["tracks"][0]["title"] == "Custom Title Here"


# ---------------------------------------------------------------------------
# prepare_singles — manifest flow
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestPrepareSinglesManifest:
    """Tests for prepare_singles with .manifest.json (new flow)."""

    @patch.object(mod, "_add_title_page_and_footer")
    def test_manifest_flow_uses_titles(self, mock_title_page, tmp_path):
        source = tmp_path / "source"
        source.mkdir()

        # Clean-titled source files (new flow)
        (source / "First Pour.xml").write_text('<score><work-title>First Pour</work-title></score>')
        (source / "First Pour.pdf").write_text("pdf content")

        manifest = {
            "tracks": [
                {"number": 1, "source_slug": "01-first-pour", "title": "First Pour"}
            ]
        }
        (source / ".manifest.json").write_text(json.dumps(manifest))

        singles = tmp_path / "singles"
        result = mod.prepare_singles(source, singles)

        assert "error" not in result
        assert len(result["tracks"]) == 1
        assert result["tracks"][0]["filename"] == "01 - First Pour"

    def test_manifest_no_tracks_returns_error(self, tmp_path):
        source = tmp_path / "source"
        source.mkdir()
        manifest = {"tracks": []}
        (source / ".manifest.json").write_text(json.dumps(manifest))

        singles = tmp_path / "singles"
        result = mod.prepare_singles(source, singles)
        assert "error" in result


# ---------------------------------------------------------------------------
# find_musescore
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestFindMusescore:
    """Tests for MuseScore detection."""

    @patch("platform.system", return_value="Linux")
    def test_returns_none_when_not_found(self, _mock_platform):
        """On a system without MuseScore, find_musescore returns None."""
        with patch.object(Path, "exists", return_value=False):
            with patch("subprocess.run", side_effect=FileNotFoundError):
                result = mod.find_musescore()
                assert result is None

    @patch("platform.system", return_value="Linux")
    def test_finds_from_path_fallback(self, _mock_platform):
        """When no known path exists, falls back to which/where."""
        with patch.object(Path, "exists", return_value=False):
            with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="/usr/local/bin/mscore\n")):
                result = mod.find_musescore()
                assert result == "/usr/local/bin/mscore"


# ---------------------------------------------------------------------------
# export_pdf
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestExportPdf:
    """Tests for PDF export via MuseScore CLI."""

    def test_dry_run_returns_true(self, tmp_path):
        result = mod.export_pdf(
            tmp_path / "in.xml", tmp_path / "out.pdf",
            musescore_path="/usr/bin/mscore", dry_run=True
        )
        assert result is True

    @patch("subprocess.run")
    def test_successful_export(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        result = mod.export_pdf(
            tmp_path / "in.xml", tmp_path / "out.pdf",
            musescore_path="/usr/bin/mscore"
        )
        assert result is True
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_failed_export(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=1, stderr="error")
        result = mod.export_pdf(
            tmp_path / "in.xml", tmp_path / "out.pdf",
            musescore_path="/usr/bin/mscore"
        )
        assert result is False

    @patch("subprocess.run")
    def test_timeout(self, mock_run, tmp_path):
        import subprocess as real_subprocess
        mock_run.side_effect = real_subprocess.TimeoutExpired(cmd="mscore", timeout=60)
        result = mod.export_pdf(
            tmp_path / "in.xml", tmp_path / "out.pdf",
            musescore_path="/usr/bin/mscore"
        )
        assert result is False
