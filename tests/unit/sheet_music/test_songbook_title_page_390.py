#!/usr/bin/env python3
"""Regression tests for songbook title-page handling (issue #390).

create_songbook used to infer ``singles_have_title_pages = manifest is not
None`` and unconditionally skip page 0 of every single. But prepare_singles
writes ``.manifest.json`` unconditionally while silently skipping the title
page when pypdf/reportlab are unavailable (or the title-page step raises). In
that case the singles have NO title page yet the manifest exists, so the
songbook dropped the real first music page of every track (the entire track
for a 1-page transcription) and miscounted the TOC.

The fix records the actual per-track title-page fact in the manifest
(``"title_page": true|false``) and makes the songbook trust that flag.

These tests use real pypdf/reportlab so the actual page slicing is exercised.

Usage:
    python -m pytest tests/unit/sheet_music/test_songbook_title_page_390.py -v
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

pytest.importorskip("pypdf")
pytest.importorskip("reportlab")

from pypdf import PdfReader, PdfWriter  # noqa: E402
from reportlab.lib.pagesizes import letter  # noqa: E402
from reportlab.pdfgen import canvas  # noqa: E402

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


def _load(module_name: str, rel_path: str):
    """Load a hyphenated tools module with REAL deps (no mocking)."""
    path = _PROJECT_ROOT / rel_path
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


songbook = _load("create_songbook_real", "tools/sheet-music/create_songbook.py")
prepare = _load("prepare_singles_real", "tools/sheet-music/prepare_singles.py")


# ---------------------------------------------------------------------------
# Helpers: build real PDFs with identifiable per-page text
# ---------------------------------------------------------------------------


def _write_pdf(path: Path, page_labels: list[str]) -> None:
    """Write a PDF with one page per label, each stamped with that label."""
    c = canvas.Canvas(str(path), pagesize=letter)
    for label in page_labels:
        c.drawString(72, 720, label)
        c.showPage()
    c.save()


def _page_texts(path: Path) -> list[str]:
    return [(p.extract_text() or "") for p in PdfReader(str(path)).pages]


def _make_single(source_dir: Path, filename: str, music_pages: int,
                 *, title_page: bool) -> str:
    """Create a single PDF and return the unique marker on its first music page.

    The marker is stamped on the first *music* page so a test can assert the
    songbook did not drop it. When ``title_page`` is True, a title page is
    prepended (as prepare_singles would), so the music pages start at index 1.
    """
    marker = f"MUSIC::{filename}::p1"
    labels: list[str] = []
    if title_page:
        labels.append(f"TITLEPAGE::{filename}")
    labels.append(marker)
    labels.extend(f"MUSIC::{filename}::p{n}" for n in range(2, music_pages + 1))
    _write_pdf(source_dir / f"{filename}.pdf", labels)
    return marker


def _write_manifest(source_dir: Path, entries: list[dict]) -> None:
    (source_dir / ".manifest.json").write_text(
        json.dumps({"tracks": entries}, indent=2), encoding="utf-8"
    )


# ===========================================================================
# Consumer: create_songbook must not drop music pages (#390 core)
# ===========================================================================


@pytest.mark.unit
class TestSongbookHonorsTitlePageFlag:
    def test_single_without_title_page_keeps_its_only_music_page(self, tmp_path):
        """A 1-page single with title_page=false must survive intact (#390).

        This is the reported worst case: without the flag the songbook skipped
        page 0 and dropped the entire track.
        """
        src = tmp_path / "singles"
        src.mkdir()
        marker = _make_single(src, "01 - Lonely Track", music_pages=1,
                              title_page=False)
        _write_manifest(src, [{
            "number": 1, "title": "Lonely Track",
            "filename": "01 - Lonely Track", "title_page": False,
        }])

        out = tmp_path / "songbook.pdf"
        ok = songbook.create_songbook(src, out, "Book", "Artist")

        assert ok is True
        texts = _page_texts(out)
        # Front matter (title, copyright, TOC) + the one music page = 4.
        assert len(texts) == 4
        assert any(marker in t for t in texts), "the only music page was dropped"

    def test_single_with_title_page_skips_only_the_title_page(self, tmp_path):
        """title_page=true → the prepended title page is skipped, music kept."""
        src = tmp_path / "singles"
        src.mkdir()
        marker = _make_single(src, "01 - Real Title", music_pages=2,
                              title_page=True)
        _write_manifest(src, [{
            "number": 1, "title": "Real Title",
            "filename": "01 - Real Title", "title_page": True,
        }])

        out = tmp_path / "songbook.pdf"
        ok = songbook.create_songbook(src, out, "Book", "Artist")

        assert ok is True
        texts = _page_texts(out)
        # 3 front matter + 2 music pages (title page dropped) = 5.
        assert len(texts) == 5
        assert any(marker in t for t in texts)
        assert not any("TITLEPAGE" in t for t in texts), "title page leaked in"

    def test_mixed_flags_across_tracks(self, tmp_path):
        """Per-track flags are honored independently (one true, one false)."""
        src = tmp_path / "singles"
        src.mkdir()
        m_no = _make_single(src, "01 - No Title", music_pages=1, title_page=False)
        m_yes = _make_single(src, "02 - Has Title", music_pages=1, title_page=True)
        _write_manifest(src, [
            {"number": 1, "title": "No Title",
             "filename": "01 - No Title", "title_page": False},
            {"number": 2, "title": "Has Title",
             "filename": "02 - Has Title", "title_page": True},
        ])

        out = tmp_path / "songbook.pdf"
        ok = songbook.create_songbook(src, out, "Book", "Artist")

        assert ok is True
        texts = _page_texts(out)
        # 3 front matter + 1 (no-title single) + 1 (has-title single, minus its
        # title page) = 5.
        assert len(texts) == 5
        assert any(m_no in t for t in texts)
        assert any(m_yes in t for t in texts)
        assert not any("TITLEPAGE" in t for t in texts)

    def test_legacy_manifest_without_flag_unchanged(self, tmp_path):
        """A manifest lacking the flag keeps the prior assume-title-page path.

        Backward-compat: existing correct singles (title pages present, old
        manifests) must not regress.
        """
        src = tmp_path / "singles"
        src.mkdir()
        marker = _make_single(src, "01 - Legacy", music_pages=1, title_page=True)
        _write_manifest(src, [{
            "number": 1, "title": "Legacy", "filename": "01 - Legacy",
        }])  # no "title_page" key

        out = tmp_path / "songbook.pdf"
        ok = songbook.create_songbook(src, out, "Book", "Artist")

        assert ok is True
        texts = _page_texts(out)
        assert len(texts) == 4  # title page skipped as before
        assert any(marker in t for t in texts)


# ===========================================================================
# Producer: prepare_singles records the real title-page fact
# ===========================================================================


@pytest.mark.unit
class TestAddTitlePageReturnsFact:
    def test_returns_true_and_prepends_page_on_success(self, tmp_path):
        pdf = tmp_path / "track.pdf"
        _write_pdf(pdf, ["MUSIC::only-page"])
        assert PdfReader(str(pdf)).pages.__len__() == 1

        added = prepare._add_title_page_and_footer(
            pdf, "My Track", "Artist", None, None, "letter"
        )

        assert added is True
        # Title page prepended: now 2 pages, page 0 is the title page.
        pages = _page_texts(pdf)
        assert len(pages) == 2
        assert "MUSIC::only-page" in pages[1]

    def test_returns_false_when_title_page_cannot_be_added(self, tmp_path):
        """A read/parse failure hits the broad except → returns False.

        This is the silent-skip path that must be recorded as title_page=false
        so the songbook does not later skip a non-existent title page.
        """
        missing = tmp_path / "does-not-exist.pdf"

        added = prepare._add_title_page_and_footer(
            missing, "My Track", "Artist", None, None, "letter"
        )

        assert added is False


@pytest.mark.unit
class TestPrepareSinglesRecordsTitlePageFact:
    """prepare_singles must write the real title-page fact into the manifest."""

    def _make_source(self, tmp_path: Path) -> Path:
        source = tmp_path / "source"
        source.mkdir()
        (source / "First Pour.xml").write_text(
            "<score><work-title>First Pour</work-title></score>"
        )
        (source / "First Pour.pdf").write_text("pdf content")
        (source / ".manifest.json").write_text(json.dumps({
            "tracks": [
                {"number": 1, "source_slug": "01-first-pour", "title": "First Pour"}
            ]
        }))
        return source

    def test_manifest_records_title_page_true_when_added(self, tmp_path):
        source = self._make_source(tmp_path)
        with patch.object(prepare, "_add_title_page_and_footer", return_value=True):
            result = prepare.prepare_singles(source, tmp_path / "singles")
        entry = result["manifest"]["tracks"][0]
        assert entry["title_page"] is True

    def test_manifest_records_title_page_false_when_skipped(self, tmp_path):
        """The bug's trigger: deps missing → title page skipped → flag False."""
        source = self._make_source(tmp_path)
        with patch.object(prepare, "_add_title_page_and_footer", return_value=False):
            result = prepare.prepare_singles(source, tmp_path / "singles")
        entry = result["manifest"]["tracks"][0]
        assert entry["title_page"] is False

        # And the persisted manifest on disk carries the same fact.
        written = json.loads(
            (tmp_path / "singles" / ".manifest.json").read_text(encoding="utf-8")
        )
        assert written["tracks"][0]["title_page"] is False
