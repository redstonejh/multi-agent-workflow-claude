#!/usr/bin/env python3
"""code_checks.py — deterministic code-work checks for Multi-Agent Workflow.

Phase 3.8 (docs/07-code-and-debugging.md). Same rule as the rest of `maw-tools/`:
**compute first, reason second.** Finding every reference to a symbol, compiling a
file, or detecting clone bodies are deterministic AST/stdlib operations — no model,
no network. The code *roster* agents (`dep_mapper`, `bug_hunter`, `debugger`,
`code_reviewer`, ...) run these and only *interpret* the result.

Subcommands
-----------
  refs    AST-scan the codebase for every file:line that references a symbol
          (function / class / constant / imported name). The deterministic
          backbone for hidden-dependency / blast-radius detection — "changing X
          touches these N sites" is computed, not guessed. `--expect N` asserts
          the count (so a self-test can pin it).
  syntax  `compile()` every target file; fail on syntax errors AND null-byte
          corruption (a real saga — see bugs/RCA-001). No .pyc is written.
  test    Forward to the existing checks.py test runner (one command for code work).
  dupes   Flag structural clone function bodies (identifiers/constants blanked).
          Fuzzy / edit-distance "near" duplicates are # MAW-TODO.

Every subcommand prints a JSON object with a boolean `passed` field and exits 0
when `passed` is true, non-zero otherwise — so callers gate on `$?`. Usage/runtime
errors exit 2. On a machine where `python` is not on PATH, invoke with `uv run`.

Examples
--------
  python code_checks.py refs --symbol dedupe_orders --root examples/coupling_demo
  python code_checks.py syntax examples/coupling_demo/orders.py
  python code_checks.py test --cmd "python test_orders.py" --cwd examples/coupling_demo
  python code_checks.py dupes --root examples/coupling_demo
"""
from __future__ import annotations

import argparse
import ast
import copy
import json
import subprocess
import sys
from pathlib import Path


def _emit(obj: dict, passed: bool) -> int:
    print(json.dumps(obj, indent=2))
    return 0 if passed else 1


def _collect_py(files: list[str] | None, root: str | None) -> list[Path]:
    """Resolve the target .py files: explicit list, or a recursive scan of root."""
    if files:
        return [Path(f) for f in files]
    base = Path(root) if root else Path(".")
    out = []
    for p in sorted(base.rglob("*.py")):
        # Filter dotted / __pycache__ components only BELOW the scan root. The root
        # itself may legitimately be a dotted path the caller named on purpose
        # (e.g. --root .claude); filtering the root's OWN parts silently returns
        # zero files, which reads as a false "all clean" / "0 refs" — the exact
        # false-negative this tool exists to prevent.
        try:
            rel_parts = p.relative_to(base).parts
        except ValueError:
            rel_parts = p.parts
        if "__pycache__" in rel_parts or any(s.startswith(".") for s in rel_parts):
            continue
        out.append(p)
    return out


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(Path.cwd()))
    except ValueError:
        return str(p)


# ---------------------------------------------------------------------------
# refs — every reference to a symbol (blast radius, docs/07 §7)
# ---------------------------------------------------------------------------

def cmd_refs(args: argparse.Namespace) -> int:
    sym = args.symbol
    files = _collect_py(args.files, args.root)
    sites: list[dict] = []
    parse_errors: list[str] = []

    for f in files:
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
        except (SyntaxError, ValueError, UnicodeDecodeError) as e:
            parse_errors.append(f"{_rel(f)}: {e}")
            continue
        for node in ast.walk(tree):
            kind = None
            if isinstance(node, ast.Name) and node.id == sym:
                kind = "name"
            elif isinstance(node, ast.Attribute) and node.attr == sym:
                kind = "attribute"
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) \
                    and node.name == sym:
                kind = "def"
            elif isinstance(node, ast.ImportFrom):
                for a in node.names:
                    if a.name == sym:
                        sites.append({"file": _rel(f), "line": node.lineno,
                                      "col": node.col_offset, "kind": "import"})
                continue
            if kind:
                sites.append({"file": _rel(f), "line": getattr(node, "lineno", 0),
                              "col": getattr(node, "col_offset", 0), "kind": kind})

    sites.sort(key=lambda s: (s["file"], s["line"], s["col"]))
    count = len(sites)
    passed = (args.expect is None) or (count == args.expect)
    return _emit({
        "check": "refs",
        "symbol": sym,
        "files_scanned": len(files),
        "ref_count": count,
        "expected": args.expect,
        "sites": sites,
        "parse_errors": parse_errors,
        "passed": passed,
        "note": (f"{count} reference site(s) — this is the blast radius of changing "
                 f"`{sym}`" if passed
                 else f"expected {args.expect} site(s), found {count}"),
    }, passed)


# ---------------------------------------------------------------------------
# syntax — compile every file; catch syntax errors AND null bytes (RCA-001)
# ---------------------------------------------------------------------------

def cmd_syntax(args: argparse.Namespace) -> int:
    files = _collect_py(args.files, args.root)
    results = []
    ok = True
    for f in files:
        try:
            src = f.read_bytes()
            # builtin compile() raises ValueError on embedded NULs and SyntaxError
            # on bad syntax — covers both failure modes, and writes no .pyc.
            compile(src, str(f), "exec")
            results.append({"file": _rel(f), "ok": True})
        except (SyntaxError, ValueError) as e:
            ok = False
            results.append({"file": _rel(f), "ok": False, "error": f"{type(e).__name__}: {e}"})
    return _emit({
        "check": "syntax",
        "files_checked": len(files),
        "results": results,
        "passed": ok,
        "note": ("all target files compile (no syntax errors, no null bytes)"
                 if ok else "compile failed — syntax error or null-byte corruption"),
    }, ok)


# ---------------------------------------------------------------------------
# test — forward to the existing checks.py test runner
# ---------------------------------------------------------------------------

def cmd_test(args: argparse.Namespace) -> int:
    checks = Path(__file__).with_name("checks.py")
    cmd = [sys.executable, str(checks), "test", "--cmd", args.cmd]
    if args.cwd:
        cmd += ["--cwd", args.cwd]
    if args.timeout is not None:
        cmd += ["--timeout", str(args.timeout)]
    # Inherit stdout/stderr so the checks.py JSON prints verbatim, and forward
    # its exit code — code work uses one `test` entry point.
    return subprocess.run(cmd).returncode


# ---------------------------------------------------------------------------
# dupes — structural clone function bodies (fuzzy near-dup is # MAW-TODO)
# ---------------------------------------------------------------------------

class _Blank(ast.NodeTransformer):
    """Erase identifiers / constants so only the structural skeleton remains."""

    def visit_Name(self, n):
        return ast.copy_location(ast.Name(id="_", ctx=n.ctx), n)

    def visit_arg(self, n):
        n.arg = "_"
        n.annotation = None
        return n

    def visit_Constant(self, n):
        return ast.copy_location(ast.Constant(value=None), n)

    def visit_Attribute(self, n):
        self.generic_visit(n)
        n.attr = "_"
        return n


def _skeleton(fn: ast.AST) -> str:
    body = copy.deepcopy(getattr(fn, "body", []))
    mod = ast.Module(body=[_Blank().visit(s) for s in body], type_ignores=[])
    return ast.dump(mod)  # attributes (lineno/col) excluded by default


def cmd_dupes(args: argparse.Namespace) -> int:
    files = _collect_py(args.files, args.root)
    buckets: dict[str, list[dict]] = {}
    for f in files:
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
        except (SyntaxError, ValueError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                n_stmts = len(node.body)
                if n_stmts < args.min_stmts:
                    continue
                buckets.setdefault(_skeleton(node), []).append(
                    {"file": _rel(f), "name": node.name, "line": node.lineno})

    groups = [g for g in buckets.values() if len(g) > 1]
    passed = len(groups) == 0
    return _emit({
        "check": "dupes",
        "files_scanned": len(files),
        "min_stmts": args.min_stmts,
        "duplicate_groups": groups,
        "group_count": len(groups),
        "passed": passed,
        "note": ("no structural clone bodies found"
                 if passed else f"{len(groups)} clone group(s) — consider extracting a"
                 " shared helper") + " (fuzzy / edit-distance near-dup is # MAW-TODO)",
    }, passed)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Deterministic code-work checks (no model, no network).")
    sub = p.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("refs", help="every file:line that references a symbol (blast radius)")
    pr.add_argument("--symbol", required=True, help="the symbol (function/class/constant) to trace")
    pr.add_argument("files", nargs="*", help="explicit files (default: scan --root)")
    pr.add_argument("--root", default=".", help="root dir to scan for *.py (default: .)")
    pr.add_argument("--expect", type=int, default=None, help="assert the reference count == N")
    pr.set_defaults(func=cmd_refs)

    ps = sub.add_parser("syntax", help="compile files; fail on syntax errors / null bytes")
    ps.add_argument("files", nargs="*", help="explicit files (default: scan --root)")
    ps.add_argument("--root", default=".", help="root dir to scan for *.py (default: .)")
    ps.set_defaults(func=cmd_syntax)

    pt = sub.add_parser("test", help="forward to checks.py test runner")
    pt.add_argument("--cmd", required=True, help="the test command to run")
    pt.add_argument("--cwd", default=None, help="working directory")
    pt.add_argument("--timeout", type=float, default=None, help="timeout in seconds")
    pt.set_defaults(func=cmd_test)

    pd = sub.add_parser("dupes", help="structural clone function bodies")
    pd.add_argument("files", nargs="*", help="explicit files (default: scan --root)")
    pd.add_argument("--root", default=".", help="root dir to scan for *.py (default: .)")
    pd.add_argument("--min-stmts", type=int, default=2, help="ignore bodies smaller than N statements")
    pd.set_defaults(func=cmd_dupes)
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
