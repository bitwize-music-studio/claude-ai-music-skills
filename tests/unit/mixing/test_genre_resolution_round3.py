"""Round-3 corrections to the #556 genre plumbing and coercion helpers.

Each test here pins a behavior an earlier round got wrong, so the failure
message names the regression rather than just the assertion.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SERVER_ROOT = PROJECT_ROOT / "servers" / "bitwize-music-server"
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

import tools.mastering.master_tracks as master_tracks
import tools.mixing.mix_tracks as mix_tracks
from handlers.processing import _helpers
from handlers.processing import mixing as mixing_mod
from tests.unit.mixing._presets import shipped_presets_only


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch: Any) -> None:
    shipped_presets_only(monkeypatch)


@pytest.fixture(autouse=True)
def _restore_preset_globals() -> Any:
    """Restore the module-level preset snapshots after each test.

    Several tests here call `refresh_genre_presets()` / `_refresh_mix_presets()`
    with a monkeypatched overrides path. `monkeypatch` restores the patched
    *function*, but the globals those calls rewrote (`GENRE_PRESETS`,
    `MIX_PRESETS`) keep the override contents and would leak a fabricated
    genre into every later test in the session.
    """
    saved_genre = master_tracks.GENRE_PRESETS
    saved_mix = mix_tracks.MIX_PRESETS
    yield
    master_tracks.GENRE_PRESETS = saved_genre
    mix_tracks.MIX_PRESETS = saved_mix


# ---------------------------------------------------------------------------
# Union genre validation (#556 round 3)
# ---------------------------------------------------------------------------


class TestGenreKnownAnywhere:
    """An explicit genre must be judged against BOTH preset sets.

    Round 2 hard-errored on mix-set membership alone, which rejects the
    ~334 real mastering genres that carry no mix section — so naming an
    album's own genre failed a call that succeeded when the argument was
    omitted and the identical value was derived.
    """

    def test_the_two_preset_sets_really_do_differ(self) -> None:
        """Precondition — without this gap the rest of the class is vacuous."""
        mix = set(mix_tracks.load_mix_presets().get("genres", {}))
        mastering = set(master_tracks.load_genre_presets())
        assert mastering - mix, (
            "expected mastering genres absent from the mix presets; if this "
            "ever becomes empty the union check below is untested"
        )

    def test_mix_only_genre_is_known(self) -> None:
        mix = set(mix_tracks.load_mix_presets().get("genres", {}))
        assert _helpers._genre_known_anywhere(next(iter(mix)))

    def test_mastering_only_genre_is_known(self) -> None:
        mix = set(mix_tracks.load_mix_presets().get("genres", {}))
        mastering = set(master_tracks.load_genre_presets())
        mastering_only = sorted(mastering - mix)[0]
        assert _helpers._genre_known_anywhere(mastering_only), (
            f"{mastering_only!r} is a real shipped mastering genre and must "
            "not be treated as a typo just because the mix presets lack a "
            "section for it"
        )

    def test_genuine_typo_is_not_known(self) -> None:
        assert not _helpers._genre_known_anywhere("not-a-real-genre-anywhere")

    def test_empty_is_not_known(self) -> None:
        assert not _helpers._genre_known_anywhere("")

    def test_case_insensitive(self) -> None:
        assert _helpers._genre_known_anywhere("ROCK")

    def test_union_contains_both_sets(self) -> None:
        mix = set(mix_tracks.load_mix_presets().get("genres", {}))
        mastering = set(master_tracks.load_genre_presets())
        assert _helpers._all_known_genres() == mix | mastering


# ---------------------------------------------------------------------------
# Mastering preset refresh (#556 round 3)
# ---------------------------------------------------------------------------


class TestRefreshGenrePresets:
    """`GENRE_PRESETS` was an import-time snapshot with no refresh, so the
    fresh loader and the snapshot `qc_track` reads could disagree."""

    def test_refresh_picks_up_a_mid_session_override(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        override_dir = tmp_path / "overrides"
        override_dir.mkdir()
        (override_dir / "mastering-presets.yaml").write_text(
            "genres:\n  brand-new-genre:\n    cut_highmid: -2.0\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(master_tracks, "_get_overrides_path", lambda: override_dir)

        assert "brand-new-genre" not in master_tracks.GENRE_PRESETS
        refreshed = master_tracks.refresh_genre_presets()
        assert "brand-new-genre" in refreshed
        assert "brand-new-genre" in master_tracks.GENRE_PRESETS, (
            "refresh must update the module global, not just return a dict — "
            "qc_tracks reads the global"
        )

    def test_qc_track_refreshes_before_resolving(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The guard/raise split closed at its source: a genre only a fresh
        read knows must not raise out of `_resolve_click_thresholds`."""
        from tools.mastering.qc_tracks import _resolve_click_thresholds

        override_dir = tmp_path / "overrides"
        override_dir.mkdir()
        (override_dir / "mastering-presets.yaml").write_text(
            "genres:\n  brand-new-genre:\n    click_peak_ratio: 9.0\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(master_tracks, "_get_overrides_path", lambda: override_dir)

        with pytest.raises(ValueError):
            _resolve_click_thresholds("brand-new-genre")

        master_tracks.refresh_genre_presets()
        peak_ratio, _fail_count = _resolve_click_thresholds("brand-new-genre")
        assert peak_ratio == 9.0


# ---------------------------------------------------------------------------
# excitation_db_when_dark scoping (#556 round 3)
# ---------------------------------------------------------------------------


class TestExcitationResolver:
    """Round 2 read this key straight out of `MIX_PRESETS["defaults"][stem]`,
    so its genre-scoped form was unreachable and a bad value raised."""

    def _install(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: str,
    ) -> None:
        override_dir = tmp_path / "overrides"
        override_dir.mkdir()
        (override_dir / "mix-presets.yaml").write_text(body, encoding="utf-8")
        monkeypatch.setattr(mix_tracks, "_get_overrides_path", lambda: override_dir)
        mix_tracks._refresh_mix_presets()

    def test_genre_scope_wins_over_defaults(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        self._install(tmp_path, monkeypatch, (
            "defaults:\n  vocals:\n    excitation_db_when_dark: 2.5\n"
            "genres:\n  electronic:\n    vocals:\n"
            "      excitation_db_when_dark: 6.0\n"
        ))
        assert mixing_mod._resolve_excitation_db_when_dark("vocals", "electronic") == 6.0

    def test_defaults_apply_without_a_genre(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        self._install(tmp_path, monkeypatch, (
            "defaults:\n  vocals:\n    excitation_db_when_dark: 2.5\n"
        ))
        assert mixing_mod._resolve_excitation_db_when_dark("vocals", None) == 2.5

    def test_unreadable_value_warns_and_defaults(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        self._install(tmp_path, monkeypatch, (
            'defaults:\n  vocals:\n    excitation_db_when_dark: "2.5 dB"\n'
        ))
        with caplog.at_level(logging.WARNING):
            value = mixing_mod._resolve_excitation_db_when_dark("vocals", None)
        assert value == mixing_mod._ANALYZER_DEFAULT_EXCITATION_DB
        assert any("excitation_db_when_dark" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Warning context and dedup keys (#556 round 3)
# ---------------------------------------------------------------------------


class TestSettingScopeLabel:
    def test_stem_settings_carry_their_scope(self) -> None:
        settings = mix_tracks._get_stem_settings("vocals", "electronic")
        assert settings[mix_tracks._SCOPE_KEY] == "electronic.vocals"

    def test_no_genre_labels_defaults(self) -> None:
        settings = mix_tracks._get_stem_settings("vocals", None)
        assert settings[mix_tracks._SCOPE_KEY] == "defaults.vocals"

    def test_full_mix_settings_carry_their_scope(self) -> None:
        settings = mix_tracks._get_full_mix_settings("electronic")
        assert settings[mix_tracks._SCOPE_KEY] == "electronic.full_mix"

    def test_warning_names_the_block_not_just_the_key(
        self, caplog: pytest.LogCaptureFixture,
    ) -> None:
        settings = {
            "noise_reduction": "nope",
            mix_tracks._SCOPE_KEY: "electronic.vocals",
        }
        with caplog.at_level(logging.WARNING):
            assert mix_tracks._setting_float(settings, "noise_reduction", 0.0) == 0.0
        assert any(
            "electronic.vocals.noise_reduction" in r.message for r in caplog.records
        ), "the surviving line must name the section to go fix"

    def test_two_blocks_sharing_a_key_and_value_both_warn(
        self, caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Keyed on the bare setting name, the second was suppressed as a
        duplicate and its block never surfaced."""
        with caplog.at_level(logging.WARNING):
            for scope in ("electronic.vocals", "rock.drums"):
                mix_tracks._setting_float(
                    {"noise_reduction": "nope", mix_tracks._SCOPE_KEY: scope},
                    "noise_reduction", 0.0,
                )
        messages = " ".join(r.message for r in caplog.records)
        assert "electronic.vocals.noise_reduction" in messages
        assert "rock.drums.noise_reduction" in messages


class TestCoercerDedupIncludesDefault:
    """The messages interpolate `default`; the keys did not, so a second
    site with a different documented default was muted."""

    def test_float_warns_once_per_default(
        self, caplog: pytest.LogCaptureFixture,
    ) -> None:
        from tools.shared.config import coerce_yaml_float

        with caplog.at_level(logging.WARNING):
            coerce_yaml_float("bad", default=1.0, context="k")
            coerce_yaml_float("bad", default=2.0, context="k")
            coerce_yaml_float("bad", default=1.0, context="k")  # true duplicate
        assert len(caplog.records) == 2

    def test_bool_warns_once_per_default(
        self, caplog: pytest.LogCaptureFixture,
    ) -> None:
        from tools.shared.config import coerce_yaml_bool

        with caplog.at_level(logging.WARNING):
            coerce_yaml_bool("maybe", default=False, context="k")
            coerce_yaml_bool("maybe", default=True, context="k")
            coerce_yaml_bool("maybe", default=False, context="k")  # true duplicate
        assert len(caplog.records) == 2


class TestClickRepairDedupKey:
    """`default_repair` differs per stem (drums/percussion get "cubic", the
    other eleven chains "linear"), and the message prints it."""

    def test_each_default_gets_its_own_warning(
        self, caplog: pytest.LogCaptureFixture,
    ) -> None:
        import numpy as np

        data = np.zeros(2048, dtype=np.float64)
        settings = {"click_removal": True, "click_repair": "linar"}
        with caplog.at_level(logging.WARNING):
            mix_tracks._apply_click_removal(
                data, 44100, settings, None, default_repair="linear",
            )
            mix_tracks._apply_click_removal(
                data, 44100, settings, None, default_repair="cubic",
            )
        messages = [r.message for r in caplog.records]
        assert any("'linear'" in m for m in messages)
        assert any("'cubic'" in m for m in messages), (
            "a run that logged only \"using default 'linear'\" could still "
            "have repaired drums with cubic interpolation"
        )
