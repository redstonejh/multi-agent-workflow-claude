"""pipeline.py — order processing. The NEAR side of the hidden coupling.

`process` and `batch_process` feed orders to `orders.dedupe_orders`, which requires
input pre-sorted by DEDUPE_KEY. The planted **BUG-001** was `process` calling
dedupe WITHOUT sorting first, so unsorted input kept its non-adjacent duplicates.

The fix is the sort below (`apply_sort=True`, the default). Passing
`apply_sort=False` reproduces the original buggy behaviour — that toggle exists
only so the demo and the self-test can show the regression test going red (bug)
then green (fix) from one committed tree. See bugs/ and the run folder.
"""
from __future__ import annotations

from orders import DEDUPE_KEY, dedupe_orders


def process(orders, *, apply_sort=True):
    """De-duplicate a list of orders. Returns orders with duplicates removed."""
    # MAW-DEP[D01]: dedupe_orders() requires input pre-sorted by DEDUPE_KEY. This
    # sort is that precondition — the planted bug was its absence. Do NOT remove
    # it without updating dedupe_orders. See deps.md#D01.
    if apply_sort:
        orders = sorted(orders, key=lambda o: o[DEDUPE_KEY])
    return dedupe_orders(orders)


def batch_process(batches, *, apply_sort=True):
    """Flatten a list of order-batches and de-duplicate across all of them."""
    flat = [order for batch in batches for order in batch]
    # MAW-DEP[D01]: same precondition as process() — sort before dedupe_orders().
    if apply_sort:
        flat = sorted(flat, key=lambda o: o[DEDUPE_KEY])
    return dedupe_orders(flat)
