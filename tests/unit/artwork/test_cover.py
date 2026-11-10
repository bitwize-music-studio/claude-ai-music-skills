"""Turning a chosen image into the files an album needs."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.artwork import cover  # noqa: E402


def _image(path: Path, size=(1254, 1254), mode="RGB", fmt="PNG") -> Path:
    Image.new(mode, size, (200, 60, 40) if mode == "RGB" else (200, 60, 40, 128)).save(path, fmt)
    return path


class TestImageSize:
    def test_size_of_a_png(self, tmp_path):
        assert cover.image_size(_image(tmp_path / "a.png")) == (1254, 1254)

    @pytest.mark.parametrize("content", [b"", b"not an image", b"\x89PNG broken"])
    def test_something_that_is_not_an_image(self, tmp_path, content):
        bad = tmp_path / "bad.png"
        bad.write_bytes(content)
        with pytest.raises(ValueError, match="not an image"):
            cover.image_size(bad)

    def test_a_missing_file(self, tmp_path):
        with pytest.raises(ValueError, match="not found"):
            cover.image_size(tmp_path / "gone.png")


class TestWriteCover:
    def test_a_codex_sized_image_is_enlarged_to_3000(self, tmp_path):
        """Codex returns 1254x1254; distributors want 3000x3000."""
        result = cover.write_cover(_image(tmp_path / "in.png"), tmp_path / "album.png")
        with Image.open(tmp_path / "album.png") as out:
            assert out.size == (3000, 3000)
            assert out.format == "PNG"
            assert out.mode == "RGB"
        assert result == {"size": [3000, 3000], "source_size": [1254, 1254], "enlarged": True}

    def test_an_image_already_big_enough_keeps_its_size(self, tmp_path):
        result = cover.write_cover(_image(tmp_path / "in.png", (3600, 3600)), tmp_path / "album.png")
        assert result == {"size": [3600, 3600], "source_size": [3600, 3600], "enlarged": False}

    def test_transparency_is_flattened(self, tmp_path):
        cover.write_cover(_image(tmp_path / "in.png", mode="RGBA"), tmp_path / "album.png")
        with Image.open(tmp_path / "album.png") as out:
            assert out.mode == "RGB"

    def test_a_jpeg_becomes_a_png(self, tmp_path):
        cover.write_cover(_image(tmp_path / "in.jpg", fmt="JPEG"), tmp_path / "album.png")
        with Image.open(tmp_path / "album.png") as out:
            assert out.format == "PNG"

    @pytest.mark.parametrize("size", [(1254, 900), (1536, 1024), (1024, 1536)])
    def test_an_image_that_is_not_square_is_refused(self, tmp_path, size):
        with pytest.raises(ValueError, match="not square"):
            cover.write_cover(_image(tmp_path / "in.png", size), tmp_path / "album.png")
        assert not (tmp_path / "album.png").exists()

    def test_a_pixel_of_rounding_is_still_square(self, tmp_path):
        result = cover.write_cover(_image(tmp_path / "in.png", (1254, 1255)), tmp_path / "album.png")
        assert result["size"] == [3000, 3000]

    def test_the_destination_folder_is_made(self, tmp_path):
        cover.write_cover(_image(tmp_path / "in.png"), tmp_path / "a" / "b" / "album.png")
        assert (tmp_path / "a" / "b" / "album.png").is_file()

    def test_a_failed_write_leaves_no_half_file(self, tmp_path):
        bad = tmp_path / "bad.png"
        bad.write_bytes(b"not an image")
        with pytest.raises(ValueError):
            cover.write_cover(bad, tmp_path / "album.png")
        assert list(tmp_path.glob("album*")) == []


class TestWritePng:
    def test_a_png_is_copied_as_it_is(self, tmp_path):
        source = _image(tmp_path / "in.png")
        cover.write_png(source, tmp_path / "album-art.png")
        assert (tmp_path / "album-art.png").read_bytes() == source.read_bytes()

    def test_another_format_is_converted_at_its_own_size(self, tmp_path):
        cover.write_png(_image(tmp_path / "in.jpg", (800, 800), fmt="JPEG"), tmp_path / "album-art.png")
        with Image.open(tmp_path / "album-art.png") as out:
            assert (out.format, out.size) == ("PNG", (800, 800))


class TestTheServerCanStartWithoutPillow:
    """The MCP server imports the artwork code when it starts.

    Pillow is only needed once an image is actually read. If it were imported
    up front, a venv with a broken Pillow would stop every other tool from
    loading, not just these.
    """

    @pytest.mark.parametrize("module", ["tools.artwork.cover", "tools.artwork.codex"])
    def test_importing_the_module_does_not_load_pillow(self, module):
        import subprocess

        code = (
            "import sys; sys.path.insert(0, %r); import %s; "
            "sys.exit(1 if 'PIL' in sys.modules else 0)" % (str(PROJECT_ROOT), module)
        )
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
        assert result.returncode == 0, f"{module} imported Pillow at import time\n{result.stderr}"
