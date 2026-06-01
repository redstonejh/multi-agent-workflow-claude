# Eval report — ML rubric scorecard (refine loop)

The evaluator here is the ML validator panel collectively, scored against the
hard-gate rubric (docs/06). A number is reported only if every applicable gate
passes.

## Iteration 1 — as found (leaky)

| Gate | Tool | Number | Exit | Verdict |
|---|---|---|---|---|
| leakage | `ml_checks.py shuffle` | shuffled 1.000 vs chance 0.575 (excess +0.425) | 1 | **FAIL** |
| overfitting | `ml_checks.py gap` | gap 0.000 (train 1.0 / test 1.0) | 0 | pass-but-flagged (perfect score = leak signature) |
| baseline | `ml_checks.py baseline` | large gain | 0 | void (gain is leakage-driven) |
| calibration | `ml_checks.py ece` | n/a | — | not scored (model invalid) |
| reproducible | metrics.json | seed 7 captured | — | pass |

**Overall: FAIL.** Leakage gate is a hard block. Critique to worker: *"shuffled-
label control 1.000 vs 0.575 chance — remove `leak`, it encodes the label."*
No score reported (a leaked metric is not a result).

## Iteration 2 — after fix (honest)

| Gate | Tool | Number | Exit | Verdict |
|---|---|---|---|---|
| leakage | `ml_checks.py shuffle` | shuffled 0.450 vs chance 0.575 (excess -0.125) | 0 | **PASS** |
| overfitting | `ml_checks.py gap` | gap -0.040 (train 0.743 / test 0.783) | 0 | **PASS** |
| baseline | `ml_checks.py baseline` | 0.783 vs 0.542, gain +0.242, CI [0.133, 0.350], p 0.0005 | 0 | **PASS** |
| calibration | `ml_checks.py ece` | ECE 0.064 (<= 0.10) | 0 | **PASS** |
| reproducible | metrics.json | seed 7 + config captured | — | **PASS** |

**Overall: PASS. SCORE = 0.783 test accuracy.** Converged in 2 iterations (under
the max_iters 3 cap). Handed to the independent acceptance gate.
