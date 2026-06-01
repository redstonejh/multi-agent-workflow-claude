# Baseline report — baseline_enforcer

## Iteration 1 — as found (leaky): PASS-but-VOID

On the leaky model the gain over baseline is large and "significant" — but it is
manufactured by the `leak` feature the leakage_auditor flagged. A gain that
exists only because of leakage is not real. **Void; blocked by the leakage gate.**

## Iteration 2 — after fix (honest): PASS

`ml_checks.py baseline --preds-file artifacts/test_preds.txt
--labels-file artifacts/test_labels.txt --iters 2000 --seed 0`
```json
{ "check": "baseline", "n": 120,
  "model_acc": 0.783333, "baseline_acc": 0.541667,
  "baseline_strategy": "always predict majority class (0)",
  "gain": 0.241667, "ci_level": 0.95, "gain_ci": [0.133333, 0.35],
  "perm_p_vs_chance": 0.0005, "passed": true }
```
Exit 0. Model 0.783 vs majority-class 0.542; gain +0.242 with a 95% bootstrap CI
of [0.133, 0.350] that **excludes 0**, and a permutation p vs chance of 0.0005.

### Baseline fairness (agent judgment)
Majority-class is the right naive comparator for a balanced-ish binary label with
no temporal/ordering structure (no "last value" baseline applies here). The gain
is over a fair baseline, not a strawman.

**Verdict: PASS (baseline + significance gates).**
