#!/usr/bin/env python3
"""The footer URL reaches every page, with the real pypdf and reportlab.

pypdf 7 refuses to merge onto a page that still belongs to its reader:
``PageObject.replace_contents()`` raises ``DeprecationError`` where pypdf 6
only warned. prepare_singles merged the footer onto each page of a single
before adding the page to the writer, so under pypdf 7 every single with a
footer URL lost its title page and its footer, and ``_add_title_page_and_footer``
caught the error and reported ``False``. ``add_footer_to_pdf`` merged the same
way. The other sheet-music tests mock pypdf or pass no footer URL, so none of
them reached that merge.

Usage:
    python -m pytest tests/unit/sheet_music/test_footer_overlay.py -v
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

pytest.importorskip("pypdf")
pytest.importorskip("reportlab")

from pypdf import PdfReader
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

FOOTER = "footer.example.org"


def _load(module_name: str, rel_path: str):
    """Load a hyphenated tools module with REAL deps (no mocking)."""
    spec = importlib.util.spec_from_file_location(module_name, _PROJECT_ROOT / rel_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


songbook = _load("create_songbook_footer", "tools/sheet-music/create_songbook.py")
prepare = _load("prepare_singles_footer", "tools/sheet-music/prepare_singles.py")


def _write_pdf(path: Path, page_labels: list[str]) -> None:
    """Write a PDF with one page per label, each stamped with that label."""
    c = canvas.Canvas(str(path), pagesize=letter)
    for label in page_labels:
        c.drawString(72, 720, label)
        c.showPage()
    c.save()


def _page_texts(path: Path) -> list[str]:
    return [(p.extract_text() or "") for p in PdfReader(str(path)).pages]


@pytest.mark.unit
class TestSingleFooter:
    def test_single_gets_title_page_and_footer_on_every_page(self, tmp_path):
        pdf = tmp_path / "track.pdf"
        _write_pdf(pdf, ["MUSIC::p1", "MUSIC::p2"])

        added = prepare._add_title_page_and_footer(
            pdf, "My Track", "Artist", None, FOOTER, "letter"
        )

        assert added is True
        texts = _page_texts(pdf)
        assert len(texts) == 3  # title page + both music pages
        assert "MUSIC::p1" in texts[1]
        assert "MUSIC::p2" in texts[2]
        assert all(FOOTER in t for t in texts), texts


@pytest.mark.unit
class TestAddFooterToPdf:
    def test_every_page_keeps_its_content_and_gains_the_footer(self, tmp_path):
        src = tmp_path / "in.pdf"
        out = tmp_path / "out.pdf"
        _write_pdf(src, ["PAGE::1", "PAGE::2"])

        songbook.add_footer_to_pdf(src, out, FOOTER)

        texts = _page_texts(out)
        assert len(texts) == 2
        assert "PAGE::1" in texts[0]
        assert "PAGE::2" in texts[1]
        assert all(FOOTER in t for t in texts), texts

    def test_rewrites_the_file_in_place(self, tmp_path):
        """input_path and output_path may be the same file (per its docstring)."""
        pdf = tmp_path / "book.pdf"
        _write_pdf(pdf, ["PAGE::1"])

        songbook.add_footer_to_pdf(pdf, pdf, FOOTER)

        texts = _page_texts(pdf)
        assert len(texts) == 1
        assert "PAGE::1" in texts[0]
        assert FOOTER in texts[0]


@pytest.mark.unit
class TestSongbookFooter:
    def test_footer_on_front_matter_and_music_pages(self, tmp_path):
        """The songbook merges onto pages the writer already holds."""
        src = tmp_path / "singles"
        src.mkdir()
        _write_pdf(src / "01 - Only Track.pdf", ["MUSIC::only"])

        out = tmp_path / "songbook.pdf"
        ok = songbook.create_songbook(src, out, "Book", "Artist", footer_url=FOOTER)

        assert ok is True
        texts = _page_texts(out)
        assert len(texts) == 4  # title, copyright, contents + the music page
        assert any("MUSIC::only" in t for t in texts)
        assert all(FOOTER in t for t in texts), texts
