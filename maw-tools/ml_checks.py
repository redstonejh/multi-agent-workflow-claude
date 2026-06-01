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
  gap       Train-vs-held-out gap (overfitting tell). Mirrors checks.py `gap`
            so an ML run can use one tool; metrics passed in.
  shuffle   Shuffled-label control (the leakage canary): is the accuracy from a
            model retrained on randomized labels near chance? Near chance =
            clean; above chance = leakage or a bug.
  baseline  Model vs. naive majority-class baseline, with a bootstrap confidence
            interval on the gain (and a permutation p-value vs. chance) so a gain
            smaller than noise is not mistaken for a real one.
  ece       Expected Calibration Error from predicted probabilities + labels.

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
import json
import math
import random
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
