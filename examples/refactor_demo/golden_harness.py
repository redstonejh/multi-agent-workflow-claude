"""Golden harness for the widgets refactor demo.

`refactor_checks.py golden` imports this and calls golden(); the variant under test
is selected with --src-dir (so `import widgets` resolves to bloated/ or split/ or
bad_split/). The returned dict is serialized byte-stably and snapshotted, then
re-run after the refactor and asserted byte-identical.

NOTE: this harness deliberately exercises cases the bundled test suite does NOT
assert (e.g. format_cents(5)), so golden is a stricter behavioral check than the
tests — it is the truth comparison.
"""


def golden() -> dict:
    import widgets as w
    return {
        "slugify":          w.slugify("Hello,  World! -- 123"),
        "shout":            w.shout("  hi   there "),
        "gcd":              w.gcd(48, 36),
        "lcm":              w.lcm(4, 6),
        "chunk_even":       w.chunk([1, 2, 3, 4, 5, 6], 2),
        "chunk_uneven":     w.chunk([1, 2, 3, 4, 5], 3),
        "flatten":          w.flatten([[1, 2], [3], [4, 5]]),
        "format_cents_big": w.format_cents(1234),
        "format_cents_sub": w.format_cents(5),     # "$0.05" — NOT asserted by tests
        "format_cents_neg": w.format_cents(-7),    # "-$0.07"
        "parse_cents":      w.parse_cents("$12.34"),
    }
