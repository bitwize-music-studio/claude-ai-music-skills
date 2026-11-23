"""The mastering docs say what ``genre-presets.yaml`` and the code do (#683).

``tools/mastering/genre-presets.yaml`` is the source of truth. These tests
parse the preset tables in ``reference/mastering/genre-specific-presets.md``
and the per-genre ``**LUFS target**`` lines in
``skills/mastering-engineer/genre-presets.md`` and fail on any value that
disagrees with the YAML; 17 genres in the reference and 8 in the skill had
drifted (opera -16 vs -18, chillwave / vaporwave / shoegaze -14 vs -16,
edm -10 to -12 vs -14, high-mid cuts). They also hold the coherence
tolerances the signature docs show to the code's defaults, and check that the
preset loader keeps ``genre_ideal_lra_lu``, which it used to drop.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.mastering import master_tracks as master_tracks_mod  # noqa: E402

PRESETS_YAML = PROJECT_ROOT / "tools" / "mastering" / "genre-presets.yaml"
REFERENCE_DOC = PROJECT_ROOT / "reference" / "mastering" / "genre-specific-presets.md"
SKILL_DOC = PROJECT_ROOT / "skills" / "mastering-engineer" / "genre-presets.md"
SPECS_DOC = PROJECT_ROOT / "reference" / "streaming-mastering-specs.md"

_YAML = yaml.safe_load(PRESETS_YAML.read_text(encoding="utf-8"))
_GENRES: dict = _YAML["genres"]
_DEFAULTS: dict = _YAML["defaults"]


def _preset(genre: str, key: str) -> float:
    return float(_GENRES[genre].get(key, _DEFAULTS[key]))


# --------------------------------------------------------------------------
# reference/mastering/genre-specific-presets.md
# --------------------------------------------------------------------------

_ROW = re.compile(r"^\| ([a-z0-9&-]+) \| ([^|]+?) \| ([^|]+?) \| [^|]* \|$")


def _reference_rows() -> list[tuple[str, str, str]]:
    rows = []
    for line in REFERENCE_DOC.read_text(encoding="utf-8").splitlines():
        m = _ROW.match(line)
        if m and m.group(1) != "genre":
            rows.append((m.group(1), m.group(2).strip(), m.group(3).strip()))
    return rows


def test_reference_doc_has_preset_rows() -> None:
    assert len(_reference_rows()) > 50


@pytest.mark.parametrize("genre, lufs, cut", _reference_rows())
def test_reference_doc_row_matches_yaml(genre: str, lufs: str, cut: str) -> None:
    assert genre in _GENRES, f"{genre} is in the doc but not in genre-presets.yaml"
    assert float(lufs) == _preset(genre, "target_lufs"), genre
    m = re.fullmatch(r"(-?\d+(?:\.\d+)?) dB", cut)
    assert m, f"{genre}: high-mid cut {cut!r} is not 'N dB'"
    assert float(m.group(1)) == _preset(genre, "cut_highmid"), genre


# --------------------------------------------------------------------------
# skills/mastering-engineer/genre-presets.md
# --------------------------------------------------------------------------

def _skill_targets() -> list[tuple[str, str]]:
    """(genre, LUFS-target text) for each section that names its preset."""
    found = []
    for section in re.split(r"(?m)^### ", SKILL_DOC.read_text(encoding="utf-8"))[1:]:
        cmd = re.search(r'genre="([^"]+)"', section)
        target = re.search(r"(?m)^\*\*LUFS target\*\*: (.*)$", section)
        if cmd and target:
            found.append((cmd.group(1), target.group(1)))
    return found


def test_skill_doc_has_preset_targets() -> None:
    assert len(_skill_targets()) > 100


@pytest.mark.parametrize("genre, text", _skill_targets())
def test_skill_lufs_target_leads_with_the_yaml_value(genre: str, text: str) -> None:
    """The line opens with the preset's value; advice for sub-styles follows
    in parentheses. A range like "-10 to -12 LUFS" can't be the preset."""
    assert genre in _GENRES, f"{genre} is in the skill but not in genre-presets.yaml"
    m = re.match(r"(-?\d+(?:\.\d+)?) LUFS(?! *to)(?:\s|$)", text)
    assert m, f"{genre}: {text!r} doesn't open with a single LUFS value"
    assert float(m.group(1)) == _preset(genre, "target_lufs"), genre


# --------------------------------------------------------------------------
# Coherence tolerances in the signature docs
# --------------------------------------------------------------------------

_TOLERANCE_KEYS = (
    "coherence_stl_95_lu", "coherence_lra_floor_lu",
    "coherence_low_rms_db", "coherence_vocal_rms_db",
)


@pytest.mark.parametrize("path", [
    SPECS_DOC,
    PROJECT_ROOT / "tools" / "mastering" / "signature_persistence.py",
])
def test_documented_tolerances_are_the_code_defaults(path: Path) -> None:
    """The docs said 1.0 / 6.0 / 2.0 / 1.5; the code uses 0.5 / 1.0 / 2.0 / 2.0."""
    text = path.read_text(encoding="utf-8")
    for key in _TOLERANCE_KEYS:
        m = re.search(rf"^\s*{key}: (-?[\d.]+)", text, re.MULTILINE)
        assert m, f"{key} not shown in {path.name}"
        assert float(m.group(1)) == master_tracks_mod._PRESET_DEFAULTS[key], key
        assert float(m.group(1)) == float(_DEFAULTS[key]), key


# --------------------------------------------------------------------------
# genre_ideal_lra_lu reaches the anchor selector
# --------------------------------------------------------------------------

@pytest.fixture
def shipped_presets(monkeypatch: pytest.MonkeyPatch) -> dict:
    monkeypatch.setattr(master_tracks_mod, "_get_overrides_path", lambda: None)
    return master_tracks_mod.load_genre_presets()


def test_loader_keeps_genre_ideal_lra(shipped_presets: dict) -> None:
    """The loader kept only the keys it listed, so the anchor always used 8.0."""
    assert shipped_presets["pop"]["genre_ideal_lra_lu"] == 5.0
    assert shipped_presets["jazz"]["genre_ideal_lra_lu"] == 7.0
    assert shipped_presets["classical"]["genre_ideal_lra_lu"] == 10.0


def test_ideal_lra_values_are_realistic_ebu_lra() -> None:
    """EBU R128 LRA of a pop/rock song is 4-6 LU (#686 measured 5.06 for a
    realistic song, 3.50 for its master); dynamic genres sit higher. 8.0 for
    every genre favoured the most dynamic track as anchor."""
    assert 4.0 <= float(_DEFAULTS["genre_ideal_lra_lu"]) <= 6.0
    for genre, preset in _GENRES.items():
        ideal = _preset(genre, "genre_ideal_lra_lu")
        target = _preset(genre, "target_lufs")
        if target <= -18.0:
            assert ideal == 10.0, genre
        elif target <= -16.0:
            assert ideal == 7.0, genre
        else:
            assert 4.0 <= ideal <= 6.0, genre


def test_loader_drops_no_scalar_yaml_key(shipped_presets: dict) -> None:
    """Every scalar key the YAML sets survives the loader.

    spectral_reference_energy is a nested curve the flat float loader can't
    hold; the anchor selector's built-in curve is the same as the YAML's.
    """
    keys = set(_DEFAULTS)
    for preset in _GENRES.values():
        keys.update(preset)
    keys.discard("spectral_reference_energy")
    missing = sorted(k for k in keys if k not in shipped_presets["pop"])
    assert missing == []


def test_effective_preset_hands_the_genre_lra_to_the_anchor(
    shipped_presets: dict, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tools.mastering.config import build_effective_preset

    monkeypatch.setattr("tools.mastering.config.load_config", lambda: None)
    bundle = build_effective_preset(genre="classical")
    assert bundle["preset_dict"]["genre_ideal_lra_lu"] == 10.0
