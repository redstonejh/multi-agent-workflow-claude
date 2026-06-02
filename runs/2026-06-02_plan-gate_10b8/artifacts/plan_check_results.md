# plan_check results — v1 (rejected) then v2 (accepted)

## `plan_check --plan plan_v1.json` -> exit 1  (REJECTED — re-plan)

```json
{
  "check": "plan",
  "task_type": "ml",
  "role_count": 4,
  "roles": [
    "planner",
    "worker",
    "baseline_enforcer",
    "acceptance_gate"
  ],
  "caps": {
    "max_agents": 5,
    "max_parallel": 3,
    "max_iters": 3
  },
  "governor": {
    "max_agents": 5,
    "max_parallel": 3,
    "max_iters": 3
  },
  "required_for_task_type": [
    "acceptance_gate",
    "leakage_auditor",
    "baseline_enforcer"
  ],
  "violation_count": 1,
  "violations": [
    "task_type 'ml' requires role 'leakage_auditor' but it is not in the plan"
  ],
  "passed": false,
  "note": "1 plan violation(s) \u2014 re-plan before executing"
}
```

## `plan_check --plan plan_v2.json` -> exit 0  (ACCEPTED — execute)

```json
{
  "check": "plan",
  "task_type": "ml",
  "role_count": 5,
  "roles": [
    "planner",
    "worker",
    "leakage_auditor",
    "baseline_enforcer",
    "acceptance_gate"
  ],
  "caps": {
    "max_agents": 5,
    "max_parallel": 3,
    "max_iters": 3
  },
  "governor": {
    "max_agents": 5,
    "max_parallel": 3,
    "max_iters": 3
  },
  "required_for_task_type": [
    "acceptance_gate",
    "leakage_auditor",
    "baseline_enforcer"
  ],
  "violation_count": 0,
  "violations": [],
  "passed": true,
  "note": "plan is structurally valid \u2014 roster, caps, acceptance gate, and required-role rules all satisfied"
}
```
