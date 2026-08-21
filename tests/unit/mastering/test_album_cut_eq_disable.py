"""Behavior tests for the album-level cut_highmid/cut_highs None sentinel (#556).

`master_audio` gained None-sentinel semantics in #553/#554 (None = use the
genre preset, explicit 0 = disable the cut, effective values echoed back).
`master_album`, `album_coherence_correct` and `polish_and_master_album` kept
the old `0.0` defaults, and `build_effective_preset` read `0.0` as "not
supplied" — so an explicit 0 could not disable a genre's cut through any of
them.

These tests pin the unified contract for all three tools: omitting the
parameter applies (and echoes) the genre preset exactly as before, an
explicit 0/0.0 disables the cut and is echoed as 0, and an explicit
non-zero value is applied and echoed.

This file also hosts `TestPolishAndMasterAlbumGenreDerivation` (#556), which
reuses the `polish_album`/`master_album`-stubbing pattern below for
`polish_and_master_album`'s own genre-derivation and per-phase fallback
behavior — a different #556 sub-issue that happens to need the exact same
scaffolding already built here for the cut-EQ tests.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from contextlib import ExitStack
from pathlib import Path
from typing import Any
from unittest.mock import patch

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
for _p in (str(PROJECT_ROOT), str(SERVER_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from handlers import _shared as shared_mod  # noqa: E402
from handlers.processing import _album_stages as album_stages_mod  # noqa: E402
from handlers.processing import _helpers as processing_helpers  # noqa: E402
from handlers.processing import audio as audio_mod  # noqa: E402
from handlers.processing import mixing as mixing_mod  # noqa: E402
from tools.mastering import master_tracks as master_tracks_mod  # noqa: E402


def _shipped_genre_preset(genre: str, key: str) -> float:
    """Read one value straight out of the genre presets this repo ships.

    Not out of ``master_tracks.GENRE_PRESETS``: that is the shipped file
    deep-merged with the developer's ``{overrides}/mastering-presets.yaml``,
    so reading it would compare the handler's output against the same
    override the handler used. The runners below patch the overrides path
    away so the handler resolves from this same file (mirrors
    test_master_audio_cut_eq_disable.py).
    """
    import yaml

    presets_file = PROJECT_ROOT / "tools" / "mastering" / "genre-presets.yaml"
    with open(presets_file, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return float(data["genres"][genre][key])


# black-metal is the one shipped genre used throughout this file: it sets
# BOTH cuts to non-zero values, so "explicit 0 disables" is a real
# assertion for each parameter rather than a vacuous one (pop, for
# instance, ships cut_highs: 0).
GENRE = "black-metal"
GENRE_CUT_HIGHMID = _shipped_genre_preset(GENRE, "cut_highmid")
GENRE_CUT_HIGHS = _shipped_genre_preset(GENRE, "cut_highs")


def _dynamic_tone(rate: int, seconds: float, freq: float,
                  base_amp: float = 0.35) -> np.ndarray:
    """A tone with a block-wise amplitude envelope.

    A flat sine measures ~0 LU of loudness range, which trips master_album's
    post-QC LRA floor (1.0 LU) and halts the pipeline before the assertions
    below can look at the settings block. The 3-second alternating envelope
    gives the track a realistic LRA while keeping the fixture deterministic.
    """
    n = int(seconds * rate)
    t = np.arange(n) / rate
    block = (t // 3.0).astype(int)
    envelope = np.where(block % 2 == 0, base_amp, base_amp * 0.25)
    return (envelope * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def _write_tone_wav(path: Path, *, rate: int = 44100,
                    seconds: float = 30.0, freq: float = 3500.0,
                    base_amp: float = 0.35) -> Path:
    import soundfile as sf

    mono = _dynamic_tone(rate, seconds, freq, base_amp)
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), np.column_stack([mono, mono]), rate, subtype="PCM_24")
    return path


class _FakeCache:
    """Minimal stand-in for the server's state cache."""

    def __init__(self, state: dict[str, Any] | None = None) -> None:
        self._state = state or {"albums": {}}

    def get_state(self) -> dict[str, Any]:
        return self._state

    def get_state_ref(self) -> dict[str, Any]:
        return self._state


# ---------------------------------------------------------------------------
# master_album
# ---------------------------------------------------------------------------

def _run_master_album(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, **kwargs: Any,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Run master_album end-to-end on a one-track album.

    Returns (parsed result, presets master_track was actually called with).
    The spy proves the resolved cut reaches the mastering function, not just
    the echoed settings block.
    """
    album_slug = kwargs.pop("album_slug", "cut-eq-album")
    _write_tone_wav(tmp_path / "01-track.wav")

    fake_state = {
        "albums": {
            album_slug: {
                "path": str(tmp_path),
                "status": "In Progress",
                "tracks": {},
                "mastering": {},
            }
        }
    }
    monkeypatch.setattr(shared_mod, "cache", _FakeCache(fake_state))
    monkeypatch.setattr(
        album_stages_mod, "_embed_wav_metadata_fn", lambda *a, **kw: None,
    )

    def _fake_resolve(slug: str, subfolder: str = "") -> tuple[str | None, Path]:
        return None, tmp_path

    captured: list[dict[str, Any]] = []
    real_master_track = master_tracks_mod.master_track

    def _spy(*args: Any, **kw: Any) -> dict[str, Any]:
        preset = kw.get("preset")
        if isinstance(preset, dict):
            captured.append(dict(preset))
        return real_master_track(*args, **kw)

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve), \
         patch.object(master_tracks_mod, "_get_overrides_path", lambda: None), \
         patch.object(master_tracks_mod, "master_track", _spy):
        result_json = asyncio.run(
            audio_mod.master_album(album_slug=album_slug, **kwargs)
        )
    return json.loads(result_json), captured


class TestMasterAlbumCutEq:
    def test_omitted_applies_and_echoes_genre_preset(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        result, captured = _run_master_album(tmp_path, monkeypatch, genre=GENRE)
        assert result.get("failed_stage") is None, result.get("failure_detail")
        assert result["settings"]["cut_highmid"] == GENRE_CUT_HIGHMID
        assert result["settings"]["cut_highs"] == GENRE_CUT_HIGHS
        assert captured, "master_track was never called"
        assert captured[0]["cut_highmid"] == GENRE_CUT_HIGHMID

    def test_explicit_zero_disables_and_echoes_zero(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        result, captured = _run_master_album(
            tmp_path, monkeypatch, genre=GENRE, cut_highmid=0.0,
        )
        assert result.get("failed_stage") is None, result.get("failure_detail")
        assert result["settings"]["cut_highmid"] == 0.0
        assert result["settings"]["cut_highmid"] != GENRE_CUT_HIGHMID
        # cut_highs was omitted — the preset must still apply to it.
        assert result["settings"]["cut_highs"] == GENRE_CUT_HIGHS
        assert captured, "master_track was never called"
        assert captured[0]["cut_highmid"] == 0.0

    def test_explicit_zero_cut_highs_disables_and_echoes_zero(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        result, captured = _run_master_album(
            tmp_path, monkeypatch, genre=GENRE, cut_highs=0.0,
        )
        assert result.get("failed_stage") is None, result.get("failure_detail")
        assert result["settings"]["cut_highs"] == 0.0
        assert result["settings"]["cut_highmid"] == GENRE_CUT_HIGHMID
        assert captured, "master_track was never called"
        assert captured[0]["cut_highs"] == 0.0

    def test_explicit_nonzero_overrides_preset_and_echoes_value(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        result, captured = _run_master_album(
            tmp_path, monkeypatch, genre=GENRE, cut_highmid=-4.5, cut_highs=-2.25,
        )
        assert result.get("failed_stage") is None, result.get("failure_detail")
        assert result["settings"]["cut_highmid"] == -4.5
        assert result["settings"]["cut_highs"] == -2.25
        assert captured, "master_track was never called"
        assert captured[0]["cut_highmid"] == -4.5
        assert captured[0]["cut_highs"] == -2.25


# ---------------------------------------------------------------------------
# album_coherence_correct
# ---------------------------------------------------------------------------

def _setup_coherence_album(tmp_path: Path, amplitudes: list[float]) -> Path:
    """polished/ + mastered/ with matching names; amplitudes drive the LUFS
    spread that makes one track a correctable outlier."""
    import soundfile as sf

    for sub in ("polished", "mastered"):
        (tmp_path / sub).mkdir()
    for i, amp in enumerate(amplitudes, start=1):
        name = f"{i:02d}-track.wav"
        rate = 44100
        mono = _dynamic_tone(rate, 30.0, 200.0 + i * 30.0, base_amp=amp)
        stereo = np.column_stack([mono, mono])
        for sub in ("polished", "mastered"):
            sf.write(str(tmp_path / sub / name), stereo, rate, subtype="PCM_24")
    return tmp_path


def _run_coherence_correct(
    tmp_path: Path, **kwargs: Any,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    _setup_coherence_album(tmp_path, [0.3, 0.6, 0.3])

    def _fake_resolve(slug: str, subfolder: str = "") -> tuple[str | None, Path]:
        return None, tmp_path

    captured: list[dict[str, Any]] = []
    real_master_track = master_tracks_mod.master_track

    def _spy(*args: Any, **kw: Any) -> dict[str, Any]:
        preset = kw.get("preset")
        if isinstance(preset, dict):
            captured.append(dict(preset))
        return real_master_track(*args, **kw)

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve), \
         patch.object(master_tracks_mod, "_get_overrides_path", lambda: None), \
         patch.object(master_tracks_mod, "master_track", _spy):
        result_json = asyncio.run(
            audio_mod.album_coherence_correct(
                album_slug="cut-eq-coherence",
                genre=GENRE,
                source_subfolder="polished",
                check_subfolder="mastered",
                anchor_track=1,
                **kwargs,
            )
        )
    return json.loads(result_json), captured


class TestAlbumCoherenceCorrectCutEq:
    def test_omitted_applies_and_echoes_genre_preset(self, tmp_path: Path) -> None:
        result, captured = _run_coherence_correct(tmp_path)
        assert "error" not in result, result
        assert result["settings"]["cut_highmid"] == GENRE_CUT_HIGHMID
        assert result["settings"]["cut_highs"] == GENRE_CUT_HIGHS
        assert captured, "master_track was never called"
        assert captured[0]["cut_highmid"] == GENRE_CUT_HIGHMID

    def test_explicit_zero_disables_and_echoes_zero(self, tmp_path: Path) -> None:
        result, captured = _run_coherence_correct(
            tmp_path, cut_highmid=0.0, cut_highs=0.0,
        )
        assert "error" not in result, result
        assert result["settings"]["cut_highmid"] == 0.0
        assert result["settings"]["cut_highs"] == 0.0
        assert result["settings"]["cut_highmid"] != GENRE_CUT_HIGHMID
        assert captured, "master_track was never called"
        assert captured[0]["cut_highmid"] == 0.0
        assert captured[0]["cut_highs"] == 0.0

    def test_explicit_nonzero_overrides_preset_and_echoes_value(
        self, tmp_path: Path,
    ) -> None:
        result, captured = _run_coherence_correct(
            tmp_path, cut_highmid=-4.5, cut_highs=-2.25,
        )
        assert "error" not in result, result
        assert result["settings"]["cut_highmid"] == -4.5
        assert result["settings"]["cut_highs"] == -2.25
        assert captured, "master_track was never called"
        assert captured[0]["cut_highmid"] == -4.5


# ---------------------------------------------------------------------------
# polish_and_master_album
# ---------------------------------------------------------------------------

def _run_polish_and_master(**kwargs: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run polish_and_master_album with both stages stubbed.

    polish_and_master_album's only job for the cut parameters is to forward
    them to master_album unchanged — proving the forwarding (and that the
    master stage's settings block comes back nested) is the whole contract;
    master_album's own behavior is pinned above.
    """
    captured: dict[str, Any] = {}

    async def _fake_polish(**kw: Any) -> str:
        return json.dumps({"stage_reached": "complete"})

    async def _fake_master(**kw: Any) -> str:
        captured.update(kw)
        return json.dumps({
            "stage_reached": "complete",
            "settings": {
                "cut_highmid": kw.get("cut_highmid"),
                "cut_highs": kw.get("cut_highs"),
            },
        })

    with patch.object(mixing_mod, "polish_album", _fake_polish), \
         patch.object(audio_mod, "master_album", _fake_master):
        result_json = asyncio.run(
            mixing_mod.polish_and_master_album(album_slug="cut-eq-pm", **kwargs)
        )
    return json.loads(result_json), captured


class TestPolishAndMasterAlbumCutEq:
    def test_omitted_forwards_none_so_preset_applies(self) -> None:
        result, captured = _run_polish_and_master(genre=GENRE)
        assert captured["cut_highmid"] is None
        assert captured["cut_highs"] is None
        assert result["master"]["settings"]["cut_highmid"] is None

    def test_explicit_zero_forwards_zero(self) -> None:
        result, captured = _run_polish_and_master(
            genre=GENRE, cut_highmid=0.0, cut_highs=0.0,
        )
        assert captured["cut_highmid"] == 0.0
        assert captured["cut_highs"] == 0.0
        assert result["master"]["settings"]["cut_highmid"] == 0.0

    def test_explicit_nonzero_forwards_value(self) -> None:
        result, captured = _run_polish_and_master(
            genre=GENRE, cut_highmid=-4.5, cut_highs=-2.25,
        )
        assert captured["cut_highmid"] == -4.5
        assert captured["cut_highs"] == -2.25
        assert result["master"]["settings"]["cut_highs"] == -2.25


# ---------------------------------------------------------------------------
# polish_and_master_album — genre derivation (#556 fix round)
# ---------------------------------------------------------------------------
#
# polish_and_master_album resolves genre once, up front (explicit wins,
# else derived from the album's state entry), and forwards it to both the
# polish and master phases. The two phases validate it against INDEPENDENT
# preset sets (tools/mixing/mix-presets.yaml vs tools/mastering/
# genre-presets.yaml) — a genre known to one and not the other is a real,
# expected case, so each phase gets its own soft fallback (warn + proceed
# without a genre preset for that phase only) rather than a hard error,
# when the genre was DERIVED rather than explicitly passed by the caller.


def _run_polish_and_master_genre(
    monkeypatch: pytest.MonkeyPatch,
    *,
    genre_arg: str = "",
    derived_genre: str | None = None,
    mastering_known_genres: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Run polish_and_master_album with both phases stubbed, capturing the
    genre kwarg each phase actually received.

    `derived_genre`, when given, patches `_derive_album_genre` so the
    "no genre argument" path resolves to a controlled value without
    needing a real state cache. `mastering_known_genres`, when given,
    patches `load_genre_presets` so the master-phase validity check can
    be forced to reject a genre the mix side would accept.
    """
    captured_polish: dict[str, Any] = {}
    captured_master: dict[str, Any] = {}

    async def _fake_polish(**kw: Any) -> str:
        captured_polish.update(kw)
        return json.dumps({"stage_reached": "complete"})

    async def _fake_master(**kw: Any) -> str:
        captured_master.update(kw)
        return json.dumps({
            "stage_reached": "complete",
            "settings": {},
        })

    with ExitStack() as stack:
        stack.enter_context(patch.object(mixing_mod, "polish_album", _fake_polish))
        stack.enter_context(patch.object(audio_mod, "master_album", _fake_master))
        if derived_genre is not None:
            stack.enter_context(patch.object(
                processing_helpers, "_derive_album_genre", return_value=derived_genre,
            ))
        if mastering_known_genres is not None:
            import tools.mastering.master_tracks as mast_mod
            stack.enter_context(patch.object(
                mast_mod, "load_genre_presets", return_value=mastering_known_genres,
            ))
        result_json = asyncio.run(
            mixing_mod.polish_and_master_album(album_slug="genre-pm", genre=genre_arg)
        )
    return json.loads(result_json), captured_polish, captured_master


class TestPolishAndMasterAlbumGenreDerivation:
    def test_explicit_genre_reaches_both_phases_undisturbed(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _result, captured_polish, captured_master = _run_polish_and_master_genre(
            monkeypatch, genre_arg=GENRE,
        )
        assert captured_polish.get("genre") == GENRE
        assert captured_master.get("genre") == GENRE

    def test_derive_helper_not_called_when_genre_explicit(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        with patch.object(processing_helpers, "_derive_album_genre") as mock_derive:
            _run_polish_and_master_genre(monkeypatch, genre_arg=GENRE)
        mock_derive.assert_not_called()

    def test_derived_genre_reaches_both_phases(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A single derivation resolves the genre used by both phases —
        proven by matching, not just each independently correct."""
        _result, captured_polish, captured_master = _run_polish_and_master_genre(
            monkeypatch, genre_arg="", derived_genre=GENRE,
        )
        assert captured_polish.get("genre") == GENRE
        assert captured_master.get("genre") == GENRE
        assert captured_polish.get("genre") == captured_master.get("genre")

    def test_derivation_failure_forwards_no_genre_to_both_phases(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _result, captured_polish, captured_master = _run_polish_and_master_genre(
            monkeypatch, genre_arg="", derived_genre="",
        )
        assert not captured_polish.get("genre")
        assert not captured_master.get("genre")

    def test_mix_known_mastering_unknown_derived_genre_masters_genre_less_with_warning(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
    ) -> None:
        """The headline case for this fix: a genre valid on the mix side
        (so the polish phase still applies genre-scoped overrides) but
        absent from the SEPARATE mastering-preset genre list masters
        without a genre preset, with a warning — not a hard failure of
        the whole run, and not silently dropped for the mix phase too.
        """
        with caplog.at_level(logging.WARNING):
            _result, captured_polish, captured_master = _run_polish_and_master_genre(
                monkeypatch, genre_arg="", derived_genre=GENRE,
                mastering_known_genres={},
            )
        assert captured_polish.get("genre") == GENRE
        assert not captured_master.get("genre")
        assert any(GENRE in r.message for r in caplog.records)

    def test_explicit_genre_unknown_to_mastering_is_not_softened(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """An EXPLICIT genre unrecognized by the mastering presets is not
        this function's call to soften — that stays master_album's own
        existing hard-validation job, unchanged from before #556."""
        _result, captured_polish, captured_master = _run_polish_and_master_genre(
            monkeypatch, genre_arg=GENRE, mastering_known_genres={},
        )
        assert captured_master.get("genre") == GENRE

    def test_mix_unknown_mastering_known_derived_genre_is_not_forwarded_to_polish(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """#556 round 2: a DERIVED genre absent from the mix presets is
        forwarded to `polish_album` as "" — not the concrete value —
        so `polish_album` re-derives it internally and applies its OWN
        keep-and-inform treatment (see test_handlers_mixing.py for that
        half). Forwarding the concrete value here would make
        `polish_album` (and, inside it, `polish_audio`) treat it as
        though a caller had typed it, tripping `polish_audio`'s hard
        "Unknown genre" error over a fact about the album's own state
        entry — the actual round-1 bug. "dark-cabaret" is a real shipped
        mastering genre with no mix-presets.yaml section (confirmed via
        grep, not assumed), so the master phase still gets it directly.
        """
        _result, captured_polish, captured_master = _run_polish_and_master_genre(
            monkeypatch, genre_arg="", derived_genre="dark-cabaret",
        )
        assert not captured_polish.get("genre")
        assert captured_master.get("genre") == "dark-cabaret"
