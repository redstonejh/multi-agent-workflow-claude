# Hand-off: worker → leakage_auditor  (run 2026-06-01_ml-leakage-demo_81f1, step 04)

## Task context
Audited verdict on the classifier. Iteration 2, after fixing the leak.

## What I did
Fixed the leak: removed the label-derived `leak` feature — feature engineering now
uses only the legitimate `x1,x2,x3`. Re-ran `uv run python train.py`. Result:
**train 0.743 / test 0.783** (no longer perfect — believable). Refreshed the test
arrays + metrics.json.

## Output / artifacts
- artifacts/iter2_honest_metrics.json  (train 0.743, test 0.783, features x1,x2,x3)
- artifacts/test_preds.txt, test_labels.txt, test_probs.txt  (honest-run arrays)

## Open questions / risks
Accuracy dropped from 1.000 to 0.783 — expected; the 1.000 was the leak. Confirm
the shuffled-label control now falls back to chance.

## Recommended next step
Re-run the shuffled-label control and re-judge with `ml_checks.py shuffle`; then
pass to overfitting/baseline and the acceptance gate.
