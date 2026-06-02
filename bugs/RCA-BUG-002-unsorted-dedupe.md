# RCA BUG-002: dedupe keeps duplicates on unsorted input
Severity: high   Status: fixed (with a regression test + MAW-DEP annotation)

## Root cause
`orders.dedupe_orders` removes duplicates by comparing **adjacent** orders only
(`key != last`). That algorithm is correct **only if the input is already sorted
by `DEDUPE_KEY`**. That precondition was an *implicit, undocumented* contract.
`pipeline.process` fed it unsorted data (no pre-sort), so non-adjacent duplicates
survived. The mechanism is the missing sort + the silent precondition — not "the
output had duplicates" (that is the symptom).

## Why not caught
- **No test for the unsorted case.** The only dedupe test used already-sorted
  input, which passes on the buggy code.
- **The coupling was implicit.** Nothing at the `process` call site said
  "`dedupe_orders` requires sorted input," so a caller (or a future edit removing a
  sort) breaks a distant function with no visible link.

## Fix
`pipeline.process` (and `batch_process`) now sort by `DEDUPE_KEY` before calling
`dedupe_orders` (`apply_sort=True`, the default). This restores the precondition
the dedupe algorithm assumes, so all duplicates are removed regardless of input
order. (The `apply_sort=False` toggle is kept only so the demo/self-test can
reproduce the original RED behaviour from one committed tree.)

## Prevention
- **Regression test** `test_unsorted_input_dedupes` — RED before the fix, GREEN
  after; kept permanently.
- **Hidden-dependency annotation**: inline `# MAW-DEP[D01]` markers above
  `dedupe_orders` and at both call sites, plus the central `deps.md#D01` entry, so
  the next editor sees the precondition before removing a sort.

## Related risks
`code_checks.py refs --symbol dedupe_orders` → 4 sites. The other caller,
`pipeline.batch_process` (`pipeline.py:33`), shares the exact same latent
assumption; it was annotated and given a pre-sort in the same change. Any *new*
caller of `dedupe_orders` inherits the precondition — `deps.md#D01` is the place to
check before adding one.
