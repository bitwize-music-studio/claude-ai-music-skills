"""build_release_kit: gathers a real album's facts and writes the page and JSON."""

from __future__ import annotations

import asyncio
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
for _path in (PROJECT_ROOT, SERVER_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from handlers import _shared as shared_mod
from handlers import release_kit as kit_mod
from tools.release.kit import LEAVE_BLANK

pytestmark = pytest.mark.unit

README = """---
title: "Paper Boats"
release_date: "2999-02-01"
tags: ["folk", "sea shanty"]
explicit: false
---
# Paper Boats

## Album Details

| Attribute | Detail |
|-----------|--------|
| **Genre** | [Folk](/genres/folk/README.md) / Indie Folk |
| **Status** | Complete |

## Concept

Songs about small boats.
"""

VOCAL = """# Harbor

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Title** | Harbor |
| **Status** | Final |
| **Explicit** | No |

## Streaming Lyrics

```
Paper boats on the water
Sailing out past the harbor
Folded from a letter that I never sent
Carried by the evening tide to where the river went
```
"""

INSTRUMENTAL = """---
instrumental: true
---
# Tide

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Title** | Tide |
| **Status** | Final |
"""


class _FakeCache:
    def __init__(self, state):
        self.state = state

    def get_state(self):
        return self.state

    def get_state_ref(self):
        return self.state


@pytest.fixture
def album(tmp_path, monkeypatch):
    content = tmp_path / "content" / "artists" / "bitwize" / "albums" / "folk" / "paper-boats"
    (content / "tracks").mkdir(parents=True)
    (content / "README.md").write_text(README, encoding="utf-8")
    (content / "tracks" / "01-harbor.md").write_text(VOCAL, encoding="utf-8")
    (content / "tracks" / "02-tide.md").write_text(INSTRUMENTAL, encoding="utf-8")

    audio = tmp_path / "audio" / "artists" / "bitwize" / "albums" / "folk" / "paper-boats"
    (audio / "mastered").mkdir(parents=True)
    for slug in ("01-harbor", "02-tide"):
        sf.write(str(audio / "mastered" / f"{slug}.wav"),
                 np.zeros((800, 2), dtype=np.float32), 8000, subtype="PCM_24")
    Image.new("RGB", (3000, 3000)).save(audio / "album.png")

    def refresh() -> dict:
        """Index the album as the server does: the state comes from the files, not by hand."""
        from tools.state.indexer import build_state

        state = build_state({
            "artist": {"name": "bitwize"},
            "paths": {"content_root": str(tmp_path / "content"),
                      "audio_root": str(tmp_path / "audio"),
                      "documents_root": str(tmp_path / "documents")},
        }, plugin_root=tmp_path)
        monkeypatch.setattr(shared_mod, "cache", _FakeCache(state))
        return state

    refresh()
    import tools.shared.config as config_mod
    monkeypatch.setattr(config_mod, "load_config", lambda *a, **k: {
        "artist": {"name": "bitwize", "legal_name": "Jane Q. Writer"},
        "release": {"ai_disclosure": ["Vocals", "Instrumental"]},
    })
    opened: list[str] = []
    monkeypatch.setattr(kit_mod.webbrowser, "open_new_tab", lambda url: opened.append(url) or True)
    return {"audio": audio, "content": content, "opened": opened, "refresh": refresh}


def _build(**kwargs) -> dict:
    return json.loads(asyncio.run(kit_mod.build_release_kit("paper-boats", **kwargs)))


def test_writes_the_page_and_json_beside_mastered(album):
    result = _build(open_page=False)

    audio = album["audio"]
    assert result["html"] == str(audio / "release-kit.html")
    assert result["json"] == str(audio / "release-kit.json")
    assert sorted(p.name for p in (audio / "mastered").iterdir()) == ["01-harbor.wav", "02-tide.wav"]
    page = (audio / "release-kit.html").read_text(encoding="utf-8")
    assert "Paper Boats" in page
    assert "Sailing out past the harbor" in page
    data = json.loads((audio / "release-kit.json").read_text(encoding="utf-8"))
    assert data["version"] == 1
    assert result["opened"] is None


def test_a_ready_album_has_nothing_to_fix(album):
    result = _build(open_page=False)
    assert result["checks"]["fail"] == 0, result["checks"]["items"]
    assert result["checks"]["warn"] == 0, result["checks"]["items"]


def test_facts_come_from_the_files_and_config(album):
    _build(open_page=False)
    data = json.loads((album["audio"] / "release-kit.json").read_text(encoding="utf-8"))
    album_fields = {f["label"]: f["value"] for f in data["distrokid"][0]["fields"]}
    assert album_fields["Primary genre"] == "Folk"
    assert album_fields["Secondary genre"] == "Indie Folk"
    assert album_fields["Release date"] == "2999-02-01"
    assert album_fields["AI disclosure"] == "Vocals, Instrumental"
    tide = {f["label"]: f["value"] for f in data["distrokid"][2]["fields"]}
    assert tide["Instrumental"] == "Yes"
    soundcloud = {f["label"]: f["value"] for f in data["soundcloud"][0]["fields"]}
    assert soundcloud["Tags"] == 'folk "sea shanty"'  # the genre "Folk" is already a tag
    assert soundcloud["Description"] == "Songs about small boats."


def test_an_older_album_jpg_cover_counts(album):
    png = album["audio"] / "album.png"
    Image.open(png).convert("RGB").save(album["audio"] / "album.jpg")
    png.unlink()
    result = _build(open_page=False)
    assert result["checks"]["fail"] == 0, result["checks"]["items"]
    data = json.loads((album["audio"] / "release-kit.json").read_text(encoding="utf-8"))
    cover = {f["label"]: f["value"] for f in data["distrokid"][0]["fields"]}["Cover art"]
    assert cover == str(album["audio"] / "album.jpg")


def test_a_stray_wav_fails(album):
    sf.write(str(album["audio"] / "mastered" / "99-demo.wav"),
             np.zeros((800, 2), dtype=np.float32), 8000)
    items = _build(open_page=False)["checks"]["items"]
    assert {"level": "fail",
            "message": "mastered/99-demo.wav matches no track: move it out before uploading"} in items


def test_opens_in_the_browser_where_panes_dont_work(album):
    result = _build()
    assert result["opened"] == "browser"
    assert album["opened"] == [(album["audio"] / "release-kit.html").as_uri()]


def test_opens_in_an_iterm2_pane_where_they_do(album, monkeypatch):
    shown: list[Path] = []
    monkeypatch.setattr(kit_mod._iterm, "unavailable_reason", lambda: None)
    monkeypatch.setattr(kit_mod._iterm, "open_page_in_pane", lambda path: shown.append(path) or {})
    result = _build()
    assert result["opened"] == "iterm2"
    assert shown == [album["audio"] / "release-kit.html"]
    assert album["opened"] == []


def test_an_unknown_album_is_an_error(album):
    result = json.loads(asyncio.run(kit_mod.build_release_kit("no-such-album", open_page=False)))
    assert "error" in result


def test_an_album_without_an_audio_folder_is_an_error(album):
    shutil.rmtree(album["audio"])
    assert "error" in _build(open_page=False)


def _add_frontmatter(path: Path, lines: str) -> None:
    text = path.read_text(encoding="utf-8")
    text = "---\n" + lines + text[4:] if text.startswith("---\n") else f"---\n{lines}---\n{text}"
    path.write_text(text, encoding="utf-8")


def _distrokid(audio: Path, block: int) -> dict:
    data = json.loads((audio / "release-kit.json").read_text(encoding="utf-8"))
    return {f["label"]: f["value"] for f in data["distrokid"][block]["fields"]}


def test_the_codes_are_the_ones_the_masters_get(album):
    """ISRC and UPC go through the parser's rule, as the cached codes master_album embeds do."""
    _add_frontmatter(album["content"] / "README.md", 'upc: "1234-5678-9012"\n')
    _add_frontmatter(album["content"] / "tracks" / "01-harbor.md", 'isrc: "us-abc-23-00001"\n')
    state = album["refresh"]()
    cached = state["albums"]["paper-boats"]
    assert (cached["upc"], cached["tracks"]["01-harbor"]["isrc"]) == ("123456789012", "USABC2300001")

    result = _build(open_page=False)
    assert _distrokid(album["audio"], 0)["UPC"] == "123456789012"
    assert _distrokid(album["audio"], 1)["ISRC"] == "USABC2300001"
    assert result["checks"]["warn"] == 0, result["checks"]["items"]


def test_a_code_that_isnt_one_is_left_blank_and_flagged(album):
    _add_frontmatter(album["content"] / "README.md", 'upc: "TBD"\n')
    _add_frontmatter(album["content"] / "tracks" / "01-harbor.md", 'isrc: "pending"\n')
    album["refresh"]()

    result = _build(open_page=False)
    assert _distrokid(album["audio"], 0)["UPC"] == LEAVE_BLANK
    assert _distrokid(album["audio"], 1)["ISRC"] == LEAVE_BLANK
    warnings = [c["message"] for c in result["checks"]["items"] if c["level"] == "warn"]
    assert [w.split(" isn't")[0] for w in warnings] == ["UPC 'TBD' in the album README",
                                                       "Track 1 (Harbor) ISRC 'pending'"]
