# Plan — fix the unsorted-dedupe bug (coupling_demo)

## Goal it serves
A durable, root-cause fix with the hidden coupling documented — not just a green
test. Duplicates surviving is a *symptom*; the plan is to find the mechanism and
make it impossible to silently reintroduce.

## Steps (reproduce-first, docs/07)
1. **Reproduce** (repro_engineer): a deterministic failing test for the unsorted
   case, confirmed RED, before touching code.
2. **Write it up** (bug_hunter): `bugs/BUG-NNN.md` with symptom / repro / expected-
   vs-actual / scope+blast-radius (`code_checks.py refs`) / evidence / severity.
3. **Find the cause** (debugger): hypothesis → probe → narrow to the single change
   that toggles the bug deterministically; understand the mechanism.
4. **Capture the coupling** (dep_mapper): if the cause is a hidden precondition,
   annotate inline `# MAW-DEP[id]` AND in `deps.md`, linked by id; pin blast radius.
5. **RCA** (rca_writer): root cause / why-not-caught / fix / prevention / related
   risks.
6. **Fix + regression test** (fixer): address the cause; repro test GREEN; suite +
   syntax clean.
7. **Independent review** (code_reviewer): re-run the checks; SHIP / NO-SHIP.

## Acceptance criteria
Every bar item in run.md holds, re-verified by the independent code_reviewer
against the on-disk tree (not the producers' say-so).
