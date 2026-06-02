# Worked example — hidden dependency + bug/RCA documentation

The Phase-3.8 demonstration (docs/07): a **hidden coupling** and a **planted bug**
with a real root cause, captured by the code-work pack — an inline `# MAW-DEP`
marker + a central `deps.md` entry, a `BUG-NNN.md` report, an RCA, a fix, and a
permanent regression test.

> All commands use `uv run python` (no `python` on PATH here). Pure standard library.

## The hidden coupling

`orders.dedupe_orders` removes duplicates by comparing **adjacent** orders only —
correct **only if the input is pre-sorted by `DEDUPE_KEY`**. That precondition is
the landmine: a distant caller that doesn't sort silently gets wrong results, with
no visible link between the two modules.

## The planted bug (BUG-002)

`pipeline.process` fed `dedupe_orders` **unsorted** input, so non-adjacent
duplicates survived. The fix sorts first (`apply_sort=True`, the default). The
`apply_sort=False` toggle reproduces the original RED behaviour from this one
committed tree, so the regression test can be shown red-before / green-after.

```bash
cd examples/coupling_demo

# Reproduce the bug (no pre-sort): non-adjacent duplicates survive
uv run python -c "from pipeline import process; print([o['id'] for o in process([{'id':3},{'id':1},{'id':3},{'id':1},{'id':2}], apply_sort=False)])"
#   -> [3, 1, 3, 1, 2]   (duplicates of 3 and 1 remain)

# The fix (default): all duplicates removed
uv run python -c "from pipeline import process; print([o['id'] for o in process([{'id':3},{'id':1},{'id':3},{'id':1},{'id':2}])])"
#   -> [1, 2, 3]

# The regression test (green on the fixed tree)
uv run python test_orders.py            # -> PASS - all 4 tests passed

# Blast radius of the coupled symbol (the deterministic backbone of dep_mapper)
uv run python ../../maw-tools/code_checks.py refs --symbol dedupe_orders --root . --expect 4
```

## The captured artifacts

| Artifact | Where |
|---|---|
| Inline coupling markers | `# MAW-DEP[D01]` in `orders.py:16`, `pipeline.py:19`, `pipeline.py:30` |
| Central dependency map | [`deps.md`](deps.md) entry `D01` |
| Bug report | [`bugs/BUG-002-unsorted-dedupe.md`](../../bugs/BUG-002-unsorted-dedupe.md) |
| Root-cause analysis | [`bugs/RCA-BUG-002-unsorted-dedupe.md`](../../bugs/RCA-BUG-002-unsorted-dedupe.md) |
| Regression test | `test_unsorted_input_dedupes` in `test_orders.py` |
| The full /maw run | [`runs/2026-06-02_coupling-demo_*/`](../../runs/) (committed) |

The inline marker and the `deps.md` entry are linked by the ID `D01` and must stay
in sync — removing the coupling means closing both.
