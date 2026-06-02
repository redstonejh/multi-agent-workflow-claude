#!/usr/bin/env python3
"""refactor_checks.py — deterministic metrics + behavior-equivalence for refactors.

The refactoring pack. A refactor must be *behavior-preserving*; this provides the
trigger (file bloat) and the truth comparison (does the public surface + runtime
behavior survive the split?). Same rule as the rest of `maw-tools/`: **compute
first, reason second** — the `refactor_scout` / `refactorer` agents act on these
numbers; they don't eyeball them.

Subcommands
-----------
  bloat   Per-file metrics (LOC, top-level def/class count, longest-function LOC,
          branch count ~ cyclomatic complexity, import count) vs configurable
          budgets. Flags + ranks offenders; exit non-zero if any file is over
          budget. This is the TRIGGER. (pure `ast`)
  api     The public API surface of a module (exported names + signatures), by
          importing it and introspecting — so a flat module and a re-exporting
          package compare identically. Snapshot, or `--baseline` to diff + gate.
  golden  Run a harness (a .py exposing `golden() -> dict`) and capture its outputs
          to a snapshot; `--compare` re-runs and asserts byte-identical output.
          This is the BEHAVIORAL truth comparison (catches what tests miss).

JSON out + exit 0/1 so callers gate on `$?`; usage/runtime errors exit 2. On a
machine where `python` is not on PATH, invoke with `uv run`.

Honesty: `branch_count` APPROXIMATES cyclomatic complexity (it counts branch-ish
AST nodes — see _branch_count); a precise McCabe number and call-graph cohesion
metrics are # MAW-TODO. `api`/`golden` import the target (they run module-level
code), which is inherent to comparing real runtime behavior.

Examples
--------
  uv run python maw-tools/refactor_checks.py bloat examples/refactor_demo/bloated/widgets.py --max-loc 120
  uv run python maw-tools/refactor_checks.py api --module widgets --src-dir examples/refactor_demo/bloated
  uv run python maw-tools/refactor_checks.py api --module widgets --src-dir examples/refactor_demo/split --baseline before_api.json
  uv run python maw-tools/refactor_checks.py golden --harness examples/refactor_demo/golden_harness.py --src-dir examples/refactor_demo/bloated --snapshot gold.json
  uv run python maw-tools/refactor_checks.py golden --harness examples/refactor_demo/golden_harness.py --src-dir examples/refactor_demo/split --compare gold.json
"""
from __future__ import annotations

import argparse
import ast
import importlib
import importlib.util
import inspect
import json
import sys
from pathlib import Path


def _emit(obj: dict, passed: bool) -> int:
    print(json.dumps(obj, indent=2))
    return 0 if passed else 1


# --------------------------------------------------------------------------- #
# bloat — per-file metrics vs budgets (pure ast). The refactor trigger.
# --------------------------------------------------------------------------- #

DEFAULT_BUDGETS = {
    "loc": 200,            # total physical lines
    "defs": 10,            # top-level def + class count
    "func_loc": 60,        # longest single function (lines)
    "branches": 40,        # branch-ish nodes ~ cyclomatic complexity (approx)
    "imports": 20,         # import statements
}

_BRANCH_NODES = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler,
                 ast.With, ast.AsyncWith, ast.IfExp)


def _branch_count(tree: ast.AST) -> int:
    """APPROXIMATE cyclomatic complexity: count branch-ish nodes. Not the exact
    McCabe number (that is # MAW-TODO) — but a deterministic, monotonic proxy."""
    n = 0
    for node in ast.walk(tree):
        if isinstance(node, _BRANCH_NODES):
            n += 1
        elif isinstance(node, ast.BoolOp):           # each and/or adds a path
            n += len(node.values) - 1
        elif isinstance(node, ast.comprehension):     # comprehension filters
            n += len(node.ifs)
        elif isinstance(node, getattr(ast, "match_case", ())):  # match arms (3.10+)
            n += 1
    return n


def _collect_py(files: list[str] | None, root: str | None) -> list[Path]:
    if files:
        return [Path(f) for f in files]
    base = Path(root) if root else Path(".")
    out = []
    for p in sorted(base.rglob("*.py")):
        try:
            rel = p.relative_to(base).parts
        except ValueError:
            rel = p.parts
        if "__pycache__" in rel or any(s.startswith(".") for s in rel):
            continue
        out.append(p)
    return out


def _file_metrics(path: Path) -> dict:
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src, filename=str(path))
    body = tree.body
    top_defs = [n for n in body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
    func_lens = [
        (n.end_lineno - n.lineno + 1)
        for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        and n.end_lineno is not None
    ]
    imports = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
    return {
        "loc": len(src.splitlines()),
        "defs": len(top_defs),
        "func_loc": max(func_lens) if func_lens else 0,
        "branches": _branch_count(tree),
        "imports": len(imports),
    }


def cmd_bloat(args: argparse.Namespace) -> int:
    budgets = dict(DEFAULT_BUDGETS)
    for k in budgets:
        v = getattr(args, f"max_{k}", None)
        if v is not None:
            budgets[k] = v

    files = _collect_py(args.files, args.root)
    reports = []
    for f in files:
        try:
            m = _file_metrics(f)
        except (SyntaxError, ValueError, UnicodeDecodeError) as e:
            reports.append({"file": str(f), "error": f"{type(e).__name__}: {e}", "over_budget": False})
            continue
        exceeded = {k: {"value": m[k], "budget": budgets[k]} for k in budgets if m[k] > budgets[k]}
        # severity = total fractional overage across the metrics that blew budget
        severity = round(sum(m[k] / budgets[k] - 1 for k in exceeded), 4)
        reports.append({
            "file": str(f), "metrics": m, "exceeded": exceeded,
            "over_budget": bool(exceeded), "severity": severity,
        })

    offenders = sorted([r for r in reports if r.get("over_budget")],
                       key=lambda r: r["severity"], reverse=True)
    passed = len(offenders) == 0
    return _emit({
        "check": "bloat",
        "budgets": budgets,
        "files_scanned": len(files),
        "over_budget_count": len(offenders),
        "offenders": offenders,
        "reports": reports,
        "passed": passed,
        "note": ("every file is within budget"
                 if passed else f"{len(offenders)} file(s) over budget — ranked worst-first; "
                 "consider a behavior-preserving split (branch_count ~ cyclomatic, approx)"),
    }, passed)


# --------------------------------------------------------------------------- #
# Shared: import a module / load a harness with extra dirs on sys.path
# --------------------------------------------------------------------------- #

def _fresh_import(name: str, src_dirs: list[str]):
    for d in reversed(src_dirs):
        if d and d not in sys.path:
            sys.path.insert(0, d)
    for m in [k for k in sys.modules if k == name or k.startswith(name + ".")]:
        del sys.modules[m]
    return importlib.import_module(name)


# --------------------------------------------------------------------------- #
# api — public surface (names + signatures) via import + introspection
# --------------------------------------------------------------------------- #

def _describe(obj) -> dict:
    if inspect.isclass(obj):
        methods = {}
        for n, m in vars(obj).items():
            if callable(m) and (not n.startswith("_") or n == "__init__"):
                try:
                    methods[n] = str(inspect.signature(m))
                except (ValueError, TypeError):
                    methods[n] = "(signature unavailable)"
        return {"kind": "class", "methods": dict(sorted(methods.items()))}
    if callable(obj):
        try:
            return {"kind": "callable", "signature": str(inspect.signature(obj))}
        except (ValueError, TypeError):
            return {"kind": "callable", "signature": "(signature unavailable)"}
    return {"kind": type(obj).__name__}


def _public_api(mod) -> dict:
    if hasattr(mod, "__all__"):
        names = list(mod.__all__)
        source = "__all__"
    else:
        names = [n for n in dir(mod) if not n.startswith("_")]
        source = "non-underscore names (no __all__; may include incidental imports — # MAW-TODO)"
    api = {}
    for n in sorted(names):
        api[n] = _describe(getattr(mod, n)) if hasattr(mod, n) else {"kind": "MISSING"}
    return {"names_source": source, "api": api}


def cmd_api(args: argparse.Namespace) -> int:
    mod = _fresh_import(args.module, [args.src_dir] if args.src_dir else [])
    surface = _public_api(mod)
    canonical = json.dumps(surface["api"], sort_keys=True)
    import hashlib
    surface["api_sha256"] = hashlib.sha256(canonical.encode()).hexdigest()
    surface["module"] = args.module

    if args.baseline:
        base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
        base_api = base.get("api", {})
        cur_api = surface["api"]
        added = sorted(set(cur_api) - set(base_api))
        removed = sorted(set(base_api) - set(cur_api))
        changed = sorted(n for n in set(cur_api) & set(base_api) if cur_api[n] != base_api[n])
        identical = not (added or removed or changed)
        return _emit({
            "check": "api", "module": args.module, "mode": "compare",
            "baseline": args.baseline,
            "added": added, "removed": removed, "changed": changed,
            "baseline_sha256": base.get("api_sha256"),
            "current_sha256": surface["api_sha256"],
            "passed": identical,
            "note": ("public API surface is byte-identical to the baseline"
                     if identical else
                     f"API surface CHANGED: +{added} -{removed} ~{changed} "
                     "— not behavior-preserving"),
        }, identical)

    # snapshot mode
    print(json.dumps(surface, indent=2))
    return 0


# --------------------------------------------------------------------------- #
# golden — run a harness, capture outputs; --compare asserts byte-identical
# --------------------------------------------------------------------------- #

def _run_harness(harness_path: str, src_dirs: list[str]) -> str:
    for d in reversed(src_dirs):
        if d and d not in sys.path:
            sys.path.insert(0, d)
    spec = importlib.util.spec_from_file_location("maw_golden_harness", harness_path)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load harness {harness_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not hasattr(mod, "golden"):
        raise ValueError(f"harness {harness_path} must define golden() -> dict")
    result = mod.golden()
    # deterministic, byte-stable serialization; default=repr so anything serializes
    return json.dumps(result, sort_keys=True, indent=2, default=repr)


def cmd_golden(args: argparse.Namespace) -> int:
    src_dirs = [args.src_dir] if args.src_dir else []
    current = _run_harness(args.harness, src_dirs)

    if args.compare:
        snap = Path(args.compare).read_text(encoding="utf-8")
        identical = current == snap
        first_diff = None
        if not identical:
            cur, old = json.loads(current), json.loads(snap)
            for k in sorted(set(cur) | set(old)):
                if cur.get(k, "<missing>") != old.get(k, "<missing>"):
                    first_diff = {"case": k, "snapshot": old.get(k, "<missing>"),
                                  "current": cur.get(k, "<missing>")}
                    break
        return _emit({
            "check": "golden", "mode": "compare", "harness": args.harness,
            "snapshot": args.compare, "cases": len(json.loads(current)),
            "identical": identical, "first_difference": first_diff,
            "passed": identical,
            "note": ("golden outputs are byte-identical to the snapshot — behavior preserved"
                     if identical else "golden outputs DIFFER from the snapshot — behavior changed"),
        }, identical)

    # snapshot mode: write the captured outputs
    if args.snapshot:
        Path(args.snapshot).write_text(current, encoding="utf-8")
        print(json.dumps({"check": "golden", "mode": "snapshot", "harness": args.harness,
                          "snapshot": args.snapshot, "cases": len(json.loads(current)),
                          "passed": True, "note": "captured golden outputs"}, indent=2))
    else:
        print(current)
    return 0


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Deterministic refactor metrics + behavior equivalence.")
    sub = p.add_subparsers(dest="cmd", required=True)

    pb = sub.add_parser("bloat", help="per-file metrics vs budgets; rank offenders")
    pb.add_argument("files", nargs="*", help="explicit files (default: scan --root)")
    pb.add_argument("--root", default=".", help="root dir to scan for *.py (default: .)")
    pb.add_argument("--max-loc", type=int, default=None, help=f"max LOC (default {DEFAULT_BUDGETS['loc']})")
    pb.add_argument("--max-defs", type=int, default=None, help=f"max top-level defs/classes (default {DEFAULT_BUDGETS['defs']})")
    pb.add_argument("--max-func-loc", type=int, default=None, dest="max_func_loc",
                    help=f"max longest-function LOC (default {DEFAULT_BUDGETS['func_loc']})")
    pb.add_argument("--max-branches", type=int, default=None, help=f"max branch count (default {DEFAULT_BUDGETS['branches']})")
    pb.add_argument("--max-imports", type=int, default=None, help=f"max imports (default {DEFAULT_BUDGETS['imports']})")
    pb.set_defaults(func=cmd_bloat)

    pa = sub.add_parser("api", help="public API surface of a module (import + introspect)")
    pa.add_argument("--module", required=True, help="importable module name (e.g. widgets)")
    pa.add_argument("--src-dir", default=None, help="dir to prepend to sys.path so --module resolves")
    pa.add_argument("--baseline", default=None, help="compare against a saved api JSON (gate mode)")
    pa.set_defaults(func=cmd_api)

    pg = sub.add_parser("golden", help="capture/compare golden outputs from a harness")
    pg.add_argument("--harness", required=True, help="path to a .py defining golden() -> dict")
    pg.add_argument("--src-dir", default=None, help="dir to prepend to sys.path for the harness's imports")
    pg.add_argument("--snapshot", default=None, help="write captured outputs here (snapshot mode)")
    pg.add_argument("--compare", default=None, help="assert outputs byte-identical to this snapshot (gate mode)")
    pg.set_defaults(func=cmd_golden)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, FileNotFoundError, ImportError, SyntaxError, json.JSONDecodeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
