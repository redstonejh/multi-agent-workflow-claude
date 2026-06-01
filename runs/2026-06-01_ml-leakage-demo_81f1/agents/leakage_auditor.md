# leakage_auditor — local notes (run 2026-06-01_ml-leakage-demo_81f1)

Your scratchpad for this run. Read this on start ("your notes so far"); append a
short structured note on finish (what you concluded, decisions, open threads).

---

## Finish note
- **Iter 1 (leaky):** shuffled-label control = 1.000 vs 0.575 chance → `ml_checks.py
  shuffle` exit 1. Named suspect `leak` (label-derived feature). Verdict FAIL.
- **Iter 2 (fixed):** control = 0.450 vs 0.575 chance → exit 0. Verdict PASS.
- **Decision:** the gap check is blind to this leak (gap 0.0); the shuffled-label
  control is the gate that catches it. Always run it before trusting any metric.
- **Open thread:** only target leakage was exercised here. Temporal/group leakage
  and a duplicate-row finder are not yet tooled — `# MAW-TODO`.
