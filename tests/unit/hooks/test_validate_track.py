"""Tests for the ``validate_track`` PostToolUse hook.

This hook runs on **every** Write/Edit the user makes. ``hooks/hooks.json``
invokes it as a bare ``python3`` — the *system* interpreter, not the plugin's
3.11+ venv — so it must import and behave correctly on whatever Python the
user happens to have, and it must never crash the session on malformed input.

That combination has already bitten once: PEP 604 (``dict | None``) annotations
evaluated eagerly raised ``TypeError`` at import on Python 3.9, so the hook died
before validating anything and track-frontmatter validation silently never ran
for those users. A silent no-op hook looks exactly like a passing hook, which is
why the annotation-laziness guard at the bottom of this file exists alongside
the behavioural tests.

Usage:
    python -m pytest tests/unit/hooks/test_validate_track.py -v
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

# Import the standalone hook module via importlib (hooks/ is not a package).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

_MODULE_PATH = _PROJECT_ROOT / "hooks" / "validate_track.py"
_spec = importlib.util.spec_from_file_location("validate_track_hook", _MODULE_PATH)
validate_track = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(validate_track)


_TRACK_PATH = "/content/artists/bitwize/albums/synthwave/my-album/tracks/01-opener.md"


def _frontmatter(**fields: str) -> str:
    body = "\n".join(f"{k}: {v}" for k, v in fields.items())
    return f"---\n{body}\n---\n\n## Lyrics\n\nsome words\n"


def _valid_content() -> str:
    return _frontmatter(title="Opener", track_number="1", status="In Progress")


def _write_event(file_path: str, content: str) -> dict:
    """A PostToolUse payload as the Write tool produces it."""
    return {
        "tool_name": "Write",
        "tool_input": {"file_path": file_path, "content": content},
    }


def _run_hook(payload: str) -> subprocess.CompletedProcess:
    """Run the hook end-to-end the way Claude Code does: JSON on stdin."""
    return subprocess.run(
        [sys.executable, str(_MODULE_PATH)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=30,
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestValidTrack:
    def test_valid_track_reports_no_issues(self):
        assert validate_track.validate(_write_event(_TRACK_PATH, _valid_content())) == []

    @pytest.mark.parametrize("status", validate_track.VALID_STATUSES)
    def test_every_documented_status_is_accepted(self, status):
        """All six workflow statuses must pass — the hook is not a bottleneck."""
        content = _frontmatter(title="Opener", track_number="1", status=status)
        assert validate_track.validate(_write_event(_TRACK_PATH, content)) == []

    def test_quoted_values_are_unwrapped(self):
        """YAML values written with quotes still validate."""
        content = '---\ntitle: "Opener"\ntrack_number: 1\nstatus: "Final"\n---\n'
        assert validate_track.validate(_write_event(_TRACK_PATH, content)) == []

    def test_valid_track_exits_zero(self):
        result = _run_hook(json.dumps(_write_event(_TRACK_PATH, _valid_content())))
        assert result.returncode == 0, (result.returncode, result.stderr)
        assert result.stderr == ""


# ---------------------------------------------------------------------------
# Rejection paths
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestInvalidTrack:
    def test_invalid_status_is_reported(self):
        content = _frontmatter(title="Opener", track_number="1", status="Almost Done")
        issues = validate_track.validate(_write_event(_TRACK_PATH, content))
        assert len(issues) == 1
        assert "Almost Done" in issues[0]
        # The message must tell the user what the legal values are.
        assert "In Progress" in issues[0]

    def test_invalid_status_exits_two(self):
        """Exit code 2 is what makes Claude Code surface the failure."""
        content = _frontmatter(title="Opener", track_number="1", status="Almost Done")
        result = _run_hook(json.dumps(_write_event(_TRACK_PATH, content)))
        assert result.returncode == 2, (result.returncode, result.stderr)
        assert "Track frontmatter validation failed" in result.stderr
        assert "Almost Done" in result.stderr

    @pytest.mark.parametrize("missing", ["title", "track_number", "status"])
    def test_each_missing_required_field_is_reported(self, missing):
        fields = {"title": "Opener", "track_number": "1", "status": "Final"}
        del fields[missing]
        issues = validate_track.validate(_write_event(_TRACK_PATH, _frontmatter(**fields)))
        assert issues == [f"Missing required frontmatter field: {missing}"]

    @pytest.mark.parametrize("empty", ["title", "track_number", "status"])
    def test_present_but_empty_required_field_is_reported(self, empty):
        """``status:`` with nothing after it is as broken as an absent key."""
        fields = {"title": "Opener", "track_number": "1", "status": "Final"}
        fields[empty] = ""
        issues = validate_track.validate(_write_event(_TRACK_PATH, _frontmatter(**fields)))
        assert issues == [f"Missing required frontmatter field: {empty}"]

    def test_all_fields_missing_reports_all_three(self):
        content = "---\nfoo: bar\n---\n"
        issues = validate_track.validate(_write_event(_TRACK_PATH, content))
        assert len(issues) == 3
        for field in ("title", "track_number", "status"):
            assert any(field in i for i in issues)

    def test_missing_frontmatter_block_is_reported(self):
        content = "# Opener\n\nJust a markdown file with no YAML header.\n"
        issues = validate_track.validate(_write_event(_TRACK_PATH, content))
        assert issues == ["Track file is missing YAML frontmatter (--- block)."]

    def test_frontmatter_must_be_at_the_top(self):
        """A ``---`` rule further down the file is not frontmatter."""
        content = "# Opener\n\n---\ntitle: Opener\nstatus: Final\n---\n"
        issues = validate_track.validate(_write_event(_TRACK_PATH, content))
        assert issues == ["Track file is missing YAML frontmatter (--- block)."]


# ---------------------------------------------------------------------------
# Scoping: the hook fires on every Write/Edit, so it must ignore non-tracks
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFileScoping:
    @pytest.mark.parametrize(
        "path",
        [
            "/content/artists/bitwize/albums/synthwave/my-album/README.md",
            "/content/artists/bitwize/albums/synthwave/my-album/tracks/notes.txt",
            "/content/tracksnotadir/01-opener.md",
            "/home/bitwize/GitHub/plugin/tools/state/indexer.py",
            "",
        ],
    )
    def test_non_track_paths_are_ignored(self, path):
        """Content that would fail validation is not even looked at."""
        assert validate_track.is_track_file(path) is False
        assert validate_track.validate(_write_event(path, "no frontmatter here")) == []

    def test_non_track_path_exits_zero(self):
        payload = json.dumps(_write_event("/some/README.md", "no frontmatter here"))
        result = _run_hook(payload)
        assert result.returncode == 0, (result.returncode, result.stderr)

    def test_track_path_is_recognised(self):
        assert validate_track.is_track_file(_TRACK_PATH) is True


# ---------------------------------------------------------------------------
# Payload shapes the hook must survive
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPayloadHandling:
    def test_edit_payload_without_content_is_not_validated(self):
        """An Edit shows a diff, not the whole file — nothing to validate."""
        event = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": _TRACK_PATH,
                "old_string": "status: Final",
                "new_string": "status: Bogus Status",
            },
        }
        assert validate_track.get_file_content(event) is None
        assert validate_track.validate(event) == []

    def test_edit_payload_exits_zero(self):
        event = {
            "tool_name": "Edit",
            "tool_input": {"file_path": _TRACK_PATH, "new_string": "status: Bogus"},
        }
        result = _run_hook(json.dumps(event))
        assert result.returncode == 0, (result.returncode, result.stderr)

    def test_empty_payload_is_tolerated(self):
        assert validate_track.validate({}) == []

    def test_missing_tool_input_is_tolerated(self):
        assert validate_track.validate({"tool_name": "Write"}) == []

    @pytest.mark.parametrize(
        "stdin",
        ["", "not json at all", "{ broken json", "{'single': 'quotes'}"],
    )
    def test_malformed_stdin_exits_zero_without_traceback(self, stdin):
        """A hook crash surfaces as a scary error in the user's session.

        Whatever arrives on stdin, this hook must degrade to "do nothing" —
        never a traceback, never a non-zero exit.
        """
        result = _run_hook(stdin)
        assert "Traceback" not in result.stderr, result.stderr
        assert result.returncode == 0, (result.returncode, result.stderr)

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "Known hook bug: main() catches only (JSONDecodeError, EOFError), so "
            "stdin holding *well-formed* JSON that is not an object reaches "
            "validate() and dies on `data.get` with AttributeError — traceback and "
            "a non-zero exit in the user's session. Not reachable from Claude Code "
            "today (it always sends an object), so this is a defence-in-depth gap, "
            "not a live failure. Remove the xfail when main() guards the shape."
        ),
    )
    @pytest.mark.parametrize("stdin", ["[1, 2, 3]", "null", '"a string"', "42"])
    def test_non_object_json_stdin_exits_zero_without_traceback(self, stdin):
        result = _run_hook(stdin)
        assert "Traceback" not in result.stderr, result.stderr
        assert result.returncode == 0, (result.returncode, result.stderr)


# ---------------------------------------------------------------------------
# Regression guard: the hook runs on the SYSTEM python3, not the plugin venv
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestOldPythonCompatibility:
    """Guards the PEP 604 import crash from coming back.

    ``hooks.json`` runs this file with a bare ``python3``. The module uses
    ``dict | None`` / ``str | None`` / ``list[str]`` annotations, which are a
    ``TypeError`` at *import* time on Python 3.9 unless annotation evaluation is
    deferred by ``from __future__ import annotations``. When that import went
    missing the hook died on startup and validation silently stopped happening.

    The primary assertion checks the *effect* (annotations are unevaluated
    strings) rather than the presence of a source line, because that is what
    actually determines whether old interpreters can import the module: a
    source grep passes on a commented-out or shadowed import, and it would also
    keep passing if someone re-introduced an eagerly-evaluated annotation
    elsewhere. The source-line check is kept as a secondary, diagnostic
    assertion so a failure points straight at the fix.
    """

    def test_annotations_are_lazily_evaluated(self):
        """No function annotation may be a live object — all must be strings."""
        offenders = []
        for name in ("is_track_file", "extract_frontmatter", "get_file_content", "validate"):
            fn = getattr(validate_track, name)
            for param, annotation in fn.__annotations__.items():
                if not isinstance(annotation, str):
                    offenders.append(f"{name}({param}): {annotation!r}")
        assert not offenders, (
            "validate_track.py annotations are evaluated eagerly: "
            + ", ".join(offenders)
            + ". Add `from __future__ import annotations` — without it the PEP 604 "
            "`dict | None` annotations raise TypeError at import on Python 3.9 and "
            "the hook silently stops validating."
        )

    def test_future_annotations_import_is_present(self):
        """Diagnostic companion to the check above: name the missing line."""
        source = _MODULE_PATH.read_text(encoding="utf-8")
        assert "from __future__ import annotations" in source

    def test_module_compiles_and_defines_the_hook_entrypoints(self):
        """A module that fails to import is a hook that silently never runs."""
        for name in ("main", "validate", "REQUIRED_FIELDS", "VALID_STATUSES"):
            assert hasattr(validate_track, name), name
        assert validate_track.REQUIRED_FIELDS == ["title", "track_number", "status"]
