#!/usr/bin/env python3
"""selftest_web_checks.py — prove maw-tools/web_checks.py reflects reality.

Green-on-good / red-on-bad for every subcommand, asserting BOTH the JSON `passed`
verdict and the process exit code, plus the exact computed contrast ratios (the
contrast check is pure math, so its numbers are pinned, not eyeballed). If a
check silently regresses — contrast math drifts, a11y stops counting an alt-less
image, links stops resolving a fragment — this turns red.

Run:  uv run python maw-tools/selftest_web_checks.py
Exit: 0 if every assertion holds, 1 otherwise.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

WC = Path(__file__).with_name("web_checks.py")
results: list[tuple[bool, str]] = []

# Pinned contrast ratios (WCAG 2.x, exact math).
EXPECT_BAD_RATIO = 2.6405      # #9aa0a6 on #ffffff  -> fails AA normal (4.5)
EXPECT_LARGE_RATIO = 3.5449    # #888888 on #ffffff  -> fails normal, passes large (3.0)


def record(ok: bool, msg: str) -> None:
    results.append((bool(ok), msg))
    print(f"  {'[ok]' if ok else '[XX]'} {msg}")


def run(*args: str) -> tuple[int, dict | None]:
    proc = subprocess.run([sys.executable, str(WC), *args], capture_output=True, text=True)
    try:
        return proc.returncode, json.loads(proc.stdout)
    except json.JSONDecodeError:
        return proc.returncode, None


def expect(args: list[str], want_pass: bool, label: str) -> None:
    code, data = run(*args)
    got_pass = bool(data and data.get("passed"))
    exit_ok = (code == 0) if want_pass else (code != 0)
    ok = (got_pass == want_pass) and exit_ok and data is not None
    record(ok, f"{label}: exit {code}, passed={got_pass} (want passed={want_pass})")


def w(tmp: Path, name: str, text: str) -> Path:
    p = tmp / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


# A clean, fully-valid page (passes every check).
GOOD_HTML = """<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Good</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>@media (max-width: 600px){ body{padding:0} }</style>
</head>
<body>
<h1>Heading</h1>
<h2>Sub</h2>
<img src="logo.svg" alt="logo">
<form><label for="q">Search</label><input type="search" id="q"></form>
<a href="#sec">jump</a>
<section id="sec">content</section>
</body>
</html>
"""

# A page riddled with deterministically-catchable defects.
BAD_HTML = """<!doctype html>
<html>
<head><meta charset="utf-8"></head>
<body>
<h1>Heading</h1>
<h3>Skipped</h3>
<img src="logo.svg">
<form><input type="text"></form>
<a href="#nope">jump</a>
</body>
</html>
"""

# Malformed markup: duplicate id + an end tag with no matching open.
MALFORMED_HTML = ("<!doctype html><html lang='en'><head><title>x</title></head>"
                  "<body><div id='d'></div><div id='d'></div></span></body></html>")


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)

        # --- contrast: exact math, both thresholds ---
        print("web_checks.py contrast:")
        code, data = run("contrast", "--fg", "#9aa0a6", "--bg", "#ffffff")
        record(code == 1 and data and abs(data["ratio"] - EXPECT_BAD_RATIO) <= 1e-4
               and data["passed"] is False,
               f"low-contrast pair ratio={data and data.get('ratio')} -> exit {code} "
               f"(want {EXPECT_BAD_RATIO}, fail)")
        expect(["contrast", "--fg", "#ffffff", "--bg", "#1558b0"], True,
               "high-contrast pair passes AA normal")
        code, data = run("contrast", "--fg", "#888888", "--bg", "#ffffff")
        record(code == 1 and data and abs(data["ratio"] - EXPECT_LARGE_RATIO) <= 1e-4,
               f"borderline pair ratio={data and data.get('ratio')} fails normal -> exit {code}")
        expect(["contrast", "--fg", "#888888", "--bg", "#ffffff", "--large"], True,
               "...same pair passes the large-text threshold (3.0)")

        # --- a11y: clean page passes; defective page flags 5 ---
        print("web_checks.py a11y:")
        good = w(tmp, "good.html", GOOD_HTML)
        w(tmp, "logo.svg", "<svg/>\n")           # so links/budget can resolve it
        expect(["a11y", "--html", str(good)], True, "clean page: 0 violations")
        bad = w(tmp, "bad.html", BAD_HTML)
        code, data = run("a11y", "--html", str(bad))
        # img-alt, control-label, heading-skip, html-lang, title = 5
        record(code == 1 and data and data["violation_count"] == 5,
               f"defective page: {data and data.get('violation_count')} violations -> exit {code} (want 5)")

        # --- budget: under passes, over fails ---
        print("web_checks.py budget:")
        expect(["budget", "--html", str(good), "--max-bytes", "100000"], True,
               "under byte budget passes")
        expect(["budget", "--html", str(good), "--max-bytes", "50"], False,
               "over byte budget fails")

        # --- links: resolving page passes; broken fragment fails ---
        print("web_checks.py links:")
        expect(["links", "--html", str(good)], True, "all internal refs resolve")
        expect(["links", "--html", str(bad)], False, "broken #fragment + missing asset flagged")

        # --- markup: clean passes; dup-id + stray end tag fails ---
        print("web_checks.py markup:")
        expect(["markup", "--html", str(good)], True, "well-formed markup passes")
        mal = w(tmp, "mal.html", MALFORMED_HTML)
        expect(["markup", "--html", str(mal)], False, "duplicate id + mismatched end tag flagged")

        # --- responsive: viewport+media passes; missing viewport fails ---
        print("web_checks.py responsive:")
        expect(["responsive", "--html", str(good)], True, "viewport meta + @media present")
        expect(["responsive", "--html", str(bad)], False, "missing viewport meta fails")

        # ------------------------------------------------------------------ #
        # change-verification + style-drift (the extension)
        # ------------------------------------------------------------------ #
        before_css = w(tmp, "before.css",
                       ".btn { background: #e0e0e0; font-size: 0.75rem; }\n")
        after_css = w(tmp, "after.css",
                      ".btn { background: #1a73e8; font-size: 1rem; }\n")
        # cascade: later declaration of the same property wins
        cascade_css = w(tmp, "cascade.css",
                        ".btn { background: #111111; }\n.btn { background: #1a73e8; }\n")
        tokens_json = w(tmp, "tokens.json",
                        '{"colors":["#1a73e8","#e0e0e0","#ffffff"],'
                        ' "spacing":["0.5rem","1rem"], "fonts":["system-ui","sans-serif"]}')

        # --- style: exact resolved value, --expect match/mismatch, cascade ---
        print("web_checks.py style:")
        code, data = run("style", "--css", str(before_css), "--selector", ".btn",
                         "--property", "background")
        record(code == 0 and data and data["value"] == "#e0e0e0",
               f"style resolves .btn background = {data and data.get('value')} (want #e0e0e0)")
        expect(["style", "--css", str(after_css), "--selector", ".btn",
                "--property", "background", "--expect", "#1a73e8"], True,
               "style --expect matches the resolved value")
        expect(["style", "--css", str(after_css), "--selector", ".btn",
                "--property", "background", "--expect", "#e0e0e0"], False,
               "style --expect mismatch fails")
        code, data = run("style", "--css", str(cascade_css), "--selector", ".btn",
                         "--property", "background")
        record(code == 0 and data and data["value"] == "#1a73e8",
               f"style cascade: last declaration wins = {data and data.get('value')} (want #1a73e8)")

        # --- changed: the "it better be changed" gate ---
        print("web_checks.py changed:")
        expect(["changed", "--css", str(after_css), "--selector", ".btn", "--property",
                "background", "--before", "#e0e0e0", "--expect", "#1a73e8"], True,
               "REAL change (#e0e0e0 -> #1a73e8) passes")
        expect(["changed", "--css", str(before_css), "--selector", ".btn", "--property",
                "background", "--before", "#e0e0e0", "--expect", "#1a73e8"], False,
               "NO-OP (value unchanged) fails")
        expect(["changed", "--css", str(after_css), "--selector", ".btn", "--property",
                "background", "--before", "#e0e0e0", "--expect", "#999999"], False,
               "WRONG-TARGET (changed but != expected) fails")
        snap = w(tmp, "snap.txt", "v1\n")
        moved = w(tmp, "moved.txt", "v2\n")
        expect(["changed", "--file", str(moved), "--snapshot", str(snap)], True,
               "file mode: differs from snapshot passes")
        expect(["changed", "--file", str(snap), "--snapshot", str(snap)], False,
               "file mode: byte-identical to snapshot fails")

        # --- tokens: clean passes; color/spacing/font drift each fail ---
        print("web_checks.py tokens:")
        expect(["tokens", "--css", str(after_css), "--tokens", str(tokens_json)], True,
               "on-palette CSS passes (no drift)")
        drift_color = w(tmp, "drift_color.css", ".btn { background: #2b7de9; }\n")
        expect(["tokens", "--css", str(drift_color), "--tokens", str(tokens_json)], False,
               "off-palette color flagged as drift")
        drift_space = w(tmp, "drift_space.css", ".btn { padding: 0.6rem; }\n")
        expect(["tokens", "--css", str(drift_space), "--tokens", str(tokens_json)], False,
               "off-token spacing flagged as drift")
        drift_font = w(tmp, "drift_font.css", ".btn { font-family: Comic Sans MS; }\n")
        expect(["tokens", "--css", str(drift_font), "--tokens", str(tokens_json)], False,
               "off-token font flagged as drift")

    ok = all(r[0] for r in results)
    print(f"\n{'ALL PASS' if ok else 'FAILURES PRESENT'}: "
          f"{sum(1 for r in results if r[0])}/{len(results)} assertions held")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
