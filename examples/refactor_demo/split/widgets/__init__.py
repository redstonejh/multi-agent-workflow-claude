"""widgets — split into cohesive modules, public API preserved exactly.

The original flat module became a package; the eight public names are re-exported
here so `import widgets` keeps the identical surface (verified by `refactor_checks
api`). Each cluster now lives with the helpers it actually shares.
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
