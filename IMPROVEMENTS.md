# Self-improvement log — branch self-improve/20260602_093545

Baseline: `uv run python maw-tools/selftest_all.py` -> **PASS 53/53** (green).

## Cycle 1 — close the scaffold_run.py test-coverage gap
**What:** Add `maw-tools/selftest_scaffold.py` (per-tool self-test for `scaffold_run.py`) and
wire it into `selftest_all.py`'s `part_selftests`.
**Why:** `scaffold_run.py` enforces the entire run-folder layout and hand-off file-naming
contract from docs/05, yet it is the ONLY `maw-tools/` script with zero test coverage — the
other three (`checks.py`, `ml_checks.py`, `code_checks.py`) each have a `selftest_*.py` pinned
in the master suite. A silent regression in slug derivation, folder layout, or hand-off
numbering would go undetected. This closes that gap with deterministic, external assertions.

## Final result summary (Cycle 1)

**Acceptance gate verdict: SHIP** (reviewed 2026-06-02 by acceptance_gate / claude-sonnet-4-6)

All three checks held:
- Task conformance: the gap (scaffold_run.py had zero test coverage) was real and the
  deliverable closes it with 16 targeted assertions.
- Claim-to-evidence: git diff confirms selftest_all.py is purely additive (no weakening),
  scaffold_run.py has empty diff, suite ran 54/54 exit 0.
- End-to-end soundness: `uv run python maw-tools/selftest_scaffold.py` -> ALL PASS 16/16;
  `uv run python maw-tools/selftest_all.py` -> PASS 54/54 assertions held.

## Cycle 2 — fix false-negative in code_checks `_collect_py` (dotted scan root)
**What:** `_collect_py` skips any file whose path has a dotted or `__pycache__` component, but
it checks ALL path parts — including the explicitly-provided `--root` itself. So scanning a
root that is (or lives under) a dotted directory (e.g. `--root .claude`) silently returns ZERO
files. `refs` then reports `0 sites`, and `syntax`/`dupes` report "all clean" — the exact
false-negative the tool exists to prevent (a blast-radius of 0 reads as "safe to change").
**Why:** Fix it to filter only on path components BELOW the scan root, so a caller who names a
dotted root on purpose gets it scanned, while `.git` / `.venv` / `__pycache__` *under* the root
are still skipped. Reproduced RED (0/0 on a dotted root holding 3 refs) before the fix.

**Pinned-value change (justified, NOT a weakening):** `selftest_all.py`'s pin for
`selftest_code_checks.py` went `10/10` -> `12/12`. This is a *tightening*: two NEW regression
assertions were added (dotted root is scanned; nested dotted dirs below it are still skipped),
both proven RED on the pre-fix code via `git stash` of the fix (10/12) and GREEN after (12/12).
No existing assertion or tolerance was loosened.

## Final result summary (Cycle 2)

**Acceptance gate verdict: SHIP** (reviewed 2026-06-02 by acceptance_gate / claude-sonnet-4-6)

All three checks held:
- Task conformance: the bug (false-negative on dotted scan root returning 0 files) was real
  and dangerous; the fix is targeted to BELOW-root filtering only. NOT over-broad.
- Claim-to-evidence: RED proof confirmed (10/12 without fix, both new assertions failing with
  files=0, refs=0). Pin bump 10->12 is pure tightening — 0 deletions in selftest_code_checks.py.
  `.git` dir below the dotted root still skipped (files_scanned=1, not 2). No weakening found.
- End-to-end soundness: `uv run python maw-tools/selftest_code_checks.py` -> ALL PASS 12/12;
  `uv run python maw-tools/selftest_all.py` -> PASS 54/54 assertions held.
