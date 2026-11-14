"""The release kit page and JSON."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.unit.release.test_kit import TODAY, _facts, _track
from tools.release.kit import build_kit
from tools.release.kit_page import render_html, render_json

pytestmark = pytest.mark.unit

FAIL_MARK = "&#x2717;"
OK_MARK = "&#x2713;"


def _page(**changes) -> str:
    return render_html(build_kit(_facts(**changes), TODAY))


def test_it_is_a_whole_page_with_both_tabs():
    page = _page()
    assert page.startswith("<!doctype html>")
    assert "<title>Release kit: Paper Boats</title>" in page
    assert 'id="panel-distrokid"' in page
    assert 'id="panel-soundcloud"' in page


def test_every_value_has_one_copy_button():
    kit = build_kit(_facts(), TODAY)
    values = sum(len(b.fields) for b in (*kit.distrokid, *kit.soundcloud))
    assert render_html(kit).count('class="copy"') == values


def test_values_are_escaped():
    page = _page(tracks=(_track(1, title="<script>alert(1)</script>"),))
    assert "<script>alert(1)" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page


def test_nothing_is_loaded_from_outside():
    page = _page(description="See https://example.org for more")
    assert not re.search(r"""(?:src|href)\s*=\s*["']?https?:""", page)


def test_long_values_fold():
    assert '<details><summary>Show</summary><pre class="value"' in _page()


def test_the_checks_come_first():
    page = _page(legal_name="")
    assert page.index('class="checks"') < page.index('id="panel-distrokid"')
    assert f'<li class="fail"><span class="mark">{FAIL_MARK}</span>' in page


def test_a_clean_album_says_so():
    page = render_html(build_kit(_facts(tracks=(_track(1, wav_format=""),)), TODAY))
    assert f"{OK_MARK} Nothing to fix" in page


def test_the_json_round_trips_with_its_version():
    kit = build_kit(_facts(), TODAY)
    data = json.loads(render_json(kit))
    assert data["version"] == 1
    assert data["album_title"] == "Paper Boats"
    assert data["distrokid"][0]["fields"][0] == {"label": "Artist", "value": "bitwize", "long": False}
    assert data["checks"] == [{"level": "info", "message": "Masters: PCM_24 96000 Hz"}]
