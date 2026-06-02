# Hand-off: repro_engineer → bug_hunter  (run 2026-06-02_coupling-demo_1e1e, step 02)

## Task context
Reproduce-first debugging of the duplicate-survival bug, then document it.

## What I did
Built a deterministic repro on unsorted input with non-adjacent duplicates and
confirmed it RED:
`process([{id:3},{id:1},{id:3},{id:1},{id:2}], apply_sort=False)` → `[3, 1, 3, 1, 2]`
(expected `[1, 2, 3]`). Added the regression test `test_unsorted_input_dedupes`.

## Output / artifacts
- artifacts/repro_before_after.txt  (RED apply_sort=False vs GREEN default)
- regression test `test_unsorted_input_dedupes` in test_orders.py

## Open questions / risks
The duplicates that survive (3 and 1) are NON-adjacent — that detail points at an
adjacency/ordering assumption somewhere downstream.

## Recommended next step
Write the structured BUG report; compute the blast radius of the dedupe primitive
with `code_checks.py refs --symbol dedupe_orders`.
