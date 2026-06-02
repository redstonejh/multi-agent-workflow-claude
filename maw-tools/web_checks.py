#!/usr/bin/env python3
"""web_checks.py — deterministic front-end / UI checks for Multi-Agent Workflow.

The front-end domain pack (a sibling of the ML pack in docs/06 and the code pack
in docs/07). Same rule as the rest of `maw-tools/`: **compute first, reason
second.** A WCAG contrast ratio is a real number, an alt-less `<img>` is a fact,
a broken `#anchor` either resolves or it doesn't — none of that needs a model.
The front-end roster agents (`a11y_auditor`, `perf_budgeter`, `markup_validator`,
`responsive_checker`, ...) run these and only *interpret* the result. Aesthetic /
"does it look good" judgment is the ONE thing left to the (advisory) `ux_critic`;
everything here is a hard, computed gate.

Pure standard library: `html.parser`, `re`, `math`, `json`, `pathlib`. No
browser, no npm, no network. True visual-regression / pixel-diff needs a real
browser (Claude-in-Chrome) and is **# MAW-TODO** — out of scope here on purpose.

Subcommands
-----------
  contrast    WCAG 2.x contrast ratio between two hex colors; pass >=4.5 (AA
              normal) or >=3.0 (--large). Pure math.
  a11y        Parse HTML; flag img-without-alt, unlabeled controls, skipped
              heading levels, missing <html lang>, missing <title>. Count
              violations; exit 1 if any.
  budget      Total bytes (HTML + referenced local CSS/JS/assets) + element and
              request counts; fail if over a configurable budget.
  links       Every internal link/anchor/asset ref resolves to an existing file
              or in-document id.
  markup      HTML well-formedness (unclosed tags, mismatched ends, duplicate
              ids) via html.parser.
  responsive  Presence of a <meta name="viewport"> and at least one CSS @media
              query (a deterministic *presence* check; layout correctness is
              # MAW-TODO — needs a real browser).
  style       Resolved value of a CSS `selector { property }` (last declaration
              wins) so before/after can be compared exactly.
  changed     Assert a value ACTUALLY changed vs a pre-change snapshot — a no-op
              or wrong-target edit exits non-zero. The "it better be changed" gate.
  tokens      Scan CSS against design-tokens.json (allowed colors/spacing/fonts)
              and flag any off-palette value = style drift. Exit non-zero on drift.

Every subcommand prints a JSON object with a boolean `passed` field and exits 0
when `passed` is true, non-zero otherwise — so callers gate on `$?`. Usage /
runtime errors exit 2. On a machine where `python` is not on PATH, invoke with
`uv run` (see CLAUDE.md / INSTALL.md).

Examples
--------
  uv run python maw-tools/web_checks.py contrast --fg "#9aa0a6" --bg "#ffffff"
  uv run python maw-tools/web_checks.py a11y --html examples/frontend_demo/index.html
  uv run python maw-tools/web_checks.py budget --html page.html --max-bytes 20000
  uv run python maw-tools/web_checks.py links --html page.html
  uv run python maw-tools/web_checks.py markup --html page.html
  uv run python maw-tools/web_checks.py responsive --html page.html --css style.css
  uv run python maw-tools/web_checks.py style --css after.css --selector .btn --property background
  uv run python maw-tools/web_checks.py changed --css after.css --selector .btn \
      --property background --before "#e0e0e0" --expect "#1a73e8"
  uv run python maw-tools/web_checks.py tokens --css after.css --tokens design-tokens.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path


def _emit(obj: dict, passed: bool) -> int:
    print(json.dumps(obj, indent=2))
    return 0 if passed else 1


# HTML void elements never have a closing tag (markup checker must not expect one).
VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}

# Resource references that point off-box / are not files — links/budget skip these.
_EXTERNAL_PREFIXES = ("http://", "https://", "//", "mailto:", "tel:", "data:",
                      "javascript:")


# --------------------------------------------------------------------------- #
# contrast — WCAG 2.x contrast ratio (pure math, docs: front-end pack)
# --------------------------------------------------------------------------- #

def _parse_hex(s: str) -> tuple[int, int, int]:
    """Parse #rgb / #rrggbb (with or without the leading #) into (r,g,b) 0-255."""
    h = s.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6 or any(c not in "0123456789abcdefABCDEF" for c in h):
        raise ValueError(f"not a hex color: {s!r}")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _rel_luminance(rgb: tuple[int, int, int]) -> float:
    """WCAG 2.x relative luminance of an sRGB color."""
    def chan(c: int) -> float:
        cs = c / 255.0
        return cs / 12.92 if cs <= 0.03928 else ((cs + 0.055) / 1.055) ** 2.4
    r, g, b = (chan(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast_ratio(fg: str, bg: str) -> float:
    l1 = _rel_luminance(_parse_hex(fg))
    l2 = _rel_luminance(_parse_hex(bg))
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def cmd_contrast(args: argparse.Namespace) -> int:
    ratio = _contrast_ratio(args.fg, args.bg)
    threshold = 3.0 if args.large else 4.5
    passed = ratio >= threshold
    return _emit({
        "check": "contrast",
        "fg": args.fg,
        "bg": args.bg,
        "ratio": round(ratio, 4),
        "threshold": threshold,
        "large_text": bool(args.large),
        "passed": passed,
        "note": (f"contrast {ratio:.2f}:1 meets WCAG AA "
                 f"({'large >=3.0' if args.large else 'normal >=4.5'})" if passed
                 else f"contrast {ratio:.2f}:1 below WCAG AA threshold {threshold} "
                      f"— text hard to read"),
    }, passed)


# --------------------------------------------------------------------------- #
# Shared HTML model — one parse, reused by a11y / links / markup / budget
# --------------------------------------------------------------------------- #

class _Doc(HTMLParser):
    """Collects the structural facts the deterministic checks need, in one pass."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list[tuple[str, dict, int]] = []   # (tag, attrs, lineno) starts
        self.ids: list[str] = []                      # every id attr value (dupe scan)
        self.imgs: list[dict] = []                    # img attr dicts
        self.controls: list[dict] = []                # input/select/textarea/button
        self.label_for: set[str] = set()              # <label for="..."> targets
        self.headings: list[int] = []                 # heading levels in document order
        self.refs: list[tuple[str, str]] = []         # (kind, url) link/asset refs
        self.html_attrs: dict | None = None
        self.title_text: str = ""
        self._in_title = False
        # markup well-formedness state
        self.open_stack: list[tuple[str, int]] = []
        self.mismatched: list[str] = []
        # label-wrapping + button-text tracking
        self._label_depth = 0
        self._control_text_stack: list[dict] = []

    # -- helpers --------------------------------------------------------------
    def _adict(self, attrs: list[tuple[str, str | None]]) -> dict:
        return {k.lower(): (v if v is not None else "") for k, v in attrs}

    # -- parser callbacks -----------------------------------------------------
    def handle_starttag(self, tag, attrs):
        self._on_open(tag, attrs, self.getpos()[0])

    def handle_startendtag(self, tag, attrs):  # <foo .../>
        # self-closing: record as a start, but never push onto the open stack
        self._on_open(tag, attrs, self.getpos()[0], self_closing=True)

    def _on_open(self, tag, attrs, lineno, self_closing=False):
        tag = tag.lower()
        a = self._adict(attrs)
        self.tags.append((tag, a, lineno))

        if "id" in a and a["id"]:
            self.ids.append(a["id"])
        if tag == "html":
            self.html_attrs = a
        if tag == "title":
            self._in_title = True
        if tag == "label":
            self._label_depth += 1
            if a.get("for"):
                self.label_for.add(a["for"])
        if tag == "img":
            self.imgs.append(a)
        if len(tag) == 2 and tag[0] == "h" and tag[1] in "123456":
            self.headings.append(int(tag[1]))
        if tag in ("input", "select", "textarea", "button"):
            ctrl = {"tag": tag, "attrs": a, "lineno": lineno,
                    "in_label": self._label_depth > 0, "text": ""}
            self.controls.append(ctrl)
            self._control_text_stack.append(ctrl)
        # resource references (for links + budget)
        if tag == "a" and a.get("href"):
            self.refs.append(("a", a["href"]))
        if tag == "link" and a.get("href"):
            self.refs.append(("link", a["href"]))
        if tag in ("script", "img", "source", "iframe", "audio", "video") and a.get("src"):
            self.refs.append((tag, a["src"]))

        # markup: push non-void, non-self-closing tags onto the open stack
        if not self_closing and tag not in VOID_TAGS:
            self.open_stack.append((tag, lineno))

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "title":
            self._in_title = False
        if tag == "label" and self._label_depth > 0:
            self._label_depth -= 1
        if tag in ("input", "select", "textarea", "button") and self._control_text_stack:
            self._control_text_stack.pop()
        if tag in VOID_TAGS:
            return
        # markup: find the nearest matching open tag; tags above it are implicitly
        # closed (lenient — HTML allows optional close for <p>, <li>, ...). Only a
        # close with NO matching open anywhere is a true mismatch.
        for i in range(len(self.open_stack) - 1, -1, -1):
            if self.open_stack[i][0] == tag:
                del self.open_stack[i:]
                return
        self.mismatched.append(tag)

    def handle_data(self, data):
        if self._in_title:
            self.title_text += data
        text = data.strip()
        if text and self._control_text_stack:
            self._control_text_stack[-1]["text"] += text


def _parse_html(path: Path) -> _Doc:
    doc = _Doc()
    doc.feed(path.read_text(encoding="utf-8"))
    doc.close()
    return doc


# --------------------------------------------------------------------------- #
# a11y — parse HTML, count accessibility violations (docs: front-end pack)
# --------------------------------------------------------------------------- #

def _control_has_name(ctrl: dict) -> bool:
    a = ctrl["attrs"]
    if a.get("aria-label") or a.get("aria-labelledby") or a.get("title"):
        return True
    if ctrl["in_label"]:                       # wrapped in a <label>
        return True
    if a.get("id") and a["id"] in ctrl.get("_label_targets", set()):
        return True
    if ctrl["tag"] == "button":
        return bool(ctrl["text"] or a.get("value"))
    if ctrl["tag"] == "input":
        # submit/button/reset get their name from the value attribute
        if a.get("type", "text").lower() in ("submit", "button", "reset"):
            return bool(a.get("value"))
        if a.get("type", "").lower() == "hidden":
            return True                        # hidden inputs need no label
    return False


def cmd_a11y(args: argparse.Namespace) -> int:
    doc = _parse_html(Path(args.html))
    violations: list[dict] = []

    # 1) <img> without an alt attribute (alt="" is allowed: decorative-by-intent)
    for a in doc.imgs:
        if "alt" not in a:
            violations.append({"rule": "img-alt", "detail":
                               f"<img src={a.get('src','?')!r}> has no alt attribute"})

    # 2) form controls without an accessible name
    for ctrl in doc.controls:
        ctrl["_label_targets"] = doc.label_for
        if not _control_has_name(ctrl):
            violations.append({"rule": "control-label", "line": ctrl["lineno"],
                               "detail": f"<{ctrl['tag']}> has no accessible label"})

    # 3) skipped heading levels (e.g. h1 -> h3)
    prev = 0
    for lvl in doc.headings:
        if prev and lvl > prev + 1:
            violations.append({"rule": "heading-skip", "detail":
                               f"heading jumps from h{prev} to h{lvl}"})
        prev = lvl

    # 4) <html> missing lang
    if doc.html_attrs is None or not doc.html_attrs.get("lang"):
        violations.append({"rule": "html-lang", "detail": "<html> has no lang attribute"})

    # 5) missing / empty <title>
    if not doc.title_text.strip():
        violations.append({"rule": "title", "detail": "document has no non-empty <title>"})

    passed = len(violations) == 0
    return _emit({
        "check": "a11y",
        "html": str(args.html),
        "violation_count": len(violations),
        "violations": violations,
        "passed": passed,
        "note": ("no accessibility violations found (deterministic subset)"
                 if passed else f"{len(violations)} accessibility violation(s) "
                 "— see list (deterministic subset; manual review still advised)"),
    }, passed)


# --------------------------------------------------------------------------- #
# budget — total bytes + element/request counts (docs: front-end pack)
# --------------------------------------------------------------------------- #

def cmd_budget(args: argparse.Namespace) -> int:
    html_path = Path(args.html)
    base = html_path.parent
    html_bytes = len(html_path.read_bytes())
    doc = _parse_html(html_path)

    assets: list[dict] = []
    asset_bytes = 0
    requests = 0
    for kind, url in doc.refs:
        if kind == "a":
            continue  # navigation links are not page-weight requests
        if url.startswith(_EXTERNAL_PREFIXES) or url.startswith("#"):
            requests += 1            # counts as a request, but bytes are off-box
            continue
        requests += 1
        local = (base / url.split("?")[0].split("#")[0])
        if local.is_file():
            b = len(local.read_bytes())
            asset_bytes += b
            assets.append({"url": url, "bytes": b})
        else:
            assets.append({"url": url, "bytes": None, "note": "unresolved (not counted)"})

    total = html_bytes + asset_bytes
    elements = len(doc.tags)

    reasons = []
    passed = True
    if args.max_bytes is not None and total > args.max_bytes:
        passed = False
        reasons.append(f"total {total} bytes > budget {args.max_bytes}")
    if args.max_elements is not None and elements > args.max_elements:
        passed = False
        reasons.append(f"{elements} elements > budget {args.max_elements}")
    if args.max_requests is not None and requests > args.max_requests:
        passed = False
        reasons.append(f"{requests} requests > budget {args.max_requests}")

    return _emit({
        "check": "budget",
        "html": str(args.html),
        "html_bytes": html_bytes,
        "asset_bytes": asset_bytes,
        "total_bytes": total,
        "element_count": elements,
        "request_count": requests,
        "assets": assets,
        "max_bytes": args.max_bytes,
        "max_elements": args.max_elements,
        "max_requests": args.max_requests,
        "passed": passed,
        "note": ("within budget" if passed else "; ".join(reasons)),
    }, passed)


# --------------------------------------------------------------------------- #
# links — internal links/anchors/assets resolve (docs: front-end pack)
# --------------------------------------------------------------------------- #

def cmd_links(args: argparse.Namespace) -> int:
    html_path = Path(args.html)
    base = html_path.parent
    root = Path(args.root) if args.root else base
    doc = _parse_html(html_path)
    ids = set(doc.ids)

    broken: list[dict] = []
    checked = 0
    external = 0
    for kind, url in doc.refs:
        u = url.strip()
        if not u or u.startswith(_EXTERNAL_PREFIXES):
            external += 1
            continue
        checked += 1
        if u.startswith("#"):                       # in-page fragment
            frag = u[1:]
            if frag and frag not in ids:
                broken.append({"kind": kind, "ref": u,
                               "detail": f"no element with id={frag!r}"})
            continue
        # file ref (optionally with a #fragment) — resolve relative to root or base
        path_part = u.split("#")[0].split("?")[0]
        anchor = base if not path_part.startswith("/") else root
        target = (anchor / path_part.lstrip("/")) if path_part.startswith("/") \
            else (base / path_part)
        if not target.is_file():
            broken.append({"kind": kind, "ref": u,
                           "detail": f"file not found: {target}"})

    passed = len(broken) == 0
    return _emit({
        "check": "links",
        "html": str(args.html),
        "checked": checked,
        "external_skipped": external,
        "broken_count": len(broken),
        "broken": broken,
        "passed": passed,
        "note": ("all internal links/anchors/assets resolve"
                 if passed else f"{len(broken)} broken internal reference(s)"),
    }, passed)


# --------------------------------------------------------------------------- #
# markup — well-formedness: unclosed/mismatched tags + duplicate ids
# --------------------------------------------------------------------------- #

def cmd_markup(args: argparse.Namespace) -> int:
    doc = _parse_html(Path(args.html))

    problems: list[dict] = []
    for tag, lineno in doc.open_stack:
        problems.append({"problem": "unclosed-tag", "tag": tag, "line": lineno})
    for tag in doc.mismatched:
        problems.append({"problem": "mismatched-end-tag", "tag": tag})

    seen: dict[str, int] = {}
    for i in doc.ids:
        seen[i] = seen.get(i, 0) + 1
    dupes = {k: v for k, v in seen.items() if v > 1}
    for k, v in dupes.items():
        problems.append({"problem": "duplicate-id", "id": k, "count": v})

    passed = len(problems) == 0
    return _emit({
        "check": "markup",
        "html": str(args.html),
        "problem_count": len(problems),
        "problems": problems,
        "passed": passed,
        "note": ("well-formed: tags balanced, ids unique (optional-tag implied "
                 "close handled leniently)"
                 if passed else f"{len(problems)} markup problem(s)"),
    }, passed)


# --------------------------------------------------------------------------- #
# responsive — viewport meta + @media presence (PRESENCE only; layout # MAW-TODO)
# --------------------------------------------------------------------------- #

def cmd_responsive(args: argparse.Namespace) -> int:
    doc = _parse_html(Path(args.html))
    has_viewport = any(
        tag == "meta" and a.get("name", "").lower() == "viewport" and a.get("content")
        for tag, a, _ln in doc.tags
    )

    def _count_media(text: str) -> int:
        # strip CSS /* */ and HTML <!-- --> comments first, so an `@media`
        # mentioned in a comment is not miscounted as a real breakpoint.
        text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
        text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
        return len(re.findall(r"@media\b", text))

    media_queries = 0
    css_scanned: list[str] = []
    # inline <style> blocks live in the HTML text itself
    html_text = Path(args.html).read_text(encoding="utf-8")
    media_queries += _count_media(html_text)
    for css in (args.css or []):
        p = Path(css)
        if p.is_file():
            css_scanned.append(css)
            media_queries += _count_media(p.read_text(encoding="utf-8"))

    passed = has_viewport and media_queries > 0
    reasons = []
    if not has_viewport:
        reasons.append("no <meta name=viewport> — page won't adapt on mobile")
    if media_queries == 0:
        reasons.append("no @media query found — no responsive breakpoints")
    return _emit({
        "check": "responsive",
        "html": str(args.html),
        "has_viewport_meta": has_viewport,
        "media_query_count": media_queries,
        "css_scanned": css_scanned,
        "passed": passed,
        "note": ("viewport meta present and >=1 @media query found (presence check "
                 "only — true layout/visual correctness needs a browser, # MAW-TODO)"
                 if passed else "; ".join(reasons)),
    }, passed)


# --------------------------------------------------------------------------- #
# CSS model — shared by style / changed / tokens (flat rule sets; @media # MAW-TODO)
# --------------------------------------------------------------------------- #

def _strip_css_comments(text: str) -> str:
    return re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)


def _parse_css(text: str) -> list[tuple[list[str], list[tuple[str, str]]]]:
    """Parse flat CSS into [(selectors, [(prop, value), ...]), ...].

    Comments are stripped first. This handles flat rule sets — the simple
    component CSS the framework's examples produce. Nested at-rules (@media,
    @supports) are NOT decomposed; rules inside them are skipped rather than
    mis-parsed. Full nested-at-rule support is # MAW-TODO.
    """
    text = _strip_css_comments(text)
    rules: list[tuple[list[str], list[tuple[str, str]]]] = []
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", text):
        prelude = m.group(1).strip()
        if prelude.startswith("@"):
            continue  # at-rule prelude (e.g. `@media ...`) — body is nested, skip
        selectors = [re.sub(r"\s+", " ", s.strip()) for s in prelude.split(",") if s.strip()]
        decls: list[tuple[str, str]] = []
        for d in m.group(2).split(";"):
            if ":" in d:
                prop, val = d.split(":", 1)
                decls.append((prop.strip().lower(), val.strip()))
        rules.append((selectors, decls))
    return rules


def _norm_value(v: str) -> str:
    """Normalize a CSS value for exact comparison: lowercase, collapse spaces,
    expand short hex (#abc -> #aabbcc), drop a trailing !important."""
    v = re.sub(r"\s+", " ", v.strip().lower())
    v = re.sub(r"\s*!important\s*$", "", v)

    def _exp(m: re.Match) -> str:
        h = m.group(1)
        if len(h) in (3, 4):
            h = "".join(c * 2 for c in h)
        return "#" + h
    return re.sub(r"#([0-9a-f]{3,8})\b", _exp, v)


def _resolve_style(rules, selector: str, prop: str) -> str | None:
    """The resolved value of `selector { prop }`: the LAST matching declaration
    wins (CSS cascade, assuming equal specificity). None if never declared."""
    target = re.sub(r"\s+", " ", selector.strip())
    prop = prop.strip().lower()
    found: str | None = None
    for selectors, decls in rules:
        if target in selectors:
            for p, val in decls:
                if p == prop:
                    found = val
    return found


def _extract_colors(value: str) -> list[str]:
    """Color literals in a declaration value: hex + rgb()/rgba()/hsl()/hsla()."""
    out = re.findall(r"#[0-9a-fA-F]{3,8}\b", value)
    out += re.findall(r"(?:rgba?|hsla?)\([^)]*\)", value, flags=re.IGNORECASE)
    return out


# spacing lives in these properties; values elsewhere (e.g. font-size) are not
# treated as spacing tokens. `0` and `auto` are always allowed.
_SPACING_PROPS = {
    "margin", "margin-top", "margin-right", "margin-bottom", "margin-left",
    "padding", "padding-top", "padding-right", "padding-bottom", "padding-left",
    "gap", "row-gap", "column-gap", "top", "right", "bottom", "left", "inset",
}
_LENGTH_RE = re.compile(r"\b\d*\.?\d+(?:px|rem|em|vh|vw|%)\b", re.IGNORECASE)


# --------------------------------------------------------------------------- #
# style — resolved value of a selector { property } (docs: front-end pack)
# --------------------------------------------------------------------------- #

def cmd_style(args: argparse.Namespace) -> int:
    rules = _parse_css(Path(args.css).read_text(encoding="utf-8"))
    value = _resolve_style(rules, args.selector, args.property)
    found = value is not None
    if args.expect is not None:
        passed = found and _norm_value(value) == _norm_value(args.expect)
    else:
        passed = found
    return _emit({
        "check": "style",
        "css": str(args.css),
        "selector": args.selector,
        "property": args.property,
        "value": value,
        "found": found,
        "expected": args.expect,
        "passed": passed,
        "note": (f"{args.selector} {{ {args.property} }} = {value!r}"
                 + ("" if args.expect is None
                    else f" {'==' if passed else '!='} expected {args.expect!r}")
                 if found else
                 f"no resolved value for {args.selector} {{ {args.property} }}"),
    }, passed)


# --------------------------------------------------------------------------- #
# changed — assert a value actually changed (the "it better be changed" gate)
# --------------------------------------------------------------------------- #

def cmd_changed(args: argparse.Namespace) -> int:
    # Mode A: selector+property in CSS vs a --before value (and optional --expect)
    if args.css:
        if not (args.selector and args.property and args.before is not None):
            print("error: CSS mode needs --selector, --property and --before",
                  file=sys.stderr)
            return 2
        rules = _parse_css(Path(args.css).read_text(encoding="utf-8"))
        current = _resolve_style(rules, args.selector, args.property)
        found = current is not None
        changed = found and _norm_value(current) != _norm_value(args.before)
        matches = (args.expect is None) or (found and _norm_value(current) == _norm_value(args.expect))
        passed = bool(found and changed and matches)
        reason = ("value not found — cannot verify the change" if not found else
                  f"NO-OP: {args.selector} {{ {args.property} }} still {current!r} "
                  f"(== before)" if not changed else
                  f"changed to {current!r} but expected {args.expect!r}" if not matches else
                  f"{args.selector} {{ {args.property} }}: {args.before!r} -> {current!r}"
                  + ("" if args.expect is None else f" (== expected {args.expect!r})"))
        return _emit({
            "check": "changed", "mode": "selector",
            "css": str(args.css), "selector": args.selector, "property": args.property,
            "before": args.before, "current": current, "expected": args.expect,
            "changed": bool(changed), "matches_expected": bool(matches),
            "passed": passed, "note": reason,
        }, passed)

    # Mode B: whole-file vs a pre-change snapshot file (optional --expect-contains)
    if args.file:
        if not args.snapshot:
            print("error: file mode needs --snapshot", file=sys.stderr)
            return 2
        current = Path(args.file).read_text(encoding="utf-8")
        before = Path(args.snapshot).read_text(encoding="utf-8")
        changed = current != before
        contains = (args.expect_contains is None) or (args.expect_contains in current)
        passed = bool(changed and contains)
        reason = ("NO-OP: file is byte-identical to the snapshot" if not changed else
                  f"changed but does not contain {args.expect_contains!r}" if not contains else
                  "file differs from snapshot"
                  + ("" if args.expect_contains is None
                     else f" and contains {args.expect_contains!r}"))
        return _emit({
            "check": "changed", "mode": "file",
            "file": str(args.file), "snapshot": str(args.snapshot),
            "changed": bool(changed), "contains_expected": bool(contains),
            "expect_contains": args.expect_contains, "passed": passed, "note": reason,
        }, passed)

    print("error: provide either --css (selector mode) or --file (snapshot mode)",
          file=sys.stderr)
    return 2


# --------------------------------------------------------------------------- #
# tokens — design-token conformance / style-drift (docs: front-end pack)
# --------------------------------------------------------------------------- #

def cmd_tokens(args: argparse.Namespace) -> int:
    spec = json.loads(Path(args.tokens).read_text(encoding="utf-8"))
    rules = _parse_css(Path(args.css).read_text(encoding="utf-8"))

    allowed_colors = {_norm_value(c) for c in spec.get("colors", [])}
    allowed_spacing = {_norm_value(s) for s in spec.get("spacing", [])} | {"0", "auto"}
    allowed_fonts = {f.strip().strip("'\"").lower() for f in spec.get("fonts", [])}

    drift: list[dict] = []
    for selectors, decls in rules:
        sel = ", ".join(selectors)
        for prop, value in decls:
            if "colors" in spec:
                for col in _extract_colors(value):
                    if _norm_value(col) not in allowed_colors:
                        drift.append({"category": "color", "selector": sel,
                                      "property": prop, "value": col})
            if "spacing" in spec and prop in _SPACING_PROPS:
                for length in _LENGTH_RE.findall(value):
                    if _norm_value(length) not in allowed_spacing:
                        drift.append({"category": "spacing", "selector": sel,
                                      "property": prop, "value": length})
            if "fonts" in spec and prop == "font-family":
                for fam in value.split(","):
                    f = fam.strip().strip("'\"").lower()
                    if f and f not in allowed_fonts:
                        drift.append({"category": "font", "selector": sel,
                                      "property": prop, "value": fam.strip()})

    passed = len(drift) == 0
    return _emit({
        "check": "tokens",
        "css": str(args.css),
        "tokens": str(args.tokens),
        "categories_checked": [c for c in ("colors", "spacing", "fonts") if c in spec],
        "drift_count": len(drift),
        "drift": drift,
        "passed": passed,
        "note": ("every scanned value is in the design-token set (no drift); "
                 "note: var(--x) refs + complex shorthand are not decomposed (# MAW-TODO)"
                 if passed else f"{len(drift)} off-palette value(s) — style drift"),
    }, passed)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Deterministic front-end checks (no browser, no network).")
    sub = p.add_subparsers(dest="cmd", required=True)

    pc = sub.add_parser("contrast", help="WCAG 2.x contrast ratio between two hex colors")
    pc.add_argument("--fg", required=True, help="foreground (text) hex color")
    pc.add_argument("--bg", required=True, help="background hex color")
    pc.add_argument("--large", action="store_true", help="large text (AA threshold 3.0 not 4.5)")
    pc.set_defaults(func=cmd_contrast)

    pa = sub.add_parser("a11y", help="accessibility violations in an HTML file")
    pa.add_argument("--html", required=True, help="path to the HTML file")
    pa.set_defaults(func=cmd_a11y)

    pb = sub.add_parser("budget", help="page-weight + element/request budget")
    pb.add_argument("--html", required=True, help="path to the HTML file")
    pb.add_argument("--max-bytes", type=int, default=None, help="max total bytes")
    pb.add_argument("--max-elements", type=int, default=None, help="max element count")
    pb.add_argument("--max-requests", type=int, default=None, help="max request count")
    pb.set_defaults(func=cmd_budget)

    pl = sub.add_parser("links", help="internal links/anchors/assets resolve")
    pl.add_argument("--html", required=True, help="path to the HTML file")
    pl.add_argument("--root", default=None, help="root for absolute (/...) refs (default: html dir)")
    pl.set_defaults(func=cmd_links)

    pm = sub.add_parser("markup", help="HTML well-formedness (unclosed tags, dup ids)")
    pm.add_argument("--html", required=True, help="path to the HTML file")
    pm.set_defaults(func=cmd_markup)

    pr = sub.add_parser("responsive", help="viewport meta + @media presence (presence only)")
    pr.add_argument("--html", required=True, help="path to the HTML file")
    pr.add_argument("--css", action="append", help="CSS file(s) to scan for @media (repeatable)")
    pr.set_defaults(func=cmd_responsive)

    psy = sub.add_parser("style", help="resolved value of a CSS selector { property }")
    psy.add_argument("--css", required=True, help="path to the CSS file")
    psy.add_argument("--selector", required=True, help="selector, e.g. .btn")
    psy.add_argument("--property", required=True, help="property, e.g. background")
    psy.add_argument("--expect", default=None, help="assert the resolved value == this")
    psy.set_defaults(func=cmd_style)

    pch = sub.add_parser("changed", help="assert a value actually changed vs a pre-change snapshot")
    pch.add_argument("--css", default=None, help="CSS file (selector mode)")
    pch.add_argument("--selector", default=None, help="selector (selector mode)")
    pch.add_argument("--property", default=None, help="property (selector mode)")
    pch.add_argument("--before", default=None, help="the pre-change value (selector mode)")
    pch.add_argument("--expect", default=None, help="assert it changed TO this (selector mode)")
    pch.add_argument("--file", default=None, help="file to check (snapshot mode)")
    pch.add_argument("--snapshot", default=None, help="pre-change snapshot file (snapshot mode)")
    pch.add_argument("--expect-contains", default=None, help="assert the new file contains this (snapshot mode)")
    pch.set_defaults(func=cmd_changed)

    pt = sub.add_parser("tokens", help="design-token conformance / style-drift scan of a CSS file")
    pt.add_argument("--css", required=True, help="path to the CSS file")
    pt.add_argument("--tokens", required=True, help="design-tokens.json (allowed colors/spacing/fonts)")
    pt.set_defaults(func=cmd_tokens)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, FileNotFoundError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
