# Code review — run 2026-06-02_coupling-demo_1e1e
Reviewer: code_reviewer (independent acceptance gate)
Date: 2026-06-02 ~10:05

## Verdict: SHIP

All four checks hold. Every command exited with the expected code. Details below.

---

## Check 1 — Repro RED then GREEN (fixes the reported symptom)

**Bug path (apply_sort=False):**
```
cmd: uv run python -c "from pipeline import process; o=[{'id':3},{'id':1},{'id':3},{'id':1},{'id':2}]; print([x['id'] for x in process(o, apply_sort=False)])"
output: [3, 1, 3, 1, 2]
```
Confirms bug is present and reproducible on the toggled path. Expected: `[3, 1, 3, 1, 2]`. PASS (RED confirmed).

**Fixed path (default apply_sort=True):**
```
cmd: uv run python -c "from pipeline import process; o=[{'id':3},{'id':1},{'id':3},{'id':1},{'id':2}]; print([x['id'] for x in process(o)])"
output: [1, 2, 3]
```
Fix is active. Expected: `[1, 2, 3]`. PASS (GREEN confirmed).

Result: RED -> GREEN. Check HOLDS.

---

## Check 2 — Claim-to-evidence (RCA root cause matches diff + blast radius matches refs)

**RCA stated root cause:** `dedupe_orders` compares adjacent orders only, correct only when input is pre-sorted by `DEDUPE_KEY`. `pipeline.process` called it without sorting — the missing pre-sort is the cause.

**Diff matches:** `pipeline.py` now sorts by `DEDUPE_KEY` before calling `dedupe_orders` (the `if apply_sort: orders = sorted(...)` block in both `process` and `batch_process`). This is exactly the missing sort the RCA identifies. No unrelated changes are present.

**Blast radius claim:** BUG-002 states 4 sites. Refs check output:
```
cmd: uv run python maw-tools/code_checks.py refs --symbol dedupe_orders --root examples/coupling_demo --expect 4
exit_code: 0
ref_count: 4  (def orders.py:20, import pipeline.py:14, call pipeline.py:24, call pipeline.py:33)
passed: true
```
Claim matches observed count exactly. Check HOLDS.

---

## Check 3 — Coupling captured in BOTH places (inline AND deps.md, same ID)

**Inline markers found (grep MAW-DEP[D01]):**
- `orders.py:16` — above `dedupe_orders`: documents the precondition, consequence, callers, and pointer to deps.md#D01
- `pipeline.py:19` — in `process`: explains the sort restores the precondition; warns not to remove without updating dedupe_orders
- `pipeline.py:30` — in `batch_process`: same precondition noted

**Central deps.md#D01 entry found:**
- `examples/coupling_demo/deps.md` has `## D01  pipeline.{process,batch_process}  ->  orders.dedupe_orders`
- Type: implicit-precondition; risk: high; blast radius: 4; annotated-at lines match the inline locations

The inline ID and the central entry use the same stable ID `D01` and agree on the same coupling (ordering precondition, both callers, all sites). Check HOLDS.

---

## Check 4 — Comment policy (why not what)

All three `# MAW-DEP[D01]` comments explain the *why* — specifically:
- What the precondition is (`input MUST be pre-sorted by DEDUPE_KEY`)
- The consequence of violating it (`unsorted input leaves non-adjacent duplicates`)
- Who is responsible (`pipeline.process, pipeline.batch_process`)
- Where to find more context (`See deps.md#D01`)

None of the comments merely restate what the code does (e.g. "this sorts the list"). The docstring on `dedupe_orders` (`"""Drop consecutive duplicate orders (by DEDUPE_KEY). Assumes sorted input."""`) is also informational, not tautological. Check HOLDS.

---

## Regression test gate

```
cmd: uv run python maw-tools/code_checks.py test --cmd "uv run python test_orders.py" --cwd examples/coupling_demo
exit_code: 0
passed: true
stdout_tail: "PASS — all 4 tests passed"
```
All 4 tests green including the permanent regression test `test_unsorted_input_dedupes`. Check HOLDS.

---

## Syntax gate

```
cmd: uv run python maw-tools/code_checks.py syntax --root examples/coupling_demo
exit_code: 0
passed: true
files_checked: 3 (orders.py, pipeline.py, test_orders.py)
```
All files compile cleanly. Check HOLDS.

---

## Summary table

| Check | Expected | Observed | Result |
|---|---|---|---|
| Repro bug path (apply_sort=False) | [3, 1, 3, 1, 2] | [3, 1, 3, 1, 2] | PASS |
| Repro fix path (default) | [1, 2, 3] | [1, 2, 3] | PASS |
| Regression test exit code | 0 | 0 | PASS |
| Regression test result | PASS 4/4 | PASS 4/4 | PASS |
| refs --expect 4 exit code | 0 | 0 | PASS |
| refs count | 4 | 4 | PASS |
| syntax exit code | 0 | 0 | PASS |
| Inline MAW-DEP[D01] in orders.py | present | orders.py:16 | PASS |
| Inline MAW-DEP[D01] in pipeline.py (process) | present | pipeline.py:19 | PASS |
| Inline MAW-DEP[D01] in pipeline.py (batch_process) | present | pipeline.py:30 | PASS |
| deps.md#D01 entry | present | line 7 | PASS |
| RCA root cause matches diff | adjacent-only dedupe + missing sort | sort added before dedupe_orders in both callers | PASS |
| BUG-002 blast radius matches refs | 4 | 4 | PASS |
| Comments explain why not what | yes | yes | PASS |

**SHIP.**
