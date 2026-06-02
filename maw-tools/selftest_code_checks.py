#!/usr/bin/env python3
"""selftest_code_checks.py — prove maw-tools/code_checks.py reflects reality.

Green-on-good / red-on-bad for every subcommand, asserting both the JSON `passed`
verdict and the process exit code. If a check silently regresses (e.g. `refs`
miscounts, or `syntax` stops catching a null byte), this turns red.

Run:  uv run python maw-tools/selftest_code_checks.py
Exit: 0 if every assertion holds, 1 otherwise.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

CC = Path(__file__).with_name("code_checks.py")
results: list[tuple[bool, str]] = []

# Reference fixture below has, for symbol `foo`: 1 def + 3 name uses = 4 sites.
REFS_FIXTURE = "def foo():\n    return 1\n\n\ndef bar():\n    return foo() + foo()\n\n\nbaz = foo\n"
EXPECT_FOO_REFS = 4


def record(ok: bool, msg: str) -> None:
    results.append((bool(ok), msg))
    print(f"  {'[ok]' if ok else '[XX]'} {msg}")


def run(*args: str) -> tuple[int, dict | None]:
    proc = subprocess.run([sys.executable, str(CC), *args], capture_output=True, text=True)
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        data = None
    return proc.returncode, data


def expect(args: list[str], want_pass: bool, label: str) -> None:
    code, data = run(*args)
    got_pass = bool(data and data.get("passed"))
    exit_ok = (code == 0) if want_pass else (code != 0)
    ok = (got_pass == want_pass) and exit_ok and data is not None
    record(ok, f"{label}: exit {code}, passed={got_pass} (want passed={want_pass})")


def w(tmp: Path, name: str, text: str) -> str:
    p = tmp / name
    p.write_text(text, encoding="utf-8")
    return str(p)


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)

        # --- refs: finds exactly the known references; wrong --expect fails ---
        print("code_checks.py refs:")
        fx = w(tmp, "refs_fixture.py", REFS_FIXTURE)
        code, data = run("refs", "--symbol", "foo", fx)
        got = data.get("ref_count") if data else None
        record(code == 0 and got == EXPECT_FOO_REFS,
               f"refs finds {EXPECT_FOO_REFS} sites for `foo`: got {got}")
        expect(["refs", "--symbol", "foo", fx, "--expect", str(EXPECT_FOO_REFS)], True,
               "refs --expect matches")
        expect(["refs", "--symbol", "foo", fx, "--expect", "99"], False,
               "refs --expect mismatch")

        # --- regression: an explicitly-named DOTTED scan root must be scanned, ---
        # --- not silently skipped (the old filter checked the root's own parts ---
        # --- too, returning 0 files == a false "0 refs" blast radius). ---
        dotted = tmp / ".hidden_root"
        (dotted / "sub" / ".git").mkdir(parents=True)
        (dotted / "mod.py").write_text(REFS_FIXTURE, encoding="utf-8")          # 4 foo sites
        (dotted / "sub" / ".git" / "hook.py").write_text("foo = 1\n", encoding="utf-8")  # must stay skipped
        code, data = run("refs", "--symbol", "foo", "--root", str(dotted),
                         "--expect", str(EXPECT_FOO_REFS))
        scanned = data.get("files_scanned") if data else None
        got = data.get("ref_count") if data else None
        record(code == 0 and scanned == 1 and got == EXPECT_FOO_REFS,
               f"refs scans a dotted root: files={scanned}, refs={got} "
               f"(want files=1, refs={EXPECT_FOO_REFS})")
        # the .git/ dir BELOW the root is still excluded — else the foo=1 inside it
        # would bump the count to 5 / files to 2.
        record(scanned == 1 and got == EXPECT_FOO_REFS,
               "dotted/__pycache__ components BELOW the scan root are still skipped")

        # --- syntax: clean compiles; syntax error and null byte both fail ---
        print("code_checks.py syntax:")
        good = w(tmp, "good.py", "def ok():\n    return 1\n")
        expect(["syntax", good], True, "clean file compiles")
        bad = w(tmp, "bad_syntax.py", "def broken(:\n    return\n")
        expect(["syntax", bad], False, "syntax error caught")
        nullf = tmp / "nullbyte.py"
        nullf.write_bytes(b"x = 1\x00\n")
        expect(["syntax", str(nullf)], False, "null-byte corruption caught")

        # --- dupes: structural clones flagged; distinct bodies pass ---
        print("code_checks.py dupes:")
        clones = w(tmp, "clones.py",
                   "def a(x):\n    y = x + 1\n    return y * 2\n\n\n"
                   "def b(z):\n    w = z + 9\n    return w * 5\n")
        expect(["dupes", clones], False, "structural clone bodies flagged")
        distinct = w(tmp, "distinct.py",
                     "def a(x):\n    return x + 1\n\n\n"
                     "def b(z):\n    for i in z:\n        print(i)\n    return None\n")
        expect(["dupes", distinct], True, "distinct bodies pass")

        # --- test: forwards the checks.py verdict + exit code ---
        print("code_checks.py test (forward):")
        expect(["test", "--cmd", f'"{sys.executable}" -c "import sys; sys.exit(0)"'], True,
               "passing command forwarded")
        expect(["test", "--cmd", f'"{sys.executable}" -c "import sys; sys.exit(1)"'], False,
               "failing command forwarded")

    ok = all(r[0] for r in results)
    print(f"\n{'ALL PASS' if ok else 'FAILURES PRESENT'}: "
          f"{sum(1 for r in results if r[0])}/{len(results)} assertions held")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
