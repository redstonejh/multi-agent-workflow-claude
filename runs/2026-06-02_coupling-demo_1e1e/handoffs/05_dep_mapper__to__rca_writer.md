# Hand-off: dep_mapper → rca_writer  (run 2026-06-02_coupling-demo_1e1e, step 05)

## Task context
The hidden coupling is captured; now write the durable RCA.

## What I did
Recorded coupling **D01** in both places, linked by id:
- inline `# MAW-DEP[D01]` above `orders.dedupe_orders` (orders.py:16) and at both
  call sites (pipeline.py:19, pipeline.py:30);
- central `examples/coupling_demo/deps.md` entry `D01` (type implicit-precondition,
  risk high, blast radius 4, annotated-at lines).

## Output / artifacts
- examples/coupling_demo/deps.md  (D01)
- inline # MAW-DEP[D01] markers in orders.py + pipeline.py

## Open questions / risks
`batch_process` shares the exact precondition — call that out as a related risk so
it isn't treated as a one-off.

## Recommended next step
Write `bugs/RCA-BUG-002-...md`: root cause (adjacency assumption + missing sort),
why-not-caught, fix, prevention (regression test + D01), related risks (the other
caller).
