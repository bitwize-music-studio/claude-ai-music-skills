"""When ctx.remaster_filenames is a non-empty set, _stage_mastering
only (re-)masters those tracks and leaves existing mastered files
alone. When None, masters all tracks (cycle 1 behavior)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
for p in (str(PROJECT_ROOT), str(SERVER_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from handlers import _shared  # noqa: E402
from handlers.processing import _album_stages  # noqa: E402
from handlers.processing._album_stages import MasterAlbumCtx  # noqa: E402


def _write_wav(path: Path, rate: int = 48000, seconds: float = 3.0,
               seed: int = 0) -> None:
    rng = np.random.default_rng(seed)
    data = rng.standard_normal((int(rate * seconds), 2)).astype(np.float64) * 0.05
    sf.write(str(path), data, rate, subtype="PCM_24")


@pytest.fixture(autouse=True)
def _patch_shared_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide a stub cache so _stage_mastering's state lookup doesn't crash."""
    class _FakeCache:
        def get_state(self) -> dict:
            return {}

        def get_state_ref(self) -> dict:
            return {}

    monkeypatch.setattr(_shared, "cache", _FakeCache())


def _make_ctx(tmp_path: Path, remaster: set[str] | None,
              loop: asyncio.AbstractEventLoop) -> MasterAlbumCtx:
    source_dir = tmp_path / "polished"
    source_dir.mkdir(exist_ok=True)
    for i, name in enumerate(["01-a.wav", "02-b.wav"]):
        if not (source_dir / name).exists():
            _write_wav(source_dir / name, seed=i)
    return MasterAlbumCtx(
        album_slug="test",
        genre="",
        target_lufs=-14.0,
        ceiling_db=-1.0,
        cut_highmid=0.0,
        cut_highs=0.0,
        source_subfolder="",
        freeze_signature=False,
        new_anchor=False,
        loop=loop,
        audio_dir=tmp_path,
        source_dir=source_dir,
        wav_files=sorted(source_dir.glob("*.wav")),
        targets={
            "output_sample_rate": 48000,
            "output_bits": 24,
            "target_lufs": -14.0,
            "ceiling_db": -1.0,
        },
        settings={},
        effective_lufs=-14.0,
        effective_ceiling=-1.0,
        effective_highmid=0.0,
        effective_highs=0.0,
        effective_compress=1.0,
        remaster_filenames=remaster,
    )


def test_first_cycle_masters_all_tracks(tmp_path: Path) -> None:
    loop = asyncio.new_event_loop()
    try:
        ctx = _make_ctx(tmp_path, remaster=None, loop=loop)
        loop.run_until_complete(_album_stages._stage_mastering(ctx))
    finally:
        loop.close()
    out = ctx.output_dir
    assert out is not None
    assert (out / "01-a.wav").exists()
    assert (out / "02-b.wav").exists()


def test_selective_remaster_only_writes_requested_tracks(tmp_path: Path) -> None:
    # First cycle: master both.
    loop1 = asyncio.new_event_loop()
    try:
        ctx1 = _make_ctx(tmp_path, remaster=None, loop=loop1)
        loop1.run_until_complete(_album_stages._stage_mastering(ctx1))
    finally:
        loop1.close()
    out = ctx1.output_dir
    assert out is not None
    bytes_before_a = (out / "01-a.wav").read_bytes()
    bytes_before_b = (out / "02-b.wav").read_bytes()

    # Second cycle: only re-master track b with a tighter ceiling.
    loop2 = asyncio.new_event_loop()
    try:
        ctx2 = _make_ctx(tmp_path, remaster={"02-b.wav"}, loop=loop2)
        ctx2.output_dir = out
        ctx2.track_ceilings = {"02-b.wav": -3.0}
        loop2.run_until_complete(_album_stages._stage_mastering(ctx2))
    finally:
        loop2.close()

    bytes_after_a = (out / "01-a.wav").read_bytes()
    bytes_after_b = (out / "02-b.wav").read_bytes()

    assert bytes_after_a == bytes_before_a, \
        "track a was re-mastered despite not being in remaster_filenames"
    assert bytes_after_b != bytes_before_b, \
        "track b was NOT re-mastered despite being in remaster_filenames"

    # ctx.mastered_files must contain both files after the selective cycle.
    mastered_names = {f.name for f in ctx2.mastered_files}
    assert "01-a.wav" in mastered_names, \
        "retained track a missing from ctx.mastered_files"
    assert "02-b.wav" in mastered_names, \
        "re-mastered track b missing from ctx.mastered_files"
