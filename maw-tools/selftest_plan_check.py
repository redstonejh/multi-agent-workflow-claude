#!/usr/bin/env python3
"""selftest_plan_check.py — prove maw-tools/plan_check.py reflects reality.

Green-on-valid / red-on-bad for every plan rule, asserting both the JSON `passed`
verdict, the exit code, AND that the SPECIFIC violation is named. A fixed --roster
keeps the test self-contained (independent of which agents currently exist on disk).

Run:  uv run python maw-tools/selftest_plan_check.py
Exit: 0 if every assertion holds, 1 otherwise.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PC = Path(__file__).with_name("plan_check.py")
ROSTER = ("planner,worker,leakage_auditor,baseline_enforcer,metric_validator,"
          "acceptance_gate,a11y_auditor,change_verifier,code_reviewer,dep_mapper")
results: list[tuple[bool, str]] = []


def record(ok: bool, msg: str) -> None:
    results.append((bool(ok), msg))
    print(f"  {'[ok]' if ok else '[XX]'} {msg}")


def run(plan: dict) -> tuple[int, dict | None]:
    proc = subprocess.run([sys.executable, str(PC), "--roster", ROSTER],
                          input=json.dumps(plan), capture_output=True, text=True)
    try:
        return proc.returncode, json.loads(proc.stdout)
    except json.JSONDecodeError:
        return proc.returncode, None


def expect_pass(plan: dict, label: str) -> None:
    code, data = run(plan)
    record(code == 0 and bool(data) and data.get("passed") is True,
           f"{label}: exit {code}, passed={data and data.get('passed')} (want pass)")


def expect_fail(plan: dict, must_contain: str, label: str) -> None:
    code, data = run(plan)
    blob = " ".join(data.get("violations", [])) if data else ""
    ok = code == 1 and bool(data) and data.get("passed") is False and must_contain in blob
    record(ok, f"{label}: exit {code}, violation~{must_contain!r} (want fail naming it)")


J = lambda n: {"name": n, "justification": "needed for this run"}


def base(roles, task_type="ml", **kw):
    return {"task_type": task_type,
            "caps": {"max_agents": 5, "max_parallel": 3, "max_iters": 3},
            "roles": roles, **kw}


ML_OK = [J("planner"), J("leakage_auditor"), J("baseline_enforcer"), J("acceptance_gate")]
FE_OK = [J("a11y_auditor"), J("change_verifier"), J("acceptance_gate")]
CODE_OK = [J("code_reviewer"), J("dep_mapper"), J("acceptance_gate")]


def main() -> int:
    print("plan_check.py — valid plans pass:")
    expect_pass(base(ML_OK), "ml plan with both required validators")
    expect_pass(base(FE_OK, "frontend"), "frontend plan with a11y + change_verifier")
    expect_pass(base(CODE_OK, "code"), "code plan with code_reviewer + dep_mapper")
    expect_pass(base([J("worker"), J("acceptance_gate")], "generic"), "generic plan")

    print("plan_check.py — required-role rules fire:")
    expect_fail(base([J("planner"), J("baseline_enforcer"), J("acceptance_gate")]),
                "leakage_auditor", "ml plan missing leakage_auditor")
    expect_fail(base([J("planner"), J("leakage_auditor"), J("acceptance_gate")]),
                "baseline_enforcer", "ml plan missing baseline_enforcer")
    expect_fail(base([J("a11y_auditor"), J("acceptance_gate")], "frontend"),
                "change_verifier", "frontend plan missing change_verifier")
    expect_fail(base([J("code_reviewer"), J("acceptance_gate")], "code"),
                "dep_mapper", "code plan missing dep_mapper")

    print("plan_check.py — structural rules fire:")
    expect_fail(base([J("planner"), J("leakage_auditor"), J("baseline_enforcer")]),
                "acceptance_gate", "missing acceptance_gate")
    expect_fail(base(ML_OK + [J("leakage_auditor")]), "duplicate", "duplicate role")
    expect_fail(base(["leakage_auditor", J("baseline_enforcer"), J("acceptance_gate")]),
                "justification", "unjustified (bare-string) role")
    expect_fail(base(ML_OK + [J("nonexistent_agent")]), "roster", "role not in roster")
    expect_fail(base([J("planner"), J("worker"), J("metric_validator"), J("leakage_auditor"),
                      J("baseline_enforcer"), J("acceptance_gate")]),
                "max_agents", "too many roles (governor max_agents)")
    expect_fail(base(ML_OK, caps={"max_agents": 9, "max_parallel": 3, "max_iters": 3}),
                "exceeds governor", "declared cap exceeds governor")
    expect_fail(base(ML_OK, parallel=4), "parallel", "planned parallel exceeds cap")
    expect_fail(base(ML_OK, task_type="bogus"), "unknown task_type", "unknown task type")

    ok = all(r[0] for r in results)
    print(f"\n{'ALL PASS' if ok else 'FAILURES PRESENT'}: "
          f"{sum(1 for r in results if r[0])}/{len(results)} assertions held")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
