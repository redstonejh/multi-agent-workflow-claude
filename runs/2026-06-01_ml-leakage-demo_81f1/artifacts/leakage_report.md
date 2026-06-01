# Leakage report — leakage_auditor

**Number first, judgment second.** The verdict comes from the deterministic
shuffled-label control, not from eyeballing accuracy.

## Iteration 1 — as found (leaky): FAIL

Control run: `uv run python train.py --inject-leak --shuffle-labels`
→ `shuffled_label_acc = 1.000`, chance (majority base rate) = 0.575.

Judge: `uv run python maw-tools/ml_checks.py shuffle --shuffled-acc 1.0 --chance 0.575 --tol 0.05`
```json
{ "check": "shuffle", "shuffled_label_acc": 1.0, "chance_level": 0.575,
  "excess_over_chance": 0.425, "tolerance": 0.05, "passed": false }
```
Exit 1. **A model cannot learn randomized labels at 100% unless label
information reaches it through a feature.** Note that the *real*-mode metrics for
this iteration are train 1.000 / test 1.000 with a **zero** train-test gap — the
overfitting gate alone is fooled; this control is what catches it.

### Feature audit (agent judgment)
Features were `["x1","x2","x3","leak"]`. `leak` is produced in the
feature-engineering step from the label itself (target leakage — the value would
not exist before the prediction moment). **Named suspect: `leak`.**

**Verdict: FAIL (leakage gate).** Recommend the worker remove the `leak` feature
and re-run.

## Iteration 2 — after fix (honest): PASS

Control run: `uv run python train.py --shuffle-labels` → `shuffled_label_acc = 0.450`,
chance = 0.575.

Judge: `ml_checks.py shuffle --shuffled-acc 0.45 --chance 0.575 --tol 0.05`
```json
{ "check": "shuffle", "shuffled_label_acc": 0.45, "chance_level": 0.575,
  "excess_over_chance": -0.125, "tolerance": 0.05, "passed": true }
```
Exit 0. Control is at/below chance — no leakage signal. Feature audit: features
are now `["x1","x2","x3"]`, all legitimately available at prediction time.

**Verdict: PASS (leakage gate).**
