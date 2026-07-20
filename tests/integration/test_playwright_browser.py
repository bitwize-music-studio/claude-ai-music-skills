"""Real Chromium launch smoke test for the document-hunter dependency.

document-hunter is a *skill* (`skills/document-hunter/SKILL.md`) — Claude drives
Playwright from instructions, and there is no product Python to unit test. So
its actual behaviour (hunting documents on live sites) is out of scope: it is
non-deterministic and network-dependent.

What IS worth guarding is that the browser this skill depends on genuinely
installs and launches on each OS. Browser download and launch are the parts that
differ per platform, and `pip install playwright` does not install a browser —
`playwright install chromium` does, out-of-band. So a passing
`import playwright` (see tests/unit/shared/test_pinned_dependencies.py) proves
nothing about whether a browser is usable here.

Gated like the other integration tests: the `integration` marker plus
BITWIZE_INTEGRATION, so the normal suite and the 3-OS matrix collect-and-skip.
Chromium is ~150MB, which is why this lives in nightly rather than on every PR.

No network is touched — the page is a `data:` URL, so this tests the browser,
not the internet.
"""

from __future__ import annotations

import os

import pytest

BITWIZE_INTEGRATION = os.getenv("BITWIZE_INTEGRATION")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not BITWIZE_INTEGRATION,
        reason="integration services not available (set BITWIZE_INTEGRATION=1)",
    ),
]

MARKER = "bitwize-playwright-smoke"
# Self-contained page: no network, so a failure means the browser, not the net.
DATA_URL = f"data:text/html,<html><body><h1 id='m'>{MARKER}</h1></body></html>"


def test_chromium_launches_and_renders() -> None:
    """Chromium must install, launch headless, and return rendered content."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
        except Exception as exc:  # pragma: no cover - real failure path
            pytest.fail(
                f"Chromium failed to launch on this platform: {exc}\n"
                "If this is a missing-executable error, `playwright install "
                "chromium` did not run or did not place a browser where "
                "Playwright expects it."
            )
        try:
            page = browser.new_page()
            page.goto(DATA_URL)
            # Assert on rendered DOM, not just that goto() returned — a browser
            # that launches but cannot render would otherwise pass.
            assert page.text_content("#m") == MARKER
            assert page.title() is not None
        finally:
            browser.close()


def test_chromium_executable_is_present() -> None:
    """The resolved browser path should exist before any launch is attempted.

    Separated from the launch test so a missing download is distinguishable from
    a browser that is present but cannot start (a sandbox or missing-shared-lib
    problem, which needs a different fix).
    """
    from pathlib import Path

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        exe = p.chromium.executable_path
    assert exe, "Playwright reported no chromium executable path"
    assert Path(exe).exists(), (
        f"Playwright expects chromium at {exe} but it is not there — "
        "`playwright install chromium` likely did not run."
    )
