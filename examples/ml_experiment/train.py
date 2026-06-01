#!/usr/bin/env python3
"""train.py — tiny, reproducible training pipeline for the ML example.

Pure stdlib logistic regression (batch gradient descent). No numpy, no sklearn,
no network — so the worked example runs anywhere `uv run python` does, which is
the point: the leakage demonstration must be replayable, not a screenshot.

The planted data-leakage bug
----------------------------
`--inject-leak` adds a feature in the FEATURE-ENGINEERING step that is derived
from the label (`leak = label`). That is exactly how target leakage happens in
the wild: a column computed from, or downstream of, the outcome sneaks into X.
With the leak the model scores ~100% and the train-test gap looks *fine* — every
metric is inflated, so the gap check alone does NOT catch it (docs/06 §2).

Why the shuffled-label control catches it
-----------------------------------------
`--shuffle-labels` randomizes the labels BEFORE feature engineering, then runs
the identical pipeline. If the leaky feature is present it is regenerated from
the *shuffled* label, so the model learns to predict random labels at ~100% —
far above chance. A leak-free pipeline scores at chance on shuffled labels. That
gap is the canary the `leakage_auditor` reads (via maw-tools/ml_checks.py shuffle).

The "fix" in the worked example is simply NOT injecting the leak (the default):
feature engineering then uses only the legitimate features, the shuffled-label
control falls back to chance, and the honest model still beats the baseline.

Artifacts written (to --artifacts-dir, default ./artifacts)
-----------------------------------------------------------
  metrics.json   train/test accuracy, shuffled-label accuracy (control runs),
                 chance level, config — the numbers the checks/gate consume.
  test_labels.txt, test_preds.txt, test_probs.txt   on-disk arrays the
                 baseline/ece checks (and the acceptance gate) re-run against.

Usage
-----
  uv run python train.py                      # honest run (no leak)
  uv run python train.py --inject-leak        # reproduce the planted-bug run
  uv run python train.py --shuffle-labels      # leakage control (no leak)
  uv run python train.py --inject-leak --shuffle-labels   # control WITH the leak
"""
from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path

HERE = Path(__file__).parent
SEED = 7
LR = 0.3
ITERS = 800
TEST_FRAC = 0.30


# --------------------------------------------------------------------------- #
# data
# --------------------------------------------------------------------------- #

def load_csv(path: Path) -> tuple[list[list[float]], list[int], list[str]]:
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    header = lines[0].split(",")
    feat_names = header[:-1]  # last column is the label
    X, y = [], []
    for line in lines[1:]:
        parts = line.split(",")
        X.append([float(v) for v in parts[:-1]])
        y.append(int(parts[-1]))
    return X, y, feat_names


def engineer_features(
    X: list[list[float]], y: list[int], feat_names: list[str], inject_leak: bool
) -> tuple[list[list[float]], list[str]]:
    """Feature engineering. With inject_leak, append a feature derived from the
    label — the planted target-leakage bug. Note it reads y: that is the smell."""
    if not inject_leak:
        return [row[:] for row in X], list(feat_names)
    names = list(feat_names) + ["leak"]
    Xout = []
    for row, label in zip(X, y):
        # MAW-BUG[ml-leak-01]: `leak` encodes the label — target leakage. A real
        # pipeline would never have the outcome available at feature time. This is
        # the deliberate bug the leakage_auditor's shuffled-label control catches.
        Xout.append(row + [float(label)])
    return Xout, names


# --------------------------------------------------------------------------- #
# model: stdlib logistic regression
# --------------------------------------------------------------------------- #

def _standardize(train: list[list[float]], *sets: list[list[float]]):
    n_feat = len(train[0])
    means = [sum(r[j] for r in train) / len(train) for j in range(n_feat)]
    stds = []
    for j in range(n_feat):
        var = sum((r[j] - means[j]) ** 2 for r in train) / len(train)
        stds.append(math.sqrt(var) or 1.0)  # guard against a constant feature

    def apply(rows):
        return [[(r[j] - means[j]) / stds[j] for j in range(n_feat)] for r in rows]

    return apply(train), [apply(s) for s in sets]


def _sigmoid(z: float) -> float:
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    e = math.exp(z)
    return e / (1.0 + e)


def train_logreg(X: list[list[float]], y: list[int]) -> tuple[list[float], float]:
    n, d = len(X), len(X[0])
    w = [0.0] * d
    b = 0.0
    for _ in range(ITERS):
        gw = [0.0] * d
        gb = 0.0
        for xi, yi in zip(X, y):
            p = _sigmoid(sum(w[j] * xi[j] for j in range(d)) + b)
            err = p - yi
            for j in range(d):
                gw[j] += err * xi[j]
            gb += err
        for j in range(d):
            w[j] -= LR * gw[j] / n
        b -= LR * gb / n
    return w, b


def predict(X, w, b):
    probs = [_sigmoid(sum(w[j] * xi[j] for j in range(len(w))) + b) for xi in X]
    preds = [1 if p >= 0.5 else 0 for p in probs]
    return preds, probs


def accuracy(preds, y):
    return sum(1 for p, t in zip(preds, y) if p == t) / len(y)


# --------------------------------------------------------------------------- #
# pipeline
# --------------------------------------------------------------------------- #

def split(X, y, frac, seed):
    idx = list(range(len(y)))
    random.Random(seed).shuffle(idx)
    cut = int(len(y) * (1 - frac))
    tr, te = idx[:cut], idx[cut:]
    return ([X[i] for i in tr], [y[i] for i in tr],
            [X[i] for i in te], [y[i] for i in te])


def main() -> int:
    ap = argparse.ArgumentParser(description="Tiny logistic-regression pipeline.")
    ap.add_argument("--data", default=str(HERE / "data.csv"))
    ap.add_argument("--artifacts-dir", default=str(HERE / "artifacts"))
    ap.add_argument("--inject-leak", action="store_true",
                    help="add a label-derived feature (the planted leakage bug)")
    ap.add_argument("--shuffle-labels", action="store_true",
                    help="randomize labels before feature engineering (leakage control)")
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args()

    X_raw, y, feat_names = load_csv(Path(args.data))

    # The control randomizes labels BEFORE feature engineering, so a leaky feature
    # (if present) is regenerated from the shuffled label — that is what makes the
    # control able to expose the leak.
    if args.shuffle_labels:
        y = list(y)
        random.Random(args.seed + 1000).shuffle(y)

    X, names = engineer_features(X_raw, y, feat_names, args.inject_leak)
    Xtr, ytr, Xte, yte = split(X, y, TEST_FRAC, args.seed)

    # Standardize on TRAIN ONLY (no preprocessing leakage), apply to test.
    Xtr_s, (Xte_s,) = _standardize(Xtr, Xte)
    w, b = train_logreg(Xtr_s, ytr)

    tr_preds, _ = predict(Xtr_s, w, b)
    te_preds, te_probs = predict(Xte_s, w, b)
    train_acc = accuracy(tr_preds, ytr)
    test_acc = accuracy(te_preds, yte)

    # chance level = majority base rate on the (test) labels actually used
    pos = sum(yte)
    chance = max(pos, len(yte) - pos) / len(yte)

    art = Path(args.artifacts_dir)
    art.mkdir(parents=True, exist_ok=True)
    metrics = {
        "mode": ("shuffled-label-control" if args.shuffle_labels else "real"),
        "inject_leak": args.inject_leak,
        "features": names,
        "n_train": len(ytr),
        "n_test": len(yte),
        "train_acc": round(train_acc, 6),
        "test_acc": round(test_acc, 6),
        "chance_level": round(chance, 6),
        "seed": args.seed,
    }
    if args.shuffle_labels:
        # Name it explicitly so the leakage check reads the right number.
        metrics["shuffled_label_acc"] = round(test_acc, 6)

    (art / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    # Only the real run's arrays feed baseline/ece; still written for the control
    # for completeness, but the gate uses the real-run files.
    if not args.shuffle_labels:
        (art / "test_labels.txt").write_text(" ".join(map(str, yte)), encoding="utf-8")
        (art / "test_preds.txt").write_text(" ".join(map(str, te_preds)), encoding="utf-8")
        (art / "test_probs.txt").write_text(
            " ".join(f"{p:.6f}" for p in te_probs), encoding="utf-8")

    print(json.dumps(metrics, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
