#!/usr/bin/env python3
"""Combine per-OS coverage data, prove the cross-OS path mapping worked, gate.

Background
----------
Coverage used to be measured on the ubuntu leg only. Every ``sys.platform ==
"win32"`` / darwin branch in ``tools/`` and ``servers/`` is unreachable on Linux,
so the headline percentage and the fail-under gate said nothing at all about the
platform-specific code — which is precisely where this project's real bugs have
lived (a hardcoded ``venv/bin/python3``, ``os.fsync`` on a read-only handle,
POSIX-only slug sanitisation, an unconditional ``import fcntl``, a bare
``os.replace`` with no Windows retry).

All three legs now measure coverage and upload their raw data. This script
merges them into one picture.

Why the assertions matter
-------------------------
``coverage combine`` fails *silently* when the ``[tool.coverage.paths]`` mapping
is wrong: it emits "Combined 3 files", the data keeps three separate absolute
paths for every source file, and the reported total collapses back to roughly
the Linux-only number. That failure mode looks exactly like success, so it is
checked explicitly rather than assumed:

1. Every measured path must live inside this checkout (proves the macOS and
   Windows absolute roots were rewritten, not carried through verbatim).
2. A known win32-only sentinel line must be covered (proves Windows data was
   really merged in, rather than merely mapped to the right names).
"""

from __future__ import annotations

import argparse
import io
import shutil
import sys
import tempfile
from pathlib import Path

from coverage import Coverage
from coverage.sqldata import CoverageData

REPO_ROOT = Path(__file__).resolve().parents[2]

# A line that only ever executes on Windows. Located by source text rather than
# by number so routine edits to indexer.py do not silently disarm the check.
SENTINEL_FILE = Path("tools/state/indexer.py")
SENTINEL_TEXT = "import msvcrt"


def sentinel_line() -> int:
    """Line number of the win32-only sentinel statement."""
    path = REPO_ROOT / SENTINEL_FILE
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip() == SENTINEL_TEXT:
            return lineno
    raise SystemExit(
        f"[FAIL] sentinel {SENTINEL_TEXT!r} no longer exists in {SENTINEL_FILE}. "
        "Pick another win32-only line and update SENTINEL_TEXT."
    )


def combine(data_files: list[Path], target: Path) -> Coverage:
    """Combine `data_files` into `target`, applying the [paths] mapping."""
    cov = Coverage(data_file=str(target))
    # keep=True: inputs are reused for the per-leg reports below.
    cov.combine([str(p) for p in data_files], keep=True)
    cov.save()
    return cov


def percent(cov: Coverage) -> float:
    """Total covered percentage, without printing the per-file table."""
    return cov.report(file=io.StringIO())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "data_dir",
        type=Path,
        help="directory holding the per-OS coverage-<os>.dat files",
    )
    parser.add_argument(
        "--fail-under",
        type=float,
        required=True,
        help="minimum combined coverage percentage",
    )
    parser.add_argument(
        "--expect-legs",
        type=int,
        default=3,
        help="number of per-OS data files that must be present",
    )
    args = parser.parse_args()

    legs = sorted(args.data_dir.rglob("coverage-*.dat"))
    print(f"Found {len(legs)} per-OS coverage data file(s):")
    for leg in legs:
        print(f"  {leg.name}  ({leg.stat().st_size} bytes)")

    if len(legs) != args.expect_legs:
        print(
            f"\n[FAIL] expected {args.expect_legs} legs, found {len(legs)}. "
            "A missing leg would quietly weaken the gate, so this is fatal."
        )
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)

        # Order matters: the mapping assertions run BEFORE any reporting.
        # Reporting on unmapped data dies with a bare `NoSource: no source for
        # code: '/Users/runner/...'` traceback, which tells a future maintainer
        # nothing about the real cause.
        combined_path = tmpdir / "combined"
        cov = combine(legs, combined_path)

        data = CoverageData(basename=str(combined_path))
        data.read()
        measured = sorted(data.measured_files())

        # Assertion 1 — everything mapped into this checkout.
        stray = [f for f in measured if not f.startswith(str(REPO_ROOT))]
        if stray:
            print(
                f"\n[FAIL] {len(stray)} measured path(s) were not mapped into "
                f"{REPO_ROOT}. The [tool.coverage.paths] section in "
                "pyproject.toml is not matching the runner layouts, so this "
                "'combine' is really three disjoint reports stapled together."
            )
            for f in stray[:10]:
                print(f"  {f}")
            return 1
        print(f"\n[OK] all {len(measured)} measured paths mapped into the checkout")

        # Assertion 2 — Windows-only code actually merged in.
        line = sentinel_line()
        sentinel_path = str(REPO_ROOT / SENTINEL_FILE)
        covered = set(data.lines(sentinel_path) or ())
        if line not in covered:
            print(
                f"\n[FAIL] win32-only sentinel {SENTINEL_FILE}:{line} "
                f"({SENTINEL_TEXT!r}) is NOT covered in the combined data.\n"
                "       Either the Windows leg contributed nothing or its paths "
                "did not merge. That is the exact blind spot this job exists to "
                "close, so it fails rather than reporting a Linux-only number."
            )
            return 1
        print(
            f"[OK] win32-only sentinel {SENTINEL_FILE}:{line} is covered — "
            "Windows data really merged"
        )

        # Per-leg totals, for a legible before/after in the job log. Each leg is
        # combined on its own so the same path mapping is applied.
        print("\nPer-leg coverage (each mapped into this checkout):")
        per_leg: dict[str, float] = {}
        for leg in legs:
            solo = tmpdir / f"solo-{leg.stem}"
            per_leg[leg.stem] = percent(combine([leg], solo))
            print(f"  {leg.stem:<28} {per_leg[leg.stem]:6.2f}%")

        total = percent(cov)
        best_leg = max(per_leg.values())
        print(f"\nCombined coverage: {total:.2f}%")
        print(f"Best single leg:   {best_leg:.2f}%  (+{total - best_leg:.2f} pts from merging)")

        # The union of measurements can never cover less than any single leg;
        # if it does, the combine is broken in a way the checks above missed.
        if total + 1e-9 < best_leg:
            print("\n[FAIL] combined total is below a single leg — combine is broken.")
            return 1

        # Persist the merged data + HTML next to the workspace for the artifact.
        #
        # NOT named `.coverage.combined`: that matches the `.coverage.*` glob
        # coverage itself uses for parallel data files, so leaving one in the
        # repo root makes the next `pytest --cov -n auto` silently absorb it
        # into its own results. Observed while building this script — a stray
        # merged file inflated a local Linux-only run by the exact set of
        # win32 lines it carried, which is precisely the kind of fake number
        # this job exists to prevent.
        shutil.copy(combined_path, REPO_ROOT / "coverage-combined.dat")
        cov.html_report(directory=str(REPO_ROOT / "coverage-html-combined"))

        if total < args.fail_under:
            print(
                f"\n[FAIL] combined coverage {total:.2f}% is below the "
                f"{args.fail_under}% gate."
            )
            return 1

    print(f"\n[OK] combined coverage {total:.2f}% meets the {args.fail_under}% gate")
    return 0


if __name__ == "__main__":
    sys.exit(main())
