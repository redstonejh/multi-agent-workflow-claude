# overfitting_checker — local notes (run 2026-06-01_ml-leakage-demo_81f1)

Your scratchpad for this run. Read this on start ("your notes so far"); append a
short structured note on finish (what you concluded, decisions, open threads).

---

## Finish note
- **Iter 1 (leaky):** gap 0.0 (train/test both 1.000) → `gap` exit 0, but accuracy
  is suspiciously perfect = the leakage signature. Did NOT green-light; deferred to
  the leakage gate (which failed). Lesson: a small gap is necessary, not sufficient.
- **Iter 2 (fixed):** gap -0.040 (0.743/0.783) → exit 0, believable. Verdict PASS.
- **Open thread:** CV-fold stability not computed — `# MAW-TODO[ml-cv]`.
