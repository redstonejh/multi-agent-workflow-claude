#!/usr/bin/env python3
"""ml_checks.py — deterministic ML validation checks for Multi-Agent Workflow.

Phase 3.7 (docs/06-ml-validation.md). The guiding rule is the same as the rest
of `maw-tools/`: **compute first, reason second.** Computing a train-test gap,
judging a shuffled-label control, testing a gain against a baseline, or measuring
calibration error are deterministic operations — they call NO model and touch NO
network. The ML *validator agents* (`leakage_auditor`, `overfitting_checker`,
`baseline_enforcer`) run these checks and only *interpret* the numbers; the
numbers themselves come from here, where they are reproducible and free.

Important boundary: **these checks operate on metrics / arrays passed in. They do
NOT train models.** Producing predictions, probabilities, or a shuffled-label
score is the *training pipeline's* job (see examples/ml_experiment/train.py). A
check receives those numbers (inline or from a file written to the run folder)
and renders a deterministic verdict on them.

Subcommands
-----------
  gap         Train-vs-held-out gap (overfitting tell). Mirrors checks.py `gap`.
  shuffle     Shuffled-label control (the leakage canary): is the accuracy from a
              model retrained on randomized labels near chance? Near chance =
              clean; above chance = leakage or a bug.
  baseline    Model vs. naive majority-class baseline, with a bootstrap confidence
              interval on the gain (and a permutation p-value vs. chance) so a gain
              smaller than noise is not mistaken for a real one.
  ece         Expected Calibration Error from predicted probabilities + labels.
  metrics     Confusion matrix + precision/recall/F1, and the accuracy-on-
              imbalanced-data flag (accuracy vs. the majority base rate).
  variance    Mean/std/CI over per-seed accuracies; fails on a large spread or a
              gain smaller than the seed-to-seed std.
  repro       sha256 of the dataset + assert metrics.json captured a seed
              (reproducibility evidence).
  dataquality Class balance + duplicate rows + missing/NaN scan on a CSV.
  robustness  Feature-dominance check (a univariate-correlation proxy): does one
              feature dominate the label? (full perturbation suite is # MAW-TODO).

Every subcommand prints a JSON object with a boolean `passed` field and exits 0
when `passed` is true, non-zero otherwise — so callers (the validators, the
acceptance gate, CI, `&&` chains) can gate on `$?`. A usage/runtime error exits 2.

Arrays are read either inline (positional, space-separated) or from a whitespace-
separated file via the matching `--*-file` flag — the latter is how the gate
re-checks the on-disk artifacts a training run wrote.

Examples
--------
  python ml_checks.py gap --train 0.99 --test 0.74 --tol 0.05
  python ml_checks.py shuffle --shuffled-acc 0.97 --chance 0.52 --tol 0.05
  python ml_checks.py baseline --preds-file preds.txt --labels-file labels.txt
  python ml_checks.py ece --probs-file probs.txt --labels-file labels.txt --tol 0.10

On a machine where `python` is not on PATH, invoke with `uv run` (see CLAUDE.md).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import statistics
import sys
from pathlib import Path


def _emit(obj: dict, passed: bool) -> int:
    """Print the result JSON and return an exit code that tracks the verdict."""
    print(json.dumps(obj, indent=2))
    return 0 if passed else 1


def _load_numbers(inline: list[str] | None, file: str | None) -> list[float]:
    """Load a numeric vector from inline args and/or a whitespace-separated file."""
    raw: list[str] = list(inline or [])
    if file:
        raw += Path(file).read_text(encoding="utf-8").split()
    if not raw:
        raise ValueError("no numbers provided (give them inline or via --*-file)")
    return [float(x) for x in raw]


def _percentile(sorted_vals: list[float], q: float) -> float:
    """Linear-interpolated percentile (q in [0,100]) of an already-sorted list."""
    if not sorted_vals:
        raise ValueError("empty distribution")
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    rank = (q / 100.0) * (len(sorted_vals) - 1)
    lo = math.floor(rank)
    hi = math.ceil(rank)
    if lo == hi:
        return sorted_vals[lo]
    frac = rank - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def _majority_label(labels: list[float]) -> tuple[float, float]:
    """Return (majority_class_value, its_base_rate) for a label vector."""
    counts: dict[float, int] = {}
    for y in labels:
        counts[y] = counts.get(y, 0) + 1
    majority_val = max(counts, key=lambda k: counts[k])
    return majority_val, counts[majority_val] / len(labels)


def _equal_len(a: list, b: list, na: str, nb: str) -> None:
    if len(a) != len(b):
        raise ValueError(f"{na} ({len(a)}) and {nb} ({len(b)}) differ in length")


def _read_csv(path: str) -> tuple[list[str], list[list[str]]]:
    """Read a header CSV into (header, rows-of-cells). No quoting support — these
    are the simple numeric CSVs the framework's examples produce."""
    lines = Path(path).read_text(encoding="utf-8").strip().splitlines()
    if not lines:
        raise ValueError(f"empty csv: {path}")
    header = lines[0].split(",")
    rows = [ln.split(",") for ln in lines[1:]]
    return header, rows


def _pearson(xs: list[float], ys: list[float]) -> float:
    """Pearson correlation; 0.0 if either series is constant (no variance)."""
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return 0.0
    return sxy / math.sqrt(sxx * syy)


# ---------------------------------------------------------------------------
# gap — train-vs-held-out gap (overfitting tell, docs/06 §1)
# ---------------------------------------------------------------------------

def cmd_gap(args: argparse.Namespace) -> int:
    gap = args.train - args.test
    passed = gap <= args.tol
    return _emit({
        "check": "gap",
        "train_score": args.train,
        "test_score": args.test,
        "gap": round(gap, 6),
        "tolerance": args.tol,
        "passed": passed,
        "note": (
            "train-test gap within tolerance"
            if passed
            else "gap exceeds tolerance — possible overfitting (docs/06 §1)"
        ),
    }, passed)


# ---------------------------------------------------------------------------
# shuffle — shuffled-label control (the leakage canary, docs/06 §2)
# ---------------------------------------------------------------------------

def cmd_shuffle(args: argparse.Namespace) -> int:
    # `chance` is the accuracy a label-blind model should get: the majority-class
    # base rate. Either pass it explicitly, or hand a label file to derive it.
    chance = args.chance
    derived_from = "explicit --chance"
    if chance is None:
        if not args.labels_file:
            print("error: provide --chance or --labels-file", file=sys.stderr)
            return 2
        labels = _load_numbers(None, args.labels_file)
        _, chance = _majority_label(labels)
        derived_from = f"majority base rate of {args.labels_file}"

    excess = args.shuffled_acc - chance
    # Near chance ⇒ clean. A model retrained on RANDOMIZED labels should not beat
    # the base rate; if it does, information about the (true) label is reaching
    # the model through a leaky feature or a contaminated split — see docs/06 §2.
    passed = excess <= args.tol
    return _emit({
        "check": "shuffle",
        "shuffled_label_acc": args.shuffled_acc,
        "chance_level": round(chance, 6),
        "chance_source": derived_from,
        "excess_over_chance": round(excess, 6),
        "tolerance": args.tol,
        "passed": passed,
        "note": (
            "shuffled-label control near chance — no leakage signal"
            if passed
            else "shuffled-label control ABOVE chance — leakage or a bug "
                 "(model learns randomized labels; docs/06 §2)"
        ),
    }, passed)


# ---------------------------------------------------------------------------
# baseline — model vs. naive baseline + significance (docs/06 §5)
# ---------------------------------------------------------------------------

def cmd_baseline(args: argparse.Namespace) -> int:
    preds = _load_numbers(args.preds, args.preds_file)
    labels = _load_numbers(args.labels, args.labels_file)
    if len(preds) != len(labels):
        print(f"error: preds ({len(preds)}) and labels ({len(labels)}) differ in length",
              file=sys.stderr)
        return 2
    n = len(labels)

    majority_val, base_rate = _majority_label(labels)
    model_acc = sum(1 for p, y in zip(preds, labels) if p == y) / n
    baseline_acc = base_rate  # always predict the majority class
    observed_gain = model_acc - baseline_acc

    rng = random.Random(args.seed)

    # Bootstrap CI on the paired gain: resample test rows with replacement, and
    # recompute (model_acc - majority_acc) each time. If the CI excludes 0 the
    # gain survives resampling noise — it is not a single-run fluke (docs/06 §5).
    gains: list[float] = []
    correct_model = [1 if p == y else 0 for p, y in zip(preds, labels)]
    correct_base = [1 if majority_val == y else 0 for y in labels]
    for _ in range(args.iters):
        m = b = 0
        for _ in range(n):
            i = rng.randrange(n)
            m += correct_model[i]
            b += correct_base[i]
        gains.append((m - b) / n)
    gains.sort()
    alpha = args.alpha
    ci_low = _percentile(gains, 100 * (alpha / 2))
    ci_high = _percentile(gains, 100 * (1 - alpha / 2))

    # Permutation p-value: how often does shuffling the predictions (breaking any
    # link to the labels) match the observed model accuracy? Small ⇒ the model's
    # accuracy is not explainable by chance alignment.
    shuffled = list(preds)
    ge = 0
    for _ in range(args.iters):
        rng.shuffle(shuffled)
        acc = sum(1 for p, y in zip(shuffled, labels) if p == y) / n
        if acc >= model_acc:
            ge += 1
    perm_p = (ge + 1) / (args.iters + 1)

    passed = ci_low > 0  # the gain over the naive baseline is real at this CI
    return _emit({
        "check": "baseline",
        "n": n,
        "model_acc": round(model_acc, 6),
        "baseline_acc": round(baseline_acc, 6),
        "baseline_strategy": f"always predict majority class ({majority_val:g})",
        "gain": round(observed_gain, 6),
        "ci_level": round(1 - alpha, 4),
        "gain_ci": [round(ci_low, 6), round(ci_high, 6)],
        "perm_p_vs_chance": round(perm_p, 6),
        "iters": args.iters,
        "seed": args.seed,
        "passed": passed,
        "note": (
            "model beats the naive baseline by more than resampling noise "
            "(gain CI excludes 0)"
            if passed
            else "gain over naive baseline NOT significant (gain CI includes 0) "
                 "— may be noise (docs/06 §5)"
        ),
    }, passed)


# ---------------------------------------------------------------------------
# ece — Expected Calibration Error (docs/06 §6)
# ---------------------------------------------------------------------------

def cmd_ece(args: argparse.Namespace) -> int:
    probs = _load_numbers(args.probs, args.probs_file)   # P(class==1)
    labels = _load_numbers(args.labels, args.labels_file)
    if len(probs) != len(labels):
        print(f"error: probs ({len(probs)}) and labels ({len(labels)}) differ in length",
              file=sys.stderr)
        return 2
    for p in probs:
        if not (0.0 <= p <= 1.0):
            print(f"error: probability {p} outside [0,1]", file=sys.stderr)
            return 2
    n = len(labels)
    bins = args.bins

    # Standard binned ECE on the predicted-class confidence. For a binary prob p,
    # the predicted class is 1 iff p>=0.5 and the confidence is max(p, 1-p); a bin
    # is calibrated when its mean confidence matches its empirical accuracy.
    bin_conf = [0.0] * bins
    bin_acc = [0.0] * bins
    bin_n = [0] * bins
    for p, y in zip(probs, labels):
        pred = 1.0 if p >= 0.5 else 0.0
        conf = p if pred == 1.0 else 1.0 - p
        # confidence lives in [0.5, 1.0]; map to a bin index in [0, bins-1]
        idx = min(bins - 1, int((conf - 0.5) / 0.5 * bins)) if conf < 1.0 else bins - 1
        idx = max(0, idx)
        bin_conf[idx] += conf
        bin_acc[idx] += 1.0 if pred == y else 0.0
        bin_n[idx] += 1

    ece = 0.0
    bin_report = []
    for k in range(bins):
        if bin_n[k] == 0:
            continue
        conf_k = bin_conf[k] / bin_n[k]
        acc_k = bin_acc[k] / bin_n[k]
        ece += (bin_n[k] / n) * abs(acc_k - conf_k)
        bin_report.append({
            "bin": k, "count": bin_n[k],
            "mean_conf": round(conf_k, 4), "accuracy": round(acc_k, 4),
        })

    passed = ece <= args.tol
    return _emit({
        "check": "ece",
        "n": n,
        "bins": bins,
        "ece": round(ece, 6),
        "tolerance": args.tol,
        "bin_detail": bin_report,
        "passed": passed,
        "note": (
            "calibration error within tolerance — probabilities trustworthy"
            if passed
            else "ECE exceeds tolerance — predicted probabilities miscalibrated "
                 "(docs/06 §6)"
        ),
    }, passed)


# ---------------------------------------------------------------------------
# metrics — confusion matrix + P/R/F1 + accuracy-on-imbalanced flag (docs/06 §4)
# ---------------------------------------------------------------------------

def cmd_metrics(args: argparse.Namespace) -> int:
    preds = _load_numbers(args.preds, args.preds_file)
    labels = _load_numbers(args.labels, args.labels_file)
    _equal_len(preds, labels, "preds", "labels")
    n = len(labels)
    pos = float(args.positive)

    tp = sum(1 for p, y in zip(preds, labels) if p == pos and y == pos)
    tn = sum(1 for p, y in zip(preds, labels) if p != pos and y != pos)
    fp = sum(1 for p, y in zip(preds, labels) if p == pos and y != pos)
    fn = sum(1 for p, y in zip(preds, labels) if p != pos and y == pos)

    accuracy = (tp + tn) / n
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    majority_val, base_rate = _majority_label(labels)
    acc_minus_base = accuracy - base_rate

    # The accuracy-on-imbalanced-data trap: high accuracy that barely clears the
    # majority base rate is the base rate, not skill. Require a real margin AND a
    # non-degenerate F1 (so a majority-only predictor — which scores 0 F1 on the
    # positive class — is caught even if the data is balanced).
    misleading = acc_minus_base <= args.min_gain
    passed = (not misleading) and (f1 >= args.min_f1)
    return _emit({
        "check": "metrics",
        "n": n,
        "positive_class": pos,
        "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "accuracy": round(accuracy, 6),
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(f1, 6),
        "majority_base_rate": round(base_rate, 6),
        "acc_minus_base": round(acc_minus_base, 6),
        "min_gain": args.min_gain,
        "min_f1": args.min_f1,
        "passed": passed,
        "note": (
            "accuracy clears the majority base rate with a real margin; "
            "report P/R/F1, not accuracy alone"
            if passed
            else "accuracy ~ majority base rate or F1 below floor — accuracy is "
                 "misleading on imbalanced data (docs/06 §4)"
        ),
    }, passed)


# ---------------------------------------------------------------------------
# variance — multi-seed stability + CI (docs/06 §5)
# ---------------------------------------------------------------------------

def cmd_variance(args: argparse.Namespace) -> int:
    accs = _load_numbers(args.accs, args.file)
    n = len(accs)
    mean = statistics.fmean(accs)
    std = statistics.stdev(accs) if n > 1 else 0.0
    half = (1.96 * std / math.sqrt(n)) if n > 0 else 0.0
    ci = [mean - half, mean + half]
    spread = max(accs) - min(accs)

    reasons: list[str] = []
    passed = True
    if std > args.max_std:
        passed = False
        reasons.append(f"seed-to-seed std {std:.4f} exceeds max {args.max_std}")
    gain = None
    if args.baseline is not None:
        gain = mean - args.baseline
        # An improvement smaller than the seed-to-seed std isn't an improvement.
        if gain <= std:
            passed = False
            reasons.append(f"gain over baseline {gain:.4f} <= seed std {std:.4f}")
    return _emit({
        "check": "variance",
        "n_seeds": n,
        "accuracies": [round(a, 6) for a in accs],
        "mean": round(mean, 6),
        "std": round(std, 6),
        "ci95": [round(ci[0], 6), round(ci[1], 6)],
        "spread": round(spread, 6),
        "baseline": args.baseline,
        "gain_over_baseline": (round(gain, 6) if gain is not None else None),
        "max_std": args.max_std,
        "passed": passed,
        "note": ("stable across seeds; gain (if given) exceeds seed-to-seed noise"
                 if passed else "; ".join(reasons)),
    }, passed)


# ---------------------------------------------------------------------------
# repro — data hash + seed-captured evidence (docs/06 §8)
# ---------------------------------------------------------------------------

def cmd_repro(args: argparse.Namespace) -> int:
    data_path = Path(args.data)
    sha = hashlib.sha256(data_path.read_bytes()).hexdigest()
    try:
        metrics = json.loads(Path(args.metrics).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as e:
        raise ValueError(f"could not read metrics json {args.metrics}: {e}")

    seed = metrics.get("seed")
    has_seed = seed is not None
    sha_ok = (args.expect_sha is None) or (sha == args.expect_sha)
    passed = has_seed and sha_ok

    reasons = []
    if not has_seed:
        reasons.append("metrics.json has no `seed` — run is not reproducible")
    if not sha_ok:
        reasons.append(f"data sha256 {sha[:12]}... != expected {args.expect_sha[:12]}...")
    return _emit({
        "check": "repro",
        "data": str(data_path),
        "data_sha256": sha,
        "seed": seed,
        "has_seed": has_seed,
        "expected_sha256": args.expect_sha,
        "sha_matches": sha_ok,
        "passed": passed,
        "note": ("seed captured" + ("" if args.expect_sha is None else " and data hash matches")
                 if passed else "; ".join(reasons)),
    }, passed)


# ---------------------------------------------------------------------------
# dataquality — class balance + duplicates + missing/NaN scan (docs/06 §7)
# ---------------------------------------------------------------------------

def cmd_dataquality(args: argparse.Namespace) -> int:
    header, rows = _read_csv(args.data)
    n_rows, n_cols = len(rows), len(header)
    label_idx = args.label_col % n_cols if n_cols else 0

    missing = 0
    for cells in rows:
        for c in cells:
            s = c.strip().lower()
            if s == "" or s in {"nan", "na", "null", "none"}:
                missing += 1

    seen: dict[str, int] = {}
    for cells in rows:
        key = ",".join(cells)
        seen[key] = seen.get(key, 0) + 1
    duplicate_rows = sum(c - 1 for c in seen.values() if c > 1)

    label_vals = [cells[label_idx] for cells in rows if len(cells) > label_idx]
    counts: dict[str, int] = {}
    for v in label_vals:
        counts[v] = counts.get(v, 0) + 1
    majority_fraction = (max(counts.values()) / len(label_vals)) if label_vals else 1.0

    reasons = []
    passed = True
    if missing > 0:
        passed = False
        reasons.append(f"{missing} missing/NaN cell(s)")
    if duplicate_rows > args.max_dupes:
        passed = False
        reasons.append(f"{duplicate_rows} duplicate row(s) (max {args.max_dupes})")
    if majority_fraction > args.max_majority:
        passed = False
        reasons.append(f"class imbalance {majority_fraction:.3f} > {args.max_majority}")
    return _emit({
        "check": "dataquality",
        "data": str(args.data),
        "n_rows": n_rows,
        "n_cols": n_cols,
        "label_column": header[label_idx] if n_cols else None,
        "class_counts": counts,
        "majority_fraction": round(majority_fraction, 6),
        "duplicate_rows": duplicate_rows,
        "missing_cells": missing,
        "passed": passed,
        "note": ("no missing cells, no duplicate rows, class balance within bounds"
                 if passed else "; ".join(reasons)),
    }, passed)


# ---------------------------------------------------------------------------
# robustness — feature-dominance proxy (docs/06 §6); perturbation suite # MAW-TODO
# ---------------------------------------------------------------------------

def cmd_robustness(args: argparse.Namespace) -> int:
    header, rows = _read_csv(args.data)
    n_cols = len(header)
    label_idx = args.label_col % n_cols if n_cols else 0
    try:
        labels = [float(cells[label_idx]) for cells in rows]
    except ValueError as e:
        raise ValueError(f"label column is not numeric: {e}")

    # Univariate |correlation| of each feature with the label. A single feature
    # whose |corr| dominates (≈1.0) is the shortcut/leakage signature — the model
    # can latch onto it. This is a no-training proxy for shortcut-learning /
    # spurious-feature robustness (docs/06 §6).
    feats = []
    for j, name in enumerate(header):
        if j == label_idx:
            continue
        try:
            col = [float(cells[j]) for cells in rows]
        except ValueError:
            continue  # non-numeric feature: skip the correlation probe
        feats.append((name, abs(_pearson(col, labels))))

    feats.sort(key=lambda t: t[1], reverse=True)
    top_name, top_corr = (feats[0] if feats else (None, 0.0))
    passed = top_corr <= args.max_corr
    return _emit({
        "check": "robustness",
        "data": str(args.data),
        "feature_abs_corr": {name: round(c, 6) for name, c in feats},
        "dominant_feature": top_name,
        "max_abs_corr": round(top_corr, 6),
        "max_corr_threshold": args.max_corr,
        "passed": passed,
        # MAW-TODO[ml-robust]: this is the feature-dominance proxy only. The full
        # docs/06 §6 robustness suite (input-perturbation stability, counterfactual
        # / distribution-shift probes) needs the trained model and is not yet built.
        "note": ("no single feature dominates the label (feature-dominance proxy "
                 "only; full perturbation suite is # MAW-TODO)"
                 if passed
                 else f"feature `{top_name}` dominates (|corr| {top_corr:.3f} > "
                      f"{args.max_corr}) — shortcut/leakage risk (docs/06 §6)"),
    }, passed)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Deterministic ML validation checks (no model, no network).")
    sub = p.add_subparsers(dest="cmd", required=True)

    pg = sub.add_parser("gap", help="train-vs-held-out gap (overfitting tell)")
    pg.add_argument("--train", type=float, required=True, help="train score")
    pg.add_argument("--test", type=float, required=True, help="held-out / test score")
    pg.add_argument("--tol", type=float, default=0.05, help="max acceptable gap (default 0.05)")
    pg.set_defaults(func=cmd_gap)

    psh = sub.add_parser("shuffle", help="shuffled-label control (leakage canary)")
    psh.add_argument("--shuffled-acc", type=float, required=True,
                     help="accuracy of a model retrained on RANDOMIZED labels")
    psh.add_argument("--chance", type=float, default=None,
                     help="chance level (majority base rate); or derive via --labels-file")
    psh.add_argument("--labels-file", default=None,
                     help="whitespace-separated labels to derive the chance level from")
    psh.add_argument("--tol", type=float, default=0.05,
                     help="max acceptable excess over chance (default 0.05)")
    psh.set_defaults(func=cmd_shuffle)

    pb = sub.add_parser("baseline", help="model vs. naive baseline + significance")
    pb.add_argument("preds", nargs="*", help="predicted labels (inline)")
    pb.add_argument("--preds-file", default=None, help="file of predicted labels")
    pb.add_argument("--labels", nargs="*", help="(unused positional guard)")
    pb.add_argument("--labels-file", default=None, help="file of true labels")
    pb.add_argument("--iters", type=int, default=2000, help="bootstrap/permutation iters")
    pb.add_argument("--alpha", type=float, default=0.05, help="1-alpha CI (default 0.05 -> 95%%)")
    pb.add_argument("--seed", type=int, default=0, help="RNG seed (reproducible)")
    pb.set_defaults(func=cmd_baseline)

    pe = sub.add_parser("ece", help="expected calibration error from probs + labels")
    pe.add_argument("probs", nargs="*", help="P(class==1) per row (inline)")
    pe.add_argument("--probs-file", default=None, help="file of positive-class probabilities")
    pe.add_argument("--labels", nargs="*", help="(unused positional guard)")
    pe.add_argument("--labels-file", default=None, help="file of true labels")
    pe.add_argument("--bins", type=int, default=10, help="number of confidence bins (default 10)")
    pe.add_argument("--tol", type=float, default=0.10, help="max acceptable ECE (default 0.10)")
    pe.set_defaults(func=cmd_ece)

    pm = sub.add_parser("metrics", help="confusion matrix + P/R/F1 + imbalance flag")
    pm.add_argument("preds", nargs="*", help="predicted labels (inline)")
    pm.add_argument("--preds-file", default=None, help="file of predicted labels")
    pm.add_argument("--labels", nargs="*", help="(unused positional guard)")
    pm.add_argument("--labels-file", default=None, help="file of true labels")
    pm.add_argument("--positive", type=float, default=1, help="positive class value (default 1)")
    pm.add_argument("--min-gain", type=float, default=0.05,
                    help="min accuracy margin over the majority base rate (default 0.05)")
    pm.add_argument("--min-f1", type=float, default=0.0, help="minimum acceptable F1 (default 0.0)")
    pm.set_defaults(func=cmd_metrics)

    pv = sub.add_parser("variance", help="multi-seed stability (mean/std/CI)")
    pv.add_argument("accs", nargs="*", help="per-seed accuracies (inline)")
    pv.add_argument("--file", default=None, help="file of per-seed accuracies")
    pv.add_argument("--baseline", type=float, default=None,
                    help="baseline to test the mean gain against the seed-to-seed std")
    pv.add_argument("--max-std", type=float, default=0.05, help="max acceptable std (default 0.05)")
    pv.set_defaults(func=cmd_variance)

    pr = sub.add_parser("repro", help="data hash + seed-captured evidence")
    pr.add_argument("--data", required=True, help="dataset file to hash")
    pr.add_argument("--metrics", required=True, help="metrics.json that should record a seed")
    pr.add_argument("--expect-sha", default=None, help="optional expected sha256 of the dataset")
    pr.set_defaults(func=cmd_repro)

    pd = sub.add_parser("dataquality", help="class balance + duplicates + missing scan")
    pd.add_argument("--data", required=True, help="CSV file to scan")
    pd.add_argument("--label-col", type=int, default=-1, help="label column index (default -1 = last)")
    pd.add_argument("--max-dupes", type=int, default=0, help="max tolerated duplicate rows (default 0)")
    pd.add_argument("--max-majority", type=float, default=0.99,
                    help="max tolerated majority-class fraction (default 0.99)")
    pd.set_defaults(func=cmd_dataquality)

    prob = sub.add_parser("robustness", help="feature-dominance proxy (shortcut/leakage risk)")
    prob.add_argument("--data", required=True, help="CSV file (features + label)")
    prob.add_argument("--label-col", type=int, default=-1, help="label column index (default -1 = last)")
    prob.add_argument("--max-corr", type=float, default=0.95,
                      help="max tolerated single-feature |corr| with the label (default 0.95)")
    prob.set_defaults(func=cmd_robustness)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, FileNotFoundError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
