"""Money utilities — BAD SPLIT: format_cents lost its cents zero-pad.

`{cents % CENTS_PER_DOLLAR}` instead of `{... :02d}`. So format_cents(5) now
returns "$0.5" instead of "$0.05". The bundled tests only assert format_cents(1234)
(== "$12.34", unaffected), so they still pass — but the golden harness asserts
format_cents(5) and catches the regression.
"""

__all__ = ["format_cents", "parse_cents"]

CENTS_PER_DOLLAR = 100


def format_cents(cents):
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}${cents // CENTS_PER_DOLLAR}.{cents % CENTS_PER_DOLLAR}"  # BUG: no :02d


def parse_cents(s):
    s = s.strip().lstrip("$")
    if "." in s:
        dollars, cents = s.split(".", 1)
        cents = (cents + "00")[:2]
    else:
        dollars, cents = s, "00"
    return int(dollars) * CENTS_PER_DOLLAR + int(cents)
