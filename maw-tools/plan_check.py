#!/usr/bin/env python3
"""plan_check.py — deterministic PRE-execution gate on the conductor's team plan.

The acceptance gate (docs/01) checks the *output* after a run. This is its mirror
image at the *start*: before any subagent runs, validate the conductor's proposed
team plan so a structurally-bad plan (a missing required validator, a cap blown, an
unjustified role) is caught by computation, not discovered three hand-offs later.
Same rule as the rest of `maw-tools/`: **compute first, reason second** — the
`plan_reviewer` agent only interprets *after* this hard gate has run.

Pure standard library, no model, no network. JSON out + exit 0/1 so callers gate
on `$?`; usage/runtime errors exit 2.

What it asserts (given a structured plan: roles + task-type tag + caps):
  - every role exists in the roster (derived from .claude/agents/, or --roster);
  - total roles within the governor `max_agents` cap, declared parallel within
    `max_parallel`, declared `max_iters` within the governor cap, and the declared
    caps themselves do not exceed the governor caps;
  - `acceptance_gate` is present (every run ends with the independent gate);
  - no duplicate roles, and no role without a one-line justification (docs/01);
  - the required-role rules for the task type fire (see REQUIRED_ROLES below).

The rule table lives in ONE obvious place — GOVERNOR and REQUIRED_ROLES below.

Plan JSON shape (via --plan FILE, or stdin):
  {
    "task_type": "ml",                       # ml | frontend | code | generic
    "caps": {"max_agents": 5, "max_parallel": 3, "max_iters": 3},
    "parallel": 2,                            # planned concurrency (optional)
    "roles": [
      {"name": "planner",          "justification": "decompose the task"},
      {"name": "worker",           "justification": "run the experiment"},
      {"name": "leakage_auditor",  "justification": "shuffled-label control"},
      {"name": "baseline_enforcer","justification": "gain vs majority + CI"},
      {"name": "acceptance_gate",  "justification": "independent terminal gate"}
    ]
  }

Examples:
  uv run python maw-tools/plan_check.py --plan plan.json
  echo '{"task_type":"ml", ...}' | uv run python maw-tools/plan_check.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# --------------------------------------------------------------------------- #
# THE RULE TABLE — the one obvious place to change policy.
# --------------------------------------------------------------------------- #

# Governor caps (docs/01). A plan may not exceed these.
GOVERNOR = {"max_agents": 5, "max_parallel": 3, "max_iters": 3}

# Roles every plan must include, regardless of task type.
ALWAYS_REQUIRED = ["acceptance_gate"]

# Task-type -> roles that MUST appear (the domain pack's non-negotiable validators).
REQUIRED_ROLES = {
    "ml":       ["leakage_auditor", "baseline_enforcer"],
    "frontend": ["a11y_auditor", "change_verifier"],
    "code":     ["code_reviewer", "dep_mapper"],
    "generic":  [],
}

ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = ROOT / ".claude" / "agents"


def _emit(obj: dict, passed: bool) -> int:
    print(json.dumps(obj, indent=2))
    return 0 if passed else 1


def _roster(args: argparse.Namespace) -> set[str]:
    """The set of valid role names: --roster override, else .claude/agents/*.md."""
    if args.roster:
        return {r.strip() for r in args.roster.split(",") if r.strip()}
    d = Path(args.agents_dir) if args.agents_dir else AGENTS_DIR
    return {p.stem for p in d.glob("*.md")}


def _load_plan(args: argparse.Namespace) -> dict:
    raw = Path(args.plan).read_text(encoding="utf-8") if args.plan else sys.stdin.read()
    return json.loads(raw)


def check_plan(plan: dict, roster: set[str]) -> list[str]:
    """Return a list of specific violation strings (empty == the plan is valid)."""
    violations: list[str] = []

    task_type = plan.get("task_type", "generic")
    caps = plan.get("caps", {}) or {}
    raw_roles = plan.get("roles", []) or []

    # Normalize roles: accept {"name","justification"} objects or bare strings.
    names: list[str] = []
    for r in raw_roles:
        if isinstance(r, str):
            names.append(r)
            violations.append(f"role '{r}' has no justification (docs/01: every role "
                              "needs a one-line justification)")
        elif isinstance(r, dict):
            name = r.get("name", "")
            names.append(name)
            if not str(r.get("justification", "")).strip():
                violations.append(f"role '{name or '?'}' has no justification "
                                  "(docs/01: every role needs a one-line justification)")
        else:
            violations.append(f"malformed role entry: {r!r}")

    # 1) every role exists in the roster
    for n in names:
        if n and n not in roster:
            violations.append(f"role '{n}' is not in the roster ({len(roster)} known agents)")

    # 2) no duplicate roles
    seen: set[str] = set()
    for n in names:
        if n in seen:
            violations.append(f"duplicate role '{n}'")
        seen.add(n)

    # 3) governor caps — declared caps must not exceed the governor, and the plan
    #    must fit within the governor caps.
    for key in ("max_agents", "max_parallel", "max_iters"):
        if key in caps and caps[key] > GOVERNOR[key]:
            violations.append(f"declared {key}={caps[key]} exceeds governor cap {GOVERNOR[key]}")
    n_roles = len(names)
    if n_roles > GOVERNOR["max_agents"]:
        violations.append(f"{n_roles} roles exceed governor max_agents {GOVERNOR['max_agents']}")
    declared_max_agents = caps.get("max_agents", GOVERNOR["max_agents"])
    if n_roles > declared_max_agents:
        violations.append(f"{n_roles} roles exceed the plan's declared max_agents {declared_max_agents}")
    parallel = plan.get("parallel")
    if parallel is not None:
        if parallel > GOVERNOR["max_parallel"]:
            violations.append(f"planned parallel={parallel} exceeds governor max_parallel "
                              f"{GOVERNOR['max_parallel']}")
        declared_par = caps.get("max_parallel", GOVERNOR["max_parallel"])
        if parallel > declared_par:
            violations.append(f"planned parallel={parallel} exceeds the plan's declared "
                              f"max_parallel {declared_par}")

    # 4) acceptance_gate (and any other always-required role) present
    name_set = set(names)
    for req in ALWAYS_REQUIRED:
        if req not in name_set:
            violations.append(f"missing required role '{req}' (every run ends with the "
                              "independent acceptance gate)")

    # 5) required-role rules per task type
    if task_type not in REQUIRED_ROLES:
        violations.append(f"unknown task_type '{task_type}' (expected one of "
                          f"{sorted(REQUIRED_ROLES)})")
    for req in REQUIRED_ROLES.get(task_type, []):
        if req not in name_set:
            violations.append(f"task_type '{task_type}' requires role '{req}' but it is "
                              "not in the plan")

    return violations


def cmd_check(args: argparse.Namespace) -> int:
    plan = _load_plan(args)
    roster = _roster(args)
    violations = check_plan(plan, roster)
    passed = len(violations) == 0
    names = [r.get("name") if isinstance(r, dict) else r for r in (plan.get("roles") or [])]
    return _emit({
        "check": "plan",
        "task_type": plan.get("task_type", "generic"),
        "role_count": len(names),
        "roles": names,
        "caps": plan.get("caps", {}),
        "governor": GOVERNOR,
        "required_for_task_type": ALWAYS_REQUIRED + REQUIRED_ROLES.get(plan.get("task_type", "generic"), []),
        "violation_count": len(violations),
        "violations": violations,
        "passed": passed,
        "note": ("plan is structurally valid — roster, caps, acceptance gate, and "
                 "required-role rules all satisfied"
                 if passed else f"{len(violations)} plan violation(s) — re-plan before executing"),
    }, passed)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Pre-execution gate on the conductor's team plan.")
    p.add_argument("--plan", default=None, help="plan JSON file (default: read stdin)")
    p.add_argument("--roster", default=None, help="comma-separated valid role names "
                   "(default: derive from .claude/agents/)")
    p.add_argument("--agents-dir", default=None, help="override the agents dir for roster derivation")
    p.set_defaults(func=cmd_check)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, FileNotFoundError, json.JSONDecodeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
