"""widgets — a deliberately BLOATED grab-bag module (the refactor trigger).

Eight unrelated public functions live in one file, in four cohesive clusters that
share private helpers/constants:
  - text:  slugify, shout      (share _normalize_ws)
  - mathx: gcd, lcm            (lcm uses gcd)
  - listx: chunk, flatten
  - money: format_cents, parse_cents  (share CENTS_PER_DOLLAR)

`refactor_checks.py bloat` flags this file as over budget; the cohesive clusters
are the natural split boundaries (group functions by shared symbols).
"""

__all__ = [
    "slugify", "shout",
    "gcd", "lcm",
    "chunk", "flatten",
    "format_cents", "parse_cents",
]

CENTS_PER_DOLLAR = 100


# --- text cluster --------------------------------------------------------- #

def _normalize_ws(s):
    out = []
    prev_space = False
    for ch in s.strip():
        if ch.isspace():
            if not prev_space:
                out.append(" ")
            prev_space = True
        else:
            out.append(ch)
            prev_space = False
    return "".join(out)


def slugify(s):
    s = _normalize_ws(s).lower()
    chars = []
    for ch in s:
        if ch.isalnum():
            chars.append(ch)
        elif ch == " " or ch == "-":
            chars.append("-")
    slug = "".join(chars)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")


def shout(s):
    s = _normalize_ws(s)
    if not s:
        return ""
    return s.upper() + "!"


# --- mathx cluster -------------------------------------------------------- #

def gcd(a, b):
    a, b = abs(a), abs(b)
    while b:
        a, b = b, a % b
    return a


def lcm(a, b):
    if a == 0 or b == 0:
        return 0
    return abs(a * b) // gcd(a, b)


# --- listx cluster -------------------------------------------------------- #

def chunk(xs, n):
    if n <= 0:
        raise ValueError("n must be positive")
    out = []
    for i in range(0, len(xs), n):
        out.append(list(xs[i:i + n]))
    return out


def flatten(xss):
    out = []
    for xs in xss:
        for x in xs:
            out.append(x)
    return out


# --- money cluster -------------------------------------------------------- #

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
