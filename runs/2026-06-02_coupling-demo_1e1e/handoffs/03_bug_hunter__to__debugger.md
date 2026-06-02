# Hand-off: bug_hunter → debugger  (run 2026-06-02_coupling-demo_1e1e, step 03)

## Task context
The duplicate-survival bug is reproduced + documented; now find the true cause.

## What I did
Filed `bugs/BUG-002-unsorted-dedupe.md` (severity high). Computed the blast radius:
`code_checks.py refs --symbol dedupe_orders` → **4 sites** (def orders.py:20,
import pipeline.py:14, callers pipeline.py:24 + :33). Noted only sorted-input cases
were tested, which is why this hid.

## Output / artifacts
- bugs/BUG-002-unsorted-dedupe.md
- artifacts/refs_dedupe_orders.json  (4 sites, ref_count pinned)

## Open questions / risks
Both callers (`process`, `batch_process`) reach `dedupe_orders` — whatever the
cause, it likely affects both. The non-adjacent-duplicate clue suggests an
adjacency assumption in `dedupe_orders`.

## Recommended next step
Hypothesis-driven search: find the single change that toggles the bug on/off.
Suspect: `dedupe_orders` compares adjacent pairs only and assumes sorted input.
