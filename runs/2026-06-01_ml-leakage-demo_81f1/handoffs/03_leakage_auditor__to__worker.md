# Hand-off: leakage_auditor → worker  (run 2026-06-01_ml-leakage-demo_81f1, step 03)

## Task context
Audited verdict on the classifier. This is the refine-loop critique returning to
the worker (a FAIL on the leakage gate).

## What I did
Ran the shuffled-label control `train.py --inject-leak --shuffle-labels` →
shuffled_label_acc **1.000**. Judged it: `ml_checks.py shuffle --shuffled-acc 1.0
--chance 0.575 --tol 0.05` → excess **+0.425**, **passed=false, exit 1**. Audited
the features: `leak` is computed from the label in feature engineering.

## Output / artifacts
- artifacts/leakage_report.md  (control result + feature audit, iteration 1: FAIL)
- key result: shuffled control 1.000 vs 0.575 chance — the model learns RANDOM
  labels, so the true label is leaking through a feature.

## Open questions / risks
The train-test gap is 0.0 and looks fine — do NOT be reassured by it; that is the
leakage signature, not health.

## Recommended next step
**Remove the `leak` feature** (the label-derived column in feature engineering)
and re-run the pipeline. Concretely: run `train.py` without `--inject-leak`. Then
hand back for re-audit.
