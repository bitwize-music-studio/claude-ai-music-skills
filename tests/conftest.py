"""Shared pytest fixtures for plugin and unit tests."""

import sys
from pathlib import Path
from typing import Any, Dict

import pytest

# Ensure project root is on sys.path for imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.fixtures.audio import (
    make_bass,
    make_bright,
    make_clicks_and_pops,
    make_clipping,
    make_drums,
    make_full_mix,
    make_noisy,
    make_phase_partial,
    make_phase_problem,
    make_silent_gaps,
    make_vocal,
    write_wav,
)
from tools.state.parsers import parse_frontmatter


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Path to the repository root."""
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def skills_dir(project_root) -> Path:
    """Path to skills/ directory."""
    return project_root / "skills"


@pytest.fixture(scope="session")
def templates_dir(project_root) -> Path:
    """Path to templates/ directory."""
    return project_root / "templates"


@pytest.fixture(scope="session")
def reference_dir(project_root) -> Path:
    """Path to reference/ directory."""
    return project_root / "reference"


@pytest.fixture(scope="session")
def genres_dir(project_root) -> Path:
    """Path to genres/ directory."""
    return project_root / "genres"


@pytest.fixture(scope="session")
def config_dir(project_root) -> Path:
    """Path to config/ directory."""
    return project_root / "config"


@pytest.fixture(scope="session")
def all_skill_dirs(skills_dir) -> list:
    """List of all skill directory paths."""
    if not skills_dir.exists():
        return []
    return sorted(
        d for d in skills_dir.iterdir()
        if d.is_dir() and not d.name.startswith('.')
    )


@pytest.fixture(scope="session")
def all_skill_frontmatter(all_skill_dirs) -> Dict[str, Dict[str, Any]]:
    """Dict of skill_name -> parsed frontmatter for all skills."""
    skills = {}
    for skill_dir in all_skill_dirs:
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            skills[skill_dir.name] = {'_error': 'Missing SKILL.md'}
            continue

        content = skill_md.read_text()
        frontmatter = parse_frontmatter(content)

        if not frontmatter and not content.startswith('---'):
            frontmatter = {'_error': 'No frontmatter (missing opening ---)'}
        elif not frontmatter and content.startswith('---'):
            frontmatter = {'_error': 'No frontmatter (missing closing ---)'}

        frontmatter['_path'] = str(skill_md)
        frontmatter['_content'] = content
        skills[skill_dir.name] = frontmatter

    return skills


@pytest.fixture(scope="session")
def claude_md_content(project_root) -> str:
    """Contents of CLAUDE.md."""
    claude_file = project_root / "CLAUDE.md"
    if claude_file.exists():
        return claude_file.read_text()
    return ""


# ---------------------------------------------------------------------------
# Audio fixtures — see tests/fixtures/audio/__init__.py for generators
# ---------------------------------------------------------------------------


@pytest.fixture
def vocal_wav(tmp_path):
    """Formant-shaped vocal with sibilant bursts."""
    data, rate = make_vocal()
    return write_wav(str(tmp_path / "vocal.wav"), data, rate)


@pytest.fixture
def drums_wav(tmp_path):
    """Sharp transients with exponential decay."""
    data, rate = make_drums()
    return write_wav(str(tmp_path / "drums.wav"), data, rate)


@pytest.fixture
def bass_wav(tmp_path):
    """80 Hz fundamental + harmonics."""
    data, rate = make_bass()
    return write_wav(str(tmp_path / "bass.wav"), data, rate)


@pytest.fixture
def full_mix_wav(tmp_path):
    """Layered vocal + drums + bass mix."""
    data, rate = make_full_mix()
    return write_wav(str(tmp_path / "full_mix.wav"), data, rate)


@pytest.fixture
def clipping_wav(tmp_path):
    """Hard-clipped signal (should fail QC)."""
    data, rate = make_clipping()
    return write_wav(str(tmp_path / "clipping.wav"), data, rate)


@pytest.fixture
def phase_problem_wav(tmp_path):
    """Phase-inverted stereo (should fail mono compat)."""
    data, rate = make_phase_problem()
    return write_wav(str(tmp_path / "phase_problem.wav"), data, rate)


@pytest.fixture
def bright_wav(tmp_path):
    """Excessive high-frequency energy (should trigger tinniness)."""
    data, rate = make_bright()
    return write_wav(str(tmp_path / "bright.wav"), data, rate)


@pytest.fixture
def noisy_wav(tmp_path):
    """Signal with elevated noise floor."""
    data, rate = make_noisy()
    return write_wav(str(tmp_path / "noisy.wav"), data, rate)


@pytest.fixture
def clicks_and_pops_wav(tmp_path):
    """Tonal bed + musical transients + injected single-sample spikes."""
    data, rate = make_clicks_and_pops()
    return write_wav(str(tmp_path / "clicks_and_pops.wav"), data, rate)


@pytest.fixture
def silent_gaps_wav(tmp_path):
    """2s audio + 1s silent gap + 2s audio (should fail silence QC)."""
    data, rate = make_silent_gaps()
    return write_wav(str(tmp_path / "silent_gaps.wav"), data, rate)


@pytest.fixture
def phase_partial_wav(tmp_path):
    """90-degree phase shift on R channel — partial cancellation in mono."""
    data, rate = make_phase_partial()
    return write_wav(str(tmp_path / "phase_partial.wav"), data, rate)


@pytest.fixture
def stem_dir(tmp_path):
    """Directory with per-stem WAV files for mixing tests."""
    stems = tmp_path / "stems" / "01-test-track"
    stems.mkdir(parents=True)

    for name, generator in [
        ("vocals", make_vocal),
        ("drums", make_drums),
        ("bass", make_bass),
    ]:
        data, rate = generator(duration=1.5)
        write_wav(str(stems / f"{name}.wav"), data, rate)

    return str(stems)
