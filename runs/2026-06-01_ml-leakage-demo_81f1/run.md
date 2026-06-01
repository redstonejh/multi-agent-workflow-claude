# Run 2026-06-01_ml-leakage-demo_81f1

- **Task:** validate the ml_experiment churn-style classifier for leakage, overfitting and baseline
- **Created:** 2026-06-01 15:42 (driven via the `/ml-experiment` skill)
- **Status:** complete — SHIP

## Conductor plan

**Objective:** Decide whether the `examples/ml_experiment` classifier is fit to
ship — i.e. whether its reported accuracy reflects a model that actually
generalizes, or an artifact of leakage / a weak baseline. The *real* ask is a
trustworthy verdict, not a high number.

**Work type:** ML / modeling → use the ML validator roster, not a generic critic
(docs/06). Score against the hard-gate ML rubric.

**Roles (each justified):**
- `planner` — decompose into experiment + the audits each metric must survive.
- `worker` — run the training pipeline, produce metrics + on-disk arrays.
- `leakage_auditor` — owns the most dangerous failure (leakage); runs the
  shuffled-label control. **This is the gate expected to fire.**
- `overfitting_checker` — train-test gap; also guards the "perfect score" blind spot.
- `baseline_enforcer` — gain over majority baseline + significance.
- `acceptance_gate` — independent terminal check; re-runs the deterministic
  checks against the on-disk artifacts before SHIP.

**Pattern:** `planner → worker → [leakage_auditor, overfitting_checker,
baseline_enforcer]` in a refine loop, then the independent acceptance gate.

**Quality bar — hard-gate ML rubric (docs/06):**
```
PASS requires ALL applicable gates:
  [ ] leakage:      ml_checks.py shuffle near chance (exit 0); feature audit clean
  [ ] overfitting:  ml_checks.py gap within tol (exit 0) AND accuracy not suspiciously perfect
  [ ] baseline:     ml_checks.py baseline gain CI excludes 0 (exit 0)
  [ ] calibration:  ml_checks.py ece within tol (exit 0)  [probabilities used]
  [ ] reproducible: seed + config captured in metrics.json
SCORE = test accuracy, reported only if every gate passes.
```

**Caps:** 7 roles used (5 default + 2 ML validators — a focused ML escalation,
justified above); max_parallel 3; max_iters 3. Validators run on cheap models
(haiku); conductor + gate stronger.

## Final result summary

**Deliverable:** an honest, audited verdict on the classifier.

- **Iteration 1 (as found, leaky):** the pipeline scored **train 1.000 / test
  1.000** — a perfect score with a *zero* train-test gap, which the overfitting
  gate alone would wave through. The **leakage gate FAILED**: the shuffled-label
  control scored **1.000 vs 0.575 chance** (excess +0.425, `ml_checks.py shuffle`
  exit 1). The auditor named the suspect feature `leak` (derived from the label
  in feature engineering). Rubric verdict: **FAIL → NO-SHIP**, looped back to the
  worker with the named leak.
- **Fix:** worker removed the label-derived feature (feature engineering now uses
  only the legitimate `x1,x2,x3`).
- **Iteration 2 (fixed):** all gates pass —
  - leakage: shuffled-label control **0.450 vs 0.575 chance** → near chance (exit 0)
  - overfitting: gap **-0.040** (train 0.743 / test 0.783) → within tol (exit 0)
  - baseline: model **0.783** vs majority **0.542**, gain **+0.242**, 95% CI
    **[0.133, 0.350]** excludes 0, perm-p 0.0005 → significant (exit 0)
  - calibration: ECE **0.064** <= 0.10 (exit 0)
  - reproducible: seed 7 + config in `metrics.json`
  - **SCORE = 0.783 test accuracy.** Rubric verdict: **PASS**.
- **Acceptance gate (independent, terminal):** re-ran all four checks against the
  on-disk artifacts itself (did not trust the validators' reports) — verdict in
  `artifacts/acceptance.md`: **SHIP**.

The demonstration is the point: a perfect-looking metric was caught as leakage by
the deterministic shuffled-label control, blocked, fixed, and only the honest
model — which genuinely beats its baseline — shipped.
