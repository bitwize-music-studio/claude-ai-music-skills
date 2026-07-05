"""Regression tests for issue #409.

Batch mode must exclude the ``--reference`` WAV from the target list
regardless of how the reference path is supplied (absolute, ``./``-prefixed,
or a bare relative name). The original code compared the glob output
(always relative, e.g. ``PosixPath('ref.wav')``) against ``Path(args.reference)``
with a lexical ``f != reference_path``; an absolute ``--reference`` never
compared equal, so the professionally-mastered reference was re-mastered as
its own target and written into the delivery set.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Import the module under test
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Force-mock matchering before importing the module so tests behave
# consistently regardless of whether matchering is installed.
_MOCK_DEPS = ["matchering"]
_SAVED_DEPS = {dep: sys.modules.get(dep) for dep in _MOCK_DEPS}
for dep in _MOCK_DEPS:
    sys.modules[dep] = MagicMock()

from tools.mastering import reference_master as mod

# Restore original modules to avoid polluting later tests
for dep, original in _SAVED_DEPS.items():
    if original is None:
        sys.modules.pop(dep, None)
    else:
        sys.modules[dep] = original


def _target_names(mock_master) -> list[str]:
    """Filenames passed as the *target* (first positional arg) to each call."""
    return [c.args[0].name for c in mock_master.call_args_list]


@pytest.mark.unit
class TestReferenceExcludedFromBatch:
    """The reference WAV living inside the batch dir must never be a target."""

    @patch.object(mod, "master_with_reference")
    def test_absolute_reference_is_excluded(self, mock_master, tmp_path, monkeypatch):
        # Reference sits *inside* the working dir alongside the tracks.
        work_dir = tmp_path / "tracks"
        work_dir.mkdir()
        (work_dir / "reference.wav").write_bytes(b"ref")
        (work_dir / "track1.wav").write_bytes(b"t1")
        (work_dir / "track2.wav").write_bytes(b"t2")
        monkeypatch.chdir(work_dir)

        # --reference supplied as an ABSOLUTE path (the real #409 trigger).
        abs_ref = (work_dir / "reference.wav").resolve()
        assert abs_ref.is_absolute()

        monkeypatch.setattr(
            "sys.argv",
            ["reference_master.py", "--reference", str(abs_ref),
             "--output-dir", str(tmp_path / "mastered")],
        )
        mod.main()

        targets = _target_names(mock_master)
        # The reference must NOT be re-mastered as its own target.
        assert "reference.wav" not in targets, (
            f"reference re-mastered as a target: {targets}"
        )
        assert set(targets) == {"track1.wav", "track2.wav"}
        assert mock_master.call_count == 2

    @patch.object(mod, "master_with_reference")
    def test_relative_reference_still_excluded(self, mock_master, tmp_path, monkeypatch):
        # Regression guard: the bare-relative form must keep working.
        work_dir = tmp_path / "tracks"
        work_dir.mkdir()
        (work_dir / "reference.wav").write_bytes(b"ref")
        (work_dir / "track1.wav").write_bytes(b"t1")
        (work_dir / "track2.wav").write_bytes(b"t2")
        monkeypatch.chdir(work_dir)

        monkeypatch.setattr(
            "sys.argv",
            ["reference_master.py", "--reference", "reference.wav",
             "--output-dir", str(tmp_path / "mastered")],
        )
        mod.main()

        targets = _target_names(mock_master)
        assert "reference.wav" not in targets
        assert set(targets) == {"track1.wav", "track2.wav"}
        assert mock_master.call_count == 2

    @patch.object(mod, "master_with_reference")
    def test_dot_prefixed_reference_is_excluded(self, mock_master, tmp_path, monkeypatch):
        # ``./ref.wav`` is normalized by pathlib, but assert it explicitly.
        work_dir = tmp_path / "tracks"
        work_dir.mkdir()
        (work_dir / "reference.wav").write_bytes(b"ref")
        (work_dir / "track1.wav").write_bytes(b"t1")
        monkeypatch.chdir(work_dir)

        monkeypatch.setattr(
            "sys.argv",
            ["reference_master.py", "--reference", "./reference.wav",
             "--output-dir", str(tmp_path / "mastered")],
        )
        mod.main()

        targets = _target_names(mock_master)
        assert "reference.wav" not in targets
        assert set(targets) == {"track1.wav"}
        assert mock_master.call_count == 1
