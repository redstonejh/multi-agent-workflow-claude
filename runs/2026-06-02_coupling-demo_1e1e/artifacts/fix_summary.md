# Fix summary — BUG-002

## Change (addresses the cause, not the symptom)
`pipeline.process` and `pipeline.batch_process` now sort by `DEDUPE_KEY` before
calling `orders.dedupe_orders` (`apply_sort=True`, the default). This restores the
precondition the adjacent-only dedupe assumes, so duplicates are removed regardless
of input order. The `apply_sort=False` toggle is retained ONLY so the demo / the
self-test can reproduce the original RED behaviour from one committed tree.

Why-comments added at the call sites link to `# MAW-DEP[D01]` / `deps.md#D01`
(comment the *why*: the invariant being restored), per docs/07 §6.

## Verification (real runs)
Before (buggy path):  `process(unsorted, apply_sort=False)` -> `[3, 1, 3, 1, 2]`  (RED)
After  (default):     `process(unsorted)`                   -> `[1, 2, 3]`        (GREEN)

`code_checks.py test --cmd "uv run python test_orders.py"` (see
artifacts/test_after_fix.json):
```
"passed": true, "exit_code": 0     # PASS - all 4 tests passed
```
`code_checks.py syntax --root .` (artifacts/syntax.json): passed = true.

## Regression test (permanent)
`test_unsorted_input_dedupes` in `examples/coupling_demo/test_orders.py` — RED on
the pre-fix path, GREEN after. Kept in the suite.
