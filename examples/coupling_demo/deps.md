# Dependency map — coupling_demo

Central, queryable record of non-obvious couplings (docs/07 §7). Each entry has a
stable ID and is mirrored by an inline `# MAW-DEP[id]` marker at the code site, so
the two stay in sync. Removing a coupling means closing **both**.

## D01  pipeline.{process,batch_process}  ->  orders.dedupe_orders
Type: implicit-precondition (ordering: input must be sorted by `DEDUPE_KEY`)
Discovered: BUG-002 debugging, 2026-06-02
Risk: high — `dedupe_orders` only compares ADJACENT orders, so unsorted input
silently keeps non-adjacent duplicates and no test guarded the unsorted case.
Blast radius: 4 reference sites for `dedupe_orders`
(`code_checks.py refs --symbol dedupe_orders`): def at orders.py:20, import at
pipeline.py:14, calls at pipeline.py:24 (process) and pipeline.py:33
(batch_process) — every caller must sort by `DEDUPE_KEY` first.
Annotated at: orders.py:16 (above `dedupe_orders`), pipeline.py:19 (in `process`),
pipeline.py:30 (in `batch_process`).
