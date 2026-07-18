"""Real-MuseScore integration test for the sheet-music PDF re-export path.

Exercises the FULL product path against a REAL MuseScore CLI install:

    tests/integration/fixtures/minimal.musicxml
      -> prepare_singles.export_pdf   (subprocess: mscore -o out.pdf in.xml)
      -> a genuine PDF on disk

Verifies the output is a real PDF (non-empty, ``%PDF`` magic bytes), so a
regression in the CLI invocation, the argument order, the timeout handling, or
the return-code check would fail here — none of which the mock-only unit tests
can catch. This is the first time the export path runs against a real binary.

Gated behind the ``integration`` marker AND ``BITWIZE_INTEGRATION`` so the
normal suite / 3-OS matrix collect-and-skip (no MuseScore present). Nothing at
import time loads the product module or shells out — the ``prepare_singles``
module is loaded inside a fixture, which only runs for a non-skipped test.

MuseScore is a Qt GUI app; the CI job runs its CLI headless via
``QT_QPA_PLATFORM=offscreen`` (set in the workflow env, not the product).

Binary resolution: the product's ``find_musescore()`` is preferred (so the
export test also covers real detection), with ``MUSESCORE_BIN`` as a robustness
fallback. ``find_musescore()`` detects the apt-installed
``/usr/bin/mscore3`` directly; ``test_find_musescore_detects_installed_binary``
pins that.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.getenv("BITWIZE_INTEGRATION"),
        reason="integration services not available (set BITWIZE_INTEGRATION=1)",
    ),
]

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_XML = Path(__file__).parent / "fixtures" / "minimal.musicxml"


@pytest.fixture
def prepare_singles():
    """Load ``tools/sheet-music/prepare_singles.py`` (hyphenated dir → importlib).

    Deferred to a fixture so plain collection (dev box / 3-OS matrix, where the
    module's tools.shared imports would still resolve but the test is skipped)
    never executes this at import time.
    """
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    path = REPO_ROOT / "tools" / "sheet-music" / "prepare_singles.py"
    spec = importlib.util.spec_from_file_location("prepare_singles_integration", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def musescore_bin(prepare_singles):
    """Resolve the MuseScore binary: find_musescore() first, MUSESCORE_BIN fallback.

    Preferring the product's own discovery means the export test also exercises
    the real detection path; MUSESCORE_BIN stays as a robustness fallback (e.g.
    a dev with a non-standard install location).
    """
    binary = prepare_singles.find_musescore() or os.getenv("MUSESCORE_BIN")
    if not binary or not Path(binary).exists():
        pytest.skip(
            "MuseScore binary not found "
            f"(find_musescore()={prepare_singles.find_musescore()!r}, "
            f"MUSESCORE_BIN={os.getenv('MUSESCORE_BIN')!r})"
        )
    return binary


def test_export_pdf_produces_real_pdf(prepare_singles, musescore_bin, tmp_path):
    """The real product export_pdf must turn the MusicXML fixture into a PDF."""
    assert FIXTURE_XML.is_file(), f"missing fixture: {FIXTURE_XML}"
    pdf = tmp_path / "minimal.pdf"

    ok = prepare_singles.export_pdf(FIXTURE_XML, pdf, musescore_bin)

    assert ok is True, "export_pdf returned False against real MuseScore"
    assert pdf.exists(), "export_pdf reported success but wrote no PDF"
    data = pdf.read_bytes()
    assert len(data) > 0, "exported PDF is empty"
    assert data[:5] == b"%PDF-", f"output is not a real PDF (magic={data[:5]!r})"


def test_export_pdf_dry_run_writes_nothing(prepare_singles, tmp_path):
    """dry_run short-circuits before invoking MuseScore — no subprocess, no file.

    Passing a bogus binary path proves dry_run never shells out (a real call
    would fail on the nonexistent binary).
    """
    pdf = tmp_path / "dry.pdf"
    ok = prepare_singles.export_pdf(
        FIXTURE_XML, pdf, "/nonexistent/mscore-does-not-exist", dry_run=True
    )
    assert ok is True
    assert not pdf.exists()


def test_find_musescore_detects_installed_binary(prepare_singles):
    """Proves the product auto-discovers the installed MuseScore on its own.

    This pins the Linux detection fix: apt `musescore3` installs
    ``/usr/bin/mscore3`` (+ a ``musescore3`` symlink), which ``find_musescore()``
    now recognises without any ``MUSESCORE_BIN`` hint.
    """
    found = prepare_singles.find_musescore()
    assert found is not None, "find_musescore() did not detect the installed MuseScore"
    assert Path(found).exists()
