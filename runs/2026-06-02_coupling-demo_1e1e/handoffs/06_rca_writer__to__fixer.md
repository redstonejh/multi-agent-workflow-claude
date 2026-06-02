# Hand-off: rca_writer → fixer  (run 2026-06-02_coupling-demo_1e1e, step 06)

## Task context
Cause + coupling documented; implement the fix that addresses the cause.

## What I did
Wrote `bugs/RCA-BUG-002-unsorted-dedupe.md`: root cause = adjacent-only dedupe with
an implicit "sorted by DEDUPE_KEY" precondition that `process` violated; why-not-
caught = no unsorted test + implicit coupling; prevention = regression test + D01
annotation; related risks = `batch_process` shares the assumption.

## Output / artifacts
- bugs/RCA-BUG-002-unsorted-dedupe.md

## Open questions / risks
Fix the *cause* (restore the precondition by sorting before dedupe), not the
symptom (don't post-filter duplicates). Keep `batch_process` consistent.

## Recommended next step
Sort by `DEDUPE_KEY` before `dedupe_orders` in `process` and `batch_process`; make
the regression test GREEN; re-run the suite + `code_checks.py syntax`.
