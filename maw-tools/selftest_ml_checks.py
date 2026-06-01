#!/usr/bin/env python3
"""selftest_ml_checks.py — prove maw-tools/ml_checks.py reflects reality.

A check is only trustworthy once it has been shown to go GREEN on a known-clean
fixture AND RED on a known-bad one. This self-test drives every `ml_checks.py`
subcommand against both, and asserts the JSON `passed` verdict and the process
exit code agree with the truth we constructed. If a check silently regresses
(e.g. always returns passed=true, or the exit code stops tracking the verdict),
this turns red — the same guard `selftest_checks.py` provides for `checks.py`.

Run:  uv run maw-tools/selftest_ml_checks.py   (or: python maw-tools/...)
Exit: 0 if every assertion holds, 1 otherwise.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ML = Path(__file__).with_name("ml_checks.py")
results: list[tuple[bool, str]] = []


def record(ok: bool, msg: str) -> None:
    results.append((ok, msg))
    print(f"  {'[ok]' if ok else '[XX]'} {msg}")


def run(*args: str) -> tuple[int, dict | None]:
    proc = subprocess.run([sys.executable, str(ML), *args], capture_output=True, text=True)
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        data = None
    return proc.returncode, data


def expect(args: list[str], want_pass: bool, label: str) -> None:
    code, data = run(*args)
    got_pass = bool(data and data.get("passed"))
    exit_ok = (code == 0) if want_pass else (code != 0)
    ok = (got_pass == want_pass) and exit_ok and data is not None
    record(ok, f"{label}: exit {code}, passed={got_pass} (want passed={want_pass})")


def write(tmp: Path, name: str, nums: list) -> str:
    p = tmp / name
    p.write_text(" ".join(str(x) for x in nums), encoding="utf-8")
    return str(p)


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)

        # --- gap: small gap clean, large gap leaky/overfit ---
        print("ml_checks.py gap:")
        expect(["gap", "--train", "0.80", "--test", "0.78", "--tol", "0.05"], True, "clean gap")
        expect(["gap", "--train", "0.99", "--test", "0.70", "--tol", "0.05"], False, "overfit gap")

        # --- shuffle: near chance clean, above chance leaky ---
        print("ml_checks.py shuffle:")
        expect(["shuffle", "--shuffled-acc", "0.51", "--chance", "0.50", "--tol", "0.05"],
               True, "near-chance control")
        expect(["shuffle", "--shuffled-acc", "0.95", "--chance", "0.50", "--tol", "0.05"],
               False, "above-chance control (leak)")

        # --- baseline: a real gain beats majority; predicting-majority does not ---
        print("ml_checks.py baseline:")
        # 40 rows, 60% class 1 -> majority baseline 0.60.
        labels = [1] * 24 + [0] * 16
        lf = write(tmp, "labels.txt", labels)
        # Clean: predictions correct on 36/40 (0.90) -> clear gain over 0.60.
        good_preds = ([1] * 24) + ([0] * 12 + [1] * 4)  # 4 of the 16 zeros mispredicted
        gp = write(tmp, "good_preds.txt", good_preds)
        expect(["baseline", "--preds-file", gp, "--labels-file", lf, "--iters", "1000", "--seed", "0"],
               True, "real gain over baseline")
        # Bad: always predict the majority class -> zero gain, CI includes 0.
        bad_preds = [1] * 40
        bp = write(tmp, "bad_preds.txt", bad_preds)
        expect(["baseline", "--preds-file", bp, "--labels-file", lf, "--iters", "1000", "--seed", "0"],
               False, "no gain over baseline")

        # --- ece: calibrated clean, confidently-wrong bad ---
        print("ml_checks.py ece:")
        # Calibrated: in the 0.9-confidence band ~90% are correct.
        cal_probs = [0.9] * 10 + [0.1] * 10          # 20 rows
        cal_labels = ([1] * 9 + [0] * 1) + ([0] * 9 + [1] * 1)
        cpf = write(tmp, "cal_probs.txt", cal_probs)
        clf = write(tmp, "cal_labels.txt", cal_labels)
        expect(["ece", "--probs-file", cpf, "--labels-file", clf, "--bins", "10", "--tol", "0.10"],
               True, "calibrated probabilities")
        # Confidently wrong: prob 0.99 but the truth is the opposite class.
        bad_probs = [0.99] * 10 + [0.01] * 10
        bad_labels = [0] * 10 + [1] * 10
        bpf = write(tmp, "bad_probs.txt", bad_probs)
        blf = write(tmp, "bad_labels.txt", bad_labels)
        expect(["ece", "--probs-file", bpf, "--labels-file", blf, "--bins", "10", "--tol", "0.10"],
               False, "confidently-wrong probabilities")

    ok = all(r[0] for r in results)
    print(f"\n{'ALL PASS' if ok else 'FAILURES PRESENT'}: "
          f"{sum(1 for r in results if r[0])}/{len(results)} assertions held")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
