"""Plain-stdlib tests for the coupling demo — run with `python test_orders.py`.

Exits 0 if all tests pass, 1 otherwise (so maw-tools/{code_checks,checks}.py `test`
can gate on it without pytest).

`test_unsorted_input_dedupes` is the permanent regression test for BUG-001: it is
RED on the buggy code (process without the pre-sort) and GREEN after the fix.
"""
import sys

from pipeline import process, batch_process


def test_sorted_input_dedupes():
    orders = [{"id": 1}, {"id": 1}, {"id": 2}, {"id": 3}, {"id": 3}]
    assert [o["id"] for o in process(orders)] == [1, 2, 3]


def test_unsorted_input_dedupes():
    # BUG-001 regression: ids 3 and 1 repeat but are NOT adjacent. The fix sorts
    # before the adjacent-dedupe, so all duplicates are removed.
    orders = [{"id": 3}, {"id": 1}, {"id": 3}, {"id": 1}, {"id": 2}]
    assert [o["id"] for o in process(orders)] == [1, 2, 3]


def test_batch_process_dedupes_across_batches():
    batches = [[{"id": 2}, {"id": 1}], [{"id": 1}, {"id": 3}], [{"id": 2}]]
    assert [o["id"] for o in batch_process(batches)] == [1, 2, 3]


def test_empty():
    assert process([]) == []


TESTS = [
    test_sorted_input_dedupes,
    test_unsorted_input_dedupes,
    test_batch_process_dedupes_across_batches,
    test_empty,
]


def run() -> int:
    failures = []
    for t in TESTS:
        try:
            t()
        except AssertionError as e:
            failures.append(f"{t.__name__}: {e or 'assertion failed'}")
        except Exception as e:  # noqa: BLE001 - any raise is a test failure
            failures.append(f"{t.__name__}: raised {e!r}")
    if failures:
        print(f"FAIL — {len(failures)}/{len(TESTS)} tests failed:")
        for f in failures:
            print("  -", f)
        return 1
    print(f"PASS — all {len(TESTS)} tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(run())
