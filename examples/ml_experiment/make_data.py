#!/usr/bin/env python3
"""make_data.py — generate the tiny, reproducible dataset for the ML example.

Pure stdlib, fixed seed: running it again reproduces byte-identical data.csv, so
the whole worked example is replayable with no network and no third-party deps.

The data has a *real but moderate* signal: the label is a noisy threshold on
three legitimate features, so an honest model can beat the majority-class
baseline (~78% vs ~52%) but not trivially. Crucially the CSV contains NO leaky
feature — the planted data-leakage bug lives in train.py's feature-engineering
step (it derives a feature from the label), which is where leaks actually happen.

Run:  uv run python make_data.py   (writes data.csv next to this script)
"""
from __future__ import annotations

import random
from pathlib import Path

SEED = 42
N = 400
OUT = Path(__file__).with_name("data.csv")


def main() -> int:
    rng = random.Random(SEED)
    rows = []
    pos = 0
    for _ in range(N):
        x1 = rng.gauss(0, 1)
        x2 = rng.gauss(0, 1)
        x3 = rng.gauss(0, 1)
        # Moderate signal + noise: the noise term keeps the task non-trivial so a
        # leak-free model lands around ~78% accuracy, not 100%.
        z = 1.6 * x1 + 1.3 * x2 - 1.1 * x3 + rng.gauss(0, 2.3)
        label = 1 if z > 0 else 0
        pos += label
        rows.append((x1, x2, x3, label))

    lines = ["x1,x2,x3,label"]
    for x1, x2, x3, label in rows:
        lines.append(f"{x1:.6f},{x2:.6f},{x3:.6f},{label}")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUT} : {N} rows, {pos} positive ({pos / N:.1%}), "
          f"majority base rate {max(pos, N - pos) / N:.1%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
