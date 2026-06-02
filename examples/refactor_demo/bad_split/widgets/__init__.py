"""widgets — a BAD split. Looks like a clean refactor and the bundled tests still
pass, but money.format_cents silently changed behavior for sub-dollar amounts
(dropped the cents zero-pad). The golden harness — which exercises format_cents(5)
— catches it; `api` does not (the signature is unchanged). This is why golden is
the behavioral truth comparison, not the tests or the API surface alone.
"""
from .text import slugify, shout
from .mathx import gcd, lcm
from .listx import chunk, flatten
from .money import format_cents, parse_cents

__all__ = [
    "slugify", "shout",
    "gcd", "lcm",
    "chunk", "flatten",
    "format_cents", "parse_cents",
]
