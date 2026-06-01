# Hand-off: planner → worker  (run 2026-06-01_ml-leakage-demo_81f1, step 01)

## Task context
Decide whether the ml_experiment classifier is fit to ship — a trustworthy,
audited verdict, not just a high accuracy number.

## What I did
Decomposed the work into the experiment plus the audits each metric must survive
(artifacts/plan.md): leakage (shuffled-label control), overfitting (gap),
baseline (gain CI), calibration (ECE). Each is a hard gate per docs/06.

## Output / artifacts
- artifacts/plan.md  (steps + acceptance criteria + the hard-gate rubric)

## Open questions / risks
The metric alone proves nothing — design the run so every number is auditable:
write the test arrays and a metrics.json with the seed/config to disk.

## Recommended next step
Run `train.py`, record train/test accuracy and the test-set arrays
(test_preds/labels/probs.txt) + metrics.json. Then hand to the leakage_auditor.
