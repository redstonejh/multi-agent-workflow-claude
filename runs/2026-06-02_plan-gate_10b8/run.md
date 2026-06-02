# Run 2026-06-02_plan-gate_10b8

- **Task:** train a churn classifier on the customer dataset — but FIRST prove the
  team plan is sound (pre-execution plan-gate demo).
- **Created:** 2026-06-02 10:40
- **Status:** plan accepted on revision 2 — ready to execute

## Conductor plan

This run demonstrates the **pre-execution plan gate** (symmetric to the acceptance
gate, but for team selection). The conductor proposes a plan; `plan_check`
(deterministic, hard gate) + `plan_reviewer` (advisory) vet it BEFORE any subagent
runs; on a flag the conductor re-plans (capped at 2 revisions).

### Revision 1 — REJECTED
Proposed team (`artifacts/plan_v1.json`): planner, worker, baseline_enforcer,
acceptance_gate. ML task.

- **plan_check → exit 1 (hard gate, NO-GO):**
  `task_type 'ml' requires role 'leakage_auditor' but it is not in the plan`.
  (Full JSON in `artifacts/plan_check_results.md`.) For an ML run that is the most
  dangerous omission possible — the `leakage_auditor` is the gate that catches the
  inflated-metric-from-leakage failure mode.
- **plan_reviewer → REVISE (advisory):** agreed; also noted the plan had no
  explicit data-quality check but that is optional for this task.

### Revision 2 — ACCEPTED
Proposed team (`artifacts/plan_v2.json`): planner, worker, **leakage_auditor**,
baseline_enforcer, acceptance_gate (5 roles, within the governor `max_agents` cap).

- **plan_check → exit 0 (hard gate, GO):** roster ✓, caps ✓, acceptance_gate ✓,
  no dupes / all justified ✓, ML required roles (leakage_auditor + baseline_enforcer) ✓.
- **plan_reviewer → APPROVE (advisory):** coverage adequate for the task; bar
  appropriate; no redundant roles.

| | revision 1 | revision 2 |
|---|---|---|
| roles | 4 (no leakage_auditor) | 5 (+ leakage_auditor) |
| plan_check | **exit 1 — REJECT** | **exit 0 — ACCEPT** |
| plan_reviewer | REVISE | APPROVE |

## Final result summary

The plan gate did its job: the structurally-unsound first plan was caught by
computation **before** any subagent ran, the conductor re-planned within the
revision cap, and only the corrected plan was cleared to execute. The two plans and
the raw `plan_check` output are committed in `artifacts/`. The RED→GREEN transition
and the required-role rule are pinned in `maw-tools/selftest_all.py` (§7), so this
write-up cannot drift from what the tool produces.

(The downstream training run itself is out of scope for this demo, which is about
the *plan gate*; the ML execution path is exercised by the committed ML run folder
`runs/2026-06-01_ml-leakage-demo_81f1/`.)
