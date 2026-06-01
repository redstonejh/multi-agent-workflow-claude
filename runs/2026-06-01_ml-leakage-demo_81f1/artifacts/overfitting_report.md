# Overfitting report — overfitting_checker

## Iteration 1 — as found (leaky): gap passes, but FLAGGED

`ml_checks.py gap --train 1.0 --test 1.0 --tol 0.05` → gap 0.0, exit 0.

The gap is within tolerance, **but accuracy is suspiciously perfect (1.000).** A
perfect score with a zero gap is the *leakage signature*, not a healthy model —
leakage inflates train and test together, so the gap looks fine. I do **not**
green-light on the gap alone; I defer to the leakage gate, which FAILED. Net for
the rubric this iteration: blocked by leakage.

## Iteration 2 — after fix (honest): PASS

`ml_checks.py gap --train 0.742857 --test 0.783333 --tol 0.05`
```json
{ "check": "gap", "gap": -0.040476, "tolerance": 0.05, "passed": true }
```
Exit 0. Test slightly exceeds train (gap -0.040) — no overfitting; accuracy is in
a believable range for a noisy 3-feature problem, not suspiciously perfect.

CV fold stability: not computed in this slice. `# MAW-TODO[ml-cv]` — add a
`cv` subcommand / CV runner for a stronger generalization claim (docs/06 §1).

**Verdict: PASS (overfitting gate).**
