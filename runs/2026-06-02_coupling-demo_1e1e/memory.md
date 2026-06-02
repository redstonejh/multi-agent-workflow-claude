# Shared journal — run 2026-06-02_coupling-demo_1e1e

Append-only, timestamped. One entry per agent turn. This is the common
blackboard: who did what, when, and where the output landed.

## 09:20 — conductor
Code/debugging task → code roster (docs/07). Planned repro → bug_hunter →
debugger → dep_mapper → rca_writer → fixer → independent code_reviewer. Bar set in
run.md (repro/cause/coupling/fix/rca/review). Next: planner orders the steps.

## 09:22 — planner
Decomposed into the reproduce-first debugging sequence (artifacts/plan.md). Key
call: the symptom (duplicates) is likely a *coupling*, so reserve dep_mapper.
Next: repro_engineer establishes a failing test.

## 09:25 — repro_engineer
Established a deterministic repro. `process([{id:3},{id:1},{id:3},{id:1},{id:2}],
apply_sort=False)` → `[3, 1, 3, 1, 2]` (dupes of 3 and 1 survive); expected
`[1, 2, 3]`. Added `test_unsorted_input_dedupes` — RED on the buggy path. Evidence:
artifacts/repro_before_after.txt. Next: bug_hunter writes it up.

## 09:29 — bug_hunter
Filed `bugs/BUG-002-unsorted-dedupe.md` (severity high). Blast radius via
`code_checks.py refs --symbol dedupe_orders` = 4 sites (def + import + 2 callers);
JSON in artifacts/refs_dedupe_orders.json. Discovery note: only sorted-input cases
were tested, so the bug hid. Next: debugger finds the cause.

## 09:36 — debugger
Hypothesis: dedupe is adjacent-only and assumes sorted input. Probe: sort the
input before `dedupe_orders` → bug flips off; remove the sort → flips on.
Deterministic on/off toggle = the cause is the missing pre-sort + the implicit
"sorted by DEDUPE_KEY" precondition (a hidden coupling, not the symptom). Trace in
artifacts/debug_trace.md. Flagged for dep_mapper. Next: dep_mapper annotates.

## 09:41 — dep_mapper
Captured coupling D01 in BOTH places: inline `# MAW-DEP[D01]` above
`orders.dedupe_orders` (orders.py:16) and at both call sites (pipeline.py:19, 30),
plus the central `examples/coupling_demo/deps.md` entry `D01` (endpoints, type
implicit-precondition, risk high, blast radius 4, annotated-at lines). refs pinned
at 4. Next: rca_writer.

## 09:46 — rca_writer
Wrote `bugs/RCA-BUG-002-unsorted-dedupe.md`: root cause = adjacent-only dedupe +
missing pre-sort; why-not-caught = no unsorted test + implicit coupling;
prevention = regression test + D01 annotation; related risks = batch_process shares
the assumption (annotated). Next: fixer.

## 09:52 — fixer
Fixed: `process`/`batch_process` sort by `DEDUPE_KEY` before `dedupe_orders`
(apply_sort=True default). Re-ran `code_checks.py test` → PASS 4/4 (was RED);
`syntax` clean. artifacts/test_after_fix.json, artifacts/fix_summary.md. Next:
independent code_reviewer.

## 10:05 — code_reviewer
Re-ran all checks independently against on-disk tree. Repro: apply_sort=False →
[3, 1, 3, 1, 2] (RED confirmed); default → [1, 2, 3] (GREEN confirmed). Test gate:
exit 0, PASS 4/4. Refs: exit 0, count=4 (matches BUG-002 blast radius claim).
Syntax: exit 0, all 3 files clean. Coupling: MAW-DEP[D01] at orders.py:16,
pipeline.py:19, pipeline.py:30 + deps.md#D01 — both sites agree, same ID, same
coupling. RCA root cause (adjacent-only dedupe + missing sort) matches diff exactly.
Comment policy: all markers explain the why (precondition, consequence, callers),
not the what. Verdict: SHIP. Output: artifacts/review.md.
