# baseline_enforcer — local notes (run 2026-06-01_ml-leakage-demo_81f1)

Your scratchpad for this run. Read this on start ("your notes so far"); append a
short structured note on finish (what you concluded, decisions, open threads).

---

## Finish note
- **Iter 2 (fixed):** model 0.783 vs majority 0.542; gain +0.242, 95% bootstrap CI
  [0.133, 0.350] excludes 0, perm-p 0.0005 → `baseline` exit 0. Verdict PASS.
- **Decision:** majority-class is the fair naive baseline here (no temporal/last-
  value structure). The gain is over a real baseline, not a strawman.
- **Note:** on the iter-1 leaky model the "gain" was large but void — it was
  manufactured by the leak. A significant gain on a leaked model is not a result.
