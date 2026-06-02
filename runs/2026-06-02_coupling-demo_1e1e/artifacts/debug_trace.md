# Debug trace — BUG-002

Hypothesis-driven root-cause search (docs/07 §3). Goal: the single change that
toggles the bug on/off deterministically.

## H1 — "dedupe_orders has an off-by-one / wrong comparison"
Probe: read `dedupe_orders` — it compares `key != last` across the iteration, i.e.
**adjacent** elements only. On *sorted* input that is correct (equal keys are
adjacent). Ran the sorted test → PASS. So the function isn't wrong in isolation.
Ruled out a standalone logic error; the issue is input-dependent.

## H2 — "the input isn't sorted, and dedupe assumes it is"
Differential probe — same data, two paths:
```
process(orders, apply_sort=False)  -> [3, 1, 3, 1, 2]   (RED: non-adjacent dupes survive)
process(orders)            (sort)  -> [1, 2, 3]         (GREEN)
```
The single change that flips the bug is **the presence/absence of the pre-sort**.
With it, equal keys become adjacent and dedupe collapses them; without it, the
duplicates 3…3 and 1…1 are non-adjacent and slip through.

## Conclusion (mechanism, not symptom)
`dedupe_orders` carries an **implicit precondition: input pre-sorted by
`DEDUPE_KEY`**. `pipeline.process` violated it by not sorting. The deterministic
on/off toggle (the sort) confirms the cause. Because the precondition is a
*distant, invisible* contract between two modules, this is a **hidden coupling** →
handed to dep_mapper for inline + central annotation (D01), and to rca_writer.

Blast radius (`code_checks.py refs --symbol dedupe_orders`): 4 sites — both callers
(`process`, `batch_process`) share the precondition.
