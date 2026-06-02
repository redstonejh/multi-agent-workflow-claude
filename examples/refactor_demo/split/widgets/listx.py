"""List utilities (cohesive cluster)."""

__all__ = ["chunk", "flatten"]


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
