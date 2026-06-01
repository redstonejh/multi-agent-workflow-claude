---
name: ml-experiment
description: ML-specialized conductor (docs/06). Like /maw, but the refine loop pulls in the ML validators (leakage_auditor, overfitting_checker, baseline_enforcer) and scores against the hard-gate ML rubric instead of a vibe score, and the acceptance gate re-runs the deterministic checks against the on-disk artifacts before SHIP. Use for ML / modeling tasks, or when the user runs /ml-experiment <task>.
---

# /ml-experiment — the ML conductor

You are running the Multi-Agent Workflow conductor specialized for ML work. A
generic "the metric went up" critic is exactly what gets fooled by leakage and
weak baselines, so for ML the quality bar is **"passes the audits,"** not "the
critic likes it." Read `CLAUDE.md` and `docs/06-ml-validation.md` first — doc 06
is the source of truth.

If `python` is not on PATH, use `uv run python` for every `maw-tools/` and
training command (this machine is one such case).

## What changes vs. plain /maw

- The team adds **ML validators** in the refine loop: `leakage_auditor`,
  `overfitting_checker`, `baseline_enforcer` (start with these three; escalate to
  `metric_validator` / `variance_auditor` / `calibration_checker` only if the task
  warrants and within the governor caps).
- The evaluator scores against the **hard-gate ML rubric** below — a checklist,
  not a number. Any failed gate ⇒ FAIL with a specific, named critique.
- Each validator **runs its `maw-tools/ml_checks.py` tool first** and only
  interprets the result. Number first, judgment second.
- The **acceptance gate re-runs the checks against the on-disk artifacts** as its
  end-to-end step and only SHIPs on genuine, reproduced passes.

## The hard-gate ML rubric (the refine loop enforces this)

```
PASS requires ALL applicable gates:
  [ ] leakage:      shuffle control near chance
                    (ml_checks.py shuffle, exit 0); no future/group leak in the
                    feature audit
  [ ] overfitting:  train-test gap within tolerance (ml_checks.py gap, exit 0) AND
                    accuracy not suspiciously perfect (perfect+tiny-gap = leak,
                    not health)
  [ ] baseline:     beats naive majority baseline, gain CI excludes 0
                    (ml_checks.py baseline, exit 0)
  [ ] calibration:  ECE within tolerance if probabilities are used
                    (ml_checks.py ece, exit 0)
  [ ] reproducible: seed / data captured (metrics.json records seed + config)

SCORE = primary metric, reported ONLY if every applicable gate passes;
otherwise FAIL + the named critique (which gate, which number, which feature).
```

A leak makes `overfitting` look fine (gap ~0 on inflated metrics), so **never
clear an ML run on the gap alone** — the `leakage` gate is the one that catches it.

## Procedure

1. **Assess & plan the team** (conductor logic, `.claude/agents/conductor.md`).
   State the real objective and the *modeling goal it serves* (not just the
   metric). Default ML shape: `planner → worker(ml) → [leakage_auditor,
   overfitting_checker, baseline_enforcer]` in a refine loop → `acceptance_gate`.
   Stay within governor caps (max_agents 5 — count the validators; if you need
   more than 5 roles, run validators in sequence or pick the task-relevant
   subset). Justify each role in one line in `run.md`.
2. **Scaffold the run folder:**
   ```bash
   uv run python maw-tools/scaffold_run.py init "<task>" \
       --agents conductor,planner,worker,leakage_auditor,overfitting_checker,baseline_enforcer,acceptance_gate --json
   ```
   Write the plan + the rubric you'll enforce into `run.md`'s "Conductor plan".
3. **Delegate with hand-offs** (scaffold `handoff` helper at every boundary):
   planner → worker (runs the experiment, writes `artifacts/` incl. `metrics.json`,
   `test_preds.txt`, `test_labels.txt`, `test_probs.txt`) → each validator runs its
   tool and writes its `*_report.md` + a `memory.md` finding.
4. **Refine loop against the rubric.** The evaluator (the validators collectively)
   returns PASS only if every applicable gate passes. On FAIL the critique is a
   hand-off back to the worker naming the gate + number + suspect feature; the
   worker fixes and the validators re-run. Stop on PASS, `max_iters`, or plateau.
5. **Acceptance gate (independent, terminal, once).** Delegate to
   `acceptance_gate`. Beyond the usual three checks it **re-runs the deterministic
   ml_checks against the artifacts on disk** (it does not trust the validators'
   say-so) and confirms the final report claims nothing the numbers don't support.
   SHIP only on genuine passes; NO-SHIP loops the reasons back.
6. **Report**: result, run-folder path, which gates passed (with numbers), the
   gate verdict. Only state what the run folder's recorded numbers support.

## Principles
- **Compute first, reason second** — the verdicts come from `ml_checks.py`, the
  agents interpret. A check's exit code is the gate.
- **Conservative team, escalate on failure.** Cheap models for the validators;
  the conductor and the independent gate stay stronger.
- **Everything in markdown on disk** — the run is reconstructable from its folder.
