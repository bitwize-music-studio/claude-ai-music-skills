#!/usr/bin/env python3
"""Songbook track numbers come from the album, not the PDFs found (#668).

create_songbook numbered tracks by their place among the PDFs it found. With
no PDF for track 2 (its transcription failed), "03 - Last Call" appeared as
"2." in the contents and on its section header page.

Usage:
    python -m pytest tests/unit/sheet_music/test_songbook_numbering_668.py -v
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("pypdf")
pytest.importorskip("reportlab")

from pypdf import PdfReader  # noqa: E402
from reportlab.lib.pagesizes import letter  # noqa: E402
from reportlab.pdfgen import canvas  # noqa: E402

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


def _load():
    path = _PROJECT_ROOT / "tools" / "sheet-music" / "create_songbook.py"
    spec = importlib.util.spec_from_file_location("create_songbook_668", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


songbook = _load()

TRACKS = [(1, "First Pour"), (2, "Running Dry"), (3, "Last Call")]


def _score(path: Path, title: str) -> None:
    c = canvas.Canvas(str(path), pagesize=letter)
    c.drawString(72, 720, f"SCORE::{title}")
    c.showPage()
    c.save()


def _album(src: Path, *, missing: int | None, manifest: bool) -> None:
    src.mkdir()
    for number, title in TRACKS:
        if number != missing:
            _score(src / f"{number:02d} - {title}.pdf", title)
    if manifest:
        (src / ".manifest.json").write_text(json.dumps({"tracks": [
            {"number": n, "title": t, "filename": f"{n:02d} - {t}", "title_page": False}
            for n, t in TRACKS
        ]}), encoding="utf-8")


def _build(tmp_path: Path, *, missing: int | None, manifest: bool) -> list[str]:
    src = tmp_path / "singles"
    _album(src, missing=missing, manifest=manifest)
    out = tmp_path / "songbook.pdf"
    assert songbook.create_songbook(src, out, "Book", "Artist",
                                    include_section_headers=True) is True
    return [(p.extract_text() or "") for p in PdfReader(str(out)).pages]


def _header_numbers(texts: list[str]) -> dict[str, str]:
    """{title: number} from the section header pages (a number above a title)."""
    headers = {}
    for text in texts:
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if len(lines) == 2 and lines[0].isdigit():
            headers[lines[1]] = lines[0]
    return headers


@pytest.mark.unit
@pytest.mark.parametrize("manifest", [True, False], ids=["manifest", "no-manifest"])
class TestSongbookNumbering:
    def test_a_missing_pdf_does_not_renumber_later_tracks(self, tmp_path, manifest):
        texts = _build(tmp_path, missing=2, manifest=manifest)

        toc = texts[2]
        assert "3." in toc and "2." not in toc
        assert _header_numbers(texts) == {"First Pour": "1", "Last Call": "3"}

    def test_a_complete_album_is_numbered_as_before(self, tmp_path, manifest):
        texts = _build(tmp_path, missing=None, manifest=manifest)

        toc = texts[2]
        assert all(f"{n}." in toc for n in (1, 2, 3))
        assert _header_numbers(texts) == {
            "First Pour": "1", "Running Dry": "2", "Last Call": "3",
        }
