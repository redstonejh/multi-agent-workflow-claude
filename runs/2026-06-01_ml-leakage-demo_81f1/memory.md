# Shared journal — run 2026-06-01_ml-leakage-demo_81f1

Append-only, timestamped. One entry per agent turn. This is the common
blackboard: who did what, when, and where the output landed.

## 15:42 — conductor
Assessed: ML/modeling task → ML validator roster (not a generic critic). Planned
`planner → worker → [leakage_auditor, overfitting_checker, baseline_enforcer]`
refine loop → independent acceptance_gate. Wrote plan + hard-gate ML rubric to
run.md. Next: planner decomposes.

## 15:44 — planner
Decomposed into experiment + the audits each metric must survive (artifacts/plan.md):
run pipeline → leakage (shuffle control) → overfitting (gap) → baseline (CI) →
calibration (ECE). Hard gates per docs/06. Next: worker runs the experiment.

## 15:47 — worker (iteration 1)
Ran `train.py --inject-leak` (the as-found pipeline). Result: train 1.000 /
test 1.000 — looks perfect. Wrote iter1_leaky_metrics.json + test arrays.
Suspiciously perfect; handing to leakage_auditor.

## 15:49 — leakage_auditor (iteration 1) — FAIL
Ran shuffled-label control `train.py --inject-leak --shuffle-labels` →
shuffled_label_acc 1.000. `ml_checks.py shuffle --shuffled-acc 1.0 --chance 0.575`
→ excess +0.425, passed=false, exit 1. A model that learns RANDOM labels at 100%
has the label leaking in. Feature audit: `leak` is derived from the label in
feature engineering → target leakage. Verdict FAIL; named suspect `leak`.
See artifacts/leakage_report.md. Critique → worker: remove `leak`.

## 15:50 — overfitting_checker (iteration 1)
`ml_checks.py gap --train 1.0 --test 1.0` → gap 0.0, exit 0 — but accuracy is
suspiciously perfect, the leakage signature. Did NOT green-light; deferred to the
leakage gate (which failed). artifacts/overfitting_report.md.

## 15:52 — worker (iteration 2) — fix
Removed the label-derived feature (dropped `--inject-leak`; feature engineering
now uses only x1,x2,x3). Re-ran `train.py` → train 0.743 / test 0.783. Wrote
iter2_honest_metrics.json + refreshed test arrays. Handing back to leakage_auditor.

## 15:54 — leakage_auditor (iteration 2) — PASS
Control `train.py --shuffle-labels` → shuffled_label_acc 0.450. `ml_checks.py
shuffle --shuffled-acc 0.45 --chance 0.575` → excess -0.125, passed=true, exit 0.
At/below chance — no leakage signal. Features now legitimate. Verdict PASS.

## 15:55 — overfitting_checker (iteration 2) — PASS
`ml_checks.py gap --train 0.742857 --test 0.783333` → gap -0.040, exit 0. No
overfitting; accuracy believable, not suspiciously perfect. PASS.

## 15:56 — baseline_enforcer (iteration 2) — PASS
`ml_checks.py baseline` on the test arrays → model 0.783 vs majority 0.542, gain
+0.242, 95% CI [0.133, 0.350] excludes 0, perm-p 0.0005, exit 0. Fair baseline.
PASS. artifacts/baseline_report.md.

## 15:57 — evaluator (rubric) — PASS
All applicable gates pass (leakage, overfitting, baseline, calibration ECE 0.064,
reproducible). SCORE = 0.783 test accuracy. Converged in 2 iterations.
artifacts/eval_report.md. Handing to the independent acceptance_gate.

<!-- acceptance_gate appends its entry below when it runs -->


## 16:15 — acceptance_gate
Re-ran all four ml_checks.py checks independently against on-disk artifacts (shuffle
honest exit 0, shuffle leaky exit 1 — gate fires correctly, gap exit 0, baseline exit 0,
ECE exit 0). Fresh `train.py` smoke test reproduced train 0.743 / test 0.783, no NaN.
All three acceptance criteria pass. Verdict: SHIP. Output: artifacts/acceptance.md.
