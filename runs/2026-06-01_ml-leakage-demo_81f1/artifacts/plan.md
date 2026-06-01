# Plan — validate the ml_experiment classifier

## Goal it serves
A trustworthy ship/no-ship verdict on the classifier. "Test accuracy is high" is
NOT the goal — a leaked or baseline-equivalent model can post a high number and
still be worthless. The plan is therefore a sequence of audits each metric must
survive.

## Steps
1. **Run the experiment** (worker): train the pipeline on `data.csv`, record
   `train_acc`, `test_acc`, the test-set arrays (`test_preds/labels/probs.txt`),
   and the config/seed to `artifacts/metrics.json`.
2. **Leakage audit** (leakage_auditor): run the shuffled-label control
   (`train.py --shuffle-labels`) and judge it with `ml_checks.py shuffle`. Audit
   each feature for target/temporal/group leakage. **Gate: shuffle near chance.**
3. **Overfitting audit** (overfitting_checker): `ml_checks.py gap`. **Gate: gap
   within tol AND accuracy not suspiciously perfect** (perfect + tiny gap = the
   leakage signature, defer to the leakage gate).
4. **Baseline audit** (baseline_enforcer): `ml_checks.py baseline` vs majority
   class with a bootstrap CI on the gain. **Gate: gain CI excludes 0.**
5. **Calibration** (if probabilities used): `ml_checks.py ece`. **Gate: ECE <= tol.**
6. **Refine** until every gate passes or max_iters; then the independent
   acceptance gate re-runs the checks on disk.

## Acceptance criteria
Every applicable rubric gate passes on a real run, reproduced by an independent
agent against the on-disk artifacts. Only then report the score.
