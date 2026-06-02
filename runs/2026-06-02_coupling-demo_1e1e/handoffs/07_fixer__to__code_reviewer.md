# Hand-off: fixer → code_reviewer  (run 2026-06-02_coupling-demo_1e1e, step 07)

## Task context
Fix implemented + regression test green; needs independent confirmation.

## What I did
`process`/`batch_process` now sort by `DEDUPE_KEY` before `dedupe_orders`
(apply_sort=True default), restoring the precondition. Repro flipped RED → GREEN:
`code_checks.py test --cmd "uv run python test_orders.py"` → passed=true, exit 0
(PASS 4/4). `code_checks.py syntax` clean.

## Output / artifacts
- artifacts/fix_summary.md, artifacts/test_after_fix.json, artifacts/syntax.json
- the fix in examples/coupling_demo/pipeline.py (sorts before dedupe)

## Open questions / risks
**Don't take my word for it** — re-run the checks yourself. Confirm the coupling is
captured in BOTH places (inline `# MAW-DEP[D01]` + `deps.md#D01`) and that the RCA's
root cause matches the actual diff.

## Recommended next step
Independent review: re-run repro (RED on apply_sort=False, GREEN default), `refs`
(=4), `syntax`; verify D01 inline+central agree and the RCA matches; SHIP / NO-SHIP.
