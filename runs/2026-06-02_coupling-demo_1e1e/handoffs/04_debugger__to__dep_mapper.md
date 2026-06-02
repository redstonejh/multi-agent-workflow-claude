# Hand-off: debugger → dep_mapper  (run 2026-06-02_coupling-demo_1e1e, step 04)

## Task context
Root cause found; it's a hidden coupling that must be annotated before the fix.

## What I did
Confirmed the cause with a differential probe (artifacts/debug_trace.md): the
single toggle is the pre-sort. `dedupe_orders` compares ADJACENT orders only, so it
carries an implicit precondition — **input pre-sorted by `DEDUPE_KEY`**. `process`
violated it. Mechanism understood; this is a coupling, not a local bug.

## Output / artifacts
- artifacts/debug_trace.md  (H1 ruled out, H2 confirmed, on/off toggle = the sort)

## Open questions / risks
The precondition is invisible at the call site — exactly the spaghetti-coupling
case. It must be captured inline AND centrally so a future edit can't silently
remove a sort. Both callers share the assumption.

## Recommended next step
Annotate coupling `D01`: inline `# MAW-DEP[D01]` above `dedupe_orders` and at the
call sites, plus a `deps.md#D01` entry; pin the blast radius (refs = 4).
