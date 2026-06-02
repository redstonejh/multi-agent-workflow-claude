"""Stdlib test suite for widgets (passes on the bloated module and the good split).

Deliberately does NOT assert format_cents on sub-dollar amounts — that gap is what
makes the golden harness a stricter check than the tests (it catches the bad split
the tests miss).
"""
import widgets as w


def check(name, got, want):
    assert got == want, f"{name}: got {got!r}, want {want!r}"


def main():
    check("slugify", w.slugify("Hello,  World! -- 123"), "hello-world-123")
    check("shout", w.shout("  hi   there "), "HI THERE!")
    check("gcd", w.gcd(48, 36), 12)
    check("lcm", w.lcm(4, 6), 12)
    check("chunk", w.chunk([1, 2, 3, 4, 5], 2), [[1, 2], [3, 4], [5]])
    check("flatten", w.flatten([[1, 2], [3], [4, 5]]), [1, 2, 3, 4, 5])
    check("format_cents_big", w.format_cents(1234), "$12.34")
    check("parse_cents", w.parse_cents("$12.34"), 1234)
    print("all widgets tests passed")


if __name__ == "__main__":
    main()
