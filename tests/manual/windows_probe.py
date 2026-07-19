#!/usr/bin/env python3
"""Manual probe: answer the Windows questions CI structurally cannot.

Run this ON A REAL WINDOWS HOST. It settles open questions that the 3-OS CI
matrix cannot reach, because CI sets ``PYTHONUTF8=1`` job-wide and because no
runner reproduces "a user has this file open in an editor".

    python tests\\manual\\windows_probe.py

Safe by construction: everything happens under a temp directory, and the real
``~/.bitwize-music`` is never read or written. Nothing here mutates the repo.

Exit code is 0 if the probe ran, regardless of individual findings — this is a
diagnostic, not a gate. Read the report.
"""

from __future__ import annotations

import json
import locale
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

FINDINGS: list[tuple[str, str, str]] = []  # (status, title, detail)


def record(status: str, title: str, detail: str = "") -> None:
    FINDINGS.append((status, title, detail))
    icon = {"PASS": "[PASS]", "FAIL": "[FAIL]", "INFO": "[INFO]", "WARN": "[WARN]"}[status]
    print(f"{icon} {title}")
    if detail:
        for line in detail.splitlines():
            print(f"        {line}")


def section(name: str) -> None:
    print(f"\n{'=' * 70}\n{name}\n{'=' * 70}")


# ---------------------------------------------------------------------------
# 0. Environment
# ---------------------------------------------------------------------------
def probe_environment() -> None:
    section("0. Environment")
    record("INFO", f"platform.system() = {platform.system()} ({platform.release()})")
    record("INFO", f"sys.platform = {sys.platform}")
    record("INFO", f"Python = {sys.version.split()[0]} at {sys.executable}")
    record("INFO", f"locale.getpreferredencoding(False) = {locale.getpreferredencoding(False)!r}")
    record("INFO", f"sys.stdout.encoding = {sys.stdout.encoding!r}")
    record("INFO", f"PYTHONUTF8 = {os.environ.get('PYTHONUTF8', '(unset)')!r}")
    if os.environ.get("PYTHONUTF8"):
        record(
            "WARN",
            "PYTHONUTF8 is SET — this masks the cp1252 conditions we are trying to test",
            "Re-run with it unset:  set PYTHONUTF8=   (cmd)   /   $env:PYTHONUTF8=$null  (pwsh)",
        )
    ff = shutil.which("ffmpeg")
    record("INFO" if ff else "WARN", f"ffmpeg on PATH: {ff or '(not found — section 2 will be skipped)'}")


# ---------------------------------------------------------------------------
# 1. find_font() — does #502 actually resolve a font here?
# ---------------------------------------------------------------------------
def probe_font() -> str | None:
    section("1. find_font() on this host  (PR #502)")
    try:
        from tools.shared.fonts import find_font
    except Exception as e:  # pragma: no cover - probe
        record("FAIL", "could not import tools.shared.fonts", repr(e))
        return None

    font = find_font()
    if not font:
        record("FAIL", "find_font() returned None — promo video has no font on this host")
        sysroot = os.environ.get("SYSTEMROOT") or os.environ.get("WINDIR") or r"C:\Windows"
        fonts_dir = Path(sysroot) / "Fonts"
        present = [p.name for p in fonts_dir.glob("*.ttf")][:15] if fonts_dir.is_dir() else []
        record("INFO", f"{fonts_dir} exists={fonts_dir.is_dir()}", f"sample: {present}")
        return None

    record("PASS", f"find_font() -> {font}", f"exists={Path(font).exists()}")
    return font


# ---------------------------------------------------------------------------
# 2. THE BIG ONE: does ffmpeg drawtext accept these paths as the product builds them?
# ---------------------------------------------------------------------------
def probe_drawtext(font: str | None) -> None:
    section("2. ffmpeg drawtext escaping  (the open question)")
    if not shutil.which("ffmpeg"):
        record("WARN", "ffmpeg not on PATH — skipping")
        return
    if not font:
        record("WARN", "no font resolved — skipping")
        return

    tmp = Path(tempfile.mkdtemp(prefix="wprobe_"))
    textfile = tmp / "title.txt"
    textfile.write_text("Probe Title", encoding="utf-8")
    out = tmp / "frame.png"

    def try_variant(name: str, fontfile_expr: str, textfile_expr: str) -> bool:
        """Render one frame with the given expressions. True == ffmpeg accepted it."""
        vf = (
            f"drawtext=textfile={textfile_expr}:"
            f"fontfile={fontfile_expr}:"
            f"fontsize=24:fontcolor=white:x=10:y=10"
        )
        cmd = [
            "ffmpeg", "-y", "-v", "error",
            "-f", "lavfi", "-i", "color=c=black:s=320x240:d=1",
            "-vf", vf, "-frames:v", "1", str(out),
        ]
        if out.exists():
            out.unlink()
        try:
            r = subprocess.run(
                cmd, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=60,
            )
        except Exception as e:  # pragma: no cover - probe
            record("FAIL", f"variant {name!r} raised", repr(e))
            return False
        ok = r.returncode == 0 and out.exists() and out.stat().st_size > 0
        detail = f"vf = {vf}"
        if not ok:
            detail += f"\nrc={r.returncode}  stderr: {(r.stderr or '').strip()[:300]}"
        record("PASS" if ok else "FAIL", f"variant {name}", detail)
        return ok

    raw_font, raw_text = font, str(textfile)
    fwd_font, fwd_text = font.replace("\\", "/"), str(textfile).replace("\\", "/")
    # ffmpeg filtergraph: ':' separates options and '\' escapes, so a drive
    # letter needs the colon escaped; forward slashes sidestep backslash escaping.
    esc_font = fwd_font.replace(":", "\\:")
    esc_text = fwd_text.replace(":", "\\:")

    print("\n-- exactly what the product builds today (fontfile unquoted, textfile single-quoted) --")
    product_ok = try_variant("PRODUCT-AS-IS  fontfile=<raw>  textfile='<raw>'", raw_font, f"'{raw_text}'")

    print("\n-- candidate fixes --")
    results = {
        "A forward-slash, both unquoted": try_variant("A", fwd_font, fwd_text),
        "B forward-slash + escaped colon, unquoted": try_variant("B", esc_font, esc_text),
        "C single-quoted, forward-slash": try_variant("C", f"'{fwd_font}'", f"'{fwd_text}'"),
        "D single-quoted, escaped colon": try_variant("D", f"'{esc_font}'", f"'{esc_text}'"),
        "E raw backslash, both single-quoted": try_variant("E", f"'{raw_font}'", f"'{raw_text}'"),
    }

    section("2b. VERDICT")
    if product_ok:
        record("PASS", "The product's current filtergraph WORKS on this host as-is",
               "No caller change needed. The #502 font fix was sufficient.")
    else:
        winners = [k for k, v in results.items() if v]
        if winners:
            record("FAIL", "Product filtergraph is BROKEN on Windows — but a fix works",
                   "Working variant(s):\n  " + "\n  ".join(winners) +
                   "\n\nThis is the escaping generate_promo_video.py must apply.")
        else:
            record("FAIL", "Product filtergraph broken AND no tested variant worked",
                   "Paste the stderr above back — the fix needs more digging.")

    shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# 3. atomic_write_text under a REAL open handle (PR #497)
# ---------------------------------------------------------------------------
def probe_atomic_write() -> None:
    section("3. atomic_write_text under real Windows file contention  (PR #497)")
    try:
        sys.path.insert(0, str(REPO_ROOT / "servers" / "bitwize-music-server"))
        from handlers._atomic import atomic_write_text
    except Exception as e:
        record("FAIL", "could not import handlers._atomic", repr(e))
        return

    tmp = Path(tempfile.mkdtemp(prefix="wprobe_atomic_"))
    target = tmp / "README.md"
    target.write_text("original\n", encoding="utf-8")

    # Baseline: no contention.
    try:
        atomic_write_text(target, "updated-1\n")
        record("PASS", "atomic_write_text with no contention",
               f"content={target.read_text(encoding='utf-8').strip()!r}")
    except Exception as e:
        record("FAIL", "atomic_write_text failed with NO contention", repr(e))

    # Contended: hold the target open the way an editor/AV would while replacing.
    try:
        holder = open(target, encoding="utf-8")  # noqa: SIM115 - deliberate
        holder.read()
        t0 = time.monotonic()
        try:
            atomic_write_text(target, "updated-2\n")
            elapsed = time.monotonic() - t0
            record("PASS", "atomic_write_text SUCCEEDED while the file was held open",
                   f"took {elapsed * 1000:.0f}ms — the #497 retry did its job\n"
                   f"content={target.read_text(encoding='utf-8').strip()!r}")
        except OSError as e:
            elapsed = time.monotonic() - t0
            record("FAIL", "atomic_write_text RAISED while the file was held open",
                   f"after {elapsed * 1000:.0f}ms: {e!r}\n"
                   f"winerror={getattr(e, 'winerror', None)}\n"
                   "If winerror is 5 or 32 the retry budget was exhausted; "
                   "any other value means it was classed non-transient and re-raised.")
        finally:
            holder.close()
    except Exception as e:  # pragma: no cover - probe
        record("WARN", "could not run the contention case", repr(e))

    shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# 4. The track hook on native Windows paths (PR #502)
# ---------------------------------------------------------------------------
def probe_hook() -> None:
    section("4. validate_track hook on native Windows paths  (PR #502)")
    hook = REPO_ROOT / "hooks" / "validate_track.py"
    if not hook.exists():
        record("FAIL", f"hook not found at {hook}")
        return

    win_path = r"C:\Users\probe\music\artists\x\albums\y\z\tracks\01-song.md"
    bad = "---\ntitle: X\n---\n"  # missing track_number + status
    payload = json.dumps({"tool_input": {"file_path": win_path, "content": bad}})

    r = subprocess.run(
        [sys.executable, str(hook)], input=payload, capture_output=True,
        text=True, encoding="utf-8", errors="replace", timeout=60,
    )
    if r.returncode == 2 and "Missing required frontmatter field" in (r.stderr or ""):
        record("PASS", "hook FIRES on a native Windows track path and reports issues",
               f"exit={r.returncode}\n{(r.stderr or '').strip()[:200]}")
    elif r.returncode == 0:
        record("FAIL", "hook silently no-opped on a native Windows path",
               "This is the bug #502 was supposed to fix — report back.")
    else:
        record("WARN", f"unexpected hook result exit={r.returncode}",
               f"stderr: {(r.stderr or '').strip()[:300]}")

    # A non-track path must stay quiet.
    r2 = subprocess.run(
        [sys.executable, str(hook)],
        input=json.dumps({"tool_input": {"file_path": r"C:\x\soundtracks\01.md", "content": bad}}),
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
    )
    record("PASS" if r2.returncode == 0 else "FAIL",
           f"soundtracks\\ correctly ignored (exit={r2.returncode})")


# ---------------------------------------------------------------------------
# 5. subprocess unicode decoding (PR #498) — the cp1252 path
# ---------------------------------------------------------------------------
def probe_subprocess_decoding() -> None:
    section("5. child-process output decoding with non-ASCII  (PR #498)")
    child = "import sys; sys.stderr.write('N\\u00f6thing \\u2014 caf\\u00e9\\n')"

    # How the product now does it (explicit utf-8 + replace).
    try:
        r = subprocess.run([sys.executable, "-c", child], capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=60)
        record("PASS", "explicit encoding='utf-8', errors='replace' decoded cleanly",
               f"stderr={r.stderr.strip()!r}")
    except Exception as e:
        record("FAIL", "explicit utf-8 decode raised", repr(e))

    # How it used to do it (locale-dependent) — the bug, if PYTHONUTF8 is unset.
    try:
        r = subprocess.run([sys.executable, "-c", child], capture_output=True,
                           text=True, timeout=60)
        record("INFO", "bare text=True also decoded (no crash)",
               f"stderr={r.stderr.strip()!r}\n"
               "If PYTHONUTF8 is unset and this still worked, this host's console "
               "codepage is already UTF-8 (e.g. Windows 11 beta UTF-8 option).")
    except UnicodeDecodeError as e:
        record("PASS", "bare text=True RAISED UnicodeDecodeError — the #498 bug reproduced",
               f"{e!r}\nThis is exactly why the explicit encoding was added.")
    except Exception as e:
        record("WARN", "bare text=True raised something else", repr(e))



# ---------------------------------------------------------------------------
# 6. END-TO-END: render using the PRODUCT's own escape_filter_path
# ---------------------------------------------------------------------------
def probe_product_escaping(font: str | None) -> None:
    section("6. product escape_filter_path() renders for real")
    if not shutil.which("ffmpeg") or not font:
        record("WARN", "ffmpeg or font unavailable — skipping")
        return
    try:
        from tools.shared.media_utils import escape_filter_path
    except Exception as e:
        record("FAIL", "could not import escape_filter_path", repr(e))
        return

    tmp = Path(tempfile.mkdtemp(prefix="wprobe_prod_"))
    textfile = tmp / "title.txt"
    textfile.write_text("Product Escaping", encoding="utf-8")
    out = tmp / "frame.png"

    font_expr = escape_filter_path(font)
    text_expr = escape_filter_path(textfile)
    record("INFO", "product emits", f"fontfile={font_expr}\ntextfile={text_expr}")

    vf = (f"drawtext=textfile={text_expr}:fontfile={font_expr}:"
          f"fontsize=24:fontcolor=white:x=10:y=10")
    r = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
         "-i", "color=c=black:s=320x240:d=1", "-vf", vf, "-frames:v", "1", str(out)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
    )
    ok = r.returncode == 0 and out.exists() and out.stat().st_size > 0
    record("PASS" if ok else "FAIL",
           "PRODUCT escaping renders a real frame on this host",
           f"rc={r.returncode} bytes={out.stat().st_size if out.exists() else 0}"
           + ("" if ok else f"\nstderr: {(r.stderr or '').strip()[:300]}"))
    shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    print("bitwize-music — Windows host probe")
    print(f"repo: {REPO_ROOT}")
    if platform.system() != "Windows":
        print("\n*** NOT running on Windows — most findings will be meaningless. ***")

    probe_environment()
    font = probe_font()
    probe_drawtext(font)
    probe_product_escaping(font)
    probe_atomic_write()
    probe_hook()
    probe_subprocess_decoding()

    section("SUMMARY")
    for status in ("FAIL", "WARN", "PASS"):
        rows = [t for s, t, _ in FINDINGS if s == status]
        if rows:
            print(f"{status}: {len(rows)}")
            for t in rows:
                print(f"   - {t}")
    print("\nPaste this whole output back into the Claude session.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
