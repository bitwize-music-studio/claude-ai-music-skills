"""Post-QC must pass the album genre through to qc_track.

Reporter case (if-anyone-makes-it-everyone-dances, electronic, 10
tracks): post_qc failed 10/10 on the "clicks" check because the stage
called `qc_track(path, None)` without `genre`, falling back to the
generic peak_ratio=6.0 / fail_count=3 threshold. Every legitimate
kick/snare transient registered as a click.

The electronic preset in `genre-presets.yaml` specifies
`click_peak_ratio: 10.0, click_fail_count: 30` precisely to let dense
transient content pass — but the threshold only applies if the genre
reaches the detector.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from handlers.processing import _album_stages as album_stages_mod  # noqa: E402


def _make_ctx(genre: str, wav: Path) -> "album_stages_mod.MasterAlbumCtx":
    ctx = album_stages_mod.MasterAlbumCtx(
        album_slug="genre-test", genre=genre, target_lufs=-14.0,
        ceiling_db=-1.0, cut_highmid=0.0, cut_highs=0.0,
        source_subfolder="", freeze_signature=False, new_anchor=False,
        loop=asyncio.get_event_loop(),
    )
    ctx.mastered_files = [wav]
    ctx.preset_dict = None
    ctx.verify_results = [{
        "filename": wav.name, "lufs": -14.0, "peak_db": -1.5,
        "short_term_range": 9.0,
    }]
    return ctx


@pytest.mark.parametrize("album_genre", ["electronic", "idm", "metal", ""])
def test_post_qc_passes_genre_to_qc_track(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, album_genre: str,
) -> None:
    """Pin the contract: _stage_post_qc forwards ctx.genre to qc_track.

    Without this the click detector falls back to generic thresholds
    (peak_ratio=6.0, fail_count=3) and rejects legitimate dense-
    transient masters — the root cause of the 10/10 fail on the
    reporter's electronic album.
    """
    wav = tmp_path / "01-track.wav"
    wav.touch()

    captured_calls: list[dict] = []

    def _spy_qc_track(path, checks=None, genre=None):
        captured_calls.append({"path": path, "checks": checks, "genre": genre})
        return {"filename": Path(path).name, "verdict": "PASS", "checks": {}}

    monkeypatch.setattr("tools.mastering.qc_tracks.qc_track", _spy_qc_track)

    async def _run():
        ctx = _make_ctx(album_genre, wav)
        await album_stages_mod._stage_post_qc(ctx)
        return ctx

    asyncio.run(_run())

    assert len(captured_calls) == 1, (
        f"Expected exactly 1 qc_track call, got {len(captured_calls)}"
    )
    call = captured_calls[0]
    expected_genre = album_genre or None
    assert call["genre"] == expected_genre, (
        f"post_qc must forward ctx.genre={album_genre!r} → qc_track(genre=...), "
        f"got genre={call['genre']!r}. This causes the click detector to "
        f"fall back to generic thresholds and reject legitimate masters."
    )
