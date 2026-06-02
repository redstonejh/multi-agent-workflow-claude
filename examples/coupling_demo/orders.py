"""orders.py — order de-duplication. The FAR side of a hidden coupling.

`dedupe_orders` removes duplicate orders by scanning ADJACENT pairs only, which is
correct *only if the input is already sorted by DEDUPE_KEY*. That precondition is
the hidden dependency: a distant caller that forgets to sort silently gets wrong
results. The coupling is captured inline (the MAW-DEP marker below) and centrally
(deps.md#D01).
"""
from __future__ import annotations

# The key every order is identified and sorted by. dedupe_orders relies on the
# input being sorted by this; every caller must sort by the SAME key.
DEDUPE_KEY = "id"


# MAW-DEP[D01]: input MUST be pre-sorted by DEDUPE_KEY ("id"). dedupe_orders only
# compares ADJACENT orders, so unsorted input leaves non-adjacent duplicates in
# place — changing or removing a caller's sort silently breaks this. Callers:
# pipeline.process, pipeline.batch_process. See deps.md#D01.
def dedupe_orders(orders):
    """Drop consecutive duplicate orders (by DEDUPE_KEY). Assumes sorted input."""
    out = []
    last = object()  # a sentinel that never equals a real key
    for o in orders:
        key = o[DEDUPE_KEY]
        if key != last:
            out.append(o)
        last = key
    return out
