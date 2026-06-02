# BUG-002: dedupe keeps duplicate orders when input arrives unsorted
Severity: high   Status: fixed (regression test added)   Found-by: bug_hunter

## Symptom
`pipeline.process(orders)` returns duplicate orders when the input list is not
already sorted by `id`. The output should contain each `id` exactly once.

## Reproduction
Deterministic, via the regression test `test_unsorted_input_dedupes`
(`examples/coupling_demo/test_orders.py`), and directly:
```
$ uv run python -c "from pipeline import process; \
  print([o['id'] for o in process([{'id':3},{'id':1},{'id':3},{'id':1},{'id':2}], apply_sort=False)])"
[3, 1, 3, 1, 2]      # buggy behaviour (no pre-sort) — duplicates of 3 and 1 survive
```

## Expected vs actual
- Expected: `[1, 2, 3]` (each id once).
- Actual (pre-fix): `[3, 1, 3, 1, 2]` — non-adjacent duplicates are not removed.

## Scope / blast radius
`orders.dedupe_orders` is the de-dupe primitive; `code_checks.py refs --symbol
dedupe_orders` reports **4 sites** — def at `orders.py:20`, import at
`pipeline.py:14`, and two callers `pipeline.process` (`pipeline.py:24`) and
`pipeline.batch_process` (`pipeline.py:33`). **Every** caller is affected: any path
that reaches `dedupe_orders` with unsorted data hits this. The coupling is recorded
as `deps.md#D01`.

## Evidence
- Failing assertion in `test_unsorted_input_dedupes` before the fix.
- `dedupe_orders` compares only `key != last` (adjacent pairs), so correctness
  depends entirely on sorted input — an implicit, undocumented precondition.
