#!/usr/bin/env python3
"""
Unit tests for font discovery utility.

Usage:
    python -m pytest tools/shared/tests/test_fonts.py -v
"""

import sys
from pathlib import Path
from unittest import mock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.shared import fonts as fonts_module
from tools.shared.fonts import find_font

# The POSIX candidate list exactly as it shipped, in order. Adding Windows
# support must not perturb macOS/Linux discovery by a single byte.
_EXPECTED_POSIX_ORDER = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/Library/Fonts/Arial Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
]


class TestFindFont:
    """Tests for find_font()."""

    def test_returns_string_or_none(self):
        """find_font returns a string path or None."""
        result = find_font()
        assert result is None or isinstance(result, str)

    def test_returned_font_exists(self):
        """A discovered font must be a path that actually exists.

        Guarded unconditionally on purpose: `if result is not None` disarmed
        this check on exactly the machines where font discovery is most likely
        broken (a CI runner with no system fonts), so a total discovery failure
        read as green. Hosts with genuinely no fonts opt out via the explicit
        skip below rather than by silently asserting nothing.
        """
        result = find_font()
        if result is None:
            pytest.skip(
                "No system font found on this host — find_font() legitimately "
                "returns None on a bare runner; nothing to validate"
            )
        assert isinstance(result, str), f"find_font() returned {type(result).__name__}"
        assert Path(result).exists(), (
            f"find_font() returned a path that does not exist: {result}"
        )

    def test_returns_none_when_no_fonts(self):
        """Returns None when no system fonts exist."""
        with mock.patch('tools.shared.fonts.Path') as MockPath:
            # Make all Path().exists() return False
            MockPath.return_value.exists.return_value = False
            result = find_font()
            assert result is None

    def test_returns_first_available_font(self):
        """Returns the first font that exists from the search list."""
        def mock_exists(self):
            # Only the third font path exists
            path_str = str(self)
            if 'Helvetica' in path_str:
                return True
            return False

        with mock.patch.object(Path, 'exists', mock_exists):
            result = find_font()
        # The mock guarantees a Helvetica path exists, so `None` here means
        # discovery is broken — it must not be waved through by an `if`.
        assert result is not None, (
            "find_font() returned None even though a candidate path exists"
        )
        assert 'Helvetica' in result, (
            f"find_font() should return the first existing candidate, got: {result}"
        )


class TestPosixCandidatesUnchanged:
    """macOS/Linux discovery must be byte-identical to the pre-Windows version."""

    @pytest.mark.parametrize("system", ["Linux", "Darwin", "FreeBSD"])
    def test_posix_candidate_order_is_untouched(self, monkeypatch, system):
        monkeypatch.setattr(fonts_module.platform, "system", lambda: system)
        assert fonts_module._candidate_fonts() == _EXPECTED_POSIX_ORDER

    @pytest.mark.parametrize("system", ["Linux", "Darwin"])
    def test_no_windows_paths_leak_onto_posix(self, monkeypatch, system):
        monkeypatch.setattr(fonts_module.platform, "system", lambda: system)
        assert not [c for c in fonts_module._candidate_fonts() if "\\" in c]

    def test_windows_candidates_are_appended_after_the_posix_ones(self, monkeypatch):
        """Order matters: the POSIX list keeps its exact leading position."""
        monkeypatch.setattr(fonts_module.platform, "system", lambda: "Windows")
        candidates = fonts_module._candidate_fonts()
        assert candidates[: len(_EXPECTED_POSIX_ORDER)] == _EXPECTED_POSIX_ORDER
        assert len(candidates) > len(_EXPECTED_POSIX_ORDER)


class TestWindowsFontDiscovery:
    """Without Windows candidates, find_font() returns None on every Windows
    host, so ffmpeg ``drawtext`` in promo-video generation has no font at all.
    """

    def _fake_windows_fonts(self, monkeypatch, tmp_path, *filenames):
        """Stand up a fake ``%SystemRoot%\\Fonts`` containing ``filenames``.

        The POSIX candidates are redirected under ``tmp_path`` so they resolve
        to nothing — modelling a real Windows host, where ``/usr/share/fonts``
        and ``/System/Library`` cannot exist. Without this the Linux test
        runner's own DejaVu would satisfy discovery and the Windows branch
        would never be reached.
        """
        monkeypatch.setattr(fonts_module.platform, "system", lambda: "Windows")
        monkeypatch.setattr(
            fonts_module,
            "_POSIX_FONT_PATHS",
            [str(tmp_path / "absent" / p.lstrip("/")) for p in _EXPECTED_POSIX_ORDER],
        )
        monkeypatch.setenv("SYSTEMROOT", str(tmp_path / "Windows"))
        fonts_dir = tmp_path / "Windows" / "Fonts"
        fonts_dir.mkdir(parents=True)
        for name in filenames:
            (fonts_dir / name).write_bytes(b"\x00")
        return fonts_dir

    def test_windows_host_resolves_a_font(self, monkeypatch, tmp_path):
        self._fake_windows_fonts(monkeypatch, tmp_path, "arialbd.ttf")
        result = find_font()
        assert result is not None, (
            "find_font() returned None on a Windows host that has Arial Bold — "
            "promo-video drawtext has no font to render with"
        )
        assert result.endswith("arialbd.ttf"), result
        assert Path(result).exists()

    @pytest.mark.parametrize(
        "filename",
        ["arialbd.ttf", "segoeuib.ttf", "calibrib.ttf", "tahomabd.ttf", "arial.ttf"],
    )
    def test_each_windows_font_is_discoverable_on_its_own(
        self, monkeypatch, tmp_path, filename
    ):
        """Every candidate must resolve even if it is the only one installed."""
        self._fake_windows_fonts(monkeypatch, tmp_path, filename)
        result = find_font()
        assert result is not None, f"{filename} present but find_font() found nothing"
        assert result.endswith(filename), result

    def test_bold_is_preferred_over_regular(self, monkeypatch, tmp_path):
        """The POSIX list is bold-first; the Windows list must match that intent."""
        self._fake_windows_fonts(monkeypatch, tmp_path, "arial.ttf", "arialbd.ttf")
        result = find_font()
        assert result is not None and result.endswith("arialbd.ttf"), result

    def test_honours_a_non_default_system_root(self, monkeypatch, tmp_path):
        """Windows is not always on C:. Candidates follow %SystemRoot%."""
        fonts_dir = self._fake_windows_fonts(monkeypatch, tmp_path, "arialbd.ttf")
        result = find_font()
        assert result is not None
        assert Path(result).parent == fonts_dir

    def test_falls_back_to_c_windows_when_systemroot_is_unset(
        self, monkeypatch, tmp_path
    ):
        monkeypatch.setattr(fonts_module.platform, "system", lambda: "Windows")
        monkeypatch.delenv("SYSTEMROOT", raising=False)
        monkeypatch.delenv("WINDIR", raising=False)
        candidates = fonts_module._candidate_fonts()
        windows_candidates = [c for c in candidates if c not in _EXPECTED_POSIX_ORDER]
        assert windows_candidates, "no Windows candidates generated"
        # Separator flavour follows os.path.join on the *running* host, so the
        # assertion is on the resolved root, not on literal backslashes.
        assert all(
            c.startswith("C:") and "Windows" in c and "Fonts" in c
            for c in windows_candidates
        ), windows_candidates

    def test_windows_host_with_no_fonts_returns_none(self, monkeypatch, tmp_path):
        self._fake_windows_fonts(monkeypatch, tmp_path)
        assert find_font() is None
