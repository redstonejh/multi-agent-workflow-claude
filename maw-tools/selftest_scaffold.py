#!/usr/bin/env python3
"""selftest_scaffold.py — prove maw-tools/scaffold_run.py reflects reality.

`scaffold_run.py` is the only `maw-tools/` script with no model and no network —
it just creates the run-folder layout and the hand-off file naming from
docs/05-memory-and-handoffs.md. The /maw conductor leans on those exact names and
that exact layout, so a silent drift (slug derivation, a missing subdir, broken
hand-off numbering, lost zero-padding) would quietly break every run. This test
pins that contract: pure-function unit checks for `slugify` / `_next_step`, plus
end-to-end CLI checks for `init` and `handoff` that assert the bytes on disk.

Run:  uv run python maw-tools/selftest_scaffold.py
Exit: 0 if every assertion holds, 1 otherwise.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

SR = Path(__file__).with_name("scaffold_run.py")
sys.path.insert(0, str(Path(__file__).parent))
import scaffold_run as sr  # noqa: E402  (path injected above)

results: list[tuple[bool, str]] = []


def record(ok: bool, msg: str) -> None:
    results.append((bool(ok), msg))
    print(f"  {'[ok]' if ok else '[XX]'} {msg}")


def run(*args: str) -> tuple[int, str]:
    proc = subprocess.run([sys.executable, str(SR), *args], capture_output=True, text=True)
    return proc.returncode, proc.stdout


def run_json(*args: str) -> tuple[int, dict | None]:
    code, out = run(*args)
    try:
        return code, json.loads(out)
    except json.JSONDecodeError:
        return code, None


def main() -> int:
    # ----------------------------------------------------------------- #
    # Pure functions — deterministic, no filesystem.
    # ----------------------------------------------------------------- #
    print("scaffold_run.py slugify / _next_step (pure):")
    record(sr.slugify("Fix the Failing Test in payments.py") == "fix-the-failing-test",
           "slugify lowercases, drops punctuation, keeps first 4 words")
    record(sr.slugify("!!! ??? ...") == "run",
           "slugify falls back to 'run' when no word chars survive")
    record(sr.slugify("alpha beta gamma delta epsilon", max_words=2) == "alpha-beta",
           "slugify honors max_words")

    with tempfile.TemporaryDirectory() as d:
        empty = Path(d)
        record(sr._next_step(empty) == 1, "_next_step on empty handoffs dir -> 1")
        for n in ("01_a__to__b.md", "02_b__to__c.md", "05_x__to__y.md", "notnum_z.md"):
            (empty / n).write_text("x", encoding="utf-8")
        record(sr._next_step(empty) == 6,
               "_next_step returns max NN + 1, ignoring non-numeric names")

    # ----------------------------------------------------------------- #
    # init — full run-folder layout from docs/05.
    # ----------------------------------------------------------------- #
    with tempfile.TemporaryDirectory() as d:
        root = Path(d) / "runs"
        print("scaffold_run.py init:")
        agents = "conductor,planner,worker,critic,acceptance_gate"
        code, data = run_json("init", "ship the thing", "--root", str(root),
                              "--agents", agents, "--json")
        ok_json = bool(data) and code == 0 and data.get("agents") == agents.split(",")
        record(ok_json, f"init --json -> exit {code}, agents echoed back")

        run_dir = Path(data["run_dir"]) if data else None
        layout_ok = bool(run_dir) and all(
            (run_dir / sub).is_dir() for sub in ("agents", "handoffs", "artifacts"))
        record(layout_ok, "init creates agents/ handoffs/ artifacts/ subdirs")

        files_ok = bool(run_dir) and (run_dir / "run.md").is_file() \
            and (run_dir / "memory.md").is_file()
        record(files_ok, "init writes run.md and memory.md")

        seeded = bool(run_dir) and all(
            (run_dir / "agents" / f"{a}.md").is_file() for a in agents.split(","))
        record(seeded, "init pre-seeds one agents/<name>.md per --agents entry")

        run_md = (run_dir / "run.md").read_text(encoding="utf-8") if run_dir else ""
        record("ship the thing" in run_md and run_dir.name in run_md,
               "run.md embeds the task text and run_id")

        # two inits must not collide (random token suffix)
        _, data2 = run_json("init", "ship the thing", "--root", str(root),
                            "--agents", agents, "--json")
        distinct = bool(data2) and data2.get("run_id") != (data or {}).get("run_id")
        record(distinct, "two inits with identical args yield distinct run_ids")

    # ----------------------------------------------------------------- #
    # handoff — docs/05 file naming + auto-increment + zero-padding.
    # ----------------------------------------------------------------- #
    with tempfile.TemporaryDirectory() as d:
        root = Path(d) / "runs"
        print("scaffold_run.py handoff:")
        _, data = run_json("init", "demo task", "--root", str(root), "--json")
        run_dir = Path(data["run_dir"])

        code, out = run("handoff", "--run", str(run_dir), "--from", "planner", "--to", "worker")
        first = Path(out.strip()) if out.strip() else None
        record(code == 0 and first is not None and first.name == "01_planner__to__worker.md",
               f"first handoff -> {first.name if first else None} (want 01_planner__to__worker.md)")

        body = first.read_text(encoding="utf-8") if first and first.is_file() else ""
        record("# Hand-off: planner → worker" in body and "step 01" in body,
               "handoff body fills the docs/05 template header (from -> to, step 01)")

        code, out = run("handoff", "--run", str(run_dir), "--from", "worker", "--to", "critic")
        second = Path(out.strip()) if out.strip() else None
        record(code == 0 and second is not None and second.name == "02_worker__to__critic.md",
               f"second handoff auto-increments -> {second.name if second else None}")

        code, out = run("handoff", "--run", str(run_dir), "--from", "critic", "--to", "worker",
                        "--step", "7")
        padded = Path(out.strip()) if out.strip() else None
        record(code == 0 and padded is not None and padded.name == "07_critic__to__worker.md",
               f"explicit --step 7 zero-pads -> {padded.name if padded else None}")

        # handoff into a path with no handoffs/ dir must refuse, exit 1
        code, _ = run("handoff", "--run", str(Path(d) / "nope"),
                      "--from", "a", "--to", "b")
        record(code == 1, "handoff into a non-run dir refuses with exit 1")

    ok = all(r[0] for r in results)
    print(f"\n{'ALL PASS' if ok else 'FAILURES PRESENT'}: "
          f"{sum(1 for r in results if r[0])}/{len(results)} assertions held")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
