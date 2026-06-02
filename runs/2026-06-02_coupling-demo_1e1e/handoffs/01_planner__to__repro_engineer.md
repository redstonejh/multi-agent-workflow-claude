# Hand-off: planner → repro_engineer  (run 2026-06-02_coupling-demo_1e1e, step 01)

## Task context
Duplicate orders survive de-duplication. Find and fix the real cause, with a
permanent regression test — reproduce first.

## What I did
Ordered the debugging sequence (artifacts/plan.md). Flagged a hypothesis to keep
in mind: the symptom looks like a *coupling* (a distant precondition), so we'll
likely need dep_mapper — but don't presume; reproduce first.

## Output / artifacts
- artifacts/plan.md  (the reproduce-first step list + acceptance criteria)

## Open questions / risks
The existing tests may only cover sorted input, which would hide the bug. Build a
repro that uses UNSORTED input with non-adjacent duplicates.

## Recommended next step
Write the smallest failing test that reproduces the duplicate-survival on unsorted
input; confirm it is RED before anyone edits code.
