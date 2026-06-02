"""Money utilities (cohesive cluster — shares CENTS_PER_DOLLAR)."""

__all__ = ["format_cents", "parse_cents"]

CENTS_PER_DOLLAR = 100


def format_cents(cents):
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}${cents // CENTS_PER_DOLLAR}.{cents % CENTS_PER_DOLLAR:02d}"


def parse_cents(s):
    s = s.strip().lstrip("$")
    if "." in s:
        dollars, cents = s.split(".", 1)
        cents = (cents + "00")[:2]
    else:
        dollars, cents = s, "00"
    return int(dollars) * CENTS_PER_DOLLAR + int(cents)
