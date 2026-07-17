"""Multi-process contention test for the state lock + atomic write path.

The other lock tests (``test_lock_backoff.py``) are single-process: they take a
lock in one file descriptor and contend from another in the *same* interpreter.
This one spawns real ``sys.executable`` subprocesses (uniform under pytest-xdist
and on all three OSes — no ``multiprocessing`` start-method quirks) that point
``tools.state.indexer``'s cache constants at a SHARED tmp location and hammer it:

* N writer processes each ``write_state`` a distinct ``{writer, seq}`` payload in
  a loop.
* One reader process ``read_state``s in a loop while the writers run.

What this test actually pins (be honest about scope):

1. The real cross-process lock primitive runs — ``fcntl.flock`` on POSIX,
   ``msvcrt.locking`` on Windows — under genuine multi-process contention (not
   two fds in one interpreter). It proves that primitive does not deadlock,
   livelock, or crash a worker when N processes fight for the lock: every worker
   exits 0 within a hard cap.
2. ``os.replace`` is atomic on the host OS — the reader never observes a partial
   file, and the final ``state.json`` is exactly one writer's last write (no
   interleaved bytes).
3. No temp-file leaks: ``write_state``'s ``.state_*.tmp`` files are all consumed
   by ``os.replace`` (or unlinked on error), so none survive.

What this test does NOT prove: that the *lock* is what prevents torn writes. It
is not — ``write_state`` publishes each state through a UNIQUE ``NamedTemporaryFile``
+ atomic ``os.replace``, so torn/interleaved reads are structurally impossible
whether or not the lock is held (disabling the lock and re-running keeps this
green). The lock serializes writers so they don't clobber each other's *temp
files* or churn the same rename target, and it is exercised here for contention
safety — but atomicity is owned by the unique-tempfile design, not the lock.

The autouse ``_isolate_state_cache`` fixture in ``tests/conftest.py`` only
redirects the constants for *this* pytest process; fresh subprocesses inherit
nothing, so each worker re-points the constants explicitly from an env var. The
real ``~/.bitwize-music`` is never touched.

read_state() contract (pinned from tools/state/indexer.py, do not invent one):
    * missing file            -> returns ``None``
    * corrupt / partial JSON,
      or a JSON non-object    -> copies the file to ``state.<ts>.corrupt`` and
                                 returns ``{}`` (it never raises)
    * a valid JSON object     -> returns it
The reader's ``None`` / ``{}`` / marker-less branches assert this contract as
live documentation, but they are UNREACHABLE-BY-DESIGN while the atomic-replace
guarantee holds: after the seed, no read can ever legitimately see a partial
file. They exist to fail loudly if a future refactor breaks atomicity (e.g.
switches ``write_state`` to an in-place truncating write) — not because the
current code can hit them. The ``state.*.corrupt`` check is the same: on-disk
proof read_state never had to quarantine a torn read.
"""

from __future__ import annotations

import contextlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]

# Tuned so the whole thing runs in a couple of seconds locally while still
# forcing real lock contention. Bump WRITER_ITERS / N_WRITERS to stress harder;
# drop them if a slow CI box brushes the hard cap.
N_WRITERS = 4
WRITER_ITERS = 15
READER_ITERS = 400
# Generous hard cap — the *only* wall-clock assertion. Never tune this to be
# tight; process spawn + fsync-per-write on a loaded CI box is unpredictable.
HARD_CAP_SECONDS = 60.0
SCHEMA_VERSION = "1.4.0"

# Worker body. Kept as a module written to tmp (rather than ``-c``) so tracebacks
# from a failing worker point at real line numbers. It re-points the indexer
# constants from env BEFORE any write/read, so it can never touch the developer's
# real ~/.bitwize-music cache.
_WORKER_SRC = '''\
import json
import os
import random
import sys
from pathlib import Path

sys.path.insert(0, os.environ["STRESS_PROJECT_ROOT"])

import tools.state.indexer as indexer

cache_dir = Path(os.environ["STRESS_CACHE_DIR"])
indexer.CACHE_DIR = cache_dir
indexer.STATE_FILE = cache_dir / "state.json"
indexer.LOCK_FILE = cache_dir / "state.lock"

MODE = sys.argv[1]
WORKER_ID = int(sys.argv[2])
ITERS = int(sys.argv[3])
FINAL_SEQ = int(sys.argv[4])
SCHEMA_VERSION = sys.argv[5]

# Distinct RNG per worker/mode so they jitter out of lockstep.
rng = random.Random((hash(MODE) & 0xFFFF) * 1000 + WORKER_ID)


def _sleep_jitter(hi):
    t = rng.uniform(0.0, hi)
    if t:
        import time
        time.sleep(t)


if MODE == "writer":
    for seq in range(ITERS):
        state = {
            "version": SCHEMA_VERSION,
            "writer": WORKER_ID,
            "seq": seq,
            "marker": "w%d-s%d" % (WORKER_ID, seq),
            "albums": {},
        }
        indexer.write_state(state)
        _sleep_jitter(0.006)
    sys.exit(0)

elif MODE == "reader":
    for _ in range(ITERS):
        state = indexer.read_state()
        if state is None:
            sys.stderr.write("READER_SAW_NONE (missing file mid-run)\\n")
            sys.exit(11)
        if not isinstance(state, dict):
            sys.stderr.write("READER_SAW_NON_DICT: %r\\n" % (state,))
            sys.exit(12)
        if "marker" not in state:
            # An empty dict is read_state's quarantine sentinel: it only returns
            # {} after backing up a corrupt/partial file -> a torn read happened.
            sys.stderr.write("READER_SAW_TORN: %r\\n" % (state,))
            sys.exit(13)
        _sleep_jitter(0.002)
    sys.exit(0)

sys.stderr.write("UNKNOWN_MODE: %r\\n" % (MODE,))
sys.exit(99)
'''


def _write_seed(state_file: Path) -> None:
    """Seed a valid state so the reader never legitimately observes ``None``."""
    seed = {
        "version": SCHEMA_VERSION,
        "writer": -1,
        "seq": -1,
        "marker": "seed",
        "albums": {},
    }
    state_file.write_text(json.dumps(seed, indent=2) + "\n", encoding="utf-8")


def _expected_final(writer_id: int) -> dict[str, object]:
    """The exact payload a writer publishes on its last iteration."""
    last = WRITER_ITERS - 1
    return {
        "version": SCHEMA_VERSION,
        "writer": writer_id,
        "seq": last,
        "marker": f"w{writer_id}-s{last}",
        "albums": {},
    }


def test_multiprocess_lock_stress(tmp_path: Path) -> None:
    """N writers + 1 reader contend on the shared state file.

    Asserts the cross-process lock primitive survives real contention (no
    deadlock/hang/crash — every worker exits 0 within the hard cap), that
    ``os.replace`` is atomic (final file is one writer's whole last write, reader
    never sees a partial one), and that no ``.tmp`` files leak. See the module
    docstring for why atomicity here is owned by the unique-tempfile design, not
    the lock.
    """
    cache_dir = tmp_path / "stress_cache"
    cache_dir.mkdir()
    state_file = cache_dir / "state.json"
    _write_seed(state_file)

    worker_py = tmp_path / "_lock_stress_worker.py"
    worker_py.write_text(_WORKER_SRC, encoding="utf-8")

    env = {
        **_base_env(),
        "STRESS_PROJECT_ROOT": str(PROJECT_ROOT),
        "STRESS_CACHE_DIR": str(cache_dir),
    }

    # Spawn everyone up front so writers and the reader genuinely overlap.
    procs: list[tuple[str, subprocess.Popen[str]]] = []
    procs.append((
        "reader",
        _spawn(worker_py, "reader", 0, READER_ITERS, WRITER_ITERS - 1, env),
    ))
    for wid in range(N_WRITERS):
        procs.append((
            f"writer-{wid}",
            _spawn(worker_py, "writer", wid, WRITER_ITERS, WRITER_ITERS - 1, env),
        ))

    start = time.monotonic()
    deadline = start + HARD_CAP_SECONDS
    failures: list[str] = []
    for name, proc in procs:
        remaining = deadline - time.monotonic()
        try:
            _out, err = proc.communicate(timeout=max(remaining, 0.001))
        except subprocess.TimeoutExpired:
            # Kill AND reap every worker before failing so no zombies survive the
            # test (CI hygiene, especially under -n auto where the xdist worker
            # keeps running further tests).
            for _n, p in procs:
                p.kill()
                with contextlib.suppress(Exception):
                    p.wait(timeout=5)
            pytest.fail(
                f"lock stress exceeded hard cap of {HARD_CAP_SECONDS}s "
                f"(worker {name} still running) — a lock deadlock or lost wakeup?"
            )
        if proc.returncode != 0:
            failures.append(f"{name} exited {proc.returncode}: {err.strip()!r}")
    elapsed = time.monotonic() - start

    assert not failures, "worker process failure(s):\n" + "\n".join(failures)

    # Final file must be intact JSON equal to *some* writer's last write — proof
    # that atomic replace never left torn/interleaved content behind.
    final_text = state_file.read_text(encoding="utf-8")
    final = json.loads(final_text)  # raises -> test fails if not valid JSON
    assert isinstance(final, dict), f"final state is not a JSON object: {final!r}"
    expected_finals = [_expected_final(wid) for wid in range(N_WRITERS)]
    assert final in expected_finals, (
        "final state.json is not any writer's last write (torn/interleaved?): "
        f"{final!r}"
    )
    # It must be a *final* write specifically (seq == last), never a stale seed
    # or mid-loop payload — the globally-last os.replace is a writer's seq N-1.
    assert final["seq"] == WRITER_ITERS - 1

    # No temp files may survive: write_state os.replace's its NamedTemporaryFile
    # (.state_*.tmp) into place on success and unlinks it on error.
    leftover_tmp = list(cache_dir.glob("*.tmp"))
    assert not leftover_tmp, f"leftover temp files after stress: {leftover_tmp}"

    # No quarantine backups: read_state only writes state.*.corrupt when it had
    # to recover a torn/partial read. None here == the reader never saw one.
    corrupt = list(cache_dir.glob("state.*.corrupt"))
    assert not corrupt, f"read_state quarantined a torn read: {corrupt}"

    # Hard cap is the only timing assertion; keep it loose. (Local runs land in
    # a few seconds; this just documents the bound and fails loudly if a future
    # regression makes the lock path pathologically slow.)
    assert elapsed < HARD_CAP_SECONDS


def _base_env() -> dict[str, str]:
    # Inherit the parent env (PATH, venv, SystemRoot on Windows) so the child
    # interpreter starts cleanly; the STRESS_* keys are layered on by the caller.
    return dict(os.environ)


def _spawn(
    worker_py: Path,
    mode: str,
    worker_id: int,
    iters: int,
    final_seq: int,
    env: dict[str, str],
) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [
            sys.executable,
            str(worker_py),
            mode,
            str(worker_id),
            str(iters),
            str(final_seq),
            SCHEMA_VERSION,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        text=True,
    )
