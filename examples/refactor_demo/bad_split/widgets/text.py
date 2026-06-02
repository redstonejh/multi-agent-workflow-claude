"""Text utilities (cohesive cluster — shares _normalize_ws)."""

__all__ = ["slugify", "shout"]


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
