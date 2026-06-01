# Hand-off: leakage_auditor → acceptance_gate  (run 2026-06-01_ml-leakage-demo_81f1, step 05)

## Task context
Audited verdict on the classifier. All component gates now pass; handing to the
independent acceptance gate for the terminal SHIP/NO-SHIP decision.

## What I did
Re-audited the fixed pipeline. Shuffled-label control `train.py --shuffle-labels`
→ shuffled_label_acc **0.450**; `ml_checks.py shuffle --shuffled-acc 0.45 --chance
0.575` → excess **-0.125**, **passed=true, exit 0**. Leakage gate now PASS. The
other validators also passed (see reports): overfitting gap -0.040; baseline
0.783 vs 0.542, gain CI [0.133, 0.350]; ECE 0.064.

## Output / artifacts
- artifacts/leakage_report.md, overfitting_report.md, baseline_report.md
- artifacts/eval_report.md  (rubric scorecard, both iterations — final PASS, score 0.783)
- artifacts/iter2_honest_metrics.json + test_preds/labels/probs.txt  (the on-disk
  arrays for you to re-check)

## Open questions / risks
**Do not trust these reports on faith** — re-run the checks yourself against the
on-disk artifacts. CV stability and recent-period robustness are out of scope for
this slice (noted `# MAW-TODO` in the reports).

## Recommended next step
Independently re-run `ml_checks.py` (shuffle / gap / baseline / ece) against the
artifacts, confirm the final report claims nothing the numbers don't support, and
return SHIP / NO-SHIP.
