#!/usr/bin/env python3
"""selftest_refactor_checks.py — prove maw-tools/refactor_checks.py reflects reality.

Green-on-good / red-on-bad for every subcommand, asserting the JSON verdict + exit
code. Self-contained: builds throwaway modules/packages/harnesses in a tempdir so
the test does not depend on the committed demo.

Run:  uv run python maw-tools/selftest_refactor_checks.py
Exit: 0 if every assertion holds, 1 otherwise.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

RC = Path(__file__).with_name("refactor_checks.py")
results: list[tuple[bool, str]] = []


def record(ok: bool, msg: str) -> None:
    results.append((bool(ok), msg))
    print(f"  {'[ok]' if ok else '[XX]'} {msg}")


def run(*args: str) -> tuple[int, dict | None]:
    proc = subprocess.run([sys.executable, str(RC), *args], capture_output=True, text=True)
    try:
        return proc.returncode, json.loads(proc.stdout)
    except json.JSONDecodeError:
        return proc.returncode, None


def run_raw(*args: str) -> tuple[int, str]:
    proc = subprocess.run([sys.executable, str(RC), *args], capture_output=True, text=True)
    return proc.returncode, proc.stdout


def w(p: Path, text: str) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)

        # ---- bloat ----------------------------------------------------- #
        print("refactor_checks.py bloat:")
        bloated = w(tmp / "bloated.py",
                    "".join(f"def f{i}(x):\n    if x:\n        return x+{i}\n    return {i}\n\n\n"
                            for i in range(8)))
        code, data = run("bloat", str(bloated), "--max-defs", "5", "--max-loc", "30")
        r = data["reports"][0] if data else {}
        record(code == 1 and data and data["passed"] is False and r.get("over_budget"),
               f"bloated file over budget -> exit {code}, exceeded={list(r.get('exceeded', {}))} (want fail)")
        small = w(tmp / "small.py", "def a(x):\n    return x\n")
        code, data = run("bloat", str(small), "--max-defs", "5", "--max-loc", "30")
        record(code == 0 and data and data["passed"] is True,
               f"small file within budget -> exit {code} (want pass)")
        # ranking: worse offender ranked first
        big = w(tmp / "big.py", "".join(f"def g{i}():\n    return {i}\n\n\n" for i in range(20)))
        code, data = run("bloat", str(bloated), str(big), "--max-defs", "5", "--max-loc", "30")
        offenders = [Path(o["file"]).name for o in (data["offenders"] if data else [])]
        record(code == 1 and offenders and offenders[0] == "big.py",
               f"offenders ranked worst-first -> {offenders} (want big.py first)")

        # ---- api ------------------------------------------------------- #
        print("refactor_checks.py api:")
        # flat module
        flat = tmp / "flatpkg"
        w(flat / "mod.py", "__all__=['f','g']\n"
                           "def f(x):\n    return x*2\n\n"
                           "def g(x, y=1):\n    return x+y\n")
        code, out = run_raw("api", "--module", "mod", "--src-dir", str(flat))
        base = tmp / "base_api.json"
        base.write_text(out, encoding="utf-8")
        names = list(json.loads(out)["api"])
        record(code == 0 and names == ["f", "g"], f"api extracts public names {names} (want ['f','g'])")
        # package re-export with identical surface
        pkg = tmp / "pkgpkg"
        w(pkg / "mod" / "__init__.py", "from .a import f\nfrom .b import g\n__all__=['f','g']\n")
        w(pkg / "mod" / "a.py", "def f(x):\n    return x*2\n")
        w(pkg / "mod" / "b.py", "def g(x, y=1):\n    return x+y\n")
        code, data = run("api", "--module", "mod", "--src-dir", str(pkg), "--baseline", str(base))
        record(code == 0 and data and data["passed"] is True,
               f"package re-export identical to flat baseline -> exit {code} (want pass)")
        # removed public name -> api diff
        gone = tmp / "gonepkg"
        w(gone / "mod.py", "__all__=['f']\ndef f(x):\n    return x*2\n")
        code, data = run("api", "--module", "mod", "--src-dir", str(gone), "--baseline", str(base))
        record(code == 1 and data and data["passed"] is False and "g" in data.get("removed", []),
               f"removed public name caught -> exit {code}, removed={data and data.get('removed')} (want fail)")
        # changed signature -> api diff
        chg = tmp / "chgpkg"
        w(chg / "mod.py", "__all__=['f','g']\ndef f(x):\n    return x*2\n\ndef g(x, y, z):\n    return x\n")
        code, data = run("api", "--module", "mod", "--src-dir", str(chg), "--baseline", str(base))
        record(code == 1 and data and data["passed"] is False and "g" in data.get("changed", []),
               f"changed signature caught -> exit {code}, changed={data and data.get('changed')} (want fail)")

        # ---- golden ---------------------------------------------------- #
        print("refactor_checks.py golden:")
        harness = w(tmp / "h.py", "def golden():\n    import mod\n    return {'f': mod.f(3), 'g': mod.g(2)}\n")
        snap = tmp / "gold.json"
        code, data = run("golden", "--harness", str(harness), "--src-dir", str(flat), "--snapshot", str(snap))
        record(code == 0 and snap.is_file(), f"golden snapshot written -> exit {code}")
        # identical behavior (package re-export) -> GREEN
        code, data = run("golden", "--harness", str(harness), "--src-dir", str(pkg), "--compare", str(snap))
        record(code == 0 and data and data["passed"] is True,
               f"golden identical behavior -> exit {code} (want pass)")
        # mutated behavior -> RED, with the first difference reported
        mut = tmp / "mutpkg"
        w(mut / "mod.py", "__all__=['f','g']\ndef f(x):\n    return x*3\n\ndef g(x, y=1):\n    return x+y\n")
        code, data = run("golden", "--harness", str(harness), "--src-dir", str(mut), "--compare", str(snap))
        record(code == 1 and data and data["passed"] is False and data.get("first_difference"),
               f"golden mutated behavior -> exit {code}, first_diff={data and data.get('first_difference')} (want fail)")

    ok = all(r[0] for r in results)
    print(f"\n{'ALL PASS' if ok else 'FAILURES PRESENT'}: "
          f"{sum(1 for r in results if r[0])}/{len(results)} assertions held")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
