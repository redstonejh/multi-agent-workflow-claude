# Run 2026-06-02_coupling-demo_1e1e

- **Task:** fix the dedupe bug in examples/coupling_demo where unsorted input keeps duplicate orders
- **Created:** 2026-06-02 09:20 (driven via `/maw` with the code-work roster, docs/07)
- **Status:** complete — SHIP

## Conductor plan

**Objective:** Find and fix the real cause of duplicate orders surviving, leave a
permanent regression test, and — because the cause is a *hidden coupling* — capture
that coupling so it can't silently recur. The real ask is a durable fix + the
landmine documented, not just "make the test pass."

**Work type:** code / debugging → use the code roster (docs/07), reproduce-first,
RCA-not-just-a-patch, annotate hidden dependencies inline + centrally.

**Roles (each justified):**
- `planner` — order the debugging steps; set the bar (repro → cause → fix → review).
- `repro_engineer` — establish a deterministic failing test before touching code.
- `bug_hunter` — write the structured `BUG-002` report; compute blast radius.
- `debugger` — hypothesis-driven search for the single cause-toggling change.
- `dep_mapper` — the cause is a hidden precondition; annotate it inline + in deps.md.
- `rca_writer` — write the RCA (root cause, why-not-caught, prevention, related risk).
- `fixer` — implement the fix + keep the regression test.
- `code_reviewer` — independent acceptance-gate review (re-runs the checks itself).

**Pattern:** `planner → repro_engineer → bug_hunter → debugger → dep_mapper →
rca_writer → fixer` (refine loop on the cause), then the independent `code_reviewer`.

**Quality bar:**
```
SHIP requires ALL:
  [ ] repro: a deterministic failing test exists, RED before the fix
  [ ] cause: a single change toggles the bug on/off, mechanism understood (not a symptom)
  [ ] coupling: hidden dependency captured BOTH inline (# MAW-DEP[id]) AND in deps.md, linked by id
  [ ] fix: regression test GREEN; no new breakage; syntax clean
  [ ] rca: written root cause + why-not-caught + prevention + related risks
  [ ] review: independent code_reviewer re-runs the checks -> SHIP
```

**Caps:** 9 roles (code-roster escalation, justified above; validators run in
sequence over the shared tree); max_parallel 1 (code edits the same module —
serialize); max_iters 3. Cheap models for routine roles; `debugger`/`fixer`/
`code_reviewer` stronger.

## Final result summary

**Deliverable:** a root-cause fix + regression test + the hidden coupling documented.

- **Reproduced (RED):** `pipeline.process` on unsorted input with non-adjacent
  duplicates returned `[3, 1, 3, 1, 2]` (the `apply_sort=False` path) instead of
  `[1, 2, 3]`. Regression test `test_unsorted_input_dedupes` added, RED.
- **Root cause:** `orders.dedupe_orders` compares only **adjacent** orders, so it is
  correct only if the input is **pre-sorted by `DEDUPE_KEY`** — an implicit,
  undocumented precondition. `process` fed it unsorted data. (Not the symptom
  "there were duplicates".) See `bugs/RCA-BUG-002-unsorted-dedupe.md`.
- **Hidden coupling captured (D01):** `code_checks.py refs --symbol dedupe_orders`
  → **4 sites** (def `orders.py:20`, import `pipeline.py:14`, callers
  `pipeline.py:24` + `pipeline.py:33`). Annotated inline with `# MAW-DEP[D01]`
  (orders.py:16, pipeline.py:19, pipeline.py:30) **and** centrally in
  `examples/coupling_demo/deps.md` (`D01`), linked by id.
- **Fix:** `process`/`batch_process` sort by `DEDUPE_KEY` before dedupe
  (`apply_sort=True` default). Regression test now **GREEN** (`test_orders.py` →
  PASS, 4/4); `code_checks.py syntax` clean.
- **Independent review:** `code_reviewer` re-ran the checks against the on-disk tree
  (repro RED→GREEN, refs 4, both coupling sites present, RCA matches the diff) —
  verdict in `artifacts/review.md`: **SHIP**.

The demonstration: a defect whose true cause is a *distant, invisible precondition*
was reproduced, traced to that precondition (not the symptom), fixed, and the
coupling captured in two linked places so the next editor can't remove a sort
without seeing the landmine.
