"""The release kit as a page to work from, and as JSON for later tools.

The page is one self-contained file, with no outside scripts, fonts or
images, so it opens offline in a browser or an iTerm2 pane. Every value has
a copy button. The Clipboard API is tried first, with select-and-copy as the
fallback a local page may need.
"""

from __future__ import annotations

import html
import json
from collections.abc import Iterator
from dataclasses import asdict
from itertools import count

from tools.release.kit import FAIL, INFO, WARN, Block, Field, Kit

# The check marks as HTML entities (cross, warning sign, information sign,
# tick), so the source stays ASCII.
_MARK = {FAIL: "&#x2717;", WARN: "&#x26A0;", INFO: "&#x2139;"}
_OK = "&#x2713;"

_CSS = """
:root{--bg:#fafaf9;--fg:#1c1917;--muted:#57534e;--line:#e7e5e4;--card:#fff;--accent:#2563eb;
--fail:#b91c1c;--warn:#a16207;--info:#475569;--ok:#15803d}
@media (prefers-color-scheme: dark){:root{--bg:#1c1917;--fg:#f5f5f4;--muted:#a8a29e;--line:#44403c;
--card:#292524;--accent:#60a5fa;--fail:#f87171;--warn:#facc15;--info:#94a3b8;--ok:#4ade80}}
*{box-sizing:border-box}
body{margin:0;padding:16px;background:var(--bg);color:var(--fg);
font:15px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
h1{margin:0;font-size:1.4rem}.sub{margin:.2rem 0 1rem;color:var(--muted)}
.checks{list-style:none;margin:0 0 1rem;padding:.6rem .8rem;border:1px solid var(--line);
border-radius:8px;background:var(--card)}
.checks li{margin:.15rem 0}.fail .mark{color:var(--fail)}.warn .mark{color:var(--warn)}
.info .mark{color:var(--info)}.ok{color:var(--ok)}
.tabs{display:flex;flex-wrap:wrap;gap:.4rem}
.tabs input{position:absolute;opacity:0;pointer-events:none}
.tabs label{order:0;padding:.35rem .9rem;border:1px solid var(--line);border-radius:999px;cursor:pointer}
.tabs input:checked+label{background:var(--accent);border-color:var(--accent);color:#fff}
.panel{order:1;display:none;width:100%}
#tab-distrokid:checked~#panel-distrokid,#tab-soundcloud:checked~#panel-soundcloud{display:block}
.block{margin:.8rem 0;padding:.6rem .8rem;border:1px solid var(--line);border-radius:8px;background:var(--card)}
.block h2{margin:0 0 .4rem;font-size:1rem}
dl{margin:0}
.field{display:grid;grid-template-columns:9rem 1fr;gap:.6rem;padding:.25rem 0;border-top:1px solid var(--line)}
.field:first-child{border-top:0}dt{color:var(--muted)}
dd{margin:0;display:flex;gap:.5rem;align-items:flex-start;min-width:0}
.value{flex:1;overflow-wrap:anywhere}pre.value{white-space:pre-wrap;margin:.3rem 0 0;font:inherit}
details{flex:1}summary{cursor:pointer;color:var(--accent)}
button.copy{flex:none;font:inherit;font-size:.85rem;padding:.15rem .6rem;border:1px solid var(--line);
border-radius:6px;background:transparent;color:var(--fg);cursor:pointer}
button.copy:hover{border-color:var(--accent)}
@media (max-width:560px){.field{grid-template-columns:1fr}}
"""

_JS = """
document.addEventListener("click", function (event) {
  var button = event.target.closest("button.copy");
  if (!button) return;
  var text = document.getElementById(button.dataset.copy).textContent;
  function done(ok) {
    button.textContent = ok ? "Copied" : "Select and copy";
    setTimeout(function () { button.textContent = "Copy"; }, 1500);
  }
  function fallback() {
    var area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    var ok = false;
    try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
    document.body.removeChild(area);
    done(ok);
  }
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(text).then(function () { done(true); }, fallback);
  } else {
    fallback();
  }
});
"""


def render_json(kit: Kit) -> str:
    """The kit as JSON, with its version, for a later fill-in step."""
    return json.dumps(asdict(kit), ensure_ascii=False, indent=2) + "\n"


def render_html(kit: Kit) -> str:
    """The kit as a page: the checks, then a DistroKid tab and a SoundCloud tab."""
    ids = count(1)
    title = html.escape(kit.album_title)
    checks = "".join(
        f'<li class="{check.level}"><span class="mark">{_MARK[check.level]}</span> '
        f"{html.escape(check.message)}</li>"
        for check in kit.checks
    ) or f'<li class="ok">{_OK} Nothing to fix</li>'
    tabs = (
        _tab("distrokid", "DistroKid", kit.distrokid, ids, checked=True)
        + _tab("soundcloud", "SoundCloud", kit.soundcloud, ids, checked=False)
    )
    return (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>Release kit: {title}</title>\n<style>{_CSS}</style>\n</head>\n<body>\n"
        f"<header><h1>{title}</h1><p class=\"sub\">Release kit: paste each value into the "
        "form, then submit it yourself</p></header>\n"
        f'<ul class="checks">{checks}</ul>\n<main class="tabs">{tabs}</main>\n'
        f"<script>{_JS}</script>\n</body>\n</html>\n"
    )


def _tab(key: str, name: str, blocks: tuple[Block, ...], ids: Iterator[int], checked: bool) -> str:
    sections = "".join(_block(block, ids) for block in blocks)
    return (
        f'<input type="radio" name="tab" id="tab-{key}"{" checked" if checked else ""}>'
        f'<label for="tab-{key}">{name}</label>'
        f'<section class="panel" id="panel-{key}">{sections}</section>'
    )


def _block(block: Block, ids: Iterator[int]) -> str:
    rows = "".join(_field(field, next(ids)) for field in block.fields)
    return f'<section class="block"><h2>{html.escape(block.heading)}</h2><dl>{rows}</dl></section>'


def _field(field: Field, n: int) -> str:
    value = html.escape(field.value)
    if field.long:
        shown = f'<details><summary>Show</summary><pre class="value" id="v{n}">{value}</pre></details>'
    else:
        shown = f'<span class="value" id="v{n}">{value}</span>'
    button = f'<button type="button" class="copy" data-copy="v{n}">Copy</button>'
    return f"<div class=\"field\"><dt>{html.escape(field.label)}</dt><dd>{shown}{button}</dd></div>"
