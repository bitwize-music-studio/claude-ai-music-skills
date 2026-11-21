"""Track numbers and file lists that drift apart in album mastering (#668).

#647 and #651 fixed one case: an anchor number counted over the sources used
as a position among the masters. The same shape showed up elsewhere. The
usual way in is ``rename_track``, which renames the track file but not its
audio, so ``polished/`` or ``mastered/`` keeps ``02-old-title.wav`` beside
the re-imported ``02-new-title.wav``. Each test here sets up that drift; the
aligned case must behave exactly as before.

Usage:
    python -m pytest tests/unit/mastering/test_master_album_index_drift.py -v
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import numpy as np
import pytest
import soundfile as sf

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
for _p in (str(PROJECT_ROOT), str(SERVER_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from handlers import _shared  # noqa: E402
from handlers.processing import _album_stages  # noqa: E402
from handlers.processing import _helpers as processing_helpers  # noqa: E402
from handlers.processing import audio as audio_mod  # noqa: E402
from handlers.processing._album_stages import MasterAlbumCtx  # noqa: E402
from tools.mastering.anchor_selector import select_anchor  # noqa: E402

pytestmark = pytest.mark.unit

# A renamed track's old file sorts before its new one and before the anchor.
DRIFTED = ["01-intro.wav", "02-storm-old-title.wav", "02-storm.wav",
           "03-anchor.wav", "04-loud.wav"]
ALIGNED = ["01-intro.wav", "02-storm.wav", "03-anchor.wav", "04-loud.wav"]


class _FakeCache:
    def __init__(self, state: dict[str, Any]) -> None:
        self._state = state

    def get_state(self) -> dict[str, Any]:
        return self._state

    def get_state_ref(self) -> dict[str, Any]:
        return self._state


@pytest.fixture(autouse=True)
def _empty_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """``_shared.cache`` starts as None (#670): give every test a state, so
    the file passes on its own. Tests that need album state replace it."""
    monkeypatch.setattr(_shared, "cache", _FakeCache({"albums": {}}))


def _analysis(filename: str, lufs: float = -14.0) -> dict[str, Any]:
    """An analyze_track-shaped result every anchor-selector check accepts."""
    return {
        "filename": filename,
        "lufs": lufs,
        "peak_db": -4.0,
        "stl_95": lufs + 2.0,
        "short_term_range": 8.0,
        "low_rms": lufs - 8.0,
        "vocal_rms": lufs - 3.0,
        "band_energy": {"sub_bass": 8.0, "bass": 18.0, "low_mid": 20.0,
                        "mid": 25.0, "high_mid": 14.0, "high": 10.0, "air": 5.0},
        "tinniness_ratio": 0.1,
    }


def _ctx(loop: asyncio.AbstractEventLoop, names: list[str]) -> MasterAlbumCtx:
    ctx = MasterAlbumCtx(
        album_slug="drift", genre="", target_lufs=-14.0, ceiling_db=-1.0,
        cut_highmid=None, cut_highs=None, source_subfolder="",
        freeze_signature=False, new_anchor=False, loop=loop,
    )
    ctx.analysis_results = [_analysis(n) for n in names]
    return ctx


def _selected_name(ctx: MasterAlbumCtx) -> str | None:
    index = ctx.anchor_result["selected_index"]
    return None if index is None else ctx.analysis_results[index - 1]["filename"]


# ---------------------------------------------------------------------------
# 1. README anchor_track is a track number, not a list position
# ---------------------------------------------------------------------------


class TestAnchorTrackNumber:
    def test_select_anchor_resolves_the_number_by_file_name(self) -> None:
        tracks = [_analysis(n) for n in DRIFTED]
        result = select_anchor(tracks, {}, override_index=3)
        assert result["method"] == "override"
        assert tracks[result["selected_index"] - 1]["filename"] == "03-anchor.wav"
        assert result["override_index"] == 3

    def test_select_anchor_aligned_album_unchanged(self) -> None:
        tracks = [_analysis(n) for n in ALIGNED]
        result = select_anchor(tracks, {}, override_index=3)
        assert result["selected_index"] == 3
        assert result["method"] == "override"
        assert result["override_reason"] is None

    def test_select_anchor_unnumbered_files_keep_the_position(self) -> None:
        tracks = [_analysis(n) for n in ("intro.wav", "storm.wav", "anchor.wav")]
        result = select_anchor(tracks, {}, override_index=2)
        assert result["selected_index"] == 2
        assert result["method"] == "override"

    def test_select_anchor_missing_number_falls_through_with_a_reason(self) -> None:
        tracks = [_analysis(n) for n in ("01-a.wav", "02-b.wav", "04-d.wav", "05-e.wav")]
        result = select_anchor(tracks, {}, override_index=3)
        assert result["method"] != "override"
        assert "no file is numbered 3" in result["override_reason"]
        assert "fell through to composite scoring" in result["override_reason"]

    def test_select_anchor_shared_number_is_not_guessed(self) -> None:
        tracks = [_analysis(n) for n in DRIFTED]
        result = select_anchor(tracks, {}, override_index=2)
        assert result["method"] != "override"
        assert "ambiguous" in result["override_reason"]
        assert "02-storm-old-title.wav" in result["override_reason"]

    def test_master_album_anchor_stage_uses_the_numbered_file(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            _shared, "cache", _FakeCache({"albums": {"drift": {"anchor_track": 3}}}),
        )

        async def _run() -> MasterAlbumCtx:
            ctx = _ctx(asyncio.get_running_loop(), DRIFTED)
            await _album_stages._stage_anchor_selection(ctx)
            return ctx

        ctx = asyncio.run(_run())
        assert _selected_name(ctx) == "03-anchor.wav"
        assert ctx.stages["anchor_selection"]["status"] == "pass"

    def test_master_album_anchor_stage_warns_on_a_missing_number(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            _shared, "cache", _FakeCache({"albums": {"drift": {"anchor_track": 7}}}),
        )

        async def _run() -> MasterAlbumCtx:
            ctx = _ctx(asyncio.get_running_loop(), ALIGNED)
            await _album_stages._stage_anchor_selection(ctx)
            return ctx

        ctx = asyncio.run(_run())
        assert ctx.stages["anchor_selection"]["status"] == "warn"
        assert any("anchor_track 7 not used" in str(w) for w in ctx.warnings)

    @pytest.mark.parametrize("handler", ["measure", "check"])
    def test_signature_and_coherence_handlers_use_the_numbered_file(
        self, tmp_path: Path, handler: str,
    ) -> None:
        mastered = tmp_path / "mastered"
        mastered.mkdir()
        for name in DRIFTED:
            (mastered / name).write_bytes(b"")

        def _fake_analyze(path: str) -> dict[str, Any]:
            return _analysis(Path(path).name)

        with patch.object(processing_helpers, "_resolve_audio_dir",
                          lambda *_a, **_k: (None, tmp_path)), \
             patch.object(processing_helpers, "_check_mastering_deps", lambda: None), \
             patch("tools.mastering.analyze_tracks.analyze_track", _fake_analyze):
            if handler == "measure":
                coro = audio_mod.measure_album_signature("drift", anchor_track=3)
            else:
                coro = audio_mod.album_coherence_check("drift", anchor_track=3)
            result = json.loads(asyncio.run(coro))

        anchor = result["anchor"]
        assert anchor["method"] == "override"
        assert DRIFTED[anchor["selected_index"] - 1] == "03-anchor.wav"


# ---------------------------------------------------------------------------
# 2. Frozen mode finds the stored anchor by file name
# ---------------------------------------------------------------------------


def _frozen(index: int, filename: str | None) -> dict[str, Any]:
    anchor: dict[str, Any] = {"index": index}
    if filename is not None:
        anchor["filename"] = filename
    return {"anchor": anchor, "delivery_targets": {}, "tolerances": {}}


def _run_frozen(names: list[str], signature: dict[str, Any]) -> MasterAlbumCtx:
    async def _run() -> MasterAlbumCtx:
        ctx = _ctx(asyncio.get_running_loop(), names)
        ctx.targets = {"target_lufs": -14.0, "ceiling_db": -1.0}
        ctx.frozen_signature = signature
        await _album_stages._stage_anchor_selection(ctx)
        return ctx

    return asyncio.run(_run())


class TestFrozenAnchor:
    def test_frozen_anchor_found_by_file_name_after_sources_changed(self) -> None:
        ctx = _run_frozen(DRIFTED, _frozen(3, "03-anchor.wav"))
        assert _selected_name(ctx) == "03-anchor.wav"
        assert ctx.stages["anchor_selection"]["status"] == "pass"

    def test_frozen_anchor_aligned_album_unchanged(self) -> None:
        ctx = _run_frozen(ALIGNED, _frozen(3, "03-anchor.wav"))
        assert ctx.anchor_result["selected_index"] == 3

    def test_frozen_anchor_without_a_file_name_keeps_the_index(self) -> None:
        ctx = _run_frozen(DRIFTED, _frozen(3, None))
        assert ctx.anchor_result["selected_index"] == 3

    def test_frozen_anchor_gone_from_the_sources_is_reported(self) -> None:
        ctx = _run_frozen(ALIGNED, _frozen(3, "03-removed.wav"))
        assert ctx.anchor_result["selected_index"] is None
        stage = ctx.stages["anchor_selection"]
        assert stage["status"] == "warn"
        assert stage["reason"] == "frozen_anchor_not_in_sources"
        assert any("03-removed.wav" in str(w) for w in ctx.warnings)


# ---------------------------------------------------------------------------
# 3. Only this run's masters are album tracks; other WAVs are strays
# ---------------------------------------------------------------------------


def _noise(path: Path, amplitude: float, seed: int, seconds: float = 3.0) -> None:
    rng = np.random.default_rng(seed)
    data = rng.standard_normal((int(48000 * seconds), 2)) * amplitude
    sf.write(str(path), data, 48000, subtype="PCM_24")


def _mastering_ctx(tmp_path: Path, loop: asyncio.AbstractEventLoop) -> MasterAlbumCtx:
    source = tmp_path / "polished"
    source.mkdir()
    for i, name in enumerate(["01-a.wav", "02-new-title.wav", "03-c.wav"]):
        _noise(source / name, 0.05, seed=i)
    return MasterAlbumCtx(
        album_slug="drift", genre="", target_lufs=-14.0, ceiling_db=-1.0,
        cut_highmid=None, cut_highs=None, source_subfolder="polished",
        freeze_signature=False, new_anchor=False, loop=loop,
        audio_dir=tmp_path, source_dir=source,
        wav_files=sorted(source.glob("*.wav")),
        targets={"output_sample_rate": 48000, "output_bits": 24,
                 "target_lufs": -14.0, "ceiling_db": -1.0},
        settings={}, effective_lufs=-14.0, effective_ceiling=-1.0,
        effective_highmid=0.0, effective_highs=0.0, effective_compress=1.0,
    )


class TestStrayMasters:
    def test_a_leftover_master_is_a_stray_not_a_track(self, tmp_path: Path) -> None:
        mastered = tmp_path / "mastered"
        mastered.mkdir()
        # The renamed track's old master, from a run at another target.
        _noise(mastered / "02-old-title.wav", 0.005, seed=9)

        async def _run() -> tuple[str | None, MasterAlbumCtx]:
            ctx = _mastering_ctx(tmp_path, asyncio.get_running_loop())
            assert await _album_stages._stage_mastering(ctx) is None
            return await _album_stages._stage_verification(ctx), ctx

        halt, ctx = asyncio.run(_run())

        assert [p.name for p in ctx.mastered_files] == [
            "01-a.wav", "02-new-title.wav", "03-c.wav",
        ]
        assert halt is None, json.loads(halt)["failure_detail"]
        assert [r["filename"] for r in ctx.verify_results] == [
            "01-a.wav", "02-new-title.wav", "03-c.wav",
        ]
        stage = ctx.stages["mastering"]
        assert stage["status"] == "warn"
        assert stage["stray_wavs"] == ["02-old-title.wav"]
        assert any("02-old-title.wav" in str(w) for w in ctx.warnings)
        # Reported, never deleted.
        assert (mastered / "02-old-title.wav").is_file()

    def test_the_playlist_lists_only_this_runs_tracks(self, tmp_path: Path) -> None:
        mastered = tmp_path / "mastered"
        mastered.mkdir()
        _noise(mastered / "02-old-title.wav", 0.005, seed=9)

        async def _run() -> MasterAlbumCtx:
            ctx = _mastering_ctx(tmp_path, asyncio.get_running_loop())
            assert await _album_stages._stage_mastering(ctx) is None
            await _album_stages._stage_layout(ctx)
            await _album_stages._stage_playlist(ctx)
            return ctx

        ctx = asyncio.run(_run())

        playlist = (tmp_path / "drift.m3u8").read_text(encoding="utf-8")
        assert "mastered/02-new-title.wav" in playlist
        assert "02-old-title.wav" not in playlist
        assert ctx.stages["playlist"]["tracks"] == 3
        assert "02-old-title.wav" not in (tmp_path / "LAYOUT.md").read_text(encoding="utf-8")

    def test_an_aligned_album_has_no_strays(self, tmp_path: Path) -> None:
        async def _run() -> MasterAlbumCtx:
            ctx = _mastering_ctx(tmp_path, asyncio.get_running_loop())
            assert await _album_stages._stage_mastering(ctx) is None
            return ctx

        ctx = asyncio.run(_run())

        assert [p.name for p in ctx.mastered_files] == [
            "01-a.wav", "02-new-title.wav", "03-c.wav",
        ]
        assert ctx.stages["mastering"]["status"] == "pass"
        assert "stray_wavs" not in ctx.stages["mastering"]
        assert not any("mastered/" in str(w) for w in ctx.warnings)
