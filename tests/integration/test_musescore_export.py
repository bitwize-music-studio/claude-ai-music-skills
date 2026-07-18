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

Binary resolution: ``MUSESCORE_BIN`` (set by the CI job to the apt-installed
``/usr/bin/mscore3``) takes precedence, falling back to the product's
``find_musescore()``. See the Task-E report: ``find_musescore()`` does NOT yet
detect apt ``musescore3`` (it installs ``/usr/bin/mscore3`` +
``/usr/bin/musescore3``, neither in the product's lookup table) — the
``test_find_musescore_detects_installed_binary`` test documents that gap.
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
    """Resolve the MuseScore binary: MUSESCORE_BIN first, then find_musescore()."""
    binary = os.getenv("MUSESCORE_BIN") or prepare_singles.find_musescore()
    if not binary or not Path(binary).exists():
        pytest.skip(
            "MuseScore binary not found "
            f"(MUSESCORE_BIN={os.getenv('MUSESCORE_BIN')!r}, "
            f"find_musescore()={prepare_singles.find_musescore()!r})"
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


@pytest.mark.xfail(
    reason="find_musescore() does not yet detect apt musescore3 "
    "(/usr/bin/mscore3, /usr/bin/musescore3) — pending approved product fix "
    "(Task-E finding). Remove this marker when the fix lands.",
    strict=False,
)
def test_find_musescore_detects_installed_binary(prepare_singles):
    """Proves the product can auto-discover the installed MuseScore.

    XFAIL until ``find_musescore()`` learns the ``mscore3`` / ``musescore3``
    names; when the approved product fix lands this passes and the marker should
    be removed so it becomes a hard assertion pinning the fix.
    """
    found = prepare_singles.find_musescore()
    assert found is not None, "find_musescore() did not detect the installed MuseScore"
    assert Path(found).exists()
