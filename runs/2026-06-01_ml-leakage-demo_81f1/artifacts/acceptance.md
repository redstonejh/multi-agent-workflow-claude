# Acceptance gate — run 2026-06-01_ml-leakage-demo_81f1

**Verdict: SHIP**

The acceptance gate re-ran every deterministic check independently against the
on-disk artifacts and reproduced the full pipeline from scratch. All three
acceptance criteria hold. (This is the verdict on the *classifier validation run*;
the gate did NOT build the model and did not trust the validators' reports.)

---

## Check 1 — Task conformance

PASS. The original request was a trustworthy, leak-free verdict on the
`ml_experiment` churn-style classifier — not just a high accuracy number. The
run delivers exactly that: it demonstrates the leaky pipeline (train 1.000 / test
1.000, shuffled-label control also 1.000) being caught by the deterministic gate,
fixed, and only the honest model (0.783 test accuracy, all gates clean) being
declared shippable. The "real objective" is a validated decision process, and the
deliverable is that process with a concrete, auditable outcome. Nothing in run.md
or eval_report.md conflates a high metric with trustworthiness — the rubric
correctly blocks the leaky model.

---

## Check 2 — Claim-to-evidence fidelity

PASS. Every number claimed in run.md and eval_report.md traces to the on-disk
JSON artifacts:

| Claim in run.md / eval_report.md | Source artifact | Matches? |
|---|---|---|
| Iter1 leaky train/test 1.000 | iter1_leaky_metrics.json: `train_acc: 1.0, test_acc: 1.0` | YES |
| Iter1 shuffled control 1.000 | iter1_leaky_control.json: `shuffled_label_acc: 1.0` | YES |
| Chance level 0.575 (leakage checks) | iter1_leaky_control.json and iter2_honest_control.json: `chance_level: 0.575` | YES |
| Iter2 honest train 0.743 / test 0.783 | iter2_honest_metrics.json: `train_acc: 0.742857, test_acc: 0.783333` | YES |
| Iter2 shuffled control 0.450 | iter2_honest_control.json: `shuffled_label_acc: 0.45` | YES |
| Gap -0.040 | Computed: 0.742857 - 0.783333 = -0.040476 | YES |
| Baseline model 0.783, majority 0.542, gain +0.242, CI [0.133, 0.350], p 0.0005 | Re-run of ml_checks.py baseline below | YES |
| ECE 0.064 | Re-run of ml_checks.py ece below | YES (0.063505) |
| Seed 7 captured | Both honest metrics JSONs: `seed: 7` | YES |
| Features iter1: x1,x2,x3,leak; iter2: x1,x2,x3 | iter1 and iter2 metrics JSONs | YES |

No inflated numbers, no dropped failures, no undocumented reversals found. The
leakage gate FAIL in iteration 1 is prominently recorded — it is not suppressed.
The chance_level difference (0.541667 in the real-run metrics vs 0.575 in the
control JSONs) is legitimate: after the control shuffles labels, the test split's
majority-class rate shifts slightly — both values are correctly reported and used.

---

## Check 3 — End-to-end soundness

PASS. The acceptance gate re-ran all four deterministic checks from scratch
against the on-disk artifacts, plus a fresh full pipeline invocation.

### Deterministic checks re-run (raw outputs and exit codes)

**shuffle — honest control (expect exit 0 / pass):**
```json
{ "check": "shuffle", "shuffled_label_acc": 0.45, "chance_level": 0.575,
  "excess_over_chance": -0.125, "tolerance": 0.05, "passed": true }
```
Exit: 0 (PASS — no leakage signal in the fixed model)

**shuffle — leaky control (expect exit 1 / fail — confirms gate fires correctly):**
```json
{ "check": "shuffle", "shuffled_label_acc": 1.0, "chance_level": 0.575,
  "excess_over_chance": 0.425, "tolerance": 0.05, "passed": false }
```
Exit: 1 (FAIL — leakage gate fires on the as-found model; confirmed working)

**gap — honest model train 0.742857 / test 0.783333 (expect exit 0):**
```json
{ "check": "gap", "gap": -0.040476, "tolerance": 0.05, "passed": true }
```
Exit: 0 (PASS — no overfitting; test exceeds train)

**baseline — against test_preds.txt + test_labels.txt, iters 2000 seed 0:**
```json
{ "check": "baseline", "n": 120, "model_acc": 0.783333, "baseline_acc": 0.541667,
  "gain": 0.241667, "gain_ci": [0.133333, 0.35], "perm_p_vs_chance": 0.0005,
  "passed": true }
```
Exit: 0 (PASS — gain CI excludes 0; significant over majority baseline)

**ece — against test_probs.txt + test_labels.txt, bins 10 tol 0.10:**
```json
{ "check": "ece", "n": 120, "ece": 0.063505, "tolerance": 0.1, "passed": true }
```
Exit: 0 (PASS — ECE 0.064 within 0.10 tolerance)

### Fresh pipeline smoke test

`uv run python examples/ml_experiment/train.py` reproduced exactly:
```json
{ "mode": "real", "inject_leak": false, "features": ["x1","x2","x3"],
  "n_train": 280, "n_test": 120, "train_acc": 0.742857, "test_acc": 0.783333,
  "chance_level": 0.541667, "seed": 7 }
```
Exit: 0. No NaN values, accuracy 0.783 is plausible (not suspiciously perfect,
not pathologically low) for a noisy 3-feature binary classification problem.
Shuffled-label control also reproduced: `shuffled_label_acc: 0.45` (exit 0).

---

## Summary

| Check | Result |
|---|---|
| Task conformance | PASS |
| Claim-to-evidence fidelity | PASS |
| End-to-end soundness | PASS |

**SHIP.** All gates pass. The leakage gate is confirmed to fire on the as-found
model (exit 1) and pass on the fixed model (exit 0). The honest model
(0.783 test accuracy) genuinely beats its majority-class baseline by a margin
whose 95% bootstrap CI [0.133, 0.350] excludes zero.

One open item noted (not a blocker): `# MAW-TODO[ml-cv]` in overfitting_report.md
flags that cross-validation fold stability was not checked. This is correctly
deferred and does not affect the current verdict.
