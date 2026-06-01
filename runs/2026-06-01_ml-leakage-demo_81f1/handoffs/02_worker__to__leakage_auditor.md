# Hand-off: worker → leakage_auditor  (run 2026-06-01_ml-leakage-demo_81f1, step 02)

## Task context
Decide whether the ml_experiment classifier is fit to ship — an audited verdict,
not just a number.

## What I did
Ran the as-found pipeline: `uv run python train.py --inject-leak`. It scored
**train 1.000 / test 1.000**. Wrote metrics + test arrays.

## Output / artifacts
- artifacts/iter1_leaky_metrics.json  (train 1.0, test 1.0, features incl. `leak`)
- artifacts/test_preds.txt, test_labels.txt, test_probs.txt  (iteration-1 arrays)

## Open questions / risks
A perfect score on a noisy 3-feature problem is implausible. The feature list
includes `leak`. Do not trust this until the shuffled-label control has run.

## Recommended next step
Run the shuffled-label control and judge it with `ml_checks.py shuffle`. Audit the
features for target leakage.
